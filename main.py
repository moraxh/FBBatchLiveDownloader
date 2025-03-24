import aiohttp
import asyncio
import subprocess
import os
import json
import logging
import coloredlogs
from urllib.parse import urlparse

# Configure coloredlogs
logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger, fmt='%(asctime)s [%(levelname)s] %(message)s', datefmt='%I:%M:%S %p', isatty=True)

# Constants
OUTPUT_DIR = "output"
FB_GRAPH_API_URL = "https://graph.facebook.com/v22.0/"
FB_BATCH_API_URL = "https://graph.facebook.com/me"
CHUNK_SIZE = 8192
MAX_WORKERS = 10
FFMPEG_COMPRESSOR_PARAMS = ["-vcodec", "libx264", "-crf", "35", "-acodec", "aac", "-b:a", "96k", "-strict", "experimental", "-aac_coder", "fast"]

downloaded_count = 0
founded_count = 0

# Load API key
FB_GRAPH_API_KEY = os.getenv('FB_GRAPH_API_KEY')
if not FB_GRAPH_API_KEY:
    raise ValueError("FB_GRAPH_API_KEY environment variable is not set")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Create an aiohttp session
session = None

async def fetch_live_streams(after_cursor=None):
    global founded_count
    params = {
        "fields": "video,status",
        "limit": 50,
        "access_token": FB_GRAPH_API_KEY,
    }
    
    if after_cursor:
        params["after"] = after_cursor
    
    async with session.get(f"{FB_GRAPH_API_URL}me/live_videos", params=params) as response:
        response.raise_for_status()
        data = await response.json()
    
    streams = data.get('data', [])
    streams = [stream for stream in streams if stream.get('status') != 'LIVE']
    founded_count += len(streams)
    
    logger.info(f"Found {len(streams)} live streams (Total so far: {founded_count})")
    
    if streams:
        await process_live_streams(streams)
    
    after_cursor = data.get('paging', {}).get('cursors', {}).get('after')
    if after_cursor:
        await fetch_live_streams(after_cursor)

async def process_live_streams(live_streams):
    batch = [{"method": "GET", "relative_url": f"{stream['video']['id']}?fields=id,description,source"} for stream in live_streams]
    params = {
        "batch": json.dumps(batch),
        "include_headers": "false",
        "access_token": FB_GRAPH_API_KEY,
    }
    
    async with session.post(FB_BATCH_API_URL, params=params) as response:
        response.raise_for_status()
        data = await response.json()
    
    tasks = []
    for resp in data:
        if resp['code'] == 200:
            tasks.append(handle_video_response(resp))
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

async def handle_video_response(response):
    body = json.loads(response['body'])
    source = body.get('source')
    if not source:
        logger.warning(f"Skipping Stream {body['id']} (No source)")
        return
    
    filename = f"{sanitize_filename(body.get('description', ''))}_{body['id']}"
    ext = get_file_extension(source)
    await download_video(source, filename, ext)

def get_file_extension(url):
    return os.path.splitext(urlparse(url).path)[1] or ".mp4"

def sanitize_filename(name):
    return ''.join(c if c.isalnum() or c in "-_" else "" for c in name.replace(' ', '_')).upper().strip('_')[:40]

async def download_video(url, filename, ext):
    global downloaded_count
    output_path = os.path.join(OUTPUT_DIR, f"{filename}{ext}")
    
    logger.info(f"Downloading {filename}{ext}")
    async with session.get(url) as response:
        response.raise_for_status()
        with open(output_path, 'wb') as file:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                file.write(chunk)
    
    downloaded_count += 1
    logger.info(f"({downloaded_count}/{founded_count}) Downloaded {filename}{ext}")
    # compress_video(output_path)

def compress_video(input_path):
    compressed_path = input_path.replace(".mp4", "_compressed.mp4")
    
    if os.path.exists(compressed_path):
        os.remove(compressed_path)
    
    logger.info(f"Compressing {os.path.basename(input_path)}")
    try:
        subprocess.run(
            ["ffmpeg", "-i", input_path, *FFMPEG_COMPRESSOR_PARAMS, compressed_path, "-loglevel", "error"],
            check=True
        )
        os.remove(input_path)
        os.rename(compressed_path, input_path)
        logger.info(f"Compressed {os.path.basename(input_path)}")
    except subprocess.CalledProcessError:
        logger.error(f"Compression failed for {os.path.basename(input_path)}")

async def main():
    global session
    # Create a session for asynchronous HTTP requests
    async with aiohttp.ClientSession() as session:
        await fetch_live_streams()

if __name__ == "__main__":
    asyncio.run(main())
