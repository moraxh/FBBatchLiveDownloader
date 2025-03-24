import requests
import subprocess
import os
import json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Constants
OUTPUT_DIR = "output"
FB_GRAPH_API_URL = "https://graph.facebook.com/v22.0/"
FB_BATCH_API_URL = "https://graph.facebook.com/me"
CHUNK_SIZE = 8192
MAX_WORKERS = 5
FFMPEG_COMPRESSOR_PARAMS = ["-vcodec", "libx264", "-crf", "35", "-acodec", "aac", "-b:a", "96k", "-strict", "experimental", "-aac_coder", "fast"]

# Load API key
FB_GRAPH_API_KEY = os.getenv('FB_GRAPH_API_KEY')
if not FB_GRAPH_API_KEY:
  raise ValueError("FB_GRAPH_API_KEY environment variable is not set")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_live_streams(after_cursor=None, total=0):
  params = {
    "fields": "video,status",
    "limit": 50,
    "access_token": FB_GRAPH_API_KEY,
  }

  if after_cursor:
    params["after"] = after_cursor

  response = requests.get(f"{FB_GRAPH_API_URL}me/live_videos", params=params)
  response.raise_for_status()
  data = response.json()

  streams = data.get('data', [])

  # Filter current live streams
  streams = [stream for stream in streams if stream.get('status') != 'LIVE']

  total += len(streams)

  print(f"{'Found':<12} | {len(streams)} live streams (Total so far: {total})")

  if streams:
    process_live_streams(streams)

  after_cursor = data.get('paging', {}).get('cursors', {}).get('after')
  if after_cursor:
    fetch_live_streams(after_cursor, total)

def process_live_streams(live_streams):
  batch = [{"method": "GET", "relative_url": f"{stream['video']['id']}?fields=id,description,source"} for stream in live_streams]
  params = {
    "batch": json.dumps(batch),
    "include_headers": "false",
    "access_token": FB_GRAPH_API_KEY,
  }

  response = requests.post(FB_BATCH_API_URL, params)
  response.raise_for_status()
  data = response.json()

  with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(handle_video_response, resp) for resp in data if resp['code'] == 200]
    for future in as_completed(futures):
      future.result()

def handle_video_response(response):
  body = json.loads(response['body'])
  source = body.get('source')
  if not source:
    print(f"{'Skipping':<12} | Stream {body['id']} has no source")
    return
  
  filename = sanitize_filename(f"{body.get('description', '')}_{body['id']}")
  ext = get_file_extension(source)
  download_video(source, filename, ext)

def get_file_extension(url):
  return os.path.splitext(urlparse(url).path)[1] or ".mp4"

def sanitize_filename(name):
  return ''.join(c if c.isalnum() or c in "-_" else "" for c in name.replace(' ', '_')).upper().strip('_')

def download_video(url, filename, ext):
  output_path = os.path.join(OUTPUT_DIR, f"{filename}{ext}")

  print(f"{'Downloading':<12} | {filename}{ext}")
  response = requests.get(url, stream=True)
  response.raise_for_status()

  with open(output_path, 'wb') as file:
    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
      file.write(chunk)
  
  print(f"{'Downloaded':<12} | {filename}{ext}")
  compress_video(output_path)

def compress_video(input_path):
  compressed_path = input_path.replace(".mp4", "_compressed.mp4")

  if os.path.exists(compressed_path):
    os.remove(compressed_path)

  print(f"{'Compressing':<12} | {os.path.basename(input_path)}")
  try:
    subprocess.run(
      ["ffmpeg", "-i", input_path, *FFMPEG_COMPRESSOR_PARAMS, compressed_path, "-loglevel", "error"],
      check=True
    )
    os.remove(input_path)
    os.rename(compressed_path, input_path)
    print(f"{'Compressed':<12} | {os.path.basename(input_path)}")
  except subprocess.CalledProcessError as e:
    print(f"{'Error':<12} | Compression failed for {os.path.basename(input_path)}")  

if __name__ == "__main__":
  fetch_live_streams()