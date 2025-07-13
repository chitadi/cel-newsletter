import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.articles.registry import load_sources, rss_sites
from src.articles.rss_scraper import fetch_rss

def main():
    engine = create_engine("sqlite:///newsletter.db")
    Session = sessionmaker(bind=engine)
    session = Session()

    sources = load_sources("ources_and_keywords/sources.yaml")
    for src in rss_sites(sources):
        print(f"Fetching RSS feed from {src['name']} …")
        try:
            fetch_rss(src, session)
        except Exception as e:
            print(f"Error on {src['name']}: {e}")
    
    session.close()
    print("Harvest complete")

if __name__ == "__main__":
    main()
