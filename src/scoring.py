import re, datetime, yaml
from collections import Counter
from dateutil import tz
from pathlib import Path

KW = yaml.safe_load(Path("keywords.yaml").read_text())["keywords"]
UTC = tz.UTC
HOURS_DECAY = 72        # only articles within this window exist anyway

def kw_hits(text):
    flat = " ".join(text.lower().split())
    counts = Counter()
    for cat, words in KW.items():
        for w in words:
            if w in flat:
                counts[cat] += 1
    return counts

def article_score(article, now):
    if article.published_at.tzinfo is None:
        article_dt = article.published_at.replace(tzinfo=UTC)
    else:
        article_dt = article.published_at
    hits = kw_hits(article.text)
    recency = 24 / max(1, (now - article_dt).total_seconds() / 3600)
    return sum(hits.values()) * 3 + recency
