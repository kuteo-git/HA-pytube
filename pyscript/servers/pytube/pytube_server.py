import os
import re
import json
import glob
from flask import Flask, jsonify, send_file, request
from pytubefix import YouTube, Playlist
from pytubefix.cli import on_progress
import yt_dlp
import logging
import time
import random
from urllib.parse import parse_qs, urlparse

# Flask app setup
app = Flask(__name__)

# Configuration
folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
HOST = '0.0.0.0'  # Allow external access
PORT = 114
MAX_RETRIES = 1

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_directory_exists(path):
    """Create directory if it doesn't exist"""
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            # logger.info(f"Created directory: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {str(e)}")
        return False


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    # Remove or replace invalid characters for filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space and strip
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


def get_device_token_path(device):
    """Get the token file path for a specific device"""
    tokens_dir = "./tokens"
    ensure_directory_exists(tokens_dir)
    return os.path.join(tokens_dir, f"{device}.json")


def extract_playlist_id(url):
    """Extract playlist ID from YouTube playlist URL"""
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'list' in query_params:
            return query_params['list'][0]
        return None
    except Exception:
        return None


def get_playlist_cache_path(playlist_id):
    """Get cache file path for playlist"""
    return os.path.join(folder_path, f"playlist_{playlist_id}.json")


def save_playlist_cache(playlist_id, data):
    """Save playlist data to cache"""
    try:
        cache_path = get_playlist_cache_path(playlist_id)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved playlist cache: {cache_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save playlist cache: {str(e)}")
        return False


def load_playlist_cache(playlist_id):
    """Load playlist data from cache"""
    try:
        cache_path = get_playlist_cache_path(playlist_id)
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded playlist from cache: {cache_path}")
            return data
        return None
    except Exception as e:
        logger.error(f"Failed to load playlist cache: {str(e)}")
        return None


def get_video_metadata_cache_path(video_id, title):
    """Get cache file path for video metadata"""
    sanitized_title = sanitize_filename(title)
    return os.path.join(folder_path, f"{sanitized_title}_{video_id}.json")


def save_video_metadata_cache(video_id, title, metadata):
    """Save video metadata to cache"""
    try:
        cache_path = get_video_metadata_cache_path(video_id, title)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved video metadata cache: {cache_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save video metadata cache: {str(e)}")
        return False


def load_video_metadata_cache(cache_path):
    """Load video metadata from cache"""
    if cache_path is None:
        return None

    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded video metadata from cache: {cache_path}")
            return data
        return None
    except Exception as e:
        logger.error(f"Failed to load video metadata cache: {str(e)}")
        return None

def find_cached_metadata_file(video_id):
    """Find cached MP3 file by video_id using glob pattern"""
    try:
        pattern = os.path.join(folder_path, f"*_{video_id}.json")
        matches = glob.glob(pattern)
        if matches:
            # Return the first match (should only be one)
            return matches[0]
        return None
    except Exception as e:
        logger.error(f"Failed to find cached MP3 file: {str(e)}")
        return None

def find_cached_mp3_file(video_id):
    """Find cached MP3 file by video_id using glob pattern"""
    try:
        pattern = os.path.join(folder_path, f"*_{video_id}.mp3")
        matches = glob.glob(pattern)
        if matches:
            # Return the first match (should only be one)
            return matches[0]
        return None
    except Exception as e:
        logger.error(f"Failed to find cached MP3 file: {str(e)}")
        return None


def create_youtube_object_with_retry(video_url, max_retries=MAX_RETRIES, device=None):
    """
    Create YouTube object with retry logic and exponential backoff
    Returns YouTube object or None if all attempts fail
    """
    for attempt in range(max_retries):
        try:
            # Add some randomization to avoid thundering herd
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0, 1)
                # logger.info(f"Retrying YouTube object creation after "
                #             f"{delay:.2f}s (attempt {attempt + 1}/"
                #             f"{max_retries})")
                time.sleep(delay)
            
            if device:
                # V2 API with device-specific token
                token_file = get_device_token_path(device)
                yt = YouTube(
                    video_url,
                    # use_oauth=False,
                    # allow_oauth_cache=True,
                    # token_file=token_file,
                    on_progress_callback=on_progress
                )
            else:
                # V1 API (original)
                yt = YouTube(
                    video_url,
                    use_oauth=True,
                    allow_oauth_cache=True,
                    on_progress_callback=on_progress
                )
            
            # Test that the object is actually accessible
            # _ = yt.title  # This will trigger the API call
            return yt
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for "
                           f"{video_url}: {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} attempts failed for "
                             f"{video_url}")
                return None
    return YouTube(video_url, on_progress_callback=on_progress)

