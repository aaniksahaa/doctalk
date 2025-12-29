import argparse
import os
import sys
import json
import requests
import time
from urllib.parse import urlencode
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# FAIL = 0

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    raise RuntimeError("RAPIDAPI_KEY not found in .env file")

BASE_URL = "https://yt-api.p.rapidapi.com/search"
SAVED_DATA_DIR = None  # Will be set via command-line argument or default

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # seconds

def get_results(query: str, channel: str, duration: str, geo: str = "BD", sort: str = "date", token: str = None):
    # global FAIL
    params = {
        "query": query,
        "geo": geo,
        "duration": duration,
        "sort_by": sort
    }
    
    if token:
        params["token"] = token

    url = f"{BASE_URL}?{urlencode(params, safe='')}"

    headers = {
        "x-rapidapi-host": "yt-api.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    # if FAIL == 1:
    #     print("Failed")
    #     sys.exit(1)

    # FAIL += 1

    # Exponential backoff with retry
    backoff = INITIAL_BACKOFF
    last_exception = None

    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=30)
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


def init_saved_data_dir():
    """Create saved-data directory if it doesn't exist"""
    global SAVED_DATA_DIR
    SAVED_DATA_DIR.mkdir(exist_ok=True)


def create_initial_state(query: str, channel: str, geo: str, sort: str, limit: int):
    """Create initial state.json"""
    state = {
        "query": query,
        "channel": channel,
        "geo": geo,
        "sort": sort,
        "limit": limit,
        "duration": "long",
        "token": None,
        "long-finished": False,
        "medium-finished": False
    }
    return state


def save_state(state: dict):
    """Save state to state.json"""
    state_path = SAVED_DATA_DIR / "state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state():
    """Load state from state.json"""
    state_path = SAVED_DATA_DIR / "state.json"
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def is_within_limit(publish_date_str: str, limit_months: int):
    """Check if a video is within the limit months from today"""
    try:
        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d")
        cutoff_date = datetime.now() - timedelta(days=30 * (limit_months + 1))
        return publish_date >= cutoff_date
    except (ValueError, TypeError):
        return True


def transform_video_data(video: dict):
    """Transform video data to keep only necessary fields"""
    return {
        "videoId": video.get("videoId"),
        "title": video.get("title"),
        "description": video.get("description"),
        "viewCount": video.get("viewCount"),
        "publishDate": video.get("publishDate"),
        "publishedAt": video.get("publishedAt"),
        "lengthText": video.get("lengthText")
    }


def process_results(results: dict, target_channel: str, limit_months: int):
    """
    Process results: filter by channel, transform data, and check date limits.
    Returns tuple: (processed_data_list, has_more_data)
    has_more_data is False if we hit the date limit
    """
    processed_data = []
    has_more_data = True
    
    if "data" not in results or not results["data"]:
        return [], False
    
    for video in results["data"]:
        if video.get("type") != "video":
            continue
        
        # Check if channel matches
        if video.get("channelId") != target_channel:
            continue
        
        # Check if within date limit
        publish_date = video.get("publishDate", "")
        if not is_within_limit(publish_date, limit_months):
            has_more_data = False
            break
        
        # Transform and add to list
        processed_data.append(transform_video_data(video))
    
    return processed_data, has_more_data


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


def merge_results():
    """
    Merge long.json and medium.json into a single results.json file sorted by publishedAt
    """
    print("\n--- Merging results ---")
    
    long_path = SAVED_DATA_DIR / "long.json"
    medium_path = SAVED_DATA_DIR / "medium.json"
    merged_path = SAVED_DATA_DIR / "results.json"
    
    merged_data = []
    
    # Load and merge long.json
    if long_path.exists():
        with open(long_path, "r", encoding="utf-8") as f:
            long_data = json.load(f)
        merged_data.extend(long_data)
        print(f"  Loaded {len(long_data)} videos from long.json")
    
    # Load and merge medium.json
    if medium_path.exists():
        with open(medium_path, "r", encoding="utf-8") as f:
            medium_data = json.load(f)
        merged_data.extend(medium_data)
        print(f"  Loaded {len(medium_data)} videos from medium.json")
    
    # Remove duplicates based on videoId
    seen_ids = set()
    unique_data = []
    for video in merged_data:
        video_id = video.get("videoId")
        if video_id not in seen_ids:
            seen_ids.add(video_id)
            unique_data.append(video)
    
    # Sort by publishedAt (most recent first)
    unique_data.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    
    # Save merged results
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)
    
    print(f"  Merged total: {len(unique_data)} unique videos (after deduplication)")
    print(f"  Saved to results.json")


