import os
import logging
from pathlib import Path
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bleeparr.core')

class Bleeparr:
    """Class to handle profanity cleaning operations"""
    
    def __init__(self, swears_file='swears.txt', output_prefix='clean_', output_directory=''):
        """
        Initialize Bleeparr processor
        
        Args:
            swears_file: Path to the file containing profanity words
            output_prefix: Prefix to add to cleaned files
            output_directory: Directory to save cleaned files (if empty, same as input)
        """
        self.swears_file = swears_file
        self.output_prefix = output_prefix
        self.output_directory = output_directory
        
        # Load swear words list
        self.swear_words = self._load_swear_words()
        
        logger.info(f"Initialized Bleeparr with {len(self.swear_words)} words to censor")
    
    def _load_swear_words(self):
        """Load swear words from file"""
        try:
            if not os.path.exists(self.swears_file):
                logger.warning(f"Swears file not found: {self.swears_file}")
                return []
                
            with open(self.swears_file, 'r') as f:
                return [line.strip().lower() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Error loading swear words: {str(e)}")
            return []
    
    def process_file(self, file_path):
        """
        Process a media file to censor profanity
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary with processing results
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {
                'success': False,
                'error': f"File not found: {file_path}"
            }
        
        try:
            # Determine output file path
            file_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            
            if self.output_directory:
                output_dir = self.output_directory
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
            else:
                output_dir = file_dir
                
            output_name = f"{self.output_prefix}{file_name}"
            output_path = os.path.join(output_dir, output_name)
            
            # Here, you would implement your actual bleeping logic
            # This is a placeholder for your existing code
            # For example, you might call an external script or use a library
            
            # Example: Call ffmpeg or another tool to process the audio
            # command = [
            #    "ffmpeg", "-i", file_path, "-acodec", "...", output_path
            # ]
            # subprocess.run(command, check=True)
            
            # For now, let's just return a success response
            logger.info(f"Would process file: {file_path}")
            logger.info(f"Output would be: {output_path}")
            
            # Simulate processing results
            swears_found = 42  # This would be the actual count
            
            return {
                'success': True,
                'output_path': output_path,
                'swears_found': swears_found
            }
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Standalone functions for compatibility with existing code
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
    # Create a temporary Bleeparr instance
    bleeper = Bleeparr(output_prefix=output_prefix)
    
    # Process the file
    result = bleeper.process_file(file_path)
    
    # Add additional info
    result['media_type'] = media_type
    result['title'] = title
    
    return result

def process_episode(episode_path, series_title, episode_info, output_prefix='clean_'):
    """Process a TV episode file"""
    title = f"{series_title} - {episode_info}"
    return process_media_file(episode_path, 'show', title, output_prefix)

def process_movie(movie_path, movie_title, output_prefix='clean_'):
    """Process a movie file"""
    return process_media_file(movie_path, 'movie', movie_title, output_prefix)