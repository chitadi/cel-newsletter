# src/youtube_rank.py
import datetime, pytz, re
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Video
from src.scoring import kw_hits   # your article keyword function
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript


UTC = pytz.utc

def rank_videos():
    engine = create_engine("sqlite:///newsletter.db")
    now    = datetime.datetime.now(tz=UTC)

    with Session(engine) as ssn:
        vids = ssn.query(Video).filter(Video.score.is_(None)).all()
        for v in vids:
            try:
                segs = YouTubeTranscriptApi.get_transcript(v.video_id)
                transcript = " ".join(s["text"] for s in segs)
            except Exception:
                transcript = v.description or ""
            hits = sum(kw_hits(transcript).values())    # total hits across all categories

            v.score = int(hits)

        ssn.commit()

if __name__ == "__main__":
    rank_videos()