def process_duration(query: str, channel_id: str, duration: str, geo: str, sort: str, limit_months: int, state: dict):
    """
    Process results for a specific duration (long or medium)
    """
    print(f"\n--- Processing {duration.upper()} duration videos ---")
    
    output_filename = f"{duration}.json"
    
    # Check if resuming from a token
    continuation_token = state.get("token")
    total_videos = 0
    
    # If resuming, count existing videos
    if continuation_token:
        file_path = SAVED_DATA_DIR / output_filename
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            total_videos = len(existing_data)
            print(f"Resuming with {total_videos} existing videos")
    
    while True:
        print(f"Fetching {duration} duration results (token: {'Yes' if continuation_token else 'No'})...")
        
        try:
            # Get results
            results = get_results(query, channel_id, duration, geo=geo, sort=sort, token=continuation_token)
            
            # Save continuation token to state
            new_token = results.get("continuation")
            state["token"] = new_token
            save_state(state)
            
            # Process results
            processed_videos, has_more_data = process_results(results, channel_id, limit_months)
            
            if processed_videos:
                save_results_to_file(processed_videos, output_filename, append=(total_videos > 0))
                total_videos += len(processed_videos)
                print(f"  Saved {len(processed_videos)} videos to {output_filename} (Total: {total_videos})")
            
            # Check if we should continue
            if not has_more_data:
                print(f"  Reached date limit, stopping {duration} processing")
                break
            
            if not new_token:
                print(f"  No more continuation tokens for {duration}")
                break
            
            continuation_token = new_token
        except Exception as e:
            print(f"Error during {duration} processing: {str(e)}")
            print(f"Progress saved with continuation token for resume")
            raise
    
    print(f"Completed {duration}: {total_videos} total videos saved")
    return total_videos > 0

def main():
    parser = argparse.ArgumentParser(
        description="Process search parameters and save results by duration"
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
        "-g", "--geo",
        default="BD",
        help="Geographic location (default: BD)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=12,
        help="Limit in months (default: 12)"
    )
    parser.add_argument(
        "--sort",
        default="date",
        help="Sort order (default: date)"
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
    
    # Check if resuming from existing state
    existing_state = load_state()
    
    if existing_state:
        print("Found existing state.json - resuming from previous run")
        print(f"  Long duration finished: {existing_state.get('long-finished', False)}")
        print(f"  Medium duration finished: {existing_state.get('medium-finished', False)}")
        if existing_state.get('token'):
            print(f"  Resuming with continuation token")
        state = existing_state
    else:
        print("Starting new session")
        # Create initial state
        state = create_initial_state(
            query=args.query,
            channel=args.channel,
            geo=args.geo,
            sort=args.sort,
            limit=args.limit
        )
        save_state(state)
    
    print(f"Configuration:")
    print(f"  Query: {state['query']}")
    print(f"  Channel ID: {state['channel']}")
    print(f"  Geo: {state['geo']}")
    print(f"  Sort: {state['sort']}")
    print(f"  Limit: {state['limit']} months")
    print(f"  Saved data directory: {SAVED_DATA_DIR}")
    
    # Process long duration (skip if already finished)
    if not state.get("long-finished", False):
        state["duration"] = "long"
        save_state(state)
        process_duration(
            query=state['query'],
            channel_id=state['channel'],
            duration="long",
            geo=state['geo'],
            sort=state['sort'],
            limit_months=state['limit'],
            state=state
        )
        state["long-finished"] = True
        state["token"] = None
        save_state(state)
    else:
        print("\n--- Skipping LONG duration (already completed) ---")
    
    # Process medium duration (skip if already finished)
    if not state.get("medium-finished", False):
        state["duration"] = "medium"
        save_state(state)
        process_duration(
            query=state['query'],
            channel_id=state['channel'],
            duration="medium",
            geo=state['geo'],
            sort=state['sort'],
            limit_months=state['limit'],
            state=state
        )
        state["medium-finished"] = True
        state["token"] = None
        save_state(state)
    else:
        print("\n--- Skipping MEDIUM duration (already completed) ---")
    
    # Merge results from long and medium
    merge_results()
    
    print("\n✓ All processing complete!")
    print(f"Results saved in {SAVED_DATA_DIR}/")


if __name__ == "__main__":
    main()
