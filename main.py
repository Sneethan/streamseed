print("""
   _____ _                             _____               _ 
  / ____| |                           / ____|             | |
 | (___ | |_ _ __ ___  __ _ _ __ ___ | (___   ___  ___  __| |
  \___ \| __| '__/ _ \/ _` | '_ ` _ \ \___ \ / _ \/ _ \/ _` |
  ____) | |_| | |  __/ (_| | | | | | |____) |  __/  __/ (_| |
 |_____/ \__|_|  \___|\__,_|_| |_| |_|_____/ \___|\___|\__,_|
                                                             
                                                             
                                                           
                    --- By Sneethan (and Joshua) ---                                                           
""")

from supabase import create_client, Client
from datetime import datetime, timedelta
from colorama import Fore, Style, init
from dotenv import load_dotenv
from typing import Optional
import subprocess
import logging
import time
import pytz
import os

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
STREAM_URL = "https://playerservices.streamtheworld.com/api/livestream-redirect/7LTNAAC.aac"
OUTPUT_DIR = "recordings"
<<<<<<< Updated upstream
RECORDING_DURATION = 7200  # 2 hours (in seconds) (real time 7200)
FFMPEG_PATH = r"ffmpeg.exe"

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def check_ffmpeg_installed(ffmpeg_path: str) -> bool:
    """Check if ffmpeg is installed and accessible.

    Args:
        ffmpeg_path (str): The path to the ffmpeg executable.

    Returns:
        bool: True if ffmpeg is available, False otherwise.
    """
    try:
        subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True)
        return True
    except FileNotFoundError:
        log_error(f"ffmpeg not found at {ffmpeg_path}.")
        return False
    except subprocess.SubprocessError as e:
        log_error(f"Error checking ffmpeg: {e}")
        return False


=======
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
>>>>>>> Stashed changes

def record_stream() -> Optional[str]:
    """Record the MP3 stream.

    Returns:
        Optional[str]: Path to the recorded file or None if recording failed.
    """
    if not check_ffmpeg_installed(FFMPEG_PATH):
        log_error("ffmpeg is not installed or the path is incorrect.")
        return None

    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(OUTPUT_DIR, f"show_{timestamp}.mp3")

        command = [
            FFMPEG_PATH,
            "-i", STREAM_URL,
            "-t", str(RECORDING_DURATION),
            "-acodec", "libmp3lame",
            "-ab", "128k",
            output_file,
        ]

        log_info(f"Recording started: {output_file}")
        log_info(f"Executing command: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            log_error(f"Recording failed: {result.stderr}")
            return None

        log_info(f"Recording finished: {output_file}")
        return output_file
    except Exception as e:
        log_error(f"Error during recording: {e}")
        return None

<<<<<<< Updated upstream
import time

def upload_to_supabase(local_file: str, supabase_key: str) -> bool:
    """Upload a file to Supabase storage.

    Args:
        local_file (str): Path to the local file.
        supabase_key (str): The destination key (file name) in Supabase storage.

=======
def upload_to_s3(local_file: str, s3_key: str) -> bool:
    """Upload a file to Vultr Object Storage.
    
>>>>>>> Stashed changes
    Returns:
        bool: True if upload was successful, False otherwise.
    """
    try:
<<<<<<< Updated upstream
        if not supabase_key.lower().endswith(".mp3"):
            log_error(f"Invalid file extension for {local_file}. Expected .mp3.")
            return False

        log_info(f"Uploading {local_file} as {supabase_key}")

        if supabase_key == "archive/latest.mp3":
            existing_file = supabase.storage.from_("streamseed").get_public_url(supabase_key)
            log_info(f"Existing file URL: {existing_file}")
            
            if existing_file:
                log_info(f"File {supabase_key} already exists. Deleting and re-uploading.")
                delete_response = supabase.storage.from_("streamseed").remove([supabase_key])
                
                if delete_response and isinstance(delete_response, list) and len(delete_response) == 0:
                    log_error(f"Error deleting the existing file {supabase_key}: {delete_response}")
                    return False
                
                log_info(f"Successfully deleted {supabase_key}.")

            else:
                log_info(f"File {supabase_key} does not exist. Proceeding with upload.")

        time.sleep(5)  

        with open(local_file, "rb") as file:
            supabase.storage.from_("streamseed").upload(supabase_key, file)

        log_info(f"Uploaded {local_file} to Supabase as {supabase_key}")
=======
        with open(local_file, 'rb') as file:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=file,
                ACL='public-read'
            )
        log_info(f"Uploaded {local_file} to Vultr Object Storage as {s3_key}")
>>>>>>> Stashed changes
        return True


    except Exception as e:
        log_error(f"Error uploading {local_file}: {e}")
        return False

def upload_latest(local_file):
    """Upload the latest recording as 'latest.mp3'."""
    latest_key = "archive/latest.mp3"
    result = upload_to_supabase(local_file, latest_key)
    if result:return True
    else:return False

def cleanup_local_file(file_path: str) -> None:
    """Remove local file after successful upload."""
    try:
        os.remove(file_path)
        log_info(f"Cleaned up local file: {file_path}")
    except Exception as e:
        log_error(f"Error cleaning up {file_path}: {e}")

def epoch_until_10pm_sydney():
    utc_now = datetime.now(pytz.utc)

    sydney_tz = pytz.timezone('Australia/Sydney')
    sydney_now = utc_now.astimezone(sydney_tz)  

    sydney_10pm = sydney_now.replace(hour=22, minute=0, second=0, microsecond=0)

    if sydney_now >= sydney_10pm:
        sydney_10pm += timedelta(days=1)

    epoch_time = int(sydney_10pm.astimezone(pytz.utc).timestamp())

    return epoch_time

if __name__ == "__main__":
    while True:
        time_until = epoch_until_10pm_sydney()
        current_epoch_time = int(datetime.now(pytz.utc).timestamp())
        time_to_wait = time_until - current_epoch_time

        if time_to_wait > 0:
            print(f"Waiting for {time_to_wait} seconds until 10 PM Sydney time.")
            time.sleep(time_to_wait)  

        # Step 1: Record the stream
        recording_file = record_stream()
        if not recording_file:
            log_error("Recording failed, exiting.")
            exit(1)

        # Step 2: Upload to SupaBase
        recording_key = f"archive/{os.path.basename(recording_file)}"
        if upload_to_supabase(recording_file, recording_key):
            # Step 3: Update the "latest" recording
            if upload_latest(recording_file):
                # Step 4: Cleanup local file after successful upload
                cleanup_local_file(recording_file)

        print("Waiting for the next 10 PM...")
