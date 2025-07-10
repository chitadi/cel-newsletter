# src/youtube_rank.py
import datetime, pytz, numpy as np, sqlalchemy as sa
from sqlalchemy.orm import Session
from src.models import Video
import itertools, yaml, numpy as np, pytz
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ── 1.  Load YAML  ─────────────────────────────────────────────────────────
CFG = yaml.safe_load(Path("sources_and_keywords/youtube_keywords.yaml").read_text())
CATEGORIES = CFG["scoring_categories"]

# build two handy dicts
KW_DICT   = {c["name"]: c["keywords"] for c in CATEGORIES}
WEIGHTS   = {c["name"]: c.get("weight", 1) for c in CATEGORIES}

# ── 2.  Single global query vector from ALL keywords  ──────────────────────
_EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_tokens = itertools.chain.from_iterable(c["keywords"] for c in CATEGORIES)
_query  = " ".join(_tokens)
_MODEL  = SentenceTransformer(_EMB_MODEL)
QUERY_VEC = _MODEL.encode([_query], normalize_embeddings=True)[0]

cfg = yaml.safe_load(Path("sources_and_keywords/youtube_keywords.yaml").read_text())
SRC_W = cfg.get("source_weights", {})


def cosine(blob):
    v = np.frombuffer(blob, dtype=np.float32)
    return float(np.dot(v, QUERY_VEC))

def source_weight(name: str) -> float:
    return float(SRC_W.get(name, 1.0))

UTC = pytz.utc

def kw_weighted_hits(text: str) -> int:
    flat = text.lower()
    total = 0
    for name, kw_list in KW_DICT.items():
        if any(k.lower() in flat for k in kw_list):
            total += WEIGHTS[name]
    return total  # simple int, not Counter now

def rank_videos():
    eng = sa.create_engine("sqlite:///newsletter.db")
    now = datetime.datetime.now(tz=UTC)
    with Session(eng) as ssn:
        vids = ssn.query(Video).filter(Video.score.is_(None)).all()
        for v in vids:
            txt   = v.transcript or v.description or ""
            sem   = cosine(v.vector) if v.vector else 0
            kw    = kw_weighted_hits(txt)
            # rec   = 24 / max(1, (now - v.published_at).total_seconds()/3600)
            w = source_weight(v.channel_name)
            v.score = int(w * (kw*1 + sem*25))
        ssn.commit()

if __name__ == "__main__":
    rank_videos()

