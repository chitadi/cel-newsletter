from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Article
from datetime import datetime
from dateutil import tz
from src.scoring import article_score

engine = create_engine("sqlite:///newsletter.db")
sess = Session(engine)
now = datetime.now(tz.tz.UTC)

fresh = sess.query(Article).filter(Article.score == None).all()
for art in fresh:
    art.score = int(article_score(art, now))
sess.commit()
