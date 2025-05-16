import os
import json
import logging
from backend.db import get_setting

logger = logging.getLogger('bleeparr.path_mapping')

def get_path_mappings():
    """Get configured path mappings from settings"""
    try:
        mappings_json = get_setting('path_mappings')
        if not mappings_json:
            # Return default mappings based on Docker Compose
            return [
                {'host_path': '/mnt/storagepool/TV', 'container_path': '/app/media/tv'},
                {'host_path': '/mnt/storagepool/CleanVid', 'container_path': '/app/CleanVid'},
                {'host_path': '/mnt/storagepool/Movies', 'container_path': '/app/media/movies'}
            ]
        
        mappings = json.loads(mappings_json)
        # Validate mappings
        valid_mappings = []
        for mapping in mappings:
            if 'host_path' in mapping and 'container_path' in mapping:
                if mapping['host_path'] and mapping['container_path']:
                    valid_mappings.append(mapping)
        
        if not valid_mappings:
            # Return default mappings if no valid mappings found
            return [
                {'host_path': '/mnt/storagepool/TV', 'container_path': '/app/media/tv'},
                {'host_path': '/mnt/storagepool/CleanVid', 'container_path': '/app/CleanVid'},
                {'host_path': '/mnt/storagepool/Movies', 'container_path': '/app/media/movies'}
            ]
        
        return valid_mappings
    except Exception as e:
        logger.error(f"Error getting path mappings: {e}")
        # Return default mappings on error
        return [
            {'host_path': '/mnt/storagepool/TV', 'container_path': '/app/media/tv'},
            {'host_path': '/mnt/storagepool/CleanVid', 'container_path': '/app/CleanVid'},
            {'host_path': '/mnt/storagepool/Movies', 'container_path': '/app/media/movies'}
        ]

def map_path(original_path):
    """
    Map a file path from host system to container path using configured mappings
    Returns the mapped path and a boolean indicating whether a mapping was found
    """
    if not original_path:
        return original_path, False
    
    mappings = get_path_mappings()
    
    # First, try exact prefix replacement
    for mapping in mappings:
        host_path = mapping['host_path']
        container_path = mapping['container_path']
        
        if original_path.startswith(host_path):
            mapped_path = original_path.replace(host_path, container_path, 1)
            logger.info(f"Mapped path: {original_path} -> {mapped_path}")
            return mapped_path, True
    
    # If no exact match is found, try more flexible matching
    # (might be needed if there are slight differences in path format)
    original_path_norm = os.path.normpath(original_path)
    for mapping in mappings:
        host_path_norm = os.path.normpath(mapping['host_path'])
        container_path_norm = os.path.normpath(mapping['container_path'])
        
        if original_path_norm.startswith(host_path_norm):
            relative_path = os.path.relpath(original_path_norm, host_path_norm)
            mapped_path = os.path.join(container_path_norm, relative_path)
            logger.info(f"Mapped path (normalized): {original_path} -> {mapped_path}")
            return mapped_path, True
    
    # No mapping found, return original path
    logger.warning(f"No path mapping found for: {original_path}")
    return original_path, False

def find_file_with_fallbacks(file_path):
    """
    Find a file using path mapping and fallback strategies
    Returns the found path or None if file not found
    """
    # First try direct path mapping
    mapped_path, was_mapped = map_path(file_path)
    
    if os.path.exists(mapped_path):
        return mapped_path
    
    # If path was already mapped but file not found, try direct methods
    if was_mapped:
        logger.warning(f"Mapped file not found at path: {mapped_path}")
    else:
        logger.warning(f"File not found at path: {file_path}")
    
    # Try fallbacks:
    # 1. Extract base name and try common media directories
    base_name = os.path.basename(file_path)
    common_dirs = [
        '/app/videos',
        '/app/media/tv',
        '/app/media/movies',
        '/app/CleanVid/TV',
        '/app/CleanVid/Movies'
    ]
    
    for directory in common_dirs:
        if os.path.exists(directory) and os.path.isdir(directory):
            test_path = os.path.join(directory, base_name)
            if os.path.exists(test_path):
                logger.info(f"Found file at fallback path: {test_path}")
                return test_path
    
    # 2. Recursive search in common directories (use with caution - can be slow)
    # Extract series/movie name from path if possible
    path_parts = file_path.split('/')
    for i, part in enumerate(path_parts):
        if 'Season' in part and i > 0:
            series_name = path_parts[i-1]
            season_name = part
            # Try more specific paths first
            specific_dirs = [
                os.path.join('/app/media/tv', series_name),
                os.path.join('/app/CleanVid/TV', series_name),
                os.path.join('/app/media/tv', series_name, season_name),
                os.path.join('/app/CleanVid/TV', series_name, season_name)
            ]
            for directory in specific_dirs:
                if os.path.exists(directory) and os.path.isdir(directory):
                    for root, _, files in os.walk(directory):
                        if base_name in files:
                            found_path = os.path.join(root, base_name)
                            logger.info(f"Found file by searching: {found_path}")
                            return found_path
    
    # 3. Last attempt: Clean up the filename and search again
    clean_base_name = base_name.replace("'", "").replace(":", "").replace(",", "").replace("&", "and")
    if clean_base_name != base_name:
        logger.info(f"Searching for cleaned filename: {clean_base_name}")
        for directory in common_dirs:
            if os.path.exists(directory) and os.path.isdir(directory):
                for root, _, files in os.walk(directory):
                    for file in files:
                        clean_file = file.replace("'", "").replace(":", "").replace(",", "").replace("&", "and")
                        if clean_file == clean_base_name:
                            found_path = os.path.join(root, file)
                            logger.info(f"Found file with similar name: {found_path}")
                            return found_path
    
    logger.error(f"File not found after trying multiple fallbacks: {file_path}")
    return None