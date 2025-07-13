import yaml

def load_sources(path="sources_and_keywords/sources.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def rss_sites(sources):
    return [s for s in sources if s.get("rss")]

def html_sites(sources):
    return [s for s in sources if s["scrape_method"] == "html"]

def api_sites(sources):
    return [s for s in sources if s["scrape_method"] == "api_search"]


main_sources = load_sources()
rss_sites_list = rss_sites(main_sources)
api_sites_list = api_sites(main_sources)
html_sites_list = html_sites(main_sources)
print(f"Loaded {len(main_sources)} sources, {len(html_sites_list)} HTML sites, {len(rss_sites_list)} RSS sites, and {len(api_sites_list)} API sites.")

