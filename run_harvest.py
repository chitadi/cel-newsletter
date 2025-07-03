import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.registry import load_sources, rss_sites
from src.rss_scraper import fetch_rss
from src.html_scraper import fetch_html
from src.registry import load_sources, html_sites 
# from twitter_stuff.twitter_scraper import fetch_tweets

def main():
    engine = create_engine("sqlite:///newsletter.db")
    Session = sessionmaker(bind=engine)
    session = Session()

    sources = load_sources("sources.yaml")
    for src in rss_sites(sources):
        print(f"Fetching RSS feed from {src['name']} …")
        try:
            fetch_rss(src, session)
        except Exception as e:
            print(f"Error on {src['name']}: {e}")

    for src in html_sites(sources):
        print(f"Scraping HTML from {src['name']}")
        try:
            fetch_html(src, session)
        except Exception as e:
            print(f"Error on {src['name']}: {e}")  

    # # for src in twitter_accounts(sources):
    # print(f"Fetching tweets …")
    # try:
    #     fetch_tweets(session)
    # except Exception as e:
    #     print(f"Error fetching tweets for: {e}")
    
    session.close()
    print("Harvest complete")

if __name__ == "__main__":
    main()
