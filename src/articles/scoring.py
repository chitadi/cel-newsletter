import datetime as dt
import itertools, yaml, numpy as np, pytz
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Load YAML configuration
CFG = yaml.safe_load(Path("sources_and_keywords/keywords.yaml").read_text())
CATEGORIES = CFG["scoring_categories"]
SEMANTIC_KEYWORDS = CFG["semantic_keywords"]
SRC_W = CFG.get("source_weights", {})

# Build keyword dictionaries and weights
KW_DICT = {c["name"]: c["keywords"] for c in CATEGORIES}
WEIGHTS = {c["name"]: c.get("weight", 1) for c in CATEGORIES}

# Initialize embedding model
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL = SentenceTransformer(EMB_MODEL)

# Create semantic vectors from YAML
def create_semantic_vectors():
    vectors = {}
    for item in SEMANTIC_KEYWORDS:
        for category, keywords in item.items():
            # Join keywords into a single string for embedding
            query_text = " ".join(keywords)
            vectors[category] = MODEL.encode([query_text], normalize_embeddings=True)[0]
    return vectors

# Generate all semantic vectors at startup
SEMANTIC_VECTORS = create_semantic_vectors()

# Helper functions
def kw_weighted_hits(text: str) -> int:
    flat = text.lower()
    total = 0
    for name, kw_list in KW_DICT.items():
        if any(k.lower() in flat for k in kw_list):
            total += WEIGHTS[name]
    return total

def semantic_scores(article_vector_bytes: bytes) -> dict:
    """Calculate semantic similarity scores for all categories."""
    if not article_vector_bytes or len(article_vector_bytes) < 1500:
        return {category: 0.0 for category in SEMANTIC_VECTORS.keys()}
    
    # Convert bytes to numpy array
    article_vec = np.frombuffer(article_vector_bytes, dtype=np.float32)
    
    # Calculate cosine similarity for each category
    scores = {}
    for category, semantic_vec in SEMANTIC_VECTORS.items():
        scores[category] = float(np.dot(article_vec, semantic_vec))
    
    return scores

def source_weight(name: str) -> float:
    return float(SRC_W.get(name, 1.0))

def ensure_aware(dt_obj: dt.datetime) -> dt.datetime:
    """Return datetime as timezone-aware in UTC."""
    UTC = pytz.utc
    if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
        return dt_obj.replace(tzinfo=UTC)
    return dt_obj.astimezone(UTC)

# Main scoring function
def article_score(article, now: dt.datetime) -> int:
    now_utc = ensure_aware(now or dt.datetime.utcnow())
    pub_utc = ensure_aware(article.published_at)
    
    # Sharper time decay (24-hour half-life)
    hours_old = max(0, (now_utc - pub_utc).total_seconds() / 3600)
    recency_factor = 0.5 ** (hours_old / 24)
    
    # Keyword scoring
    keyword_score = kw_weighted_hits(article.text)
    
    # Semantic scoring with reduced weights
    sem_scores = semantic_scores(article.vector)
    semantic_contribution = (
        sem_scores.get("quality_terms", 0) * 8 +       
        sem_scores.get("business_terms", 0) * 7 +      
        sem_scores.get("growth_terms", 0) * 6 +        
        sem_scores.get("innovation_terms", 0) * 5 +    
        sem_scores.get("governance_terms", 0) * 4          
    )
    
    # Source multiplier
    source_mult = source_weight(article.source_name)
    
    # More balanced final score
    content_score = (
        keyword_score * 1.2 +           # Increased keyword influence
        semantic_contribution           # Reduced semantic influence
    )
    
    return max(1, int(source_mult * content_score * recency_factor))