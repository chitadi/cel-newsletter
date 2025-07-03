from bs4 import BeautifulSoup
from dateutil import parser as dtparse
from dateutil import tz
from typing import Optional
import json

def sniff_date(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    # <meta property="article:published_time">
    t = soup.find("meta", property="article:published_time")
    if t and t.get("content"):
        return t["content"]

    # <time datetime="">
    t = soup.find("time")
    if t and t.get("datetime"):
        return t["datetime"]

    # JSON-LD
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and "datePublished" in data:
                return data["datePublished"]
        except json.JSONDecodeError:
            continue
    return None

def parse_date(datestr: str):
    # return dtparse.parse(datestr).astimezone(dtparse.tz.UTC)

    dt = dtparse.parse(datestr)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.UTC)
    return dt.astimezone(tz.UTC)
