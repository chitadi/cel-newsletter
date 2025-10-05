import os, textwrap, dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from openai import OpenAI
import google.generativeai as genai
from src.models import Video
from src.articles.summarise import clean_summary

dotenv.load_dotenv()                               

MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free" 
DB  = "newsletter.db"

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

# Configure Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

# Configure OpenRouter as fallback
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def get_summary_gemini(text: str) -> str:
    try:
        response = gemini_model.generate_content(PROMPT_TMPL.format(text=text))
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

def summarise_batch(limit: int = 1) -> None:
    eng = create_engine("sqlite:///newsletter.db")

    with Session(eng) as ssn:
        vids = ssn.scalars(
            select(Video)
            .where(Video.summary.is_(None))
            .order_by(Video.score.desc())
            .limit(limit)
        ).all()

        for i, v in enumerate(vids):
            content_text = v.transcript or v.description
            snippet = content_text[:10000]
            
            # Try Gemini first
            summary = get_summary_gemini(snippet)
            
            # Fallback to OpenRouter if Gemini fails
            if not summary:
                print(f"🔄 Falling back to OpenRouter for: {v.title[:60]}")
                summary = get_summary_openrouter(snippet)
            
            if not summary:
                print(f"⚠️ Both APIs failed for: {v.title[:60]}")
                continue
            
            v.summary = clean_summary(summary)
            ssn.commit()
            print(f"summarised → {v.title[:60]}")
  
if __name__ == "__main__":
    summarise_batch()