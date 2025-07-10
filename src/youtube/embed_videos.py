"""
Embed each video's transcript (or description) by splitting into
~750-word chunks, encoding with MiniLM, and mean-pooling.
Stores the float32 vector in Video.vector.
"""

import numpy as np, sqlalchemy as sa
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from src.models import Video
from src.youtube.youtube_utils import get_video_transcript
import time

EMB_MODEL       = "sentence-transformers/all-MiniLM-L6-v2"
MAX_WORDS_CHUNK = 750      # ≈512 tokens
MAX_CHUNKS      = 6        # first 5 chunks ≈3 750 words
BATCH_SIZE      = 32

model = SentenceTransformer(EMB_MODEL)

def chunk_text(txt: str):
    words = txt.split()
    for i in range(0, len(words), MAX_WORDS_CHUNK):
        yield " ".join(words[i : i + MAX_WORDS_CHUNK])

def main():
    eng = sa.create_engine("sqlite:///newsletter.db")
    with Session(eng) as ssn:
        vids = (
            ssn.query(Video)
               .filter(Video.vector.is_(None))
               .all()
        )
        total = len(vids)
        for i in range(0, total, BATCH_SIZE):
            batch = vids[i : i + BATCH_SIZE]
            texts = []
            for v in batch:
                if v.transcript and v.transcript.strip():
                    txt = v.transcript
                else:
                    time.sleep(3)
                    txt = get_video_transcript(v)  # fetches & writes v.transcript
                chunks = list(chunk_text(txt))[:MAX_CHUNKS] or [txt[:1000]]
                texts.append(chunks)
            # Flatten and encode
            flat_chunks = [c for sub in texts for c in sub]
            vecs        = model.encode(flat_chunks, normalize_embeddings=True)

            # mean-pool back to per-video
            idx = 0
            for v, chunk_list in zip(batch, texts):
                k = len(chunk_list)
                v.vector = (
                    np.mean(vecs[idx : idx + k], axis=0)
                    .astype(np.float32)
                    .tobytes()
                )
                idx += k
            ssn.commit()
            print(f"embedded video {v.title}")
    print(f"✅ embedded {total} videos")

if __name__ == "__main__":
    main()
