import argparse
import os
import sys
import json
import requests
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List, Set
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

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # seconds
BATCH_SIZE = 50  # Maximum videos to fetch details in one request


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
        "maxResults": 50,
        "q": query,
        "channelId": channel_id,
        "publishedAfter": published_after,
        "key": YOUTUBE_API_KEY
    }

    # Only include regionCode if provided
    if region_code:
        params["regionCode"] = region_code

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
                print(f"    Attempt {attempt + 1} failed: {str(e)}")
                print(f"    Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            else:
                print(f"    All {MAX_RETRIES} attempts failed")

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
                print(f"      Attempt {attempt + 1} failed: {str(e)}")
                print(f"      Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            else:
                print(f"      All {MAX_RETRIES} attempts failed")

    # If all retries failed, raise the last exception
    raise last_exception


def parse_duration(iso_duration: str):
    """Parse ISO 8601 duration string (PT22M11S) to seconds"""
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
    
    print(f"    Fetching detailed metadata for {len(video_ids)} videos...")
    
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
        
        print(f"    ✓ Enriched {len(video_ids)} videos with metadata")
        
    except Exception as e:
        print(f"    Warning: Failed to enrich videos: {str(e)}")
        print(f"    Continuing with basic data...")
    
    return videos


def load_existing_results(filepath: Path) -> tuple[List[dict], Set[str]]:
    """Load existing results and return list + set of existing videoIds"""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_ids = {v.get("videoId") for v in existing_data if v.get("videoId")}
        return existing_data, existing_ids
    return [], set()


def save_results(filepath: Path, data: List[dict]):
    """Save results to JSON file"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_single_query(
    query: str, 
    channel_id: str, 
    region_code: str, 
    published_after: str,
    min_duration_seconds: float = None,
    existing_video_ids: Set[str] = None
) -> List[dict]:
    """
    Search for videos for a single query/channel pair.
    Returns list of new videos (not in existing_video_ids).
    """
    if existing_video_ids is None:
        existing_video_ids = set()
    
    all_new_videos = []
    page_token = None
    
    while True:
        print(f"    Fetching results (page token: {'Yes' if page_token else 'No'})...")
        
        try:
            # Get results
            results = get_results(
                query=query,
                channel_id=channel_id,
                region_code=region_code,
                published_after=published_after,
                page_token=page_token
            )

            # Process results
            processed_videos, next_page_token = process_results(results)

            if processed_videos:
                # Filter out already existing videos
                new_videos = [
                    v for v in processed_videos 
                    if v.get("videoId") and v.get("videoId") not in existing_video_ids
                ]
                
                skipped = len(processed_videos) - len(new_videos)
                if skipped > 0:
                    print(f"    Skipped {skipped} duplicate videos")
                
                if new_videos:
                    # Enrich videos with additional metadata
                    new_videos = enrich_videos_with_details(new_videos)
                    
                    # Filter by minimum duration if specified
                    if min_duration_seconds is not None:
                        before_filter = len(new_videos)
                        new_videos = [
                            v for v in new_videos 
                            if v.get("duration") is not None and v.get("duration") >= min_duration_seconds
                        ]
                        filtered_out = before_filter - len(new_videos)
                        if filtered_out > 0:
                            print(f"    Filtered out {filtered_out} videos shorter than {min_duration_seconds/60:.1f} minutes")
                    
                    # Add to our collection and update existing IDs set
                    for v in new_videos:
                        existing_video_ids.add(v.get("videoId"))
                    
                    all_new_videos.extend(new_videos)
                    print(f"    Found {len(new_videos)} new videos (Total new: {len(all_new_videos)})")

            # Check for next page
            if next_page_token:
                page_token = next_page_token
            else:
                break

        except Exception as e:
            print(f"    Error during processing: {str(e)}")
            print(f"    Continuing with collected videos...")
            break
    
    return all_new_videos


def main():
    parser = argparse.ArgumentParser(
        description="Bulk fetch and save YouTube videos using YouTube Data API v3"
    )

    # Required argument for bulk mode
    parser.add_argument(
        "--queries-json",
        required=True,
        help="Path to JSON file containing query/channel pairs"
    )
    
    # Optional arguments
    parser.add_argument(
        "-r", "--region",
        default=None,
        help="Region code (optional, not included in API query if not specified)"
    )
    parser.add_argument(
        "--min-duration-in-minutes",
        type=float,
        default=None,
        help="Minimum video duration in minutes (videos shorter than this will be rejected)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=60,
        help="Limit in months (default: 60 months = 5 years)"
    )
    parser.add_argument(
        "-d", "--data-dir",
        default="saved-data",
        help="Directory to save data (default: saved-data)"
    )
    parser.add_argument(
        "-o", "--output",
        default="results.json",
        help="Output filename (default: results.json)"
    )

    args = parser.parse_args()

    # Set global SAVED_DATA_DIR variable
    global SAVED_DATA_DIR
    SAVED_DATA_DIR = Path(args.data_dir)

    # Initialize saved-data directory
    init_saved_data_dir()

    # Load queries from JSON file
    queries_file = Path(args.queries_json)
    if not queries_file.exists():
        print(f"Error: Queries file not found: {args.queries_json}")
        sys.exit(1)
    
    with open(queries_file, "r", encoding="utf-8") as f:
        queries = json.load(f)
    
    if not queries:
        print("Error: No queries found in JSON file")
        sys.exit(1)

    # Calculate published_after date
    published_after = get_published_after_date(args.limit + 1)
    
    # Calculate min duration in seconds
    min_duration_seconds = None
    if args.min_duration_in_minutes is not None:
        min_duration_seconds = args.min_duration_in_minutes * 60

    print("=" * 60)
    print("YouTube Bulk Search")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Queries file: {args.queries_json}")
    print(f"  Number of query/channel pairs: {len(queries)}")
    print(f"  Region: {args.region if args.region else 'Not specified (global)'}")
    print(f"  Limit: {args.limit} months")
    print(f"  Published After: {published_after}")
    if args.min_duration_in_minutes:
        print(f"  Min Duration: {args.min_duration_in_minutes} minutes")
    print(f"  Output directory: {SAVED_DATA_DIR}")
    print(f"  Output file: {args.output}")
    print("=" * 60)

    # Load existing results for deduplication
    output_path = SAVED_DATA_DIR / args.output
    existing_videos, existing_video_ids = load_existing_results(output_path)
    
    if existing_videos:
        print(f"\nLoaded {len(existing_videos)} existing videos from {args.output}")
        print(f"Will skip duplicates based on videoId")
    
    # Track statistics
    total_new_videos = 0
    processed_queries = 0
    failed_queries = []

    # Process each query/channel pair
    for i, query_item in enumerate(queries[10:], 1):
        # Support both formats: 
        # 1. {"search_query": "...", "yt_channel_id": "..."}
        # 2. {"query": "...", "channel": "..."}
        query = query_item.get("search_query") or query_item.get("query")
        channel_id = query_item.get("yt_channel_id") or query_item.get("channel_id") or query_item.get("channel")
        tv_channel_name = query_item.get("tv_channel_name", "Unknown")
        
        if not query or not channel_id:
            print(f"\n[{i}/{len(queries)}] Skipping invalid entry: missing query or channel_id")
            continue
        
        print(f"\n{'='*60}")
        print(f"[{i}/{len(queries)}] {tv_channel_name}")
        print(f"  Query: {query}")
        print(f"  Channel ID: {channel_id}")
        print("-" * 60)
        
        try:
            new_videos = search_single_query(
                query=query,
                channel_id=channel_id,
                region_code=args.region,
                published_after=published_after,
                min_duration_seconds=min_duration_seconds,
                existing_video_ids=existing_video_ids
            )
            
            if new_videos:
                existing_videos.extend(new_videos)
                total_new_videos += len(new_videos)
                print(f"  ✓ Added {len(new_videos)} new videos")
                
                # Save after each successful query (for resilience)
                save_results(output_path, existing_videos)
                print(f"  ✓ Saved to {args.output} (Total: {len(existing_videos)})")
            else:
                print(f"  ✓ No new videos found")
            
            processed_queries += 1
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            failed_queries.append({
                "query": query,
                "channel_id": channel_id,
                "error": str(e)
            })
    
    # Final save
    save_results(output_path, existing_videos)
    
    # Save metadata
    metadata = {
        "queries_file": args.queries_json,
        "region_code": args.region,
        "limit_months": args.limit,
        "min_duration_minutes": args.min_duration_in_minutes,
        "published_after": published_after,
        "total_queries": len(queries),
        "processed_queries": processed_queries,
        "failed_queries": len(failed_queries),
        "total_videos": len(existing_videos),
        "new_videos_added": total_new_videos,
        "timestamp": datetime.now(UTC).isoformat()
    }
    
    metadata_path = SAVED_DATA_DIR / "search-bulk-metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Processed queries: {processed_queries}/{len(queries)}")
    print(f"  Failed queries: {len(failed_queries)}")
    print(f"  New videos added: {total_new_videos}")
    print(f"  Total videos in {args.output}: {len(existing_videos)}")
    print(f"  Results saved to: {output_path}")
    print(f"  Metadata saved to: {metadata_path}")
    
    if failed_queries:
        print("\nFailed queries:")
        for fq in failed_queries:
            print(f"  - {fq['query']}: {fq['error']}")


if __name__ == "__main__":
    main()
