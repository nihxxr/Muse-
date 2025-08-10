# selenium_scraper.py
import time, json, re
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()

def _extract_from_jsonld(soup: BeautifulSoup):
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") in ("Review", "Product"):
                if it.get("@type") == "Review":
                    body = _clean(it.get("reviewBody") or it.get("description") or "")
                    if len(body.split()) >= 5 and len(body) > 30:
                        out.append(body)
                if it.get("@type") == "Product" and "review" in it:
                    revs = it["review"]
                    if isinstance(revs, dict): revs = [revs]
                    for r in revs or []:
                        body = _clean(r.get("reviewBody") or r.get("description") or "")
                        if len(body.split()) >= 5 and len(body) > 30:
                            out.append(body)
    return out

def _extract_from_selectors(soup: BeautifulSoup):
    out = []
    sels = [
        '[itemprop="reviewBody"]',
        ".jdgm-rev__body",            # Judge.me
        ".spr-review-content",        # Shopify Reviews
        ".okeReviews-reviewText",     # Okendo
        ".yotpo-review-content",      # Yotpo
        ".yotpo-review",
        ".review-content", ".review-text",
        "blockquote",
    ]
    for sel in sels:
        for el in soup.select(sel):
            txt = _clean(el.get_text(" ", strip=True))
            if len(txt.split()) >= 5 and len(txt) > 30:
                out.append(txt)
    return out

def extract_reviews_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    texts.extend(_extract_from_jsonld(soup))
    texts.extend(_extract_from_selectors(soup))
    seen, out = set(), []
    for t in texts:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    return out[:300]

def scrape_js_reviews(url: str, scroll_rounds: int = 6, sleep_sec: float = 1.2):
    """Render the page with Chrome, scroll to load widgets, then extract reviews."""
    opts = uc.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=opts)
    try:
        driver.get(url)
        last_h = 0
        for _ in range(scroll_rounds):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(sleep_sec)
            h = driver.execute_script("return document.body.scrollHeight")
            if h == last_h:
                break
            last_h = h
        html = driver.page_source
    finally:
        driver.quit()
    return extract_reviews_from_html(html)
