import datetime, pathlib
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from premailer import transform
from slugify import slugify
from src.models import Article, Video


TODAY = datetime.date.today()

def load_top_articles(limit=5):
    eng = create_engine("sqlite:///newsletter.db")
    with Session(eng) as ssn:
        return (
            ssn.query(Article)
               .order_by(Article.score.desc())
               .limit(limit)
               .all()
        )

def load_top_videos(limit=3):
    eng = create_engine("sqlite:///newsletter.db")
    with Session(eng) as ssn:
        return (
            ssn.query(Video)
               .filter(Video.summary.isnot(None))
               .order_by(Video.score.desc())
               .limit(limit)
               .all()
        )


def build():
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(enabled_extensions=("html",))
    )
    tpl = env.get_template("newsletter.html.j2")
    articles = load_top_articles()
    # tweets   = load_top_tweets()
    videos = load_top_videos()


    raw_html   = tpl.render(articles=articles, 
                            # tweets=tweets, 
                            videos=videos,
                            date=TODAY)

    html_body  = transform(raw_html)        # inline CSS
    plaintext  = "\n\n".join(
        [f"{a.title}\n{a.summary}\n{a.url}" for a in articles] +
        [f"{v.title}\n{v.summary}\n{v.url}" for v in videos]
        # +
        # [f"{t.title}\n{t.summary}\n{t.url}" for t in tweets]  # not title something else, we need to generate a title then?
    )

    base = f"newsletter_{TODAY}"
    pathlib.Path(f"{base}.html").write_text(html_body,  encoding="utf-8")
    pathlib.Path(f"{base}.txt").write_text(plaintext,  encoding="utf-8")
    print(f"Generated {base}.html & {base}.txt")



if __name__ == "__main__":
    build()
