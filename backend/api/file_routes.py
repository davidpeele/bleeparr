from fastapi import APIRouter, HTTPException
import os
import logging
from typing import List, Dict, Optional
import re

router = APIRouter()
logger = logging.getLogger('bleeparr.files')

# Define common video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.ts', '.mpg', '.mpeg', '.webm']

def is_video_file(filename: str) -> bool:
    """Check if a file is a video file based on its extension"""
    _, ext = os.path.splitext(filename)
    return ext.lower() in VIDEO_EXTENSIONS

def is_safe_path(path: str) -> bool:
    """Validate that a path is safe to access"""
    # Normalize path and resolve any symlinks
    try:
        clean_path = os.path.normpath(os.path.realpath(path))
        
        # Ensure path is within allowed directories
        allowed_prefixes = [
            "/app/media",            # Docker container media path
            "/app/CleanVid",         # Docker container output path
            "/mnt/storagepool/TV",   # Host TV shows path
            "/mnt/storagepool/Movies", # Host Movies path
            "/app/videos"            # Test videos path
        ]
        
        # Check if path starts with any allowed prefix
        return any(clean_path.startswith(prefix) for prefix in allowed_prefixes)
    except:
        return False

def get_directory_files(directory: str) -> List[Dict]:
    """Get all video files in a directory"""
    try:
        if not os.path.exists(directory):
            logger.warning(f"Directory not found: {directory}")
            
            # Try to map from host path to Docker container path
            if directory.startswith('/mnt/storagepool/TV/'):
                container_path = directory.replace('/mnt/storagepool/TV/', '/app/media/tv/')
                logger.info(f"Trying mapped path: {container_path}")
                
                if os.path.exists(container_path):
                    logger.info(f"Found directory at mapped path: {container_path}")
                    directory = container_path
            elif directory.startswith('/mnt/storagepool/Movies/'):
                container_path = directory.replace('/mnt/storagepool/Movies/', '/app/media/movies/')
                logger.info(f"Trying mapped path for movies: {container_path}")
                
                if os.path.exists(container_path):
                    logger.info(f"Found directory at mapped path: {container_path}")
                    directory = container_path
            else:
                return []
        
        # Ensure the path is safe to access
        if not is_safe_path(directory):
            logger.error(f"Attempted to access unsafe path: {directory}")
            return []
            
        files = []
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            
            if os.path.isfile(filepath) and is_video_file(filename):
                try:
                    stat = os.stat(filepath)
                    files.append({
                        "name": filename,
                        "path": filepath,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "is_processed": filename.startswith("clean_")
                    })
                except Exception as e:
                    logger.error(f"Error getting file info for {filepath}: {e}")
                    continue
                    
        # Sort files by name
        files.sort(key=lambda x: x["name"])
        return files
    except Exception as e:
        logger.error(f"Error listing directory {directory}: {e}")
        return []

@router.get("/api/files/directory")
def list_directory_files(directory: str):
    """API endpoint to list all video files in a directory"""
    if not directory:
        raise HTTPException(status_code=400, detail="Directory parameter is required")
        
    # Ensure the path is safe to access
    if not is_safe_path(directory):
        raise HTTPException(status_code=403, detail="Access to this directory is not allowed")
    
    files = get_directory_files(directory)
    return {"directory": directory, "files": files}

