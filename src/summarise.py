import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import openai 
from openai import OpenAI

from src.models import Article
import re

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

    Example:

    Google has unveiled a new AI feature for Gmail aimed at speeding up email replies.
                              
    The update is part of the company’s broader effort to integrate generative AI into its core products.
                              
    Google plans to expand the feature to Docs and Meet next.

    Article:
    ---
    {text}
""")



client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key = os.getenv("OPENROUTER_API_KEY"),
)

# better idea just to summarise top 5?
def summarise_batch(limit: int = 4) -> None:
    """Fill `summary` for up to <limit> unsummarised rows (highest score first)."""
    eng = create_engine("sqlite:///newsletter.db")
    
    with Session(eng) as ssn:
        to_do = (
            ssn.scalars(
                select(Article)
                .where(Article.summary.is_(None))
                .group_by(Article.url)
                .order_by(Article.score.desc())
                .limit(limit)
            )
            .all()
        )

        for art in to_do:
            snippet = art.text[:6000]

            try:
                completion = client.chat.completions.create(
                extra_body={},
                model="deepseek/deepseek-r1-0528:free",
                messages=[
                    {
                    "role": "user",
                    "content": PROMPT_TMPL.format(text=snippet)
                    }
                ]
                )
                choices = getattr(completion, "choices", None)
                if not choices or not choices[0].message or not choices[0].message.content:
                    print(f"⚠️  No summary returned for {art.title!r}; skipping.")
                    continue
            except Exception as e:
                print(f"❌ summarisation error for {art.title!r}: {e}")
                continue

            raw = choices[0].message.content.strip()
            art.summary = clean_summary(raw)   # or just raw
            ssn.commit()
            print(f"✅ summarised → {art.title[:60]}")

if __name__ == "__main__":
    summarise_batch()