def download_audio_with_ytdlp(video_id):
    """Download audio using yt-dlp and get info in single call"""
    youtube_url = f"https://youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        # Try m4a format which doesn't need conversion
        'format': '140/bestaudio',
        'outtmpl': os.path.join(folder_path, '%(title)s_%(id)s.mp3'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # External downloader
        'external_downloader': 'aria2c',
        'downloader_args': {
            'aria2c': [
                '-x', '16',
                '-s', '16',
                '-k', '1M',
            ],
        },
        # Cookie
        'cookiefile': 'cookies.txt'
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        cached_mp3_file = find_cached_mp3_file(video_id)
        if cached_mp3_file and os.path.exists(cached_mp3_file):
            return cached_mp3_file, info
        else:
            raise Exception("Downloaded file not found at expected location")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'YouTube Downloader API',
        'cache_directory': folder_path,
        'directory_exists': os.path.exists(folder_path)
    })


@app.route('/', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        'service': 'YouTube Downloader API',
        'version': '2.0.0',
        'endpoints': {
            'GET /': 'API information',
            'GET /health': 'Health check',
            'GET /v2/playlist?url=<playlist_url>&device=<device_id>': (
                'Get simplified playlist info with smart caching'
            ),
            'GET /v2/video/<video_id>?device=<device_id>': (
                'Get video information with mp3_url if cached'
            ),
            'GET /v2/mp3/<video_id>?device=<device_id>': (
                'Serve cached MP3 file directly'
            )
        },
        'cache_directory': folder_path,
        'tokens_directory': './tokens'
    })


# ================= V2 API ENDPOINTS =================

@app.route('/v2/playlist', methods=['GET'])
def get_playlist_videos_v2():
    """
    V2: Get videos from a YouTube playlist with device-specific tokens
    Expected query parameters: url (YouTube playlist URL), device (device identifier)
    Returns: JSON array with simplified video information and caching
    """
    try:
        playlist_url = request.args.get('url')
        device = request.args.get('device')
        
        if not playlist_url:
            return jsonify({
                'error': 'Missing required parameter: url',
                'message': 'Please provide a YouTube playlist URL'
            }), 400
            
        if not device:
            return jsonify({
                'error': 'Missing required parameter: device',
                'message': 'Please provide a device identifier'
            }), 400

        # Extract playlist ID for caching
        playlist_id = extract_playlist_id(playlist_url)
        if not playlist_id:
            return jsonify({
                'error': 'Invalid playlist URL',
                'message': 'Could not extract playlist ID from URL'
            }), 400

        # Ensure cache directory exists
        if not ensure_directory_exists(folder_path):
            logger.warning(f"Could not create cache directory: {folder_path}")

        logger.info(
            f"Processing playlist (v2): {playlist_url} for device: {device}"
        )

        try:
            # Always try to get playlist from YouTube API first
            playlist = Playlist(playlist_url)
            video_urls = playlist.video_urls

            if not video_urls:
                # If no videos found, try to return cached data
                cached_data = load_playlist_cache(playlist_id)
                if cached_data:
                    logger.info(
                        f"No videos found in API, returning cached data for {playlist_id}"
                    )
                    return jsonify(cached_data)
                
                return jsonify({
                    'error': 'No videos found',
                    'message': (
                        'The playlist appears to be empty or inaccessible'
                    )
                }), 404

            # Build response data
            videos_info = []
            for video_url in video_urls:
                video_id = video_url.split('watch?v=')[-1].split('&')[0]
                video_info = {
                    "video_url": video_url,
                    "video_id": video_id
                }
                videos_info.append(video_info)

            # Save successful results to cache
            save_playlist_cache(playlist_id, videos_info)
            logger.info(
                f"Successfully processed {len(videos_info)} videos (v2)"
            )

            return jsonify(videos_info)

        except Exception as e:
            logger.error(f"Error processing playlist: {str(e)}")
            # Only if API fails, try to return cached data
            cached_data = load_playlist_cache(playlist_id)
            if cached_data:
                logger.info(
                    f"API failed, returning cached data for {playlist_id}: {str(e)}"
                )
                return jsonify(cached_data)
            
            return jsonify({
                'error': 'Failed to process playlist',
                'message': str(e)
            }), 500

    except Exception as e:
        logger.error(f"Error in v2 playlist endpoint: {str(e)}")
        return jsonify({
            'error': 'Failed to process playlist',
            'message': str(e)
        }), 500


