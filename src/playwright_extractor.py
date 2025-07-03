from playwright.sync_api import sync_playwright

def extract_with_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=15000)
        text = page.content()
        browser.close()
        return text
