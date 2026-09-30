import requests
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bleeparr.radarr')

class RadarrAPI:
    """Class to handle interactions with the Radarr API"""
    
    def __init__(self, url: str, api_key: str):
        """
        Initialize the Radarr API connection
        
        Args:
            url: Base URL for Radarr (e.g., http://localhost:7878)
            api_key: API key for authentication
        """
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        self._last_queue_check = 0
        self._last_history_check = 0
        self._monitored_movie_ids = set()
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to the Radarr API
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/system/status", headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                version = data.get('version', 'unknown')
                return True, f"Connected to Radarr v{version}"
            else:
                return False, f"Failed to connect to Radarr: HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Error connecting to Radarr: {str(e)}"
    
    def get_movie_list(self) -> List[Dict[str, Any]]:
        """
        Get the list of all movies from Radarr
        
        Returns:
            List of movie objects
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/movie", headers=self.headers)
            if response.status_code == 200:
                movie_list = response.json()
                logger.info(f"Retrieved {len(movie_list)} movies from Radarr")
                return movie_list
            else:
                logger.error(f"Failed to get movie list: HTTP {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting movie list: {str(e)}")
            return []
    
    def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific movie by ID
        
        Args:
            movie_id: The Radarr movie ID
            
        Returns:
            Movie object or None if not found
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/movie/{movie_id}", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get movie {movie_id}: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting movie {movie_id}: {str(e)}")
            return None
    
    def get_movie_file(self, movie_file_id: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific movie file
        
        Args:
            movie_file_id: The Radarr movie file ID
            
        Returns:
            Movie file object or None if not found
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/moviefile/{movie_file_id}", 
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get movie file {movie_file_id}: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting movie file {movie_file_id}: {str(e)}")
            return None
    
    def get_queue(self) -> List[Dict[str, Any]]:
        """
        Get the current download queue
        
        Returns:
            List of queue items
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/queue", headers=self.headers)
            if response.status_code == 200:
                queue_data = response.json()
                queue_items = queue_data.get('records', [])
                logger.info(f"Retrieved {len(queue_items)} items from queue")
                return queue_items
            else:
                logger.error(f"Failed to get queue: HTTP {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting queue: {str(e)}")
            return []
    
    def set_monitored_movies(self, movie_ids: List[int]) -> None:
        """
        Set which movie IDs to monitor for new downloads
        
        Args:
            movie_ids: List of Radarr movie IDs to monitor
        """
        self._monitored_movie_ids = set(movie_ids)
        logger.info(f"Now monitoring {len(self._monitored_movie_ids)} movies")
    
    def is_movie_monitored(self, movie_id: int) -> bool:
        """
        Check if a movie is being monitored by Bleeparr
        
        Args:
            movie_id: The Radarr movie ID
            
        Returns:
            True if monitored, False otherwise
        """
        return movie_id in self._monitored_movie_ids
    
    def get_movie_path(self, movie_id: int) -> Optional[str]:
        """
        Get the file path for a specific movie
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            File path or None if not found
        """
        try:
            movie = self.get_movie_by_id(movie_id)
            if not movie:
                return None
                
            movie_file_id = movie.get('movieFile', {}).get('id')
            if not movie_file_id:
                logger.warning(f"Movie {movie_id} has no file ID")
                return None
            
            # Get the movie file details to get the path
            movie_file = self.get_movie_file(movie_file_id)
            if movie_file:
                return movie_file.get('path')
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting movie {movie_id}: {str(e)}")
            return None

# Compatibility function to match the style of fetch_sonarr_series
def fetch_radarr_movies():
    """
    Fetch all movies from Radarr
    
    Returns:
        List of movie objects from Radarr
    """
    import os
    
    url = os.getenv("RADARR_URL")
    api_key = os.getenv("RADARR_API_KEY")
    
    if not url or not api_key:
        logger.error("Radarr URL or API key not set")
        return []
    
    api = RadarrAPI(url, api_key)
    return api.get_movie_list()
