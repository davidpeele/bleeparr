from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging
from backend.db import set_setting, get_all_settings
from typing import Optional

# Set up logging
logger = logging.getLogger('bleeparr.settings')

router = APIRouter()

class Settings(BaseModel):
    sonarr_url: Optional[str] = None
    sonarr_api_key: Optional[str] = None
    radarr_url: Optional[str] = None
    radarr_api_key: Optional[str] = None
    swears_file: Optional[str] = None
    output_prefix: Optional[str] = None
    output_directory: Optional[str] = None
    enable_auto_processing: Optional[bool] = None
    poll_interval_seconds: Optional[int] = None
    boost_db: Optional[int] = None
    pre_buffer: Optional[int] = None
    post_buffer: Optional[int] = None
    bleeptool: Optional[str] = None
    # New options from bleeparr.py v1.2
    use_beep: Optional[bool] = None
    beep_mode: Optional[str] = None
    temp_dir: Optional[str] = None
    retain_clips: Optional[bool] = None

@router.get("/api/settings")
def get_settings():
    """Get all application settings"""
    try:
        logger.info("Fetching all settings from database")
        settings = get_all_settings()
        logger.info(f"Retrieved settings from database: {settings}")
        
        # Log environment variables for comparison
        logger.info(f"SONARR_URL env: {os.getenv('SONARR_URL')}")
        logger.info(f"SONARR_API_KEY env: {os.getenv('SONARR_API_KEY')}")
        logger.info(f"RADARR_URL env: {os.getenv('RADARR_URL')}")
        logger.info(f"RADARR_API_KEY env: {os.getenv('RADARR_API_KEY')}")
        
        # Check if environment variables should be used as defaults
        if 'sonarr_url' not in settings or not settings['sonarr_url']:
            logger.info("Using SONARR_URL from environment")
            settings['sonarr_url'] = os.getenv("SONARR_URL", "")
        
        if 'sonarr_api_key' not in settings or not settings['sonarr_api_key']:
            logger.info("Using SONARR_API_KEY from environment")
            settings['sonarr_api_key'] = os.getenv("SONARR_API_KEY", "")
        
        if 'radarr_url' not in settings or not settings['radarr_url']:
            logger.info("Using RADARR_URL from environment")
            settings['radarr_url'] = os.getenv("RADARR_URL", "")
        
        if 'radarr_api_key' not in settings or not settings['radarr_api_key']:
            logger.info("Using RADARR_API_KEY from environment")
            settings['radarr_api_key'] = os.getenv("RADARR_API_KEY", "")
        
        # Convert some values to appropriate types
        if 'enable_auto_processing' in settings:
            settings['enable_auto_processing'] = settings['enable_auto_processing'] == '1'
        
        if 'poll_interval_seconds' in settings:
            try:
                settings['poll_interval_seconds'] = int(settings['poll_interval_seconds'])
            except ValueError:
                settings['poll_interval_seconds'] = 300
        
        if 'boost_db' in settings:
            try:
                settings['boost_db'] = int(settings['boost_db'])
            except ValueError:
                settings['boost_db'] = 6
        
        if 'pre_buffer' in settings:
            try:
                settings['pre_buffer'] = int(settings['pre_buffer'])
            except ValueError:
                settings['pre_buffer'] = 100
        
        if 'post_buffer' in settings:
            try:
                settings['post_buffer'] = int(settings['post_buffer'])
            except ValueError:
                settings['post_buffer'] = 100
        
        # New options
        if 'use_beep' in settings:
            settings['use_beep'] = settings['use_beep'] == '1'
        else:
            settings['use_beep'] = False
            
        if 'beep_mode' not in settings:
            settings['beep_mode'] = 'words'
            
        if 'temp_dir' not in settings:
            settings['temp_dir'] = ''
            
        if 'retain_clips' in settings:
            settings['retain_clips'] = settings['retain_clips'] == '1'
        else:
            settings['retain_clips'] = False

        logger.info(f"Final settings being returned: {settings}")            
        return settings
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting settings: {str(e)}")

@router.post("/api/settings")
def update_settings(settings: Dict[str, Any] = Body(...)):
    """Update application settings"""
    try:
        logger.info(f"Received settings update: {settings}")

        # Convert boolean values to strings for storage
        if 'enable_auto_processing' in settings:
            settings['enable_auto_processing'] = '1' if settings['enable_auto_processing'] else '0'
            logger.info(f"Converted enable_auto_processing to: {settings['enable_auto_processing']}")
        
        # New options
        if 'use_beep' in settings:
            settings['use_beep'] = '1' if settings['use_beep'] else '0'
            logger.info(f"Converted use_beep to: {settings['use_beep']}")
            
        if 'retain_clips' in settings:
            settings['retain_clips'] = '1' if settings['retain_clips'] else '0'
            logger.info(f"Converted retain_clips to: {settings['retain_clips']}")
        
        # Update each setting in the database
        for key, value in settings.items():
            logger.info(f"Setting {key} = {value}")
            set_setting(key, str(value))
        
        # Update environment variables for immediate use
        if 'sonarr_url' in settings:
            os.environ['SONARR_URL'] = str(settings['sonarr_url'])
        
        if 'sonarr_api_key' in settings:
            os.environ['SONARR_API_KEY'] = str(settings['sonarr_api_key'])
        
        if 'radarr_url' in settings:
            os.environ['RADARR_URL'] = str(settings['radarr_url'])
        
        if 'radarr_api_key' in settings:
            os.environ['RADARR_API_KEY'] = str(settings['radarr_api_key'])

        logger.info("Settings updated successfully")
        return {"success": True, "message": "Settings updated successfully"}
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")
