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
from typing import Optional
from dotenv import load_dotenv

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def log_info(message: str):
    logger.info(Fore.GREEN + message)

def log_error(message: str):
    logger.error(Fore.RED + message)

# Load environment variables
load_dotenv()

# Configuration
STREAM_URL = "https://14533.live.streamtheworld.com/7LTNAAC_SC"
OUTPUT_DIR = "recordings"
RECORDING_DURATION = 120  # 2 hours (in seconds)
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

def record_stream() -> Optional[str]:
    """Record the MP3 stream.
    
    Returns:
        Optional[str]: Path to the recorded file or None if recording failed
    """
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

def upload_to_s3(local_file: str, s3_key: str) -> bool:
    """Upload a file to Vultr Object Storage.
    
    Returns:
        bool: True if upload was successful, False otherwise
    """
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

if __name__ == "__main__":
    # Step 1: Record the stream
    recording_file = record_stream()
    if not recording_file:
        log_error("Recording failed, exiting.")
        exit(1)

    # Step 2: Upload to S3
    recording_key = f"archive/{os.path.basename(recording_file)}"
    if upload_to_s3(recording_file, recording_key):
        # Step 3: Update the "latest" recording
        if upload_latest(recording_file):
            # Step 4: Cleanup local file after successful upload
            cleanup_local_file(recording_file)
