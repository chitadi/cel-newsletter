import feedparser, hashlib, datetime, pytz, requests
from sqlalchemy.orm import Session
from src.models import Article
from src.articles.article_extractor import extract_text 
from bs4 import BeautifulSoup
import dateutil.parser
import urllib.parse
from playwright.sync_api import sync_playwright

UTC = pytz.utc 

UA = {"User-Agent": "Mozilla/5.0"}

def resolve_google_news_url(url: str) -> str:
    """Resolve Google News redirect URLs to actual article URLs"""
    if "news.google.com/rss/articles" not in url:
        return url
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-web-security']
            )
            
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            print(f"Resolving Google News URL: {url}")
            
            # Navigate and wait for redirects
            response = page.goto(url, timeout=30000, wait_until='networkidle')
            
            if response is None:
                raise Exception("Failed to navigate to Google News URL")
            
            # Wait a bit more for any additional redirects
            page.wait_for_timeout(3000)
            
            final_url = page.url
            browser.close()
            
            print(f"Resolved to: {final_url}")
            return final_url
            
    except Exception as e:
        print(f"Error resolving Google News URL {url}: {str(e)}")
        return url

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
        url = resolve_google_news_url(url)
        if not url:
            print(f"❌ No link found for entry in {source['name']}, skipping")
            continue

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
            text=text,
            fetched_at=datetime.datetime.utcnow(),
            image_url=img
        ))
    db.commit()
