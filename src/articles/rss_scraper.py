import feedparser, hashlib, datetime, pytz, requests
from sqlalchemy.orm import Session
from src.models import Article
from src.articles.article_extractor import extract_text 
from bs4 import BeautifulSoup

UTC = pytz.utc 

UA = {"User-Agent": "Mozilla/5.0"}

def fetch_rss(source: dict, db: Session, horizon_hours=24):
    cutoff = datetime.datetime.now(tz=UTC) - datetime.timedelta(hours=horizon_hours)
    feed = feedparser.parse(source["feed_url"])
    
    for entry in feed.entries:
        img = None
        if not hasattr(entry, "published_parsed"):
            continue
        published = datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        if published.tzinfo is None:      # some feeds omit tz
            published = published.replace(tzinfo=UTC)
        if published < cutoff:
            continue

        url = entry.link
        aid = hashlib.sha256(url.encode()).hexdigest()
        if db.query(Article).get(aid):
            continue

        html = requests.get(url, headers=UA, timeout=10).text
        text = extract_text(html, url)

        # next bit is for loading images if they exist
        if entry.get("media_content"):
            img = entry.media_content[0].get("url")
        elif entry.get("enclosures"):
            img = entry.enclosures[0].get("href")

        html = requests.get(url, headers=UA, timeout=10).text
        if not img:
            soup = BeautifulSoup(html, "html.parser")

            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                img = og["content"]

            if not img:
                first_img = soup.find("img", src=True)
                if first_img:
                    img = first_img["src"]

        db.add(Article(
            id=aid,
            source_name=source["name"],
            url=url,
            title=entry.title,
            published_at=published,
            html=html,
            text=text,
            fetched_at=datetime.datetime.utcnow(),
            image_url=img
        ))
    db.commit()
