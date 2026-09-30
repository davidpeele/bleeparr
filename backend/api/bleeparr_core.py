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
    
    def __init__(self, swears_file='swears.txt', output_prefix='clean_', output_directory='', 
                 temp_dir='', retain_clips=False, use_beep=False, beep_mode='words'):
        """
        Initialize Bleeparr processor
        
        Args:
            swears_file: Path to the file containing profanity words
            output_prefix: Prefix to add to cleaned files
            output_directory: Directory to save cleaned files (if empty, same as input)
            temp_dir: Directory to store temporary clips (if empty, uses default)
            retain_clips: Whether to retain clips folder after processing
            use_beep: Use beep tone instead of muting
            beep_mode: Beep mode (words, segments, or both)
        """
        self.swears_file = swears_file
        self.output_prefix = output_prefix
        self.output_directory = output_directory
        self.temp_dir = temp_dir
        self.retain_clips = retain_clips
        self.use_beep = use_beep
        self.beep_mode = beep_mode
        
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
                "./bleeparr.py", 
                "--input", file_path,
                "--swears", self.swears_file,
                "--boost-db", str(boost_db),
                "--pre-buffer", str(pre_buffer),
                "--post-buffer", str(post_buffer),
                "--bleeptool", bleeptool
            ]
            
            # Add new options from v1.2
            if self.use_beep:
                cmd.append("--beep")
                if self.beep_mode:
                    cmd.extend(["--beep-mode", self.beep_mode])
            
            if self.temp_dir:
                cmd.extend(["--temp-dir", self.temp_dir])
                
            if self.retain_clips:
                cmd.append("--retain-clips")
            
            if dry_run:
                cmd.append("--dry-run")
                logger.info(f"Dry run on: {file_path}")
            
            # Run the command
            logger.info(f"Running command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True)

            # Log the complete stdout and stderr
            logger.info(f"Command stdout: {process.stdout}")
            logger.info(f"Command stderr: {process.stderr}")
            
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
            # Look for lines with "Mute Summary" section
            found_summary = False
            for line in output.splitlines():
                if "📋 Mute Summary:" in line:
                    found_summary = True
                    continue
                    
                if found_summary and "Total Words Muted" in line:
                    try:
                        swears_found = int(line.split(":")[-1].strip())
                    except:
                        pass
                elif found_summary and line.startswith("🔹"):
                    # Parse each mute count line
                    try:
                        count_str = line.split()[0]
                        count = int(count_str.strip("🔹 "))
                        swears_found += count
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
def process_media_file(file_path, media_type, title, output_prefix='clean_', dry_run=False,
                       temp_dir='', retain_clips=False, use_beep=False, beep_mode='words', 
                       boost_db=6, pre_buffer=100, post_buffer=100, bleeptool="S-M-FSM"):
    """
    Process a media file to censor profanity
    
    Args:
        file_path: Path to the media file
        media_type: Type of media ('show' or 'movie')
        title: Title of the media
        output_prefix: Prefix for the output file name
        dry_run: If True, will not actually make changes
        temp_dir: Directory to store temporary clips
        retain_clips: Whether to retain clips folder after processing
        use_beep: Use beep tone instead of muting
        beep_mode: Beep mode (words, segments, or both)
        boost_db: Audio boost level in dB for improved detection
        pre_buffer: Pre-mute buffer in milliseconds
        post_buffer: Post-mute buffer in milliseconds
        bleeptool: Passes to run (S-M-FSM, S-FSM, S-M, S)
        
    Returns:
        Dictionary with processing results
    """
    # Create a temporary Bleeparr instance with the provided settings
    bleeper = Bleeparr(
        output_prefix=output_prefix,
        temp_dir=temp_dir,
        retain_clips=retain_clips,
        use_beep=use_beep,
        beep_mode=beep_mode
    )
    
    # Process the file
    result = bleeper.process_file(
        file_path, 
        dry_run=dry_run,
        boost_db=boost_db,
        pre_buffer=pre_buffer,
        post_buffer=post_buffer,
        bleeptool=bleeptool
    )
    
    # Add additional info
    result['media_type'] = media_type
    result['title'] = title
    
    return result

def process_episode(episode_path, series_title, episode_info, output_prefix='clean_', dry_run=False,
                   temp_dir='', retain_clips=False, use_beep=False, beep_mode='words',
                   boost_db=6, pre_buffer=100, post_buffer=100, bleeptool="S-M-FSM"):
    """Process a TV episode file"""
    title = f"{series_title} - {episode_info}"
    return process_media_file(
        episode_path, 'show', title, output_prefix, dry_run,
        temp_dir, retain_clips, use_beep, beep_mode,
        boost_db, pre_buffer, post_buffer, bleeptool
    )

def process_movie(movie_path, movie_title, output_prefix='clean_', dry_run=False,
                 temp_dir='', retain_clips=False, use_beep=False, beep_mode='words',
                 boost_db=6, pre_buffer=100, post_buffer=100, bleeptool="S-M-FSM"):
    """Process a movie file"""
    return process_media_file(
        movie_path, 'movie', movie_title, output_prefix, dry_run,
        temp_dir, retain_clips, use_beep, beep_mode,
        boost_db, pre_buffer, post_buffer, bleeptool
    )

def clean_file(file_path, dry_run=False):
    """Legacy function for backward compatibility"""
    bleeper = Bleeparr()
    return bleeper.process_file(file_path, dry_run=dry_run)
