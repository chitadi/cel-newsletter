# src/article_extractor.py

import trafilatura
from urllib.parse import urlparse

def extract_text(html: str, url: str) -> str:
    """
    Given raw HTML and its URL, return the cleaned article text.
    Falls back to a simple BeautifulSoup extract if Trfilatura fails.
    """
    downloaded = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True
    )
    if downloaded and len(downloaded) > 100:
        return downloaded.strip()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    return "\n\n".join(paragraphs).strip()
