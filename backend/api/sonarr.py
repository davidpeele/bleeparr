import requests
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bleeparr.sonarr')

class SonarrAPI:
    """Class to handle interactions with the Sonarr API"""
    
    def __init__(self, url: str, api_key: str):
        """
        Initialize the Sonarr API connection
        
        Args:
            url: Base URL for Sonarr (e.g., http://localhost:8989)
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
        self._monitored_series_ids = set()
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to the Sonarr API
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/system/status", headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                version = data.get('version', 'unknown')
                return True, f"Connected to Sonarr v{version}"
            else:
                return False, f"Failed to connect to Sonarr: HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Error connecting to Sonarr: {str(e)}"
    
    def get_series_list(self) -> List[Dict[str, Any]]:
        """
        Get the list of all series from Sonarr
        
        Returns:
            List of series objects
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/series", headers=self.headers)
            if response.status_code == 200:
                series_list = response.json()
                logger.info(f"Retrieved {len(series_list)} series from Sonarr")
                return series_list
            else:
                logger.error(f"Failed to get series list: HTTP {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting series list: {str(e)}")
            return []
    
    def get_series_by_id(self, series_id: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific series by ID
        
        Args:
            series_id: The Sonarr series ID
            
        Returns:
            Series object or None if not found
        """
        try:
            response = requests.get(f"{self.base_url}/api/v3/series/{series_id}", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get series {series_id}: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting series {series_id}: {str(e)}")
            return None
    
    def get_episodes_by_series_id(self, series_id: int) -> List[Dict[str, Any]]:
        """
        Get all episodes for a specific series
        
        Args:
            series_id: The Sonarr series ID
            
        Returns:
            List of episode objects
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/episode", 
                headers=self.headers,
                params={'seriesId': series_id}
            )
            if response.status_code == 200:
                episodes = response.json()
                logger.info(f"Retrieved {len(episodes)} episodes for series {series_id}")
                return episodes
            else:
                logger.error(f"Failed to get episodes for series {series_id}: HTTP {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting episodes for series {series_id}: {str(e)}")
            return []
    
    def get_episode_file(self, episode_file_id: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific episode file
        
        Args:
            episode_file_id: The Sonarr episode file ID
            
        Returns:
            Episode file object or None if not found
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/episodefile/{episode_file_id}", 
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get episode file {episode_file_id}: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting episode file {episode_file_id}: {str(e)}")
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

    def get_history(self, event_type=None, since=None, limit=10):
        """
        Get history items from Sonarr
        
        Args:
            event_type: Optional filter by event type (e.g., 'downloadFolderImported')
            since: Optional datetime to filter by (only get items since this time)
            limit: Maximum number of items to return
        
        Returns:
            List of history items
        """
        try:
            params = {'pageSize': limit}
            
            if event_type:
                params['eventType'] = event_type
                
            response = requests.get(
                f"{self.base_url}/api/v3/history", 
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                history_data = response.json()
                records = history_data.get('records', [])

                # Filter by date if needed
                if since and isinstance(since, datetime):
                    # Convert to ISO format string
                    since_str = since.isoformat()
                    records = [
                        record for record in records 
                        if record.get('date', '') >= since_str
                    ]

                logger.info(f"Retrieved {len(records)} history items from Sonarr")
                return records
            else:
                logger.error(f"Failed to get history: HTTP {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting history: {str(e)}")
            return []

    
    def set_monitored_series(self, series_ids: List[int]) -> None:
        """
        Set which series IDs to monitor for new episodes
        
        Args:
            series_ids: List of Sonarr series IDs to monitor
        """
        self._monitored_series_ids = set(series_ids)
        logger.info(f"Now monitoring {len(self._monitored_series_ids)} series")
    
    def is_series_monitored(self, series_id: int) -> bool:
        """
        Check if a series is being monitored by Bleeparr
        
        Args:
            series_id: The Sonarr series ID
            
        Returns:
            True if monitored, False otherwise
        """
        return series_id in self._monitored_series_ids
    
    def get_episode_path(self, episode_id: int) -> Optional[str]:
        """
        Get the file path for a specific episode
        
        Args:
            episode_id: Sonarr episode ID
            
        Returns:
            File path or None if not found
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/episode/{episode_id}", 
                headers=self.headers
            )
            if response.status_code == 200:
                episode_data = response.json()
                episode_file_id = episode_data.get('episodeFileId')
                
                if not episode_file_id:
                    logger.warning(f"Episode {episode_id} has no file ID")
                    return None
                
                # Get the episode file details to get the path
                episode_file = self.get_episode_file(episode_file_id)
                if episode_file:
                    return episode_file.get('path')
                return None
            else:
                logger.error(f"Failed to get episode {episode_id}: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting episode {episode_id}: {str(e)}")
            return None

def fetch_sonarr_series():
    """
    Fetch all series from Sonarr
    
    This function is maintained for compatibility with existing code.
    It creates a temporary SonarrAPI instance and uses it to fetch the series list.
    
    Returns:
        List of series objects from Sonarr
    """
    import os
    
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")
    
    if not url or not api_key:
        logger.error("Sonarr URL or API key not set")
        return []
    
    api = SonarrAPI(url, api_key)
    return api.get_series_list()
