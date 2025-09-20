from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import random, requests

def resolve_google_news_url(url: str) -> str:
    if "news.google.com/rss/articles" not in url:
        return url
    
    print(f"🔍 Resolving Google News URL...")
    
    # Try multiple approaches in order
    methods = [
        _try_playwright_enhanced,
        _try_playwright_original
    ]
    
    for i, method in enumerate(methods, 1):
        try:
            print(f"Attempt {i}: {method.__name__}")
            resolved_url = method(url)
            
            if resolved_url and resolved_url != url and _is_valid_resolved_url(resolved_url):
                print(f"✅ Resolved to: {resolved_url}")
                return resolved_url
            else:
                print(f"⚠️ Method {i} returned invalid URL: {resolved_url}")
                
        except Exception as e:
            print(f"❌ Method {i} failed: {e}")
            continue
    
    print(f"🔄 All methods failed, returning original URL")
    return url


def _try_playwright_enhanced(url: str) -> str:
    """Enhanced Playwright approach with Yahoo Finance specific handling"""
    try:
        with sync_playwright() as p:
            # browser = p.chromium.launch(
            #     headless=True,
            #     args=[
            #         '--no-sandbox', 
            #         '--disable-web-security',
            #         '--disable-features=VizDisplayCompositor',
            #         '--disable-dev-shm-usage'
            #     ]
            # )
            browser = p.chromium.launch(
                        headless=True,
                        executable_path='/usr/bin/google-chrome',
                        args=[
                            '--no-sandbox',
                            '--disable-dev-shm-usage', 
                            '--disable-blink-features=AutomationControlled',
                            '--disable-web-security',
                            '--disable-features=VizDisplayCompositor'
                        ]
                    )            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            # Track all navigation events
            final_url = None
            redirect_urls = []
            
            def handle_response(response):
                nonlocal final_url, redirect_urls
                redirect_urls.append(response.url)
                if response.status in [301, 302, 303, 307, 308]:
                    location = response.headers.get('location')
                    if location:
                        redirect_urls.append(location)
                
            def handle_navigation(frame):
                nonlocal final_url
                if frame == page.main_frame:
                    final_url = frame.url
            
            page.on('response', handle_response)
            page.on('framenavigated', handle_navigation)
            
            print(f"📄 Navigating with Playwright...")
            
            # Navigate with longer timeout for Yahoo Finance
            response = page.goto(url, timeout=45000, wait_until='domcontentloaded')
            
            if response is None:
                raise Exception("No response from navigation")
            
            # Wait for potential additional redirects (Yahoo Finance can be slow)
            page.wait_for_timeout(5000)
            
            # Get the final URL
            current_url = page.url
            browser.close()
            
            print(f"📍 Final URL from Playwright: {current_url}")
            print(f"📋 Redirect chain: {' -> '.join(redirect_urls[-3:])}")  # Show last 3
            
            return current_url
            
    except Exception as e:
        print(f"Enhanced Playwright error: {e}")
        return None

def _try_playwright_original(url: str) -> str:
    """Your original Playwright approach as fallback"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-web-security']
            )
            
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            response = page.goto(url, timeout=30000, wait_until='networkidle')
            
            if response is None:
                raise Exception("Failed to navigate to Google News URL")
            
            page.wait_for_timeout(3000)
            final_url = page.url
            browser.close()
            
            return final_url
            
    except Exception:
        return None

def _is_valid_resolved_url(url: str) -> bool:
    """Check if the resolved URL is valid and not a Google News URL"""
    if not url:
        return False
    
    # Should not still be a Google News URL
    if "news.google.com" in url:
        return False
    
    # Should be a proper HTTP/HTTPS URL
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Should have a valid domain
    try:
        parsed = urlparse(url)
        if not parsed.netloc or len(parsed.netloc) < 4:
            return False
    except:
        return False
    
    return True

def fetch_with_selenium_stealth(url):
    """Use regular Selenium with stealth modifications"""
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Optional: run headless
    options.add_argument('--headless')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        print("Loading with Selenium...")
        driver.get(url)
        
        # Random delay to seem more human
        time.sleep(random.uniform(2, 5))
        
        html = driver.page_source
        
        if "Please enable JS" in html:
            return None
        
        return html
        
    except Exception as e:
        return None, str(e)
    finally:
        if driver:
            driver.quit()