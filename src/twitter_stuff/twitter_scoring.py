from collections import Counter
import datetime, pytz, yaml, re
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Tweet
from datetime import datetime
from dateutil import tz


KW  = yaml.safe_load(Path("keywords.yaml").read_text())["keywords"]
UTC = pytz.utc
HOURS_DECAY = 72

def kw_hits(text):
    flat = " ".join(text.lower().split())
    c = Counter()
    for cat, words in KW.items():
        for w in words:
            if w in flat:
                c[cat] += 1
    return c

def tweet_score(tweet, now):
    hits = kw_hits(tweet.text)
    recency = 24 / max(1, (now - tweet.created_at).total_seconds() / 3600)
    engagement = (tweet.like_count + 2 * tweet.retweet_count) / 50  # scale down
    return sum(hits.values()) * 3 + engagement + recency

def tweet_rank():
    engine = create_engine("sqlite:///newsletter.db")
    sess = Session(engine)
    now = datetime.now(tz.tz.UTC)

    fresh = sess.query(Tweet).filter(Tweet.score == None).all()
    for t in fresh:
        t.score = int(tweet_score(t, now))
    sess.commit()

if __name__ == "__main__":
    tweet_rank()
    print("Tweet ranking complete")
