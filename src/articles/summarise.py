import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from openai import OpenAI
import re, sqlalchemy as sa
from sqlalchemy.orm import Session
from src.models import Article
import time
import random
from google import genai

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

DB  = "newsletter.db"

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

# Configure Gemini client
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Configure OpenRouter as fallback
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

ROUNDUP_RE = re.compile(r"\bround[\s-]*up\b", re.I)
COHORT_RE = re.compile(r"\bcohort\b", re.I)

def get_summary_gemini(text: str) -> str:
    """Try to get summary using Gemini API."""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=PROMPT_TMPL.format(text=text)
        )
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini API error: {e}")
        return None

def get_summary_openrouter(text: str) -> str:
    """Fallback to OpenRouter API."""
    try:
        completion = openrouter_client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{
                "role": "user",
                "content": PROMPT_TMPL.format(text=text)
            }],
            extra_body={}
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ OpenRouter API error: {e}")
        return None
    
def summarise_batch(limit: int = 5) -> None:
    """Summarise the top <limit> scored, non-duplicate, non-roundup articles."""

    eng = sa.create_engine("sqlite:///newsletter.db")

    with Session(eng) as ssn:
        # Pull a wider pool (3× limit) sorted by score
        pool = (
            ssn.query(Article)
               .filter(Article.summary.is_(None))
               .order_by(Article.score.desc())
               .limit(limit * 3)
               .all()
        )

        # Summarise each selected article
        for i, art in enumerate(pool):
            try:
                if ROUNDUP_RE.search(art.title) or COHORT_RE.search(art.title):
                    ssn.delete(art)
                    continue
    
                snippet = art.text[:6_000]

                # Try Gemini first
                content = get_summary_gemini(snippet)
                
                # Fallback to OpenRouter if Gemini fails
                if not content:
                    print(f"🔄 Falling back to OpenRouter for: {art.title[:60]}")
                    content = get_summary_openrouter(snippet)
                
                if not content:
                    print(f"⚠️ Both APIs failed for: {art.title[:60]}")
                    continue
                
                art.summary = clean_summary(content)
                
                # Add delay after each API call
                if i < len(pool) - 1:
                    sleep_time = random.uniform(5, 10)
                    print(f"💤 Sleeping {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

            except Exception as e:
                print(f"❌ Error on: {art.title[:60]} – {e}")
                continue

        ssn.commit()
        print(f"✅ summarised {len([a for a in pool if a.summary])} / {limit} articles")

if __name__ == "__main__":
    summarise_batch()
