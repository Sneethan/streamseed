#!/usr/bin/env python3

# Import colorama first for the ASCII art
from colorama import Fore, Style, init
init(autoreset=True)

def print_banner():
    """Print the StreamSeed ASCII banner."""
    banner = f"""{Fore.CYAN}
   _____ _                             _____               _ 
  / ____| |                           / ____|             | |
 | (___ | |_ _ __ ___  __ _ _ __ ___ | (___   ___  ___  __| |
  \___ \| __| '__/ _ \/ _` | '_ ` _ \ \___ \ / _ \/ _ \/ _` |
  ____) | |_| | |  __/ (_| | | | | | |____) |  __/  __/ (_| |
 |_____/ \__|_|  \___|\__,_|_| |_| |_|_____/ \___|\___|\__,_|
                                                             
                                                             
{Fore.GREEN}                    --- By Sneethan and Joshua ---{Style.RESET_ALL}
"""
    print(banner)

# Rest of the imports
import subprocess
import datetime
import os
import boto3
import logging
from typing import Optional, Literal
from dotenv import load_dotenv
import schedule
import time
import pytz
import signal
from functools import wraps
import sys
import requests

# Print banner before setting up logging
print_banner()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Update Discord configuration with better defaults and validation
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
NOTIFICATION_LEVEL = os.getenv("NOTIFICATION_LEVEL", "error").lower()  # 'all', 'error', or 'none'
DISCORD_TIMEOUT = 5  # seconds

def send_discord_notification(
    message: str,
    level: Literal["info", "error", "success"] = "info",
    retry_count: int = 2
) -> bool:
    """
    Send notification to Discord webhook with improved error handling and retries.
    Returns True if notification was sent successfully, False otherwise.
    """
    # Early return if Discord notifications are disabled or webhook URL is not set
    if not DISCORD_WEBHOOK_URL or NOTIFICATION_LEVEL == "none":
        return False
    
    # Check notification level filtering
    if NOTIFICATION_LEVEL == "error" and level not in ["error", "success"]:
        return False

    colors = {
        "info": 3447003,     # Blue
        "error": 15158332,   # Red
        "success": 3066993   # Green
    }

    payload = {
        "embeds": [{
            "title": f"StreamSeed {level.title()} Notification",
            "description": message,
            "color": colors.get(level, colors["info"]),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "footer": {
                "text": f"StreamSeed Bot • {level.title()}"
            }
        }]
    }

    for attempt in range(retry_count + 1):
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=DISCORD_TIMEOUT
            )
            
            if response.status_code == 429:  # Rate limited
                retry_after = int(response.headers.get('Retry-After', 5))
                if attempt < retry_count:
                    time.sleep(retry_after)
                    continue
                    
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            if attempt == retry_count:
                logger.error(f"Discord notification timed out after {DISCORD_TIMEOUT}s")
            
        except requests.exceptions.RequestException as e:
            if attempt == retry_count:
                logger.error(f"Failed to send Discord notification: {str(e)}")
            
        except Exception as e:
            if attempt == retry_count:
                logger.error(f"Unexpected error sending Discord notification: {str(e)}")
            
        if attempt < retry_count:
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return False

# Update the logging functions with better formatting
def format_log_message(message: str, level: str) -> str:
    """Format log message with timestamp and level."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {level.upper()}: {message}"

def log_info(message: str):
    """Log info message with optional Discord notification."""
    formatted_msg = format_log_message(message, "info")
    logger.info(Fore.CYAN + formatted_msg)
    send_discord_notification(message, "info")

def log_error(message: str):
    """Log error message with Discord notification."""
    formatted_msg = format_log_message(message, "error")
    logger.error(Fore.RED + formatted_msg)
    send_discord_notification(message, "error", retry_count=3)  # More retries for errors

def log_success(message: str):
    """Log success message with Discord notification."""
    formatted_msg = format_log_message(message, "success")
    logger.info(Fore.GREEN + formatted_msg)
    send_discord_notification(message, "success")

# Add a function to test Discord notifications
def test_discord_notification() -> bool:
    """Test Discord webhook configuration."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured")
        return False
        
    test_message = "StreamSeed Discord notification test - If you see this, notifications are working!"
    if send_discord_notification(test_message, "info"):
        logger.info("Discord notification test successful")
        return True
    else:
        logger.error("Discord notification test failed")
        return False

# Load environment variables
load_dotenv()

# Configuration
STREAM_URL = "https://14533.live.streamtheworld.com/7LTNAAC_SC"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
RECORDING_DURATION = 7200  # 2 hours (in seconds)
BUCKET_NAME = os.getenv("BUCKET_NAME", "dnr")
VULTR_HOSTNAME = os.getenv("VULTR_HOSTNAME")  # e.g., "ewr1.vultrobjects.com"
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

