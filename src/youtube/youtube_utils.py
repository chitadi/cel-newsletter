"""
Light‑weight YouTube caption helper *v4* — handles CAPTCHA‑gated videos,
adds cookie support, Tor rotation and bounded retries.

Usage recap
-----------
* **Install yt‑dlp** → `brew install yt-dlp` **or** `pip install -U yt-dlp`
* Export or auto‑extract YouTube cookies so yt‑dlp can bypass the
  “Sign‑in to confirm you’re not a robot” wall.
* Run Tor (`brew services start tor`) so requests go through a clean IP.
* Call `enrich_video_with_transcript(video)` from your ORM pipeline; or
  run the CLI for a quick test:

```bash
python -m src.youtube_utils ids.txt  # one video ID/URL per line
```
This saves `transcripts.json` in the current directory.
"""

from __future__ import annotations

import html
import json
import os
import random
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from yt_dlp import YoutubeDL
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript,
)

# ---------------------------------------------------------------------------
# Config & TOR
# ---------------------------------------------------------------------------

TOR_SOCKS_PORT = 9050  # change to 9150 when using Tor Browser
SOCKS_PROXY = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"
PROXIES = {"http": SOCKS_PROXY, "https": SOCKS_PROXY}
PREFERRED_EN_KEYS = ("en", "en-US", "en-GB", "a.en", "xx")
CAPTION_EXTS = ("vtt", "srt", "srv3", "json3")
MAX_RETRIES_PER_VIDEO = 3

DEBUG = bool(os.getenv("YT_CAPTION_DEBUG", "0"))

# ---------------- Cookie handling ----------------
COOKIE_FILE = Path(os.getenv("YT_COOKIE_FILE"))
if not COOKIE_FILE.exists():
    # Attempt live browser extraction (Chrome/Firefox)
    try:
        import browser_cookie3 as bc3  # type: ignore

        cj = bc3.load(domain_name="youtube.com")
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with COOKIE_FILE.open("w") as fh:
            for c in cj:
                fh.write("\t".join([
                    c.domain,
                    "TRUE" if c.domain.startswith(".") else "FALSE",
                    c.path,
                    "TRUE" if c.secure else "FALSE",
                    str(int(c.expires or 0)),
                    c.name,
                    c.value,
                ]) + "\n")
        if DEBUG:
            print(f"[cookies] extracted fresh cookies to {COOKIE_FILE}")
    except Exception:
        if DEBUG:
            print("[cookies] no cookies available; continuing without")
        COOKIE_FILE = None  # disable cookie use

# ---------------------------------------------------------------------------
# yt‑dlp base options
# ---------------------------------------------------------------------------

YDL_OPTS = {
    "skip_download": True,
    "quiet": not DEBUG,
    "proxy": SOCKS_PROXY,
    "nocheckcertificate": True,
}
if COOKIE_FILE and COOKIE_FILE.exists():
    YDL_OPTS["cookiefile"] = str(COOKIE_FILE)
    if DEBUG:
        print(f"[yt-dlp] using cookies from {COOKIE_FILE}")
else:
    # Fall back to live browser extraction during yt-dlp run
    # Equivalent to CLI flag --cookies-from-browser chrome
    YDL_OPTS["cookiesfrombrowser"] = "chrome"
    if DEBUG:
        print("[yt-dlp] will load cookies from Chrome at runtime")

# ---------------- Tor rotation helper ----------------
try:
    from stem import Signal  # type: ignore
    from stem.control import Controller  # type: ignore

    def _rotate_tor_identity(password: str | None = None) -> None:
        """Send NEWNYM to Tor control port → new exit IP."""
        with suppress(Exception):
            with Controller.from_port(port=9051) as ctl:
                ctl.authenticate(password=password)
                ctl.signal(Signal.NEWNYM)
                if DEBUG:
                    print("[Tor] NEWNYM → IP rotated")
except ModuleNotFoundError:

    def _rotate_tor_identity(password: str | None = None):  # type: ignore
        return

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_caption_payload(raw: str) -> str:
    """Convert caption payload (.json3/.srv3/.vtt/.srt) → plain text."""
    if raw.lstrip().startswith("{"):
        try:
            obj = json.loads(raw)
            return "\n".join(html.unescape(seg["utf8"]) for ev in obj["events"]
                                    if "segs" in ev for seg in ev["segs"] if seg.get("utf8"))
        except Exception:
            return ""

    lines: List[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln and not ln.isdigit() and "-->" not in ln and not ln.lower().startswith("webvtt"):
            lines.append(ln)
    return "\n".join(lines)


def _pick_caption(info: dict) -> Optional[dict]:
    pool = {}
    for key in PREFERRED_EN_KEYS:
        for track in info.get("subtitles", {}).get(key, []) + info.get("automatic_captions", {}).get(key, []):
            ext = track.get("ext")
            if ext in CAPTION_EXTS and ext not in pool:
                pool[ext] = track
    for ext in CAPTION_EXTS:  # priority order
        if ext in pool:
            return pool[ext]
    return None


def _fetch_transcript_ytdlp(video_id: str, attempt: int = 0) -> Optional[str]:
    if attempt >= MAX_RETRIES_PER_VIDEO:
        return None
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception as exc:
        if DEBUG:
            print(f"[yt-dlp] info error: {exc}")
        _rotate_tor_identity()
        return _fetch_transcript_ytdlp(video_id, attempt + 1)

    cap = _pick_caption(info)
    if not cap:
        if DEBUG:
            print("[yt-dlp] no suitable captions found")
        return None

    try:
        time.sleep(random.uniform(3, 6))
        r = requests.get(cap["url"], proxies=PROXIES, timeout=30)
        if r.status_code in {403, 429}:
            if DEBUG:
                print(f"[yt-dlp] {r.status_code} – rotate & retry ({attempt + 1})")
            _rotate_tor_identity()
            time.sleep(5)
            return _fetch_transcript_ytdlp(video_id, attempt + 1)
        if r.status_code != 200:
            if DEBUG:
                print(f"[yt-dlp] caption GET {r.status_code}")
            return None
        return _strip_caption_payload(r.text)
    except Exception as exc:
        if DEBUG:
            print(f"[yt-dlp] download error: {exc}")
        _rotate_tor_identity()
        return _fetch_transcript_ytdlp(video_id, attempt + 1)


def _fetch_transcript_ytapi(video_id: str) -> Optional[str]:
    # First try preferred English keys → then any language → then auto‑translate.
    for langs in (PREFERRED_EN_KEYS, ()):  # empty tuple means “any”
        try:
            data = YouTubeTranscriptApi.fetch(video_id, languages=list(langs), proxies=PROXIES)
            if data:
                return "\n".join(chunk["text"].strip() for chunk in data if chunk["text"].strip())
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except CouldNotRetrieveTranscript:
            _rotate_tor_identity()
            time.sleep(5)
            continue
    # auto‑translate generated ASR to English
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id, proxies=PROXIES)
        gen = transcripts.find_generated_transcript(transcripts._languages)
        data = gen.translate("en").fetch()
        return "\n".join(chunk["text"].strip() for chunk in data if chunk["text"].strip())
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_video_with_transcript(video):
    """Populate `video.transcript` if empty and return the text used."""
    if getattr(video, "transcript", None):
        return video.transcript

    text = _fetch_transcript_ytdlp(video.video_id)
    source = "yt-dlp"

    if not text:
        text = _fetch_transcript_ytapi(video.video_id)
        source = "transcript-api"

    if not text:
        text = getattr(video, "description", "") or ""
        source = "description"

    video.transcript = text
    print(f"✓ {source} for {video.title}" if text else f"→ no captions for {video.title}")
    return text

# Legacy alias
get_video_transcript = enrich_video_with_transcript

# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def refresh_transcripts(videos: Iterable):
    """Iterate through `videos` collection, enrich missing transcripts."""
    for v in videos:
        time.sleep(random.uniform(2, 4))
        try:
            enrich_video_with_transcript(v)
        except Exception as exc:
            print(f"✗ {v.title}: {exc}")
        processed += 1
        if processed % 10 == 0:
            _rotate_tor_identity()
            time.sleep(5)
