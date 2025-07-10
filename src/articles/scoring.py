import datetime as _dt
import itertools, yaml, numpy as np, pytz
from pathlib import Path
from collections import Counter
from sentence_transformers import SentenceTransformer

# ── 1.  Load YAML  ─────────────────────────────────────────────────────────
CFG = yaml.safe_load(Path("sources_and_keywords/keywords.yaml").read_text())
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

cfg = yaml.safe_load(Path("sources_and_keywords/keywords.yaml").read_text())
SRC_W = cfg.get("source_weights", {})

# ── 3.  Helper: keyword hits with weights  ─────────────────────────────────
def kw_weighted_hits(text: str) -> int:
    flat = text.lower()
    total = 0
    for name, kw_list in KW_DICT.items():
        if any(k.lower() in flat for k in kw_list):
            total += WEIGHTS[name]
    return total  # simple int, not Counter now

# ── 4.  Helper: cosine on stored vector bytes  ─────────────────────────────
def cosine(blob: bytes) -> float:
    if not blob or len(blob) < 1500:      # 384 floats ×4 = 1536 bytes
        return 0.0                        # treat as “no vector”
    v = np.frombuffer(blob, dtype=np.float32)
    return float(np.dot(v, QUERY_VEC))

# ── 5.  Final blended score  ───────────────────────────────────────────────
def _ensure_aware(dt: _dt.datetime) -> _dt.datetime:
    """Return `dt` as timezone-aware in UTC."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def source_weight(name: str) -> float:
    return float(SRC_W.get(name, 1.0))

UTC = pytz.utc

def article_score(article, now: _dt.datetime) -> int:

    now_utc = _ensure_aware(now or _dt.datetime.utcnow())
    pub_utc = _ensure_aware(article.published_at)

    recency_h = max(1, (now_utc-pub_utc).total_seconds() / 3600)
    rec      = 24 / recency_h                    # newer ⇒ higher

    kw_hits  = kw_weighted_hits(article.text)    # weighted keywords
    sem_sim  = cosine(article.vector) if article.vector else 0.0

    w = source_weight(article.source_name)

    # Tune weights as you like
    return int(
        w * (
        kw_hits           * 1   +   # keyword importance
        rec               * 0.5 +   # freshness
        sem_sim           * 40       # semantic relevance
        ))