@app.route('/v2/video/<video_id>', methods=['GET'])
def get_video_info_v2(video_id):
    """
    V2: Get video information by video ID with device-specific tokens
    Expected query parameter: device (device identifier)
    Returns: JSON with video information
    """
    try:
        device = request.args.get('device')
        
        if not device:
            return jsonify({
                'error': 'Missing required parameter: device',
                'message': 'Please provide a device identifier'
            }), 400

        logger.info(f"Processing video info (v2): {video_id} for device: {device}")

        # Create YouTube object with device-specific token
        youtube_url = f"https://youtube.com/watch?v={video_id}"

        # Check if MP3 file already exists in cache
        cached_mp3_file = find_cached_mp3_file(video_id)
        
        if cached_mp3_file and os.path.exists(cached_mp3_file):
            mp3_url = f"/v2/mp3/{video_id}?device={device}"
            # Load metadata
            cached_meta_data_path = find_cached_metadata_file(video_id)
            cached_meta_data = load_video_metadata_cache(cached_meta_data_path)
            if not cached_meta_data:
                cached_meta_data = {
                        "video_title": "",
                        "video_thumbnail_url": "",
                        "video_id": video_id,
                        "video_url": youtube_url,
                        "video_duration": "0",
                        "mp3_url": mp3_url
                    }
                
            # logger.info(f"Returning cached MP3 info (v2): {cached_meta_data.get("video_title", "")}. Metadata: {cached_meta_data}")
                        
            # File exists, return info with mp3_url
            video_info = {
                "video_title": cached_meta_data.get("video_title", ""),
                "video_thumbnail_url": cached_meta_data["video_thumbnail_url"],
                "video_id": video_id,
                "video_url": youtube_url,
                "video_duration": cached_meta_data["video_duration"],
                "mp3_url": mp3_url,
                "is_loaded_from_cache": True
            }
            return jsonify(video_info)
        
        # File doesn't exist, download it
        logger.info(f"MP3 not cached, downloading (v2): {video_id}")
        
        # Create YouTube object with device-specific token
        yt = create_youtube_object_with_retry(youtube_url, max_retries=MAX_RETRIES, device=device)
        if not yt:
            return jsonify({
                'error': 'Video unavailable',
                'message': f'Could not access video {video_id}. The video may be private, deleted, or temporarily unavailable.',
                'video_id': video_id
            }), 404
        
        # Ensure download directory exists
        if not ensure_directory_exists(folder_path):
            return jsonify({
                'error': 'Directory creation failed',
                'message': f'Could not create or access directory: {folder_path}'
            }), 500

        # Download audio stream with retry logic
        audio_stream = None
        max_retries = MAX_RETRIES
        try:
            audio_stream = yt.streams.get_audio_only()
        except Exception as e:
            logger.warning(
                f"failed: {str(e)}"
            )
            return jsonify({
                'error': 'Download failed',
                'message': (
                    f'Failed to get audio stream for video {video_id} '
                    f'after {max_retries} attempts: {str(e)}'
                ),
                'video_id': video_id
            }), 500

        # Download the file with retry logic
        sanitized_title = sanitize_filename(yt.title)
        temp_filename = f"{sanitized_title}_{video_id}.mp4"
        
        downloaded_file = None
        try:
            downloaded_file = audio_stream.download(
                output_path=folder_path,
                filename=temp_filename
            )
        except Exception as e:
            logger.warning(
                f"failed: {str(e)}"
            )
            return jsonify({
                'error': 'Download failed',
                'message': (
                    f'Failed to download video {video_id} '
                    f'after {max_retries} attempts: {str(e)}'
                ),
                'video_id': video_id
            }), 500

        # Rename to .mp3 extension
        mp3_filepath = downloaded_file.replace('.mp4', '.mp3')
        if downloaded_file != mp3_filepath:
            os.rename(downloaded_file, mp3_filepath)

        # Prepare metadata for caching
        metadata = {
            "video_title": yt.title,
            "video_thumbnail_url": yt.thumbnail_url,
            "video_id": video_id,
            "video_url": youtube_url,
            "video_duration": yt.length,
            "mp3_url": mp3_filepath
        }

        # Save metadata to cache
        save_video_metadata_cache(video_id, yt.title, metadata)

        # Return video info with mp3_url
        mp3_url = f"/v2/mp3/{video_id}?device={device}"
        video_info = {
            "video_title": yt.title,
            "video_thumbnail_url": yt.thumbnail_url,
            "video_id": video_id,
            "video_url": youtube_url,
            "video_duration": yt.length,
            "mp3_url": mp3_url,
            "is_loaded_from_cache": False
        }

        logger.info(f"Successfully downloaded and cached (v2): {yt.title}")
        return jsonify(video_info)

    except Exception as e:
        logger.error(f"Error getting video info (v2) for {video_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to get video information',
            'message': str(e),
            'video_id': video_id
        }), 500

  
