# Facebook Batch Live Video Downloader

A Python tool to download and process Facebook live videos in batch mode using the Facebook Graph API.

## Features
- Batch download of Facebook live videos
- Automatic video compression using FFmpeg
- Concurrent downloads with configurable worker count
- Duplicate video detection
- Progress tracking and logging
- CSV-based video metadata storage

## Requirements
- Python 3.9+
- Facebook Graph API access token
- FFmpeg installed

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/FBBatchLiveDownloader.git
   cd FBBatchLiveDownloader
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file with your Facebook Graph API key:
   ```
   FB_GRAPH_API_KEY=your_api_key_here
   ```

## Usage
Run the downloader:
```bash
python main.py
```

## Configuration
You can modify the following constants in `main.py`:
- `MAX_WORKERS_DOWNLOAD`: Number of concurrent downloads (default: 5)
- `MAX_WORKERS_COMPRESS`: Number of concurrent compression jobs (default: 5)
- `STOP_ON_FOUNDED_DOWNLOADED_VIDEOS`: Stop when encountering already downloaded videos (default: False)

## File Structure
```
FBBatchLiveDownloader/
├── data/
│   ├── output/          # Downloaded videos
│   └── videos.csv       # Video metadata
├── main.py              # Main application
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose configuration
└── README.md            # This file
```

## Docker Support
You can run the application in a Docker container:

1. Build the image:
   ```bash
   docker-compose build
   ```

2. Run the container:
   ```bash
   docker-compose up
   ```

## Logging
The application uses colored logs with the following format:
```
[HH:MM:SS AM/PM] [LEVEL] Message
```

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
