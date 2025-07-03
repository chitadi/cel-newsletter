#!/usr/bin/env bash
set -euo pipefail

# Load secrets from .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

cd "$(dirname "$0")"  # change to the script's directory (your project root)

# ENV vars (or source from .env)

# 1. Harvest articles
python3 run_harvest.py
python3 -m src.rank
python3 -m src.summarise

# 2. harvest YouTube videos
python3 -m src.youtube_scraper
python3 -m src.youtube_rank
python3 -m src.youtube_summarise

# 3. harvest tweets
# python3 -m src.twitter_scraper
# python3 -m src.twitter_rank
# python3 -m src.twitter_summarise

# 4. Build and send newsletter
python3 -m src.render_newsletter
python3 -m src.smtp_mailer

# python3 -m src.housekeeping