#!/usr/bin/env bash
set -euo pipefail

# Load secrets from .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

cd "$(dirname "$0")"  # change to the script's directory (your project root)

# ENV vars (or source from .env)

# 1. Harvest articles
python3 -m src.articles.run_harvest.py
python3 -m src.articles.embed_articles
python3 -m src.articles.rank
python3 -m src.articles.summarise

# 2. harvest YouTube videos
python3 -m src.youtube.youtube_scraper
python3 -m src.youtube.embed_videos
python3 -m src.youtube.youtube_rank
python3 -m src.youtube.youtube_summarise

# 3. Build and send newsletter
python3 -m src.render_newsletter
python3 -m src.smtp_mailer

python3 -m src.housekeeping