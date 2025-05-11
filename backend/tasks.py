import asyncio
import threading
import time
import logging
import os
from datetime import datetime, timedelta
from backend.db import add_to_processing_queue, get_processing_queue, remove_from_processing_queue, is_in_queue_or_history, save_processing_history, get_processing_history
from api.sonarr import SonarrAPI
from api.radarr import RadarrAPI
from api.bleeparr_core import process_episode, process_movie

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bleeparr.tasks')

# Settings
POLL_INTERVAL = 300  # 5 minutes in seconds
SONARR_AVAILABLE = True
RADARR_AVAILABLE = False  # Set to True if Radarr is available and configured
PROCESSING_QUEUE = []
PROCESSING_HISTORY = []
MAX_HISTORY = 100

def polling_task():
    """Thread function for running the polling loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_loop())

async def poll_loop():
    """Main polling loop that runs continuously"""
    logger.info("Starting polling loop")
    last_poll = datetime.now() - timedelta(minutes=10)  # Start by running immediately
    
    while True:
        try:
            if (datetime.now() - last_poll).total_seconds() >= POLL_INTERVAL:
                logger.info("Running scheduled poll")
                last_poll = datetime.now()
                
                # Check new episodes from Sonarr
                if SONARR_AVAILABLE:
                    logger.info("Polling Sonarr for new episodes...")
                    await poll_sonarr()
                
                # Check new movies from Radarr
                if RADARR_AVAILABLE:
                    logger.info("Polling Radarr for new movies...")
                    await poll_radarr()
                
                # Process any items in the queue
                await process_queue()
                
                logger.info("Polling cycle complete")
        
        except Exception as e:
            logger.error(f"Error during polling cycle: {e}")
        
        # Sleep before next iteration check
        await asyncio.sleep(10)  # Check every 10 seconds if it's time to poll again

async def poll_sonarr():
    """Check Sonarr for new downloads or imports and queue them for processing"""
    try:
        # Get Sonarr API credentials from environment
        url = os.getenv("SONARR_URL")
        api_key = os.getenv("SONARR_API_KEY")
        
        if not url or not api_key:
            logger.error("Sonarr URL or API key not set")
            return
        
        # Initialize API
        api = SonarrAPI(url, api_key)
        
        # Get filtered series IDs from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bleeparr_items WHERE type = 'show' AND filtered = 1")
        filtered_series_ids = [row[0] for row in cursor.fetchall()]
        
        if not filtered_series_ids:
            logger.info("No series marked for filtering")
            return
        
        # Get queue items
        queue_items = api.get_queue()
        logger.info(f"Found {len(queue_items)} items in Sonarr queue")

        # Get recently downloaded episodes
        # We'll check episodes downloaded in the last hour to avoid missing anything
        try:
            history_items = api.get_history(event_type="downloadFolderImported", 
                                          since=datetime.now() - timedelta(hours=1))
            logger.info(f"Found {len(history_items)} recently imported episodes in Sonarr history")
        except Exception as e:
            logger.error(f"Error fetching Sonarr history: {e}")
            history_items = []
        
        # Process imported episodes
        for item in history_items:
            series_id = item.get('seriesId')
            
            # Only process if this series is marked for filtering
            if series_id in filtered_series_ids:
                episode_id = item.get('episodeId')
                episode_path = api.get_episode_path(episode_id)
                
                if episode_path:
                    # Get series details
                    series = api.get_series_by_id(series_id)
                    if not series:
                        continue
                    
                    # Get episode details
                    episode = api.get_episode_by_id(episode_id)
                    if not episode:
                        continue
                    
                    series_title = series.get('title')
                    episode_info = f"S{episode.get('seasonNumber', 0):02d}E{episode.get('episodeNumber', 0):02d} - {episode.get('title', 'Unknown')}"
                    
                    # Add to processing queue
                    queue_item = {
                        'type': 'show',
                        'file_path': episode_path,
                        'title': series_title,
                        'detail': episode_info,
                        'id': episode_id,
                        'parent_id': series_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Add to queue if not already in queue or recently processed
                    if not is_item_already_processed(queue_item):
                        PROCESSING_QUEUE.append(queue_item)
                        logger.info(f"Queued episode for processing: {series_title} - {episode_info}")
        
    except Exception as e:
        logger.error(f"Error polling Sonarr: {e}")

async def poll_radarr():
    """Check Radarr for new downloads or imports and queue them for processing"""
    try:
        # Get Radarr API credentials from environment
        url = os.getenv("RADARR_URL")
        api_key = os.getenv("RADARR_API_KEY")
        
        if not url or not api_key:
            logger.error("Radarr URL or API key not set")
            return
        
        # Initialize API
        api = RadarrAPI(url, api_key)
        
        # Get filtered movie IDs from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bleeparr_items WHERE type = 'movie' AND filtered = 1")
        filtered_movie_ids = [row[0] for row in cursor.fetchall()]
        
        if not filtered_movie_ids:
            logger.info("No movies marked for filtering")
            return
        
        # Get recently downloaded movies (last hour)
        history_items = api.get_history(event_type="downloadFolderImported", 
                                      since=datetime.now() - timedelta(hours=1))
        logger.info(f"Found {len(history_items)} recently imported movies in Radarr history")
        
        # Process imported movies
        for item in history_items:
            movie_id = item.get('movieId')
            
            # Only process if this movie is marked for filtering
            if movie_id in filtered_movie_ids:
                movie_path = api.get_movie_path(movie_id)
                
                if movie_path:
                    # Get movie details
                    movie = api.get_movie_by_id(movie_id)
                    if not movie:
                        continue
                    
                    movie_title = movie.get('title')
                    
                    # Add to processing queue
                    queue_item = {
                        'type': 'movie',
                        'file_path': movie_path,
                        'title': movie_title,
                        'detail': f"{movie.get('year', '')}",
                        'id': movie_id,
                        'parent_id': movie_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Add to queue if not already in queue or recently processed
                    if not is_item_already_processed(queue_item):
                        PROCESSING_QUEUE.append(queue_item)
                        logger.info(f"Queued movie for processing: {movie_title}")
        
    except Exception as e:
        logger.error(f"Error polling Radarr: {e}")

def is_item_already_processed(item):
    """Check if an item is already in the queue or has been recently processed"""
    item_path = item.get('file_path')
    
    # Check queue
    for queue_item in PROCESSING_QUEUE:
        if queue_item.get('file_path') == item_path:
            return True
    
    # Check history
    for history_item in PROCESSING_HISTORY:
        if history_item.get('file_path') == item_path:
            return True
    
    return False

async def process_queue():
    """Process items in the queue"""
    queue_items = get_processing_queue()
    logger.info(f"Checking processing queue, currently contains {len(queue_items)} items")
    
    if not queue_items:
        return
    
    logger.info(f"Processing queue with {len(queue_items)} items")
    
    for item in queue_items:
        try:
            logger.info(f"Processing {item['item_type']}: {item['title']} - {item['detail']}")
            
            result = None
            if item['item_type'] == 'show':
                result = process_episode(
                    item['file_path'],
                    item['title'],
                    item['detail']
                )
            elif item['item_type'] == 'movie':
                result = process_movie(
                    item['file_path'],
                    item['title']
                )
            
            # Add to history and remove from queue
            if result:
                process_result = {
                    'id': item['item_id'],
                    'type': item['item_type'],
                    'file_path': item['file_path'],
                    'title': item['title'],
                    'detail': item['detail'],
                    'parent_id': item['parent_id'],
                    'success': result.get('success', False),
                    'result': result
                }
                
                # Save to history
                save_processing_history(process_result)
                
                # Log result
                if result.get('success'):
                    logger.info(f"Successfully processed {item['item_type']}: {item['title']} - {item['detail']}")
                    logger.info(f"Found {result.get('swears_found', 0)} swear words")
                else:
                    logger.error(f"Failed to process {item['item_type']}: {item['title']} - {item['detail']}")
                    logger.error(f"Error: {result.get('error', 'Unknown error')}")
                
                # Remove from queue
                remove_from_processing_queue(item['id'])
        
        except Exception as e:
            logger.error(f"Error processing queue item: {e}")

def get_processing_status():
    """Get current processing status"""
    queue = get_processing_queue()
    history = get_processing_history(limit=20)
    
    return {
        'queue': queue,
        'history': history,
        'sonarr_available': SONARR_AVAILABLE,
        'radarr_available': RADARR_AVAILABLE
    }

def add_to_queue(item_type, item_id, file_path, title, detail="", parent_id=None):
    """Manually add an item to the processing queue"""
    queue_item = {
        'type': item_type,         # Changed 'item_type' to 'type' to match expected field
        'id': item_id,             # Changed 'item_id' to 'id' to match expected field
        'item_type': item_type,
        'item_id': item_id,
        'file_path': file_path,
        'title': title,
        'detail': detail,
        'parent_id': parent_id or item_id,
        'manual': True
    }
    
    if not is_in_queue_or_history(item_id, item_type):
        add_to_processing_queue(queue_item)
        logger.info(f"Manually queued {item_type} for processing: {title}")
        return True
    else:
        logger.info(f"Item already in queue or recently processed: {title}")
        return False

def start_polling_loop():
    """Start the background polling thread"""
    thread = threading.Thread(target=polling_task, daemon=True)
    thread.start()
    logger.info("Background polling thread started")
    return thread
