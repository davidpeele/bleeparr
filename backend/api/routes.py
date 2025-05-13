from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
import os
import requests
import logging
logger = logging.getLogger('bleeparr.routes')
from backend.db import get_db
from backend.tasks import add_to_queue, get_processing_status
from typing import List, Dict, Any, Optional

# ?this next line may need to go also:
#from api.settings_routes import router as settings_router
from backend.api.settings_routes import router as settings_router


router = APIRouter()


# Status endpoint
@router.get("/api/status")
def get_status():
    """Get overall system status"""
    sonarr_url = os.getenv("SONARR_URL")
    sonarr_api_key = os.getenv("SONARR_API_KEY")
    radarr_url = os.getenv("RADARR_URL")
    radarr_api_key = os.getenv("RADARR_API_KEY")
    
    sonarr_status = {"configured": bool(sonarr_url and sonarr_api_key), "connected": False}
    radarr_status = {"configured": bool(radarr_url and radarr_api_key), "connected": False}
    
    # Test Sonarr connection if configured
    if sonarr_status["configured"]:
        try:
            response = requests.get(f"{sonarr_url}/api/v3/system/status", 
                                   headers={"X-Api-Key": sonarr_api_key}, 
                                   timeout=5)
            sonarr_status["connected"] = response.status_code == 200
            if sonarr_status["connected"]:
                sonarr_status["version"] = response.json().get("version", "unknown")
        except:
            pass
    
    # Test Radarr connection if configured
    if radarr_status["configured"]:
        try:
            response = requests.get(f"{radarr_url}/api/v3/system/status", 
                                   headers={"X-Api-Key": radarr_api_key}, 
                                   timeout=5)
            radarr_status["connected"] = response.status_code == 200
            if radarr_status["connected"]:
                radarr_status["version"] = response.json().get("version", "unknown")
        except:
            pass
    
    # Get processing status from task system
    processing_status = get_processing_status()
    
    return {
        "sonarr": sonarr_status,
        "radarr": radarr_status,
        "processing": {
            "queue_size": len(processing_status["queue"]),
            "history_size": len(processing_status["history"]),
            "sonarr_monitoring": processing_status["sonarr_available"],
            "radarr_monitoring": processing_status["radarr_available"]
        }
    }