@app.route('/v3/video/<video_id>', methods=['GET'])
def get_video_info_v3(video_id):
    """
    V3: Get video information by video ID with device-specific tokens using yt-dlp
    Expected query parameter: device (device identifier)
    Returns: JSON with video information
    """
    try:
        device = request.args.get('device')
        
        if not device:
            return jsonify({
                'error': 'Missing required parameter: device',
                'message': 'Please provide a device identifier'
            }), 400

        logger.info(f"Processing video info (v3): {video_id} for device: {device}")

        # Create YouTube URL
        youtube_url = f"https://youtube.com/watch?v={video_id}"

        # Ensure download directory exists
        if not ensure_directory_exists(folder_path):
            return jsonify({
                'error': 'Directory creation failed',
                'message': f'Could not create or access directory: {folder_path}'
            }), 500

        # Check if MP3 file already exists in cache
        cached_mp3_file = find_cached_mp3_file(video_id)
        
        if cached_mp3_file and os.path.exists(cached_mp3_file):
            mp3_url = f"/v3/mp3/{video_id}?device={device}"
            
            # Load metadata
            cached_meta_data_path = find_cached_metadata_file(video_id)
            cached_meta_data = load_video_metadata_cache(cached_meta_data_path)
            
            if not cached_meta_data:
                # If metadata doesn't exist, create minimal metadata
                cached_meta_data = {
                    "video_title": "",
                    "video_thumbnail_url": "",
                    "video_id": video_id,
                    "video_url": youtube_url,
                    "video_duration": "0",
                    "mp3_url": mp3_url
                }
                
            logger.info(f"Returning cached MP3 info (v3): {cached_meta_data.get('video_title', 'Unknown')}. Metadata: {cached_meta_data}")
                        
            # File exists, return info with mp3_url
            video_info = {
                "video_title": cached_meta_data.get("video_title", ""),
                "video_thumbnail_url": cached_meta_data.get("video_thumbnail_url", ""),
                "video_id": video_id,
                "video_url": youtube_url,
                "video_duration": str(cached_meta_data.get("video_duration", "0")),
                "mp3_url": mp3_url,
                "is_loaded_from_cache": True
            }
            return jsonify(video_info)
        
        # File doesn't exist, download it
        logger.info(f"MP3 not cached, downloading (v3): {video_id}")
        
        # Download the audio file
        try:
            downloaded_file, video_info_data = download_audio_with_ytdlp(video_id)
            
        except Exception as e:
            logger.error(f"Download failed for {video_id}: {str(e)}")
            return jsonify({
                'error': 'Download failed',
                'message': f'Failed to download video {video_id}: {str(e)}',
                'video_id': video_id
            }), 500

        # Extract video information
        video_title = video_info_data.get('title', 'Unknown')
        video_duration = video_info_data.get('duration', 0)
        video_thumbnail_url = video_info_data.get('thumbnail', '')

        # Prepare metadata for caching
        metadata = {
            "video_title": video_title,
            "video_thumbnail_url": video_thumbnail_url,
            "video_id": video_id,
            "video_url": youtube_url,
            "video_duration": video_duration,
            "mp3_url": downloaded_file
        }

        # Save metadata to cache
        save_video_metadata_cache(video_id, video_title, metadata)

        # Return video info with mp3_url
        mp3_url = f"/v3/mp3/{video_id}?device={device}"
        video_info = {
            "video_title": video_title,
            "video_thumbnail_url": video_thumbnail_url,
            "video_id": video_id,
            "video_url": youtube_url,
            "video_duration": str(video_duration),
            "mp3_url": mp3_url,
            "is_loaded_from_cache": False
        }

        logger.info(f"Successfully downloaded and cached (v3): {video_title}")
        return jsonify(video_info)

    except Exception as e:
        logger.error(f"Error getting video info (v3) for {video_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to get video information',
            'message': str(e),
            'video_id': video_id
        }), 500


