import os
import datetime
import pytz
import yaml
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Video

from dotenv import load_dotenv
load_dotenv() 

UTC = pytz.utc
HOURS = 24 # lookback window in hours basically 7 days here
MIN_DURATION_SEC = 5 * 60  # 5 minutes

def load_channels(config_path="sources_and_keywords/channels.yaml"):
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("channels", [])


def parse_iso_duration(duration):
    m = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', duration)
    if not m:
        return 0
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2)) if m.group(2) else 0
    seconds = int(m.group(3)) if m.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


def fetch_videos(max_results_per_channel=7, config_path="sources_and_keywords/channels.yaml"):
    """
    Fetch recent videos >= MIN_DURATION_SEC from each channel's uploads playlist
    and store new ones in the DB.
    """
    youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))
    cutoff = datetime.datetime.now(tz=UTC) - datetime.timedelta(hours=HOURS)
    channels = load_channels(config_path)

    engine = create_engine("sqlite:///newsletter.db")
    with Session(engine) as ssn:
        for ch in channels:
            channel_id = ch.get("id")
            channel_name = ch.get("name", channel_id)

            # 1. Retrieve the channel's 'uploads' playlist ID
            ch_resp = youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()
            items = ch_resp.get("items", [])
            if not items:
                print(f"Channel not found: {channel_name} ({channel_id})")
                continue

            uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # 2. Paginate through the uploads playlist
            next_page_token = None
            fetched = 0
            stop_channel = False
            while not stop_channel and fetched < max_results_per_channel:
                try:
                    pl_resp = youtube.playlistItems().list(
                        part="snippet",
                        playlistId=uploads_pl,
                        maxResults=min(50, max_results_per_channel - fetched),
                        pageToken=next_page_token
                    ).execute()
                except HttpError as e:
                    if e.status_code == 403:
                        print(f"⚠️ Skipping {channel_name}: playlistItems blocked (403)")
                        break  # stop paging this channel
                    else:
                        raise   # re-raise other errors

                video_ids = [item["snippet"]["resourceId"]["videoId"] for item in pl_resp.get("items", [])]
                # Batch get durations
                if video_ids:
                    video_resp = youtube.videos().list(
                        part="contentDetails",
                        id=",".join(video_ids)
                    ).execute()
                    durations = {item["id"]: item["contentDetails"]["duration"] for item in video_resp.get("items", [])}
                else:
                    durations = {}

                for item in pl_resp.get("items", []):
                    snip = item["snippet"]
                    vid = snip["resourceId"]["videoId"]
                    published_at = datetime.datetime.fromisoformat(
                        snip["publishedAt"].replace("Z", "+00:00")
                    )
                    if published_at.tzinfo is None:
                        published_at = UTC.localize(published_at)

                    # Stop when we hit older videos
                    if published_at < cutoff:
                        print(f"video for {channel_name} too old")
                        stop_channel = True
                        break

                    # Skip if already in DB
                    if ssn.get(Video, vid):
                        print(f"video for {channel_name} already present in db")
                        continue

                    # Filter by duration
                    dur_iso = durations.get(vid, "")
                    if parse_iso_duration(dur_iso) < MIN_DURATION_SEC:
                        print(f"video for {channel_name} too short")
                        continue

                    # Add new video record
                    ssn.add(Video(
                        video_id=vid,
                        channel_name=channel_name,
                        url=f"https://youtu.be/{vid}",
                        title=snip["title"],
                        description=snip.get("description", ""),
                        thumbnail_url=snip["thumbnails"]["high"]["url"],
                        published_at=published_at,
                    ))
                    fetched += 1
                    print(f"Fetched {vid} from {channel_name} ({published_at})")


                next_page_token = pl_resp.get("nextPageToken")
                if not next_page_token:
                    break
        ssn.commit()


if __name__ == "__main__":
    fetch_videos()