import subprocess
import logging

def clean_file(file_path: str, dry_run: bool = False):
    cmd = ["python3", "bleeparr.py", "--input", file_path]
    if dry_run:
        cmd.append("--dry-run")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        logging.error(e.stderr)
        return {"status": "error", "error": e.stderr}

def process_media_file(file_path, media_type, title, output_prefix='clean_'):
    """
    Process a media file to censor profanity
    
    Args:
        file_path: Path to the media file
        media_type: Type of media ('show' or 'movie')
        title: Title of the media
        output_prefix: Prefix for the output file name
        
    Returns:
        Dictionary with processing results
    """
    import os
    from pathlib import Path
    import subprocess
    import logging
    
    logger = logging.getLogger('bleeparr.processor')
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {
            'success': False,
            'error': f"File not found: {file_path}",
            'media_type': media_type,
            'title': title
        }
    
    try:
        # Determine output file path
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        output_name = f"{output_prefix}{file_name}"
        output_path = os.path.join(file_dir, output_name)
        
        # Here you would add your actual bleeping logic
        # This is a placeholder for your existing code
        # For example:
        # result = run_bleeping_process(file_path, output_path)
        
        # Simulate processing for now
        logger.info(f"Processing {media_type}: {title}")
        logger.info(f"Input: {file_path}")
        logger.info(f"Output: {output_path}")
        
        # In a real implementation, you would call your actual processing code here
        success = True  # Set based on actual processing result
        swears_found = 42  # This would be the actual count from processing
        
        return {
            'success': success,
            'output_path': output_path,
            'swears_found': swears_found,
            'media_type': media_type,
            'title': title
        }
    except Exception as e:
        logger.error(f"Error processing {media_type} '{title}': {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'media_type': media_type,
            'title': title
        }

def process_episode(episode_path, series_title, episode_info, output_prefix='clean_'):
    """Process a TV episode file"""
    title = f"{series_title} - {episode_info}"
    return process_media_file(episode_path, 'show', title, output_prefix)

def process_movie(movie_path, movie_title, output_prefix='clean_'):
    """Process a movie file"""
    return process_media_file(movie_path, 'movie', movie_title, output_prefix)