@router.get("/api/episodes/{series_id}/{season_id}/files")
def list_episode_files(series_id: int, season_id: int, episode_id: Optional[int] = None):
    """API endpoint to list files for a specific episode or season"""
    try:
        # We need to get the series path from Sonarr
        import requests
        import os
        
        sonarr_url = os.getenv("SONARR_URL")
        sonarr_api_key = os.getenv("SONARR_API_KEY")
        
        if not sonarr_url or not sonarr_api_key:
            raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")
            
        # Get series details from Sonarr
        response = requests.get(
            f"{sonarr_url}/api/v3/series/{series_id}",
            headers={"X-Api-Key": sonarr_api_key}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Series not found: {series_id}")
            
        series = response.json()
        path = series.get("path")
        
        if not path:
            raise HTTPException(status_code=404, detail="Series path not found")
            
        # Construct the season path
        season_path = os.path.join(path, f"Season {season_id}")
        
        # If episode ID is provided, get files for just that episode
        if episode_id:
            # Get episode filename pattern from Sonarr
            ep_response = requests.get(
                f"{sonarr_url}/api/v3/episode/{episode_id}",
                headers={"X-Api-Key": sonarr_api_key}
            )
            
            if ep_response.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
                
            episode = ep_response.json()
            episode_num = episode.get("episodeNumber")
            season_num = episode.get("seasonNumber")
            
            # Filter files for this episode
            all_files = get_directory_files(season_path)
            
            # Pattern to match S01E01 or 1x01 format in filename
            pattern1 = rf'[sS]{season_num:02d}[eE]{episode_num:02d}'
            pattern2 = rf'{season_num}[xX]{episode_num:02d}'
            
            episode_files = [
                f for f in all_files 
                if re.search(pattern1, f["name"]) or re.search(pattern2, f["name"])
            ]
            
            return {
                "series_id": series_id,
                "series_title": series.get("title"),
                "season": season_id,
                "episode": episode_id,
                "directory": season_path,
                "files": episode_files
            }
        else:
            # Return all files in the season
            files = get_directory_files(season_path)
            return {
                "series_id": series_id,
                "series_title": series.get("title"),
                "season": season_id,
                "directory": season_path,
                "files": files
            }
    except Exception as e:
        logger.error(f"Error getting episode files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/movies/{movie_id}/files")
def list_movie_files(movie_id: int):
    """API endpoint to list files for a specific movie"""
    try:
        # We need to get the movie path from Radarr
        import requests
        import os
        
        radarr_url = os.getenv("RADARR_URL")
        radarr_api_key = os.getenv("RADARR_API_KEY")
        
        if not radarr_url or not radarr_api_key:
            raise HTTPException(status_code=500, detail="Radarr URL or API key not set")
            
        # Get movie details from Radarr
        response = requests.get(
            f"{radarr_url}/api/v3/movie/{movie_id}",
            headers={"X-Api-Key": radarr_api_key}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Movie not found: {movie_id}")
            
        movie = response.json()
        path = movie.get("path")
        
        if not path:
            raise HTTPException(status_code=404, detail="Movie path not found")
            
        # Get all video files in the movie directory
        files = get_directory_files(path)
        
        return {
            "movie_id": movie_id,
            "movie_title": movie.get("title"),
            "directory": path,
            "files": files
        }
    except Exception as e:
        logger.error(f"Error getting movie files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/process")
def process_file(file_path: str):
    """API endpoint to process a specific file"""
    try:
        # Ensure the path is safe to access
        if not is_safe_path(file_path):
            raise HTTPException(status_code=403, detail="Access to this file is not allowed")
            
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        # Queue the file for processing
        from backend.tasks import add_to_queue
        
        # Extract information from filename
        filename = os.path.basename(file_path)
        
        # Determine if it's a movie or show (simplified)
        # In a real implementation, you might want to check the path or query Sonarr/Radarr
        is_show = 'Season' in file_path or any(pattern in filename for pattern in ['S01E', 'S02E', '1x', '2x'])
        
        if is_show:
            # Try to extract series and episode info from filename
            series_title = "Unknown Series"
            episode_info = "Unknown Episode"
            
            # Add to queue
            result = add_to_queue(
                item_type='show',
                item_id=0,  # We don't have a real ID
                file_path=file_path,
                title=series_title,
                detail=episode_info,
                parent_id=0,
                manual=True
            )
        else:
            # Assume it's a movie
            movie_title = "Unknown Movie"
            
            # Add to queue
            result = add_to_queue(
                item_type='movie',
                item_id=0,  # We don't have a real ID
                file_path=file_path,
                title=movie_title,
                detail="",
                parent_id=0,
                manual=True
            )
        
        if result:
            return {"success": True, "message": f"File added to processing queue: {filename}"}
        else:
            return {"success": False, "message": "File already in queue or recently processed"}
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