@app.route('/v2/mp3/<video_id>', methods=['GET'])
def serve_mp3_v2(video_id):
    """
    V2: Serve cached MP3 file by video_id
    Expected query parameter: device (device identifier)
    Returns: MP3 file or 404 if not cached
    """
    try:
        device = request.args.get('device')
        
        if not device:
            return jsonify({
                'error': 'Missing required parameter: device',
                'message': 'Please provide a device identifier'
            }), 400

        # Find cached MP3 file
        cached_mp3_file = find_cached_mp3_file(video_id)
        
        if not cached_mp3_file or not os.path.exists(cached_mp3_file):
            return jsonify({
                'error': 'MP3 not found',
                'message': f'No cached MP3 file found for video {video_id}',
                'video_id': video_id
            }), 404

        # Extract filename for download
        filename = os.path.basename(cached_mp3_file)
        
        logger.info(f"Serving cached MP3 (v2): {filename}")
        
        return send_file(
            cached_mp3_file,
            as_attachment=True,
            download_name=filename,
            mimetype='audio/mpeg'
        )

    except Exception as e:
        logger.error(f"Error serving MP3 (v2) for {video_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to serve MP3',
            'message': str(e),
            'video_id': video_id
        }), 500
        
@app.route('/v3/mp3/<video_id>', methods=['GET'])
def serve_mp3_v3(video_id):
    """
    V3: Serve cached MP3 file by video_id
    Expected query parameter: device (device identifier)
    Returns: MP3 file or 404 if not cached
    """
    try:
        device = request.args.get('device')
        
        if not device:
            return jsonify({
                'error': 'Missing required parameter: device',
                'message': 'Please provide a device identifier'
            }), 400

        # Find cached MP3 file
        cached_mp3_file = find_cached_mp3_file(video_id)
        
        if not cached_mp3_file or not os.path.exists(cached_mp3_file):
            return jsonify({
                'error': 'MP3 not found',
                'message': f'No cached MP3 file found for video {video_id}',
                'video_id': video_id
            }), 404

        # Extract filename for download
        filename = os.path.basename(cached_mp3_file)
        
        logger.info(f"Serving cached MP3 (v2): {filename}")
        
        return send_file(
            cached_mp3_file,
            as_attachment=True,
            download_name=filename,
            mimetype='audio/mpeg'
        )

    except Exception as e:
        logger.error(f"Error serving MP3 (v3) for {video_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to serve MP3',
            'message': str(e),
            'video_id': video_id
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


if __name__ == '__main__':
    # Ensure the cache directory exists on startup
    if ensure_directory_exists(folder_path):
        logger.info(f"Cache directory ready: {folder_path}")
    else:
        logger.warning(f"Could not create cache directory: {folder_path}")

    logger.info(f"Starting YouTube Downloader API on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
