"""
   _____ _                             _____               _ 
  / ____| |                           / ____|             | |
 | (___ | |_ _ __ ___  __ _ _ __ ___ | (___   ___  ___  __| |
  \___ \| __| '__/ _ \/ _` | '_ ` _ \ \___ \ / _ \/ _ \/ _` |
  ____) | |_| | |  __/ (_| | | | | | |____) |  __/  __/ (_| |
 |_____/ \__|_|  \___|\__,_|_| |_| |_|_____/ \___|\___|\__,_|
                                                             
                                                             
                                                           
                    --- By Sneethan and Joshua ---                                                           
"""

from colorama import Fore, Style, init
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

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add Discord configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
NOTIFICATION_LEVEL = os.getenv("NOTIFICATION_LEVEL", "error")  # 'all', 'error', or 'none'

def send_discord_notification(
    message: str,
    level: Literal["info", "error", "success"] = "info"
) -> bool:
    """Send notification to Discord webhook."""
    if not DISCORD_WEBHOOK_URL or NOTIFICATION_LEVEL == "none":
        return False
    
    if NOTIFICATION_LEVEL == "error" and level == "info":
        return False

    colors = {
        "info": 3447003,     # Blue
        "error": 15158332,   # Red
        "success": 3066993   # Green
    }

    try:
        payload = {
            "embeds": [{
                "title": f"StreamSeed {level.title()} Notification",
                "description": message,
                "color": colors[level],
                "timestamp": datetime.datetime.utcnow().isoformat()
            }]
        }
        
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        log_error(f"Failed to send Discord notification: {e}")
        return False

# Update the logging functions to include Discord notifications
def log_info(message: str):
    logger.info(Fore.GREEN + message)
    send_discord_notification(message, "info")

def log_error(message: str):
    logger.error(Fore.RED + message)
    send_discord_notification(message, "error")

def log_success(message: str):
    logger.info(Fore.GREEN + message)
    send_discord_notification(message, "success")

# Load environment variables
load_dotenv()

# Configuration
STREAM_URL = "https://14533.live.streamtheworld.com/7LTNAAC_SC"
OUTPUT_DIR = "recordings"
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

# Add scheduling configuration
SYDNEY_TZ = pytz.timezone('Australia/Sydney')
SCHEDULE_DAY = 'wednesday'
SCHEDULE_TIME = '22:00'  # 10:07 AM Sydney time

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

def main():
    """Main function that handles recording and uploading."""
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

    # Schedule the job using Sydney time directly
    if SCHEDULE_DAY.lower() == 'saturday':
        schedule.every().saturday.at(SCHEDULE_TIME).do(main)
    elif SCHEDULE_DAY.lower() == 'wednesday':
        schedule.every().wednesday.at(SCHEDULE_TIME).do(main)

    log_info(f"Scheduler set for every {SCHEDULE_DAY} at {SCHEDULE_TIME} Sydney time")

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
            log_info(f"Current time (Sydney): {now.strftime('%H:%M')}")
            
            # Check if we should run now
            if time_diff < 1 and now.strftime('%H:%M') == SCHEDULE_TIME:
                log_info("Schedule time reached, running job now...")
                main()
            
            schedule.run_pending()
            time.sleep(60)  # Check schedule every minute
    except Exception as e:
        log_error(f"Scheduler error: {e}")
        sys.exit(1)