# Fetch shows from Sonarr
@router.get("/api/shows")
def get_shows():
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/series", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Fetch movies from Radarr
@router.get("/api/movies")
def get_movies():
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Radarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/movie", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get a specific show from Sonarr
@router.get("/api/shows/{show_id}")
def get_show(show_id: int):
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/series/{show_id}", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get a specific movie from Radarr
@router.get("/api/movies/{movie_id}")
def get_movie(movie_id: int):
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Radarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/movie/{movie_id}", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get episodes for a show from Sonarr
@router.get("/api/shows/{show_id}/episodes")
def get_episodes(show_id: int):
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        response = requests.get(
            f"{url}/api/v3/episode", 
            params={"seriesId": show_id},
            headers={"X-Api-Key": api_key}
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Test Sonarr connection
@router.get("/api/sonarr/test")
def test_sonarr_connection():
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        return {"success": False, "message": "Sonarr URL or API key not set"}

    try:
        response = requests.get(f"{url}/api/v3/system/status", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        data = response.json()
        version = data.get("version", "unknown")
        return {"success": True, "message": f"Connected to Sonarr v{version}"}
    except requests.RequestException as e:
        return {"success": False, "message": f"Error connecting to Sonarr: {str(e)}"}

# Test Radarr connection
@router.get("/api/radarr/test")
def test_radarr_connection():
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")

    if not url or not api_key:
        return {"success": False, "message": "Radarr URL or API key not set"}

    try:
        response = requests.get(f"{url}/api/v3/system/status", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        data = response.json()
        version = data.get("version", "unknown")
        return {"success": True, "message": f"Connected to Radarr v{version}"}
    except requests.RequestException as e:
        return {"success": False, "message": f"Error connecting to Radarr: {str(e)}"}

# Generalized filtered flag routes for shows or movies
@router.get("/api/filtered/{item_type}")
def get_filtered_items(item_type: str):
    if item_type not in ("show", "movie"):
        raise HTTPException(status_code=400, detail="Invalid item type")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filtered FROM bleeparr_items WHERE type = ?", (item_type,))
    return [{"id": row[0], "filtered": bool(row[1])} for row in cursor.fetchall()]

@router.put("/api/filtered/{item_type}/{item_id}")
def update_filtered_item(item_type: str, item_id: int, filtered: bool = Query(...)):
    if item_type not in ("show", "movie"):
        raise HTTPException(status_code=400, detail="Invalid item type")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM bleeparr_items WHERE id = ? AND type = ?", (item_id, item_type))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("UPDATE bleeparr_items SET filtered = ? WHERE id = ? AND type = ?", (int(filtered), item_id, item_type))
    else:
        cursor.execute("INSERT INTO bleeparr_items (id, type, filtered) VALUES (?, ?, ?)", (item_id, item_type, int(filtered)))
    conn.commit()
    return {"id": item_id, "type": item_type, "filtered": filtered}

# Get queue from Sonarr
@router.get("/api/sonarr/queue")
def get_sonarr_queue():
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/queue", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get queue from Radarr
@router.get("/api/radarr/queue")
def get_radarr_queue():
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Radarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/queue", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Debug endpoint to check file paths
@router.get("/api/debug/file-paths")
def debug_file_paths():
    """Debug endpoint to check file paths"""
    # Check common directories
    directories = [
        "/app/videos",
        "/app/media",
        "/app/CleanVid",
        "/app/media/tv"
    ]
    
    results = {}
    for directory in directories:
        exists = os.path.exists(directory)
        is_dir = os.path.isdir(directory) if exists else False
        results[directory] = {
            "exists": exists,
            "is_directory": is_dir
        }
        
        if exists and is_dir:
            # List top-level contents
            try:
                contents = os.listdir(directory)
                results[directory]["contents"] = contents[:10]  # First 10 items
                results[directory]["total_items"] = len(contents)
            except Exception as e:
                results[directory]["error"] = str(e)
    
    # Check file system mounts
    try:
        with open('/proc/mounts', 'r') as f:
            mounts = f.read()
        results["mounts"] = mounts
    except Exception as e:
        results["mounts_error"] = str(e)
        
    return results

# Process an episode - Manual trigger
@router.post("/api/process/episode/{episode_id}")
def process_episode(episode_id: int, background_tasks: BackgroundTasks, dry_run: bool = Query(False)):
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        # Get episode details
        response = requests.get(
            f"{url}/api/v3/episode/{episode_id}", 
            headers={"X-Api-Key": api_key}
        )
        response.raise_for_status()
        episode = response.json()
        
        # Get series details
        series_id = episode.get('seriesId')
        if not series_id:
            raise HTTPException(status_code=400, detail="Episode missing series ID")
            
        series_response = requests.get(
            f"{url}/api/v3/series/{series_id}",
            headers={"X-Api-Key": api_key}
        )
        series_response.raise_for_status()
        series = series_response.json()
        
        # Get episode file
        episode_file_id = episode.get('episodeFileId')
        if not episode_file_id:
            raise HTTPException(status_code=404, detail="Episode has no file")
            
        file_response = requests.get(
            f"{url}/api/v3/episodefile/{episode_file_id}",
            headers={"X-Api-Key": api_key}
        )
        file_response.raise_for_status()
        episode_file = file_response.json()
        
        # Get file path
        file_path = episode_file.get('path')
        if not file_path:
            raise HTTPException(status_code=404, detail="Episode file path not found")

        # Check if file exists and try path mapping if needed
        if not os.path.exists(file_path):
            logger.warning(f"File does not exist at path: {file_path}")
            
            # Try various path mappings
            possible_paths = []
            base_name = os.path.basename(file_path)
            
            # Extract series and season info for better path mapping
            parts = file_path.split('/')
            series_name = None
            season_name = None
            
            for i, part in enumerate(parts):
                if i > 0 and 'Season' in part:
                    season_name = part
                    series_name = parts[i-1]
                    break
            
            # Map 1: Try direct CleanVid path
            if 'CleanVid' in file_path:
                # If the path has CleanVid but is not /app/CleanVid
                if not file_path.startswith('/app/CleanVid'):
                    clean_path = '/app/CleanVid' + file_path.split('CleanVid', 1)[1]
                    possible_paths.append(clean_path)
            
            # Map 2: Try to construct path from known information
            if series_name and season_name:
                # Try CleanVid TV path
                clean_tv_path = f'/app/CleanVid/TV/{series_name}/{season_name}/{base_name}'
                possible_paths.append(clean_tv_path)
                
                # Try media TV path
                media_tv_path = f'/app/media/tv/{series_name}/{season_name}/{base_name}'
                possible_paths.append(media_tv_path)
            
            # Map 3: Try general locations
            possible_paths.append(f'/app/videos/{base_name}')
            possible_paths.append(f'/app/videos/{base_name.replace(" ", "_")}')
            
            # Try each possible path
            found_path = None
            for path in possible_paths:
                logger.info(f"Trying alternative path: {path}")
                if os.path.exists(path):
                    logger.info(f"Found file at path: {path}")
                    found_path = path
                    break
            
            if found_path:
                file_path = found_path
            else:
                # If we still can't find it, search recursively
                logger.warning("Could not find file at any mapped paths, searching directories...")
                search_dirs = ['/app/videos', '/app/CleanVid/TV', '/app/media/tv']
                
                if series_name:
                    # Add more specific search paths if we know the series name
                    search_dirs.append(f'/app/CleanVid/TV/{series_name}')
                    search_dirs.append(f'/app/media/tv/{series_name}')
                
                for search_dir in search_dirs:
                    if os.path.exists(search_dir) and os.path.isdir(search_dir):
                        logger.info(f"Searching recursively in: {search_dir}")
                        for root, dirs, files in os.walk(search_dir):
                            if base_name in files:
                                found_path = os.path.join(root, base_name)
                                logger.info(f"Found file by searching: {found_path}")
                                file_path = found_path
                                break
                        if found_path:
                            break
                
                if not found_path:
                    # Last attempt: Try to clean up the filename and search again
                    clean_base_name = base_name.replace("'", "").replace(":", "").replace(",", "").replace("&", "and")
                    if clean_base_name != base_name:
                        logger.info(f"Searching for cleaned filename: {clean_base_name}")
                        for search_dir in search_dirs:
                            if os.path.exists(search_dir) and os.path.isdir(search_dir):
                                for root, dirs, files in os.walk(search_dir):
                                    for file in files:
                                        if file.replace("'", "").replace(":", "").replace(",", "").replace("&", "and") == clean_base_name:
                                            found_path = os.path.join(root, file)
                                            logger.info(f"Found file with similar name: {found_path}")
                                            file_path = found_path
                                            break
                                    if found_path:
                                        break
                            if found_path:
                                break
                    
                    if not found_path:
                        raise HTTPException(status_code=404, detail=f"File not found after trying multiple paths. Original path: {file_path}")
        
        # Create episode info
        season_num = str(episode.get('seasonNumber', 0)).zfill(2)
        episode_num = str(episode.get('episodeNumber', 0)).zfill(2)
        episode_title = episode.get('title', 'Unknown Episode')
        episode_info = f"S{season_num}E{episode_num} - {episode_title}"
        
        # Add to processing queue for background processing
        if add_to_queue(
            item_type='show',
            item_id=episode_id,
            file_path=file_path,
            title=series.get('title', 'Unknown Series'),
            detail=episode_info,
            parent_id=series_id
        ):
            return {
                "success": True,
                "message": f"Episode queued for processing: {series.get('title')} - {episode_info}",
                "file_path": file_path,
                "dry_run": dry_run
            }
        else:
            return {
                "success": False,
                "message": "Episode already in queue or recently processed",
                "file_path": file_path
            }
            
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Process a movie - Manual trigger
@router.post("/api/process/movie/{movie_id}")
def process_movie(movie_id: int, background_tasks: BackgroundTasks, dry_run: bool = Query(False)):
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Radarr URL or API key not set")

    try:
        # Get movie details
        response = requests.get(
            f"{url}/api/v3/movie/{movie_id}", 
            headers={"X-Api-Key": api_key}
        )
        response.raise_for_status()
        movie = response.json()
        
        # Get movie file
        movie_file = movie.get('movieFile', {})
        if not movie_file:
            raise HTTPException(status_code=404, detail="Movie has no file")
        
        movie_file_id = movie_file.get('id')
        if movie_file_id:
            # Get more detailed file info if needed
            file_response = requests.get(
                f"{url}/api/v3/moviefile/{movie_file_id}",
                headers={"X-Api-Key": api_key}
            )
            file_response.raise_for_status()
            movie_file = file_response.json()
        
        # Get file path
        file_path = movie_file.get('path')
        if not file_path:
            raise HTTPException(status_code=404, detail="Movie file path not found")

        # Check if file exists and try path mapping if needed
        if not os.path.exists(file_path):
            logger.warning(f"File does not exist at path: {file_path}")
            
            # Try various path mappings
            possible_paths = []
            base_name = os.path.basename(file_path)
            
            # Extract movie title for better path mapping
            movie_title = movie.get('title')
            
            # Map 1: Try direct CleanVid path
            if 'CleanVid' in file_path:
                # If the path has CleanVid but is not /app/CleanVid
                if not file_path.startswith('/app/CleanVid'):
                    clean_path = '/app/CleanVid' + file_path.split('CleanVid', 1)[1]
                    possible_paths.append(clean_path)
            
            # Map 2: Try to construct path from known information
            if movie_title:
                # Try CleanVid Movies path
                clean_movie_path = f'/app/CleanVid/Movies/{movie_title}/{base_name}'
                possible_paths.append(clean_movie_path)
                
                # Try media Movies path if it exists
                media_movie_path = f'/app/media/movies/{movie_title}/{base_name}'
                possible_paths.append(media_movie_path)
            
            # Map 3: Try general locations
            possible_paths.append(f'/app/videos/{base_name}')
            possible_paths.append(f'/app/videos/{base_name.replace(" ", "_")}')
            
            # Try each possible path
            found_path = None
            for path in possible_paths:
                logger.info(f"Trying alternative path: {path}")
                if os.path.exists(path):
                    logger.info(f"Found file at path: {path}")
                    found_path = path
                    break
            
            if found_path:
                file_path = found_path
            else:
                # If we still can't find it, search recursively
                logger.warning("Could not find file at any mapped paths, searching directories...")
                search_dirs = ['/app/videos', '/app/CleanVid/Movies']
                
                if movie_title:
                    # Add more specific search paths if we know the movie title
                    search_dirs.append(f'/app/CleanVid/Movies/{movie_title}')
                
                for search_dir in search_dirs:
                    if os.path.exists(search_dir) and os.path.isdir(search_dir):
                        logger.info(f"Searching recursively in: {search_dir}")
                        for root, dirs, files in os.walk(search_dir):
                            if base_name in files:
                                found_path = os.path.join(root, base_name)
                                logger.info(f"Found file by searching: {found_path}")
                                file_path = found_path
                                break
                        if found_path:
                            break
                
                if not found_path:
                    # Last attempt: Try to clean up the filename and search again
                    clean_base_name = base_name.replace("'", "").replace(":", "").replace(",", "").replace("&", "and")
                    if clean_base_name != base_name:
                        logger.info(f"Searching for cleaned filename: {clean_base_name}")
                        for search_dir in search_dirs:
                            if os.path.exists(search_dir) and os.path.isdir(search_dir):
                                for root, dirs, files in os.walk(search_dir):
                                    for file in files:
                                        if file.replace("'", "").replace(":", "").replace(",", "").replace("&", "and") == clean_base_name:
                                            found_path = os.path.join(root, file)
                                            logger.info(f"Found file with similar name: {found_path}")
                                            file_path = found_path
                                            break
                                    if found_path:
                                        break
                            if found_path:
                                break
                    
                    if not found_path:
                        raise HTTPException(status_code=404, detail=f"Movie file not found after trying multiple paths. Original path: {file_path}")
        
        # Add to processing queue for background processing
        if add_to_queue(
            item_type='movie',
            item_id=movie_id,
            file_path=file_path,
            title=movie.get('title', 'Unknown Movie'),
            detail=f"{movie.get('year', '')}"
        ):
            return {
                "success": True,
                "message": f"Movie queued for processing: {movie.get('title')}",
                "file_path": file_path,
                "dry_run": dry_run
            }
        else:
            return {
                "success": False,
                "message": "Movie already in queue or recently processed",
                "file_path": file_path
            }
            
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get processing queue and history
@router.get("/api/processing")
def get_processing():
    """Get current processing queue and history"""
    return get_processing_status()

# Process all episodes for a series
@router.post("/api/process/series/{series_id}")
def process_series(series_id: int, dry_run: bool = Query(False)):
    """Process all episodes for a series"""
    logger.info(f"Processing series requested for ID: {series_id}")
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        logger.error("Sonarr URL or API key not set")
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")
    
    try:
        # Get series details
        logger.info(f"Fetching series details from Sonarr for ID: {series_id}")
        series_response = requests.get(
            f"{url}/api/v3/series/{series_id}",
            headers={"X-Api-Key": api_key}
        )
        if series_response.status_code != 200:
            logger.error(f"Failed to get series from Sonarr: HTTP {series_response.status_code}")
            raise HTTPException(status_code=500, detail=f"Failed to get series from Sonarr: HTTP {series_response.status_code}")
            
        series = series_response.json()
        logger.info(f"Successfully fetched series: {series.get('title')}")
        
        # Get episodes
        logger.info(f"Fetching episodes for series ID: {series_id}")
        episodes_response = requests.get(
            f"{url}/api/v3/episode",
            params={"seriesId": series_id},
            headers={"X-Api-Key": api_key}
        )
        if episodes_response.status_code != 200:
            logger.error(f"Failed to get episodes from Sonarr: HTTP {episodes_response.status_code}")
            raise HTTPException(status_code=500, detail=f"Failed to get episodes from Sonarr: HTTP {episodes_response.status_code}")
            
        episodes = episodes_response.json()
        logger.info(f"Retrieved {len(episodes)} episodes for series ID: {series_id}")
        
        # Filter to episodes that have files
        episodes_with_files = [ep for ep in episodes if ep.get('hasFile', False)]
        logger.info(f"Found {len(episodes_with_files)} episodes with files")
        
        if not episodes_with_files:
            logger.warning(f"No episodes with files found for series: {series.get('title')}")
            return {
                "success": False,
                "message": f"No episodes with files found for series: {series.get('title')}",
                "series_id": series_id
            }
        
        # Queue each episode for processing
        queued_count = 0
        for episode in episodes_with_files:
            try:
                episode_id = episode.get('id')
                episode_file_id = episode.get('episodeFileId')
                logger.info(f"Processing episode ID: {episode_id}, file ID: {episode_file_id}")
                
                if not episode_file_id:
                    logger.warning(f"Episode ID {episode_id} has no file ID")
                    continue
                    
                # Get file details
                logger.info(f"Fetching file details for episode file ID: {episode_file_id}")
                file_response = requests.get(
                    f"{url}/api/v3/episodefile/{episode_file_id}",
                    headers={"X-Api-Key": api_key}
                )
                
                if file_response.status_code != 200:
                    logger.warning(f"Failed to get episode file {episode_file_id}: HTTP {file_response.status_code}")
                    continue
                    
                episode_file = file_response.json()
                file_path = episode_file.get('path')
                logger.info(f"Got file path: {file_path}")
                
                if not file_path:
                    logger.warning(f"No file path found for episode file ID: {episode_file_id}")
                    continue
                
                # Verify file exists
                if not os.path.exists(file_path):
                    logger.warning(f"File does not exist at path: {file_path}")
                    
                    # Try various path mappings
                    possible_paths = []
                    base_name = os.path.basename(file_path)
                    
                    # Extract series and season info for better path mapping
                    parts = file_path.split('/')
                    series_name = None
                    season_name = None
                    
                    for i, part in enumerate(parts):
                        if i > 0 and 'Season' in part:
                            season_name = part
                            series_name = parts[i-1]
                            break
                    
                    # Map 1: Try direct CleanVid path
                    if 'CleanVid' in file_path:
                        # If the path has CleanVid but is not /app/CleanVid
                        if not file_path.startswith('/app/CleanVid'):
                            clean_path = '/app/CleanVid' + file_path.split('CleanVid', 1)[1]
                            possible_paths.append(clean_path)
                    
                    # Map 2: Try to construct path from known information
                    if series_name and season_name:
                        # Try CleanVid TV path
                        clean_tv_path = f'/app/CleanVid/TV/{series_name}/{season_name}/{base_name}'
                        possible_paths.append(clean_tv_path)
                        
                        # Try media TV path
                        media_tv_path = f'/app/media/tv/{series_name}/{season_name}/{base_name}'
                        possible_paths.append(media_tv_path)
                    
                    # Map 3: Try general locations
                    possible_paths.append(f'/app/videos/{base_name}')
                    possible_paths.append(f'/app/videos/{base_name.replace(" ", "_")}')
                    
                    # Try each possible path
                    found_path = None
                    for path in possible_paths:
                        logger.info(f"Trying alternative path: {path}")
                        if os.path.exists(path):
                            logger.info(f"Found file at path: {path}")
                            found_path = path
                            break
                    
                    if found_path:
                        file_path = found_path
                    else:
                        # If we still can't find it, search recursively
                        logger.warning("Could not find file at any mapped paths, searching directories...")
                        search_dirs = ['/app/videos', '/app/CleanVid/TV', '/app/media/tv']
                        
                        if series_name:
                            # Add more specific search paths if we know the series name
                            search_dirs.append(f'/app/CleanVid/TV/{series_name}')
                            search_dirs.append(f'/app/media/tv/{series_name}')
                        
                        for search_dir in search_dirs:
                            if os.path.exists(search_dir) and os.path.isdir(search_dir):
                                logger.info(f"Searching recursively in: {search_dir}")
                                for root, dirs, files in os.walk(search_dir):
                                    if base_name in files:
                                        found_path = os.path.join(root, base_name)
                                        logger.info(f"Found file by searching: {found_path}")
                                        file_path = found_path
                                        break
                                if found_path:
                                    break
                        
                        if not found_path:
                            # Last attempt: Try to clean up the filename and search again
                            clean_base_name = base_name.replace("'", "").replace(":", "").replace(",", "").replace("&", "and")
                            if clean_base_name != base_name:
                                logger.info(f"Searching for cleaned filename: {clean_base_name}")
                                for search_dir in search_dirs:
                                    if os.path.exists(search_dir) and os.path.isdir(search_dir):
                                        for root, dirs, files in os.walk(search_dir):
                                            for file in files:
                                                if file.replace("'", "").replace(":", "").replace(",", "").replace("&", "and") == clean_base_name:
                                                    found_path = os.path.join(root, file)
                                                    logger.info(f"Found file with similar name: {found_path}")
                                                    file_path = found_path
                                                    break
                                            if found_path:
                                                break
                                    if found_path:
                                        break
                            
                            if not found_path:
                                logger.warning(f"Episode file not found after trying multiple paths, skipping this episode")
                                continue

                # Create episode info
                season_num = str(episode.get('seasonNumber', 0)).zfill(2)
                episode_num = str(episode.get('episodeNumber', 0)).zfill(2)
                episode_title = episode.get('title', 'Unknown Episode')
                episode_info = f"S{season_num}E{episode_num} - {episode_title}"
                
                # Add to processing queue
                logger.info(f"Adding to queue: {series.get('title')} - {episode_info}")
                from backend.tasks import add_to_queue
                result = add_to_queue(
                    item_type='show',
                    item_id=episode_id,
                    file_path=file_path,
                    title=series.get('title', 'Unknown Series'),
                    detail=episode_info,
                    parent_id=series_id
                )
                
                if result:
                    queued_count += 1
                    logger.info(f"Successfully queued episode: {episode_info}")
                else:
                    logger.warning(f"Episode already in queue or recently processed: {episode_info}")
            except Exception as episode_error:
                logger.error(f"Error processing episode ID {episode.get('id')}: {str(episode_error)}")
                continue
        
        logger.info(f"Queued {queued_count} episodes for processing from series: {series.get('title')}")
        return {
            "success": True,
            "message": f"Queued {queued_count} episodes for processing from series: {series.get('title')}",
            "series_id": series_id,
            "queued_count": queued_count,
            "total_episodes": len(episodes_with_files),
            "dry_run": dry_run
        }
    
    except requests.RequestException as e:
        logger.error(f"API error while processing series {series_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while processing series {series_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Include the routes from settings_router in this router
router.include_router(settings_router)
