import feedparser, hashlib, datetime, pytz, requests
from sqlalchemy.orm import Session
from src.models import Article
from src.articles.article_extractor import extract_text 
from bs4 import BeautifulSoup
import dateutil.parser
from src.articles.rss_scraper_utils import fetch_with_selenium_stealth, resolve_google_news_url

UTC = pytz.utc 

UA = {"User-Agent": "Mozilla/5.0"}

def fetch_rss(source: dict, db: Session, horizon_hours=24):
    cutoff = datetime.datetime.now(tz=UTC) - datetime.timedelta(hours=horizon_hours)
    feed = feedparser.parse(source["feed_url"])
    
    for entry in feed.entries:
        img = None
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            # Normal case (RFC822 etc.)
            published = datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        else:
            # Fallback to raw string
            raw_date = getattr(entry, "published", None) or entry.get("pubDate")
            if raw_date:
                try:
                    published = dateutil.parser.parse(raw_date)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=UTC)
                    print(f"⚠️ Fallback date parse for {source['name']}: {raw_date}")
                except Exception as e:
                    print(f"❌ Failed to parse date for {source['name']}: {raw_date} ({e})")
                    continue
            else:
                print(f"❌ No date found for entry in {source['name']}, skipping")
                continue

        if published < cutoff:
            continue
            
        # --- URL handling ---
        url = getattr(entry, "link", None)
        url = resolve_google_news_url(url)
        if not url:
            print(f"❌ No link found for entry in {source['name']}, skipping")
            continue

        aid = hashlib.sha256(url.encode()).hexdigest()
        if db.query(Article).get(aid):
            continue

        html = requests.get(url, headers=UA, timeout=10).text
        text = extract_text(html, url)

        if not text or len(text) < 200:
            print(f"⚠️ Extracted text too short ({len(text) if text else 0}) for {url}, trying Selenium...")
            html = fetch_with_selenium_stealth(url)
            if html:
                text = extract_text(html, url)
            else:
                print(f"❌ Selenium fetch failed for {url}, sticking to whatever was there before")

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
        
        if entry.description:
            if len(text) < len(entry.description):
                text = entry.description

        db.add(Article(
            id=aid,
            source_name=source["name"],
            url=url,
            title=entry.title,
            published_at=published,
            text=text,
            fetched_at=datetime.datetime.utcnow(),
            image_url=img
        ))
    db.commit()
