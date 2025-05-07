import asyncio
import threading
from api.sonarr import fetch_sonarr_series

POLL_INTERVAL = 600

def polling_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_loop())

async def poll_loop():
    while True:
        try:
            # Process TV shows
            print("Polling Sonarr for new episodes...")
            shows = fetch_sonarr_series()
            process_sonarr_content(shows)
            
            # Process movies if Radarr is available
            if RADARR_AVAILABLE:
                print("Polling Radarr for new movies...")
                movies = fetch_radarr_movies()
                process_radarr_content(movies)
                
        except Exception as e:
            print(f"Error polling media services: {e}")
        await asyncio.sleep(POLL_INTERVAL)

def process_sonarr_content(shows):
    """Process content from Sonarr"""
    from backend.db import get_db
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get list of shows to be filtered
    cursor.execute("SELECT id FROM bleeparr_items WHERE type = 'show' AND filtered = 1")
    filtered_show_ids = [row[0] for row in cursor.fetchall()]
    
    # Process only shows marked for filtering
    for show in shows:
        if show.get('id') in filtered_show_ids:
            print(f"Would process show: {show.get('title')}")
            # Here you would add your actual processing logic
            # For example, getting episodes and processing their audio files
    
    conn.close()

def process_radarr_content(movies):
    """Process content from Radarr"""
    from backend.db import get_db
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get list of movies to be filtered
    cursor.execute("SELECT id FROM bleeparr_items WHERE type = 'movie' AND filtered = 1")
    filtered_movie_ids = [row[0] for row in cursor.fetchall()]
    
    # Process only movies marked for filtering
    for movie in movies:
        if movie.get('id') in filtered_movie_ids:
            print(f"Would process movie: {movie.get('title')}")
            # Here you would add your actual processing logic
            # For example, processing the movie file audio
    
    conn.close()
def start_polling_loop():
    thread = threading.Thread(target=polling_task, daemon=True)
    thread.start()
