import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import openai 
from openai import OpenAI

from src.models import Tweet
from twitter_stuff.twitter_scraper import capture_tweet_screenshot

dotenv.load_dotenv()                               

MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free" 
DB  = "newsletter.db"
import textwrap

PROMPT_TMPL = textwrap.dedent("""\
    Please create a catchy headline for the following tweet for a general-audience newsletter.

    Format your response as a single line, without any additional text or formatting. Either
    put it forward as an interesting fact, excitement if it is an announcement, or a question
    that would make the reader want to read the tweet.

    Examples:
                              
    OpenAI has announced a one week leave for all its employees to avoid burnout.
           
    Google has unveiled a new AI feature for Gmail aimed at speeding up email replies!
                              
    Is the new AI feature in Gmail going to change how we write emails forever?
    
    Please do not use any hashtags, emojis, or other special characters in the headline.

    Tweet:
    ---
    {text}
""")

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key = os.getenv("OPENROUTER_API_KEY"),
)

def summarise_batch(limit: int = 3) -> None:
    eng = create_engine("sqlite:///newsletter.db")
    
    with Session(eng) as ssn:
        to_do = (
            ssn.scalars(
                select(Tweet)
                .where(Tweet.title.is_(None))
                .group_by(Tweet.url)
                .order_by(Tweet.score.desc())
                .limit(limit)
            )
            .all()
        )

        for t in to_do:
            snippet = t.text

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
            t.title = completion.choices[0].message.content.strip()


         # 2️⃣  Capture screenshot (skip if already present)
            try:
                img_path = capture_tweet_screenshot(t.url)
                t.image_url = img_path                          # store relative path
                print(f"📸  Screenshot saved → {img_path}")
            except Exception as e:
                print(f"⚠️  Could not screenshot {t.url}: {e}")

            ssn.commit()
            print(f"title generated → {t.title}")

            # here e add the tweet screenshot

if __name__ == "__main__":
    summarise_batch()
