import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from openai import OpenAI
import re, sqlalchemy as sa
from sqlalchemy.orm import Session
from src.models import Article
import time
import random

import re

def clean_summary(text: str) -> str:
    # 1. Remove Markdown formatting (bold, italics, headings, inline code)
    text = re.sub(r'[*_`#]+', '', text)

    # 2. Remove existing Markdown bullets (-, *, + at line start)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)

    # 3. Replace multiple newlines/tabs with a single space
    text = re.sub(r'\s+', ' ', text).strip()

    # 4. Split into sentences using basic punctuation rule
    sentences = re.split(r'(?<=[.!?]) +', text)

    # 5. Strip and filter empty ones
    sentences = [s.strip() for s in sentences if s.strip()]

    # 6. Format with bullets and line breaks
    return "\n\n".join(f"◦ {s}" for s in sentences)


dotenv.load_dotenv()                               

MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free" 
DB  = "newsletter.db"
import textwrap

PROMPT_TMPL = textwrap.dedent("""\
    Please summarize the following article for a general-audience newsletter.

    Format your response as:
    - 3 simple bullet points, each one sentence long, leave a linespace after each bullet point for better readability.
    - Do not use any Markdown formatting (no **bold**, no # headings).
    - Keep the language clear and concise, suitable for mobile reading.

    Example Response:

    Google has unveiled a new AI feature for Gmail aimed at speeding up email replies.
                              
    The update is part of the company’s broader effort to integrate generative AI into its core products.
                              
    Google plans to expand the feature to Docs and Meet next.

    Article to summarise is below:
    ---
    {text}
""")



client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key = os.getenv("OPENROUTER_API_KEY"),
)

ROUNDUP_RE = re.compile(r"\bround[\s-]*up\b", re.I)
COHORT_RE = re.compile(r"\bcohort\b", re.I)


def summarise_batch(limit: int = 5) -> None:
    """Summarise the top <limit> scored, non-duplicate, non-roundup articles."""

    eng = sa.create_engine("sqlite:///newsletter.db")

    with Session(eng) as ssn:

        # 1️⃣  Pull a wider pool (3× limit) sorted by score
        pool = (
            ssn.query(Article)
               .filter(Article.summary.is_(None))
               .order_by(Article.score.desc())
               .limit(limit * 3)
               .all()
        )

        # 3️⃣  Summarise each selected article
        for i, art in enumerate(pool):
            try:
                if ROUNDUP_RE.search(art.title) or COHORT_RE.search(art.title):
                    ssn.delete(art)  # remove roundup articles
                    continue                      # skip roundup articles
    
                snippet = art.text[:6_000]

                completion = client.chat.completions.create(
                    model="x-ai/grok-4-fast:free",
                    messages=[{
                        "role": "user",
                        "content": PROMPT_TMPL.format(text=snippet)
                    }],
                    extra_body={}
                )
                content = completion.choices[0].message.content.strip()
                if not content:
                    print(f"⚠️  Empty summary for: {art.title[:60]}")
                    continue
                art.summary = clean_summary(content)
                # Add delay after each API call (except the last one)
                if i < len(pool) - 1:
                    sleep_time = random.uniform(5, 10)  # 2-4 seconds random delay
                    print(f"💤 Sleeping {sleep_time:.1f}s to avoid rate limits...")
                    time.sleep(sleep_time)

            except Exception as e:
                print(f"❌ LLM error on: {art.title[:60]} – {e}")
                continue

        ssn.commit()   # one commit for all updates
        print(f"✅ summarised {len([a for a in pool if a.summary])} / {limit} articles")

if __name__ == "__main__":
    summarise_batch()
