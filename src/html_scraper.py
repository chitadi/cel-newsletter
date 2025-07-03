import hashlib, datetime, pytz, requests, backoff
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from src.models import Article
from src.url_filters import looks_like_article
from src.date_sniffer import sniff_date, parse_date
from src.article_extractor import extract_text
from src.playwright_extractor import extract_with_playwright 

UTC = pytz.utc
UA = {"User-Agent": "Mozilla/5.0"}

@backoff.on_exception(backoff.expo, Exception, max_tries=5)
def get(url):
    return requests.get(url, headers=UA, timeout=10)

def is_junk_page(text):
    junk_indicators = ["sign in", "log in", "subscribe", "create an account", "cookies", "privacy policy"]
    return any(word in text.lower() for word in junk_indicators)

def fetch_html(source: dict, db: Session, horizon_hours=120):
    # Try requests first; fall back to Playwright if it's JS-rendered
    try:
        html = get(source["url"]).text
        if len(html) < 2000 or "<script" in html.lower():
            raise ValueError("Likely JS-rendered")
    except Exception:
        print(f"⚠️  Using Playwright for landing page: {source['url']}")
        html = extract_with_playwright(source["url"])

    soup = BeautifulSoup(html, "html.parser")


    links = {
        looks_like_article(a.get("href"), source["url"])
        for a in soup.find_all("a")
    }
    links.discard(None)

    cutoff = datetime.datetime.now(tz=UTC) - datetime.timedelta(hours=horizon_hours)
    added = skipped = 0

    for url in links:
        aid = hashlib.sha256(url.encode()).hexdigest()
        if db.get(Article, aid):
            skipped += 1
            continue

        try:
            page = get(url).text
        except Exception as e:
            print("❌ fetch failed:", url, e)
            skipped += 1
            continue

        # Try to detect date from original fetch
        ds = sniff_date(page)
        if not ds:
            skipped += 1
            continue

        published = parse_date(ds)
        if published < cutoff:
            skipped += 1
            continue

        # Extract text via article_extractor
        text = extract_text(page, url)

        # Fallback to Playwright if page looks bad
        if len(text) < 200 or is_junk_page(text):
            print(f"⚠️  fallback to Playwright for: {url}")
            try:
                page = extract_with_playwright(url)
                text = extract_text(page, url)
            except Exception as e:
                print("❌ Playwright failed:", url, e)
                skipped += 1
                continue

        # Final quality check
        if len(text) < 200 or is_junk_page(text):
            skipped += 1
            continue

        soup = BeautifulSoup(page, "html.parser")
        og = soup.find("meta", property="og:image")
        img = og["content"] if og and og.get("content") else None

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title:
            skipped += 1
            continue

        db.add(Article(
            id=aid,
            source_name=source["name"],
            url=url,
            title=title,
            published_at=published,
            html=page,
            text=text,
            fetched_at=datetime.datetime.now(tz=UTC),
            image_url=img
        ))
        added += 1

    db.commit()
    print(f"✅ {source['name']}: {added} added, {skipped} skipped ({len(links)} scanned)")