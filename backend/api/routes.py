from fastapi import APIRouter, HTTPException, Query
import os
import requests
from backend.db import get_db
from typing import List, Dict, Any, Optional

router = APIRouter()

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

def update_filtered(series_id: int, filtered: bool = Query(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bleeparr_items (id, type, filtered)
        VALUES (?, 'show', ?)
        ON CONFLICT(id) DO UPDATE SET filtered = excluded.filtered
    """, (series_id, int(filtered)))
    conn.commit()
    return {"series_id": series_id, "filtered": filtered}

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

# Get status for both services
@router.get("/api/status")
def get_status():
    sonarr_url = os.getenv("SONARR_URL")
    sonarr_api_key = os.getenv("SONARR_API_KEY")
    radarr_url = os.getenv("RADARR_URL")
    radarr_api_key = os.getenv("RADARR_API_KEY")
    
    sonarr_status = {"configured": bool(sonarr_url and sonarr_api_key), "connected": False}
    radarr_status = {"configured": bool(radarr_url and radarr_api_key), "connected": False}
    
    if sonarr_status["configured"]:
        try:
            response = requests.get(f"{sonarr_url}/api/v3/system/status", headers={"X-Api-Key": sonarr_api_key}, timeout=5)
            sonarr_status["connected"] = response.status_code == 200
            if sonarr_status["connected"]:
                sonarr_status["version"] = response.json().get("version", "unknown")
        except:
            pass
    
    if radarr_status["configured"]:
        try:
            response = requests.get(f"{radarr_url}/api/v3/system/status", headers={"X-Api-Key": radarr_api_key}, timeout=5)
            radarr_status["connected"] = response.status_code == 200
            if radarr_status["connected"]:
                radarr_status["version"] = response.json().get("version", "unknown")
        except:
            pass
    
    return {
        "sonarr": sonarr_status,
        "radarr": radarr_status
    }
    
    from fastapi import APIRouter, HTTPException, Query
import os
import requests
from backend.db import get_db

router = APIRouter()


# Process an episode - New Endpoint
@router.post("/api/process/episode/{episode_id}")
def process_episode(episode_id: int):
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
        
        # Create episode info
        season_num = str(episode.get('seasonNumber', 0)).zfill(2)
        episode_num = str(episode.get('episodeNumber', 0)).zfill(2)
        episode_title = episode.get('title', 'Unknown Episode')
        episode_info = f"S{season_num}E{episode_num} - {episode_title}"
        
        # Call your bleeping processing function here
        # This is a placeholder - implement your actual processing logic
        from backend.api.bleeparr_core import process_episode
        result = process_episode(
            file_path, 
            series.get('title', 'Unknown Series'), 
            episode_info
        )
        
        return result
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Process a movie - New Endpoint
@router.post("/api/process/movie/{movie_id}")
def process_movie(movie_id: int):
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
        
        # Call your bleeping processing function here
        # This is a placeholder - implement your actual processing logic
        from backend.api.bleeparr_core import process_movie
        result = process_movie(
            file_path, 
            movie.get('title', 'Unknown Movie')
        )
        
        return result
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






