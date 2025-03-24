import requests
import subprocess
import os
import json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables from .env file
FB_GRAPH_API_KEY = os.getenv('FB_GRAPH_API_KEY')

OUTPUT_DIR = "output"

if not os.path.exists(OUTPUT_DIR):
  os.makedirs(OUTPUT_DIR)

if FB_GRAPH_API_KEY is None:
    raise ValueError("FB_GRAPH_API_KEY environment variable is not set")

def get_live_streams(after=None, total=0):
  url = f"https://graph.facebook.com/v22.0/me/live_videos?fields=video&limit=50&access_token={FB_GRAPH_API_KEY}"
  if not after is None:
    url += f"&after={after}"
  r = requests.get(url)
  r.raise_for_status() 

  data = r.json()
  found = len(data.get('data', []))
  total += found

  print(f"{'Found':<12} | {found} live streams (Total so far: {total})")

  if (data.get('data', []) != []):
    batch_get_live_streams_sources(data.get('data', []))

  after = data.get('paging', {}).get('cursors', {}).get('after')
  if after:
    return get_live_streams(after, total)
  
  return total

def get_file_extension(url):
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext if ext else ".mp4"

def batch_get_live_streams_sources(live_streams):
  batch = []

  print(f"{'Batching':<12} | {len(live_streams)} live streams")

  for live_stream in live_streams:
    request = {
      "method": "GET",
      "relative_url": f"{live_stream['video']['id']}?fields=id,description,source",
    }
    batch.append(request)
  
  r = requests.post(f"https://graph.facebook.com/me?batch={batch}&include_headers=false&access_token={FB_GRAPH_API_KEY}")
  r.raise_for_status() 

  data = r.json()

  download_tasks = []
  with ThreadPoolExecutor(max_workers=5) as executor:
    for response in data:
      if response['code'] != 200:
        print(f"{'Error':<12} | API Error: {response['code']} - {response['body']['error']['message']}")
      else:
        body = json.loads(response['body'])
        filename = sanitize_filename(body.get('description', body['id']))
        filename = sanitize_filename(f"{body.get('description', '')}_{body['id']}")
        ext = get_file_extension(body['source'])
        download_tasks.append(executor.submit(download_video, body['source'], filename, ext))

      for future in as_completed(download_tasks):
        try:
            future.result()
        except Exception as e:
          print(f"{'Error':<12} | Download Failed: {e}")

def sanitize_filename(name):
    return name.replace("/", "_").replace("\\", "_").replace(":", "_") \
               .replace("?", "_").replace("*", "_").replace("\"", "_").replace("<", "_") \
               .replace(">", "_").replace("|", "_").upper()

def download_video(source, filename, ext=".mp4"):
  output_path = f"{OUTPUT_DIR}/{filename}{ext}"

  print(f"{'Downloading':<12} | {filename}{ext}")

  r = requests.get(source, stream=True)
  r.raise_for_status()

  with open(output_path, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
      if chunk:
        f.write(chunk)
      
  print(f"{'Done':<12} | {filename}{ext}")

  compress_video(filename, ext)

def compress_video(filename, ext):
  print(f"{'Compressing':<12} | {filename}{ext}")

  output_path = f"{OUTPUT_DIR}/{filename}{ext}"
  compressed_path = f"{OUTPUT_DIR}/{filename}_compressed{ext}"

  try:
    subprocess.run(
      ["ffmpeg", "-i", output_path, "-vcodec", "libx264", "-crf", "35", compressed_path, "-loglevel", "error"],
      check=True
    )

    # Delete the original video
    os.remove(output_path)

    # Rename the compressed video to the original name
    os.rename(compressed_path, output_path)

    print(f"{'Compressed':<12} | {filename}{ext}")
  except:
    print(f"{'Error':<12} | Compression Failed: {filename}{ext}")
    return

if __name__ == "__main__":
  get_live_streams()