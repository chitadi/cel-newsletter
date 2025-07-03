import re
from urllib.parse import urljoin, urlparse

DATE_SLUG  = re.compile(r"/20\d{2}/\d{2}/\d{2}/")          # dated slug
DASH_SLUG  = re.compile(r"/[a-z0-9-]{20,}/?$")             # long dash-separated slug
KEYWORDS   = ("article", "story", "archive", "blog", "news", "post")

def looks_like_article(href: str, base: str):
    if not href or href.startswith("#"):
        return None
    url = urljoin(base, href)
    if urlparse(url).netloc != urlparse(base).netloc:
        return None

    path = urlparse(url).path.lower()
    if DATE_SLUG.search(path):
        return url
    if any(k in path for k in KEYWORDS):
        return url
    if DASH_SLUG.search(path) and path.count("/") >= 2:
        return url
    return None

