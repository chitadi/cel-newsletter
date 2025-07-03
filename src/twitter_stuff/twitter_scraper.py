import csv, datetime as dt, os, time, yaml, requests
from dotenv import load_dotenv
from urllib.parse import urljoin
from sqlalchemy.orm import Session
from src.models import Tweet
import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from typing import Optional

UTC = dt.timezone.utc
LOBSTR_BASE = "https://api.lobstr.io/v1/"
CRAWLER_HASH = "9d6b83aaf1ae9d5b4a775d223e3eb5df"  # from Lobstr

load_dotenv()
LOBSTR_KEY  = os.getenv("LOBSTR_API_KEY")
X_AUTH_TOKEN= os.getenv("TWITTER_AUTH_TOKEN")
X_CT0       = os.getenv("TWITTER_CT0")

HEADERS = {
    "Authorization": f"Token {LOBSTR_KEY}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

# ===== utilities for keeping / deleting the squid =========
_SQUID_FILE = "squid_id.txt"

def _save_squid_id(squid_id: str):
    if not squid_id:
        raise ValueError("Empty squid_id cannot be saved")
    with open(_SQUID_FILE, "w") as f:
        f.write(squid_id)

def _load_squid_id() -> Optional[str]:
    if os.path.exists(_SQUID_FILE):
        return open(_SQUID_FILE).read().strip()
    return None

def _delete_squid_id_file():
    if os.path.exists(_SQUID_FILE):
        os.remove(_SQUID_FILE)

def _ensure_squid() -> str:
    """
    Re-use an existing squid if we created one earlier;
    otherwise create a new one and store its id.
    """
    sid = _load_squid_id()
    if sid:
        return sid                     # <- reuse slot, no 400

    # first run: really create it
    # payload = {"crawler": CRAWLER_HASH, "name": "timeline-squid"}
    # payload = {"type": "twitter-sync",
    #            "cookies": {"auth_token": X_AUTH_TOKEN, "ct0": X_CT0}}
    # sid = _lobstr("POST", "squids", json=payload)["id"]
    payload = {"type": "twitter-sync",
               "cookies": {"auth_token": X_AUTH_TOKEN, "ct0": X_CT0},
               "crawler": CRAWLER_HASH,
               "name": "timeline-squid"}
    resp    = requests.post(
                 urljoin(LOBSTR_BASE, "squids"),
                 headers=HEADERS,
                 json=payload,
                 timeout=30)

    print("CREATE squid status:", resp.status_code)
    print("CREATE squid body  :", resp.text[:300])

    resp.raise_for_status()
    body = resp.json() if resp.text else {}
    sid  = body.get("id")
    if not sid:
        raise RuntimeError("Lobstr didn't return an 'id'; aborting.")
    
    # sync_id = _lobstr("POST", "accounts/cookies", json=payload)["id"]
    # _lobstr("GET", f"synchronize/{sid}")       # marks it active

    _save_squid_id(sid)
    return sid


def _lobstr(method, endpoint, **kw):
    url  = urljoin(LOBSTR_BASE, endpoint)
    resp = requests.request(method, url, headers=HEADERS, **kw, timeout=30)
    if resp.status_code >= 400:
        print(f"🟥 {method} {url} – {resp.status_code}")
        print("🟥 Response:", resp.text[:500])   # show first 500 bytes
    resp.raise_for_status()
    return resp.json()

def _run_crawler(handles)-> tuple[str, str]:
    squid_id = _ensure_squid()

    _lobstr(                   # this is a PATCH-style “update squid”
        "POST",
        f"squids/{squid_id}",
        json={"params": {"max_results": 10}}   # ← pick any number you need
    )

    payload = {                       # <-- top-level
        "tasks": [{
            'username': h}
        for h in handles],
        "squid": squid_id
    }
    _lobstr("POST", "tasks", json=payload)


    run_id = _lobstr("POST", "runs", json={"squid": squid_id})["id"]

    # poll until done
    while True:
        stats = _lobstr("GET", f"runs/{run_id}/stats")
        if stats["is_done"]:
            break
        print(f"… {stats['percent_done']} %")
        time.sleep(4)

    # download CSV
    s3   = _lobstr("GET", f"runs/{run_id}/download")["s3"]
    data = requests.get(s3, timeout=60)
    data.raise_for_status()

    tmp = "tweets_raw.csv"
    with open(tmp, "wb") as f:
        f.write(data.content)
    return squid_id, tmp                                             # path to CSV

def fetch_tweets(db: Session, horizon_hours=72):
    cutoff = dt.datetime.now(tz=UTC) - dt.timedelta(hours=horizon_hours)

    handles = yaml.safe_load(open("twitter_accounts.yaml"))["twitter_handles"]
    handles = [h.lower().lstrip("@") for h in handles]

    # _sync_account()
    squid_id, csv_path = _run_crawler(handles)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            created = dt.datetime.fromisoformat(row["created_at"].rstrip("Z")).replace(tzinfo=UTC)
            if created < cutoff:
                continue

            tid = row["tweet_id"]
            if db.query(Tweet).get(tid):
                continue

            tweet = Tweet(
                id            = tid,
                handle        = row["author_handle"].lstrip("@"),
                url           = f"https://twitter.com/{row['author_handle']}/status/{tid}",
                text          = row["full_text"],
                created_at    = created,
                like_count    = int(row.get("favorite_count", 0)),
                retweet_count = int(row.get("retweet_count", 0)),
                fetched_at    = dt.datetime.utcnow().replace(tzinfo=UTC)
            )
            db.add(tweet)
    db.commit()
    # ----- tidy up squid slot so we never exceed the limit -----
    try:
        _lobstr("DELETE", f"squids/{squid_id}")
    finally:
        _delete_squid_id_file()


def _tweet_id_from_url(url: str) -> str:
    """Extract the numeric tweet ID from a standard tweet URL."""
    return urlparse(url).path.split("/")[-1]

def capture_tweet_screenshot(tweet_url: str, out_dir: str = "screenshots") -> str:
    """
    Render the tweet in a headless Chromium tab, grab only the <article> element,
    and save it to screenshots/<tweet_id>.png.
    Returns the *relative* file path (good for storing in DB).
    """
    tweet_id = _tweet_id_from_url(tweet_url)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{tweet_id}.png")

    # Skip if we already captured it earlier
    if os.path.exists(out_path):
        return out_path

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tweet_url, timeout=0)                 # wait until network idle
        page.wait_for_selector("article", timeout=10000)
        tweet_node = page.query_selector("article")
        tweet_node.screenshot(path=out_path)
        browser.close()

    return out_path

