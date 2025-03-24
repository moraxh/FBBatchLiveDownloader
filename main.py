import aiohttp
import aiofiles
import asyncio
import subprocess
import ffmpeg
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

downloaded_count = 0
founded_count = 0

# Load API key
FB_GRAPH_API_KEY = os.getenv('FB_GRAPH_API_KEY')
if not FB_GRAPH_API_KEY:
    raise ValueError("FB_GRAPH_API_KEY environment variable is not set")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def fetch_live_streams(session, semaphore, after_cursor=None):
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
        await process_live_streams(session, semaphore, streams)
    
    after_cursor = data.get('paging', {}).get('cursors', {}).get('after')
    if after_cursor:
        await fetch_live_streams(session, semaphore, after_cursor)

async def process_live_streams(session, semaphore, live_streams):
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
            tasks.append(handle_video_response(session, semaphore, resp))
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

async def handle_video_response(session, semaphore, response):
    body = json.loads(response['body'])
    source = body.get('source')
    if not source:
        logger.warning(f"Skipping Stream {body['id']} (No source)")
        return
    
    filename = f"{sanitize_filename(body.get('description', ''))}_{body['id']}"
    ext = get_file_extension(source)
    
    async with semaphore:
        await download_video(session, source, filename, ext)

def get_file_extension(url):
    return os.path.splitext(urlparse(url).path)[1] or ".mp4"

def sanitize_filename(name):
    return ''.join(c if c.isalnum() or c in "-_" else "" for c in name.replace(' ', '_')).upper().strip('_')[:40]

async def download_video(session, url, filename, ext):
    global downloaded_count
    output_path = os.path.join(OUTPUT_DIR, f"{filename}{ext}")
    
    logger.info(f"Downloading {filename}{ext}")
    async with session.get(url) as response:
        response.raise_for_status()
        async with aiofiles.open(output_path, 'wb') as file:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                await file.write(chunk)
    
    downloaded_count += 1
    logger.info(f"\033[32m({downloaded_count}/{founded_count})\033[0m Downloaded {filename}{ext}")
    compress_video(output_path)

def compress_video(input_path):
    compressed_path = input_path.replace(".mp4", "_compressed.mp4")
    
    if os.path.exists(compressed_path):
        os.remove(compressed_path)
    
    logger.info(f"Compressing {os.path.basename(input_path)}")
    try:
      original_size = os.path.getsize(input_path)

      ffmpeg.input(input_path).output(
        compressed_path, vcodec='libx264', crf=35, acodec='aac', b='64k', loglevel='panic'
      ).run(overwrite_output=True)

      compressed_size = os.path.getsize(compressed_path)

      if original_size > compressed_size:
        os.remove(input_path)
        os.rename(compressed_path, input_path)
        logger.info(f"\033[36m({100-(compressed_size/original_size*100):.2f}%)\033[0m Compressed {os.path.basename(input_path)}")
      else:
        os.remove(compressed_path)
        logger.info(f"Compression not needed for {os.path.basename(input_path)}")
    except:
        logger.error(f"Compression failed for {os.path.basename(input_path)}")

async def main():
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    async with aiohttp.ClientSession() as session:
        await fetch_live_streams(session, semaphore)

if __name__ == "__main__":
    asyncio.run(main())