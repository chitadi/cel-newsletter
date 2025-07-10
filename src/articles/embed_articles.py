import numpy as np, sqlalchemy as sa
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from src.models import Article

EMB_MODEL      = "sentence-transformers/all-MiniLM-L6-v2"
MAX_WORDS_CHUNK= 750           # ≈512 tokens
MAX_CHUNKS     = 7             # first 5 chunks (~3750 words)

model = SentenceTransformer(EMB_MODEL)

def chunk_article(text):
    words = text.split()
    for i in range(0, len(words), MAX_WORDS_CHUNK):
        yield " ".join(words[i : i + MAX_WORDS_CHUNK])

def main(batch_size=32):
    eng = sa.create_engine("sqlite:///newsletter.db")
    with Session(eng) as ssn:
        pending = (
            ssn.query(Article)
               .filter(Article.vector.is_(None))
               .filter(Article.text.isnot(None))
               .all()
        )
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            # encode each article separately (variable chunk counts)
            for art in batch:
                chunks = list(chunk_article(art.text))[:MAX_CHUNKS]
                emb_mb = (model.encode(chunks, normalize_embeddings=True)
                               .mean(axis=0)
                               .astype(np.float32)
                               .tobytes())
                art.vector = emb_mb
            ssn.commit()
    print(f"✅ embedded {len(pending)} articles")

if __name__ == "__main__":
    main()
