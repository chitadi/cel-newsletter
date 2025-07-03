from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Article

eng = create_engine("sqlite:///newsletter.db")
ssn = Session(eng)
top_articles = (
    ssn.query(Article)
       .order_by(Article.score.desc())
       .limit(5)
       .all()
)

for art in top_articles:
    print(f"• {art.title}  ({art.score})  -> {art.url}")
