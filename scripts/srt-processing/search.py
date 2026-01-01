import argparse
import os
import sys
import json
import requests
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any
import re
import unicodedata

# Load environment variables
load_dotenv()

# YouTube Data API configuration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY not found in .env file")

BASE_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_BASE_URL = "https://www.googleapis.com/youtube/v3/videos"
SAVED_DATA_DIR = None  # Will be set via command-line argument or default
STATE_FILE = "search-state.json"

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # secondsBATCH_SIZE = 50  # Maximum videos to fetch details in one request

def get_published_after_date(limit_months: int):
    """Calculate the publishedAfter date based on limit months"""
    cutoff_date = datetime.now(UTC) - timedelta(days=30 * limit_months)
    # Format as RFC 3339 datetime
    return cutoff_date.strftime("%Y-%m-%dT00:00:00Z")


def get_results(query: str, channel_id: str, region_code: str, published_after: str, page_token: str = None):
    """Fetch results from YouTube Data API v3"""
    params = {
        "part": "snippet",
        "type": "video",
        "order": "date",
        "regionCode": region_code,
        "maxResults": 50,
        "q": query,
        "channelId": channel_id,
        "publishedAfter": published_after,
        "key": YOUTUBE_API_KEY
    }

    if page_token:
        params["pageToken"] = page_token

    headers = {
        "Accept": "application/json"
    }

    # Exponential backoff with retry
    backoff = INITIAL_BACKOFF
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                print(f"  Attempt {attempt + 1} failed: {str(e)}")
                print(f"  Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            else:
                print(f"  All {MAX_RETRIES} attempts failed")

    # If all retries failed, raise the last exception
    raise last_exception

def normalize_youtube_description(
    text: str,
    *,
    replace_urls: bool = True,
    replace_emails: bool = True,
    normalize_unicode: bool = True,
    keep_hashtags: bool = True,
    min_line_length: int = 0
) -> str:
    """
    Normalize YouTube video descriptions for LLM processing.
    Language-agnostic (Bangla, English, Spanish, etc.).

    Args:
        text (str): Raw description text
        replace_urls (bool): Replace URLs with <URL>
        replace_emails (bool): Replace emails with <EMAIL>
        normalize_unicode (bool): Apply NFC unicode normalization
        keep_hashtags (bool): Keep hashtags or remove them
        min_line_length (int): Drop lines shorter than this length

    Returns:
        str: Cleaned description
    """

    if not text:
        return ""

    # Normalize unicode (important for Bangla, Arabic, etc.)
    if normalize_unicode:
        text = unicodedata.normalize("NFC", text)

    # Replace URLs
    if replace_urls:
        text = re.sub(
            r"(https?://\S+|www\.\S+)",
            "<URL>",
            text,
            flags=re.IGNORECASE
        )

    # Replace emails
    if replace_emails:
        text = re.sub(
            r"\b[\w\.-]+@[\w\.-]+\.\w+\b",
            "<EMAIL>",
            text
        )

    # Normalize line breaks
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # Remove very short noise lines if requested
    if min_line_length > 0:
        lines = [l for l in lines if len(l) >= min_line_length]

    text = "\n".join(lines)

    # Collapse repeated separators
    text = re.sub(r"_+", "_", text)
    text = re.sub(r"-{3,}", "---", text)

    # Optionally remove hashtags
    if not keep_hashtags:
        text = re.sub(r"#\w+", "", text)

    # Normalize excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def load_metadata(metadata_path: str, folder: str, file: str, model: str) -> Dict[str, Any]:
    """Load or create filter metadata."""
    if os.path.exists(metadata_path):
        return json.load(open(metadata_path, 'r', encoding='utf-8'))
    
    return {
        'folder': folder,
        'file': file,
        'model': model,
        'failures': []
    }


def save_metadata(metadata_path: str, metadata: Dict[str, Any]) -> None:
    """Save filter metadata."""
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def get_video_details(video_ids: list):
    """Fetch video details from YouTube Data API v3 for multiple videos"""
    # Join video IDs with comma
    ids_param = ",".join(video_ids)

    params = {
        "part": "snippet,statistics,contentDetails",
        "id": ids_param,
        "key": YOUTUBE_API_KEY
    }

    headers = {
        "Accept": "application/json"
    }

    # Exponential backoff with retry
    backoff = INITIAL_BACKOFF
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(VIDEOS_BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                print(f"    Attempt {attempt + 1} failed: {str(e)}")
                print(f"    Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            else:
                print(f"    All {MAX_RETRIES} attempts failed")

    # If all retries failed, raise the last exception
    raise last_exception


def parse_duration(iso_duration: str):
    """Parse ISO 8601 duration string (PT22M11S) to seconds"""
    import re
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, iso_duration)
    if not match:
        return None
    
    hours, minutes, seconds = match.groups()
    total_seconds = 0
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)
    
    return total_seconds


def init_saved_data_dir():
    """Create saved-data directory if it doesn't exist"""
    global SAVED_DATA_DIR
    SAVED_DATA_DIR.mkdir(exist_ok=True)


def create_initial_state(query: str, channel: str, region_code: str, limit: int, published_after: str):
    """Create initial search-state.json"""
    state = {
        "query": query,
        "channel": channel,
        "region_code": region_code,
        "limit_months": limit,
        "published_after": published_after,
        "page_token": None,
        "finished": False
    }
    return state


def save_state(state: dict):
    """Save state to search-state.json"""
    state_path = SAVED_DATA_DIR / STATE_FILE
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state():
    """Load state from search-state.json"""
    state_path = SAVED_DATA_DIR / STATE_FILE
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def transform_video_data(item: dict):
    """Transform YouTube API video data to keep only necessary fields"""
    snippet = item.get("snippet", {})
    return {
        "videoId": item.get("id", {}).get("videoId"),
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "publishedAt": snippet.get("publishedAt"),
        "channelId": snippet.get("channelId"),
        "channelTitle": snippet.get("channelTitle")
    }


def process_results(results: dict):
    """
    Process results: transform data and extract relevant fields.
    Returns tuple: (processed_data_list, next_page_token)
    """
    processed_data = []

    if "items" not in results or not results["items"]:
        return [], None

    for item in results["items"]:
        # Skip if not a video
        if item.get("kind") != "youtube#searchResult":
            continue

        # Transform and add to list
        processed_data.append(transform_video_data(item))

    # Get next page token if available
    next_page_token = results.get("nextPageToken")

    return processed_data, next_page_token


def enrich_videos_with_details(videos: list):
    """
    Enrich video data by fetching additional details from YouTube API
    Updates description, adds duration and viewCount
    """
    if not videos:
        return videos
    
    # Extract video IDs
    video_ids = [v.get("videoId") for v in videos if v.get("videoId")]
    
    if not video_ids:
        return videos
    
    print(f"  Fetching detailed metadata for {len(video_ids)} videos...")
    
    try:
        # Fetch video details
        response = get_video_details(video_ids)
        
        if "items" not in response:
            return videos
        
        # Create a mapping of videoId to details
        details_map = {}
        for item in response["items"]:
            video_id = item.get("id")
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})
            
            details_map[video_id] = {
                "description": snippet.get("description"),
                "duration": parse_duration(content_details.get("duration")),
                "durationText": content_details.get("duration"),
                "viewCount": int(statistics.get("viewCount", 0)) if statistics.get("viewCount") else 0,
                "likeCount": int(statistics.get("likeCount", 0)) if statistics.get("likeCount") else 0
            }
        
        # Update videos with fetched details
        for video in videos:
            video_id = video.get("videoId")
            if video_id in details_map:
                details = details_map[video_id]
                video["description"] = details["description"]
                video["normalizedDescription"] = normalize_youtube_description(details["description"])
                if details["duration"] is not None:
                    video["duration"] = details["duration"]
                if details["durationText"]:
                    video["durationText"] = details["durationText"]
                video["viewCount"] = details["viewCount"]
                video["likeCount"] = details["likeCount"]
        
        print(f"  ✓ Enriched {len(video_ids)} videos with metadata")
        
    except Exception as e:
        print(f"  Warning: Failed to enrich videos: {str(e)}")
        print(f"  Continuing with basic data...")
    
    return videos


def save_results_to_file(data_list: list, filename: str, append: bool = False):
    """Save or append results to a JSON file"""
    file_path = SAVED_DATA_DIR / filename
    
    if append and file_path.exists():
        # Load existing data and append
        with open(file_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_data.extend(data_list)
        data_to_save = existing_data
    else:
        data_to_save = data_list
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and save YouTube videos using YouTube Data API v3"
    )

    # Optional arguments with defaults
    parser.add_argument(
        "-q", "--query",
        default="স্বাস্থ্য জিজ্ঞাসা",
        help="Search query (default: স্বাস্থ্য জিজ্ঞাসা)"
    )
    parser.add_argument(
        "-c", "--channel",
        default="UClzwimpLoZu9us9MwalLbtA",
        help="Channel ID to filter by"
    )
    parser.add_argument(
        "-r", "--region",
        default="BD",
        help="Region code (default: BD)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=12,
        help="Limit in months (default: 12)"
    )
    parser.add_argument(
        "-d", "--data-dir",
        default="saved-data",
        help="Directory to save data (default: saved-data)"
    )

    args = parser.parse_args()

    # Set global SAVED_DATA_DIR variable
    global SAVED_DATA_DIR
    SAVED_DATA_DIR = Path(args.data_dir)

    # Initialize saved-data directory
    init_saved_data_dir()

    # Calculate published_after date
    published_after = get_published_after_date(args.limit + 1)

    metadata_path = SAVED_DATA_DIR / 'search-metadata.json'

    # Check if resuming from existing state
    existing_state = load_state()

    if existing_state:
        print("Found existing search-state.json - resuming from previous run")
        if existing_state.get("finished"):
            print("  Previous run finished successfully")
        else:
            print(f"  Resuming with page token: {existing_state.get('page_token', 'None')}")
        state = existing_state
    else:
        print("Starting new session")
        # Create initial state
        state = create_initial_state(
            query=args.query,
            channel=args.channel,
            region_code=args.region,
            limit=args.limit,
            published_after=published_after
        )

        metadata = {
            "query": args.query,
            "channel": args.channel,
            "region_code": args.region,
            "limit": args.limit,
            "published_after": published_after
        }
        save_state(state)
        save_metadata(str(metadata_path), metadata)

    print(f"Configuration:")
    print(f"  Query: {state['query']}")
    print(f"  Channel ID: {state['channel']}")
    print(f"  Region: {state['region_code']}")
    print(f"  Limit: {state['limit_months']} months")
    print(f"  Published After: {state['published_after']}")
    print(f"  Saved data directory: {SAVED_DATA_DIR}")

    # Skip if already finished
    if state.get("finished", False):
        print("\n--- Previous run completed successfully ---")
        print(f"Results saved in {SAVED_DATA_DIR}/results.json")
        return

    # Process results with pagination
    print("\n--- Fetching YouTube videos ---")

    page_token = state.get("page_token")
    total_videos = 0

    # If resuming, count existing videos
    if page_token:
        file_path = SAVED_DATA_DIR / "results.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            total_videos = len(existing_data)
            print(f"Resuming with {total_videos} existing videos")

    while True:
        print(f"Fetching results (page token: {'Yes' if page_token else 'No'})...")

        try:
            # Get results
            results = get_results(
                query=state['query'],
                channel_id=state['channel'],
                region_code=state['region_code'],
                published_after=state['published_after'],
                page_token=page_token
            )

            # Process results
            processed_videos, next_page_token = process_results(results)

            if processed_videos:
                # Enrich videos with additional metadata
                processed_videos = enrich_videos_with_details(processed_videos)
                
                save_results_to_file(processed_videos, "results.json", append=(total_videos > 0))
                total_videos += len(processed_videos)
                print(f"  Saved {len(processed_videos)} videos (Total: {total_videos})")

            # Update state with next page token
            if next_page_token:
                state["page_token"] = next_page_token
                save_state(state)
                print(f"  Saved continuation token for resume")
                page_token = next_page_token
            else:
                # No more pages, mark as finished
                print(f"  No more pages, marking as finished")
                state["finished"] = True
                state["page_token"] = None
                save_state(state)
                break

        except Exception as e:
            print(f"Error during processing: {str(e)}")
            print(f"Progress saved with continuation token for resume")
            raise

    print(f"\n✓ Completed: {total_videos} total videos saved")
    print(f"Results saved in {SAVED_DATA_DIR}/results.json")

    state_path = SAVED_DATA_DIR / STATE_FILE
    if state_path.exists():
        state_path.unlink()


if __name__ == "__main__":
    main()
