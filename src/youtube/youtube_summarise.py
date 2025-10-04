import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import openai
from src.models import Video
from src.articles.summarise import clean_summary

dotenv.load_dotenv()                               

MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free" 
DB  = "newsletter.db"
import textwrap

PROMPT_TMPL = textwrap.dedent("""\
    Please summarize the following video for a general-audience newsletter.

    Format your response as:
    - Then 3 bullet points, each one sentence long, leave a linespace after each bullet point for better readability.
    - Do not use any Markdown formatting (no **bold**, no # headings).
    - Keep the language clear and concise, suitable for mobile reading.

    Example:

    Marques Brownlee talks about how Google has unveiled a new AI feature for Gmail aimed at speeding up email replies.
                              
    The update is part of the company’s broader effort to integrate generative AI into its core products.
                              
    Marques discusses Google's plans to expand the feature to Docs and Meet next.
    ---
    {text}
""")

client = openai.OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key = os.getenv("OPENROUTER_API_KEY"),
)

def summarise_batch(limit: int = 1) -> None:
    eng = create_engine("sqlite:///newsletter.db")

    with Session(eng) as ssn:
        vids = ssn.scalars(
            select(Video)
            .where(Video.summary.is_(None))
            .order_by(Video.score.desc())
            .limit(limit)
        ).all()

        for v in vids:
            content = v.transcript or v.description
            snippet = content[:10000]  # keep under context window
            completion = client.chat.completions.create(
            extra_body={},
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {
                "role": "user",
                "content": PROMPT_TMPL.format(text=snippet)
                }
            ]
            )
            v.summary = clean_summary(completion.choices[0].message.content.strip())
            ssn.commit()
            print(f"summarised → {v.title[:60]}")

if __name__ == "__main__":
    summarise_batch()