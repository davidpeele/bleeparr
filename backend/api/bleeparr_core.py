import os
import logging
import subprocess
from pathlib import Path
import json

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
        
        # Validate swears file exists
        if not os.path.exists(self.swears_file):
            logger.warning(f"Swears file not found: {self.swears_file}")
        else:
            # Count swear words for logging
            try:
                with open(self.swears_file, 'r') as f:
                    swear_count = len([line for line in f if line.strip()])
                logger.info(f"Initialized Bleeparr with {swear_count} words to censor")
            except Exception as e:
                logger.error(f"Error reading swear words: {str(e)}")
    
    def process_file(self, file_path, dry_run=False, boost_db=6, pre_buffer=100, post_buffer=100, bleeptool="S-M-FSM"):
        """
        Process a media file to censor profanity
        
        Args:
            file_path: Path to the media file
            dry_run: If True, will not actually make changes
            boost_db: Audio boost level in dB for processing
            pre_buffer: Pre-mute buffer in milliseconds
            post_buffer: Post-mute buffer in milliseconds
            bleeptool: Passes to run (S=Small, M=Medium, FSM=Fallback subtitle mute)
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Attempting to process file: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {
                'success': False,
                'error': f"File not found: {file_path}",
                'file_path': file_path
            }
        
        try:
            # Determine output file path if not dry run
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
            
            # Build command for bleeparr CLI
            cmd = [
                "python3", 
                "./bleeparr-1.1.py", 
                "--input", file_path,
                "--swears", self.swears_file,
                "--boost-db", str(boost_db),
                "--pre-buffer", str(pre_buffer),
                "--post-buffer", str(post_buffer),
                "--bleeptool", bleeptool
            ]
            
            if dry_run:
                cmd.append("--dry-run")
                logger.info(f"Dry run on: {file_path}")
            else:
                # Add output related options
                if output_dir != file_dir:
                    # Handle custom output directory
                    # The CLI doesn't support direct output dir specification,
                    # so we'll need to move the file after processing
                    pass
            
            # Run the command
            logger.info(f"Running command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Bleeparr CLI process failed: {process.stderr}")
                return {
                    'success': False,
                    'error': process.stderr,
                    'command': ' '.join(cmd),
                    'file_path': file_path
                }
            
            # Parse output to get stats
            output = process.stdout
            swears_found = 0
            # Look for lines with "Muting X Bad Words"
            for line in output.splitlines():
                if "Total Words Muted" in line:
                    try:
                        swears_found = int(line.split(":")[-1].strip())
                    except:
                        pass
            
            return {
                'success': True,
                'output_path': output_path if not dry_run else None,
                'swears_found': swears_found,
                'output': output,
                'file_path': file_path,
                'dry_run': dry_run
            }
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path
            }

# Standalone functions for compatibility with existing code
def process_media_file(file_path, media_type, title, output_prefix='clean_', dry_run=False):
    """
    Process a media file to censor profanity
    
    Args:
        file_path: Path to the media file
        media_type: Type of media ('show' or 'movie')
        title: Title of the media
        output_prefix: Prefix for the output file name
        dry_run: If True, will not actually make changes
        
    Returns:
        Dictionary with processing results
    """
    # Create a temporary Bleeparr instance
    bleeper = Bleeparr(output_prefix=output_prefix)
    
    # Process the file
    result = bleeper.process_file(file_path, dry_run=dry_run)
    
    # Add additional info
    result['media_type'] = media_type
    result['title'] = title
    
    return result

def process_episode(episode_path, series_title, episode_info, output_prefix='clean_', dry_run=False):
    """Process a TV episode file"""
    title = f"{series_title} - {episode_info}"
    return process_media_file(episode_path, 'show', title, output_prefix, dry_run)

def process_movie(movie_path, movie_title, output_prefix='clean_', dry_run=False):
    """Process a movie file"""
    return process_media_file(movie_path, 'movie', movie_title, output_prefix, dry_run)

def clean_file(file_path, dry_run=False):
    """Legacy function for backward compatibility"""
    bleeper = Bleeparr()
    return bleeper.process_file(file_path, dry_run=dry_run)