# Updated S3 client configuration for Vultr
session = boto3.session.Session()
s3_client = session.client('s3',
    region_name=VULTR_HOSTNAME.split('.')[0] if VULTR_HOSTNAME else None,
    endpoint_url=f"https://{VULTR_HOSTNAME}" if VULTR_HOSTNAME else None,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# Update scheduling configuration - remove SCHEDULE_DAY since we only run on Wednesday
SYDNEY_TZ = pytz.timezone('Australia/Sydney')
SCHEDULE_TIME = '22:00'  # 10:00 PM Sydney time

# Add minimum file size threshold (e.g., 1MB)
MIN_FILE_SIZE = 1024 * 1024  # 1MB in bytes
MAX_UPLOAD_RETRIES = 3

def retry_decorator(max_retries=3, delay=5):
    """Decorator to retry functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    wait_time = delay * (2 ** attempt)
                    log_error(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

def verify_recording(file_path: str) -> bool:
    """Verify the recording meets minimum requirements."""
    try:
        if not os.path.exists(file_path):
            log_error(f"Recording file not found: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        if file_size < MIN_FILE_SIZE:
            log_error(f"Recording file too small ({file_size} bytes): {file_path}")
            return False
            
        return True
    except Exception as e:
        log_error(f"Error verifying recording: {e}")
        return False

@retry_decorator(max_retries=MAX_UPLOAD_RETRIES)
def upload_to_s3(local_file: str, s3_key: str) -> bool:
    """Upload a file to Vultr Object Storage with retries."""
    try:
        with open(local_file, 'rb') as file:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=file,
                ACL='public-read'
            )
        log_info(f"Uploaded {local_file} to Vultr Object Storage as {s3_key}")
        return True
    except Exception as e:
        log_error(f"Error uploading {local_file}: {e}")
        return False

def upload_latest(local_file):
    """Upload the latest recording as 'latest.mp3'."""
    latest_key = "latest.mp3"
    upload_to_s3(local_file, latest_key)

def cleanup_local_file(file_path: str) -> None:
    """Remove local file after successful upload."""
    try:
        os.remove(file_path)
        log_info(f"Cleaned up local file: {file_path}")
    except Exception as e:
        log_error(f"Error cleaning up {file_path}: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    log_info("Shutdown signal received. Cleaning up...")
    # Add any cleanup code here
    sys.exit(0)

def record_stream() -> Optional[str]:
    """Record the MP3 stream."""
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(OUTPUT_DIR, f"show_{timestamp}.mp3")

        command = [
            "ffmpeg",
            "-i", STREAM_URL,
            "-t", str(RECORDING_DURATION),
            "-acodec", "libmp3lame",
            "-ab", "128k",
            output_file,
        ]

        log_info(f"Recording started: {output_file}")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            log_error(f"Recording failed: {result.stderr}")
            return None
            
        log_info(f"Recording finished: {output_file}")
        return output_file
    except Exception as e:
        log_error(f"Error during recording: {e}")
        return None

# Add executable check for ffmpeg
def check_ffmpeg():
    """Check if ffmpeg is installed and accessible."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode != 0:
            raise Exception("FFmpeg check failed")
        return True
    except Exception as e:
        log_error(f"FFmpeg not found or not accessible: {e}")
        return False

def main():
    """Main function that handles recording and uploading."""
    # Test Discord notifications on startup
    test_discord_notification()
    
    # Add FFmpeg check
    if not check_ffmpeg():
        log_error("FFmpeg is required but not found. Please install FFmpeg.")
        return
        
    log_info("Starting new recording session...")
    
    # Step 1: Record the stream
    recording_file = record_stream()
    if not recording_file:
        log_error("Recording failed, exiting.")
        return

    # Step 2: Verify recording
    if not verify_recording(recording_file):
        log_error("Recording verification failed, exiting.")
        cleanup_local_file(recording_file)
        return

    # Step 3: Upload to S3
    recording_key = f"archive/{os.path.basename(recording_file)}"
    if upload_to_s3(recording_file, recording_key):
        # Step 4: Update the "latest" recording
        if upload_latest(recording_file):
            log_success(f"Successfully recorded and uploaded {recording_key}")
            # Step 5: Cleanup local file after successful upload
            cleanup_local_file(recording_file)

if __name__ == "__main__":
    # Print banner on startup
    print_banner()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create today's date in Sydney timezone with the scheduled time
    now = datetime.datetime.now(SYDNEY_TZ)
    schedule_time_parts = SCHEDULE_TIME.split(':')
    schedule_time_sydney = now.replace(
        hour=int(schedule_time_parts[0]),
        minute=int(schedule_time_parts[1]),
        second=0,
        microsecond=0
    )

    # Schedule only for Wednesday
    schedule.every().wednesday.at(SCHEDULE_TIME).do(main)

    log_info(f"Scheduler set for every Wednesday at {SCHEDULE_TIME} Sydney time")

    try:
        # Keep the script running
        while True:
            now = datetime.datetime.now(SYDNEY_TZ)
            schedule_today = now.replace(
                hour=int(schedule_time_parts[0]),
                minute=int(schedule_time_parts[1]),
                second=0,
                microsecond=0
            )
            
            time_diff = abs((now - schedule_today).total_seconds() / 60)  # difference in minutes
            
            # Check if we should run now
            if time_diff < 1 and now.strftime('%H:%M') == SCHEDULE_TIME and now.strftime('%A').lower() == 'wednesday':
                log_info("Schedule time reached, running job now...")
                main()
            
            schedule.run_pending()
            time.sleep(60)  # Check schedule every minute
    except Exception as e:
        log_error(f"Scheduler error: {e}")
        sys.exit(1)
