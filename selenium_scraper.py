# selenium_scraper.py
from __future__ import annotations
import os, re, time
from typing import List
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA}

# -------------------- Helpers --------------------

def _dedup(texts: List[str], min_words: int = 5, key_len: int = 200) -> List[str]:
    out, seen = [], set()
    for t in texts:
        t = re.sub(r"\s+", " ", (t or "")).strip()
        if len(t.split()) < min_words:
            continue
        k = t.lower()[:key_len]
        if k not in seen:
            seen.add(k); out.append(t)
    return out

def _extract_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    hits: List[str] = []

    # Okendo (common on MyMuse)
    for sel in [
        ".okeReviews-review-body",
        ".okeReviews-review-content",
        ".okeReviewsReviewContent",
        "[data-oke-review-text]",
    ]:
        for el in soup.select(sel):
            txt = el.get_text(" ", strip=True)
            if len(txt.split()) >= 5:
                hits.append(txt)

    # Generic fallbacks (Judge.me / Shopify Reviews / Stamped / Yotpo)
    for sel in [
        ".jdgm-rev__body, .jdgm-rev__content, .jdgm-rev__title",
        ".spr-review-content, .spr-review-body, .spr-review-header-title",
        ".stamped-review-message, .stamped-review-content",
        ".yotpo-review, .yotpo-main .content-review, .yotpo-review-content",
    ]:
        for el in soup.select(sel):
            txt = el.get_text(" ", strip=True)
            if len(txt.split()) >= 5:
                hits.append(txt)

    return _dedup(hits)

# -------------------- Fast (no JS) --------------------

def fetch_static_reviews(url: str, timeout: int = 15) -> List[str]:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return _extract_from_html(r.text)

# -------------------- Selenium (JS + shadow DOM) --------------------

def _collect_reviews_via_js(driver) -> List[str]:
    """
    Traverse normal DOM + open shadow roots and collect review texts
    for common Okendo/Judge.me/Stamped/Yotpo selectors.
    """
    js = r"""
const sels = [
  ".okeReviews-review-body",
  ".okeReviews-review-content",
  ".okeReviewsReviewContent",
  "[data-oke-review-text]",
  ".jdgm-rev__body", ".jdgm-rev__content", ".jdgm-rev__title",
  ".spr-review-content", ".spr-review-body", ".spr-review-header-title",
  ".stamped-review-message", ".stamped-review-content",
  ".yotpo-review", ".yotpo-main .content-review", ".yotpo-review-content"
];

function collectFrom(root) {
  const out = [];
  const stack = [root];
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;

    // If node matches, capture text
    if (node.matches) {
      for (const sel of sels) {
        try {
          if (node.matches(sel)) {
            const t = (node.innerText || "").trim();
            if (t.split(/\s+/).length >= 5) out.push(t);
            break;
          }
        } catch(e) {}
      }
    }

    // Descend into children
    if (node.children) {
      for (const c of node.children) stack.push(c);
    }
    // Traverse open shadow roots
    if (node.shadowRoot) {
      stack.push(node.shadowRoot);
      if (node.shadowRoot.children) {
        for (const c of node.shadowRoot.children) stack.push(c);
      }
    }
  }
  return out;
}

const all = new Set(collectFrom(document));
return Array.from(all);
"""
    try:
        return driver.execute_script(js) or []
    except Exception:
        return []

def scrape_js_reviews(url: str, initial_wait: int = 8, clicks: int = 6) -> List[str]:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    v_env = os.environ.get("UC_VERSION_MAIN")
    v_main = int(v_env) if v_env and v_env.isdigit() else None

    opts = uc.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1366,1100")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"user-agent={UA}")

    driver = uc.Chrome(options=opts, version_main=v_main) if v_main else uc.Chrome(options=opts)

    try:
        driver.get(url)
        # Wait for any Okendo container
        WebDriverWait(driver, 25).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-oke-reviews]")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".okeReviews, .okeReviewsWidget"))
            )
        )
        time.sleep(initial_wait)

        # Try to expand "Load more" several times
        for _ in range(clicks):
            buttons = driver.find_elements(By.CSS_SELECTOR,
                "[data-oke-reviews-more-button], .okeReviews-more, .okeReviews-loadMore, button[aria-label*='More']"
            )
            clicked = False
            for b in buttons:
                try:
                    if b.is_displayed() and b.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", b)
                        time.sleep(0.25)
                        b.click()
                        clicked = True
                        time.sleep(1.8)
                except Exception:
                    pass
            if not clicked:
                break

        # Scroll to trigger any lazy chunks
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.6)

        # Collect via JS across shadow roots
        texts = _collect_reviews_via_js(driver)

        # Fallback: also parse current page source with BeautifulSoup
        if len(texts) < 10:
            from bs4 import BeautifulSoup
            texts += _extract_from_html(driver.page_source)

        return _dedup(texts)[:150]
    finally:
        try:
            driver.quit()
        except Exception:
            pass

# -------------------- Public entry --------------------

def scrape_reviews(url: str, timeout: int = 15) -> List[str]:
    # 1) Fast static pass first
    try:
        revs = fetch_static_reviews(url, timeout=timeout)
        if revs:
            return revs
    except Exception:
        pass

    # 2) JS fallback (unless disabled in env)
    if os.environ.get("DISABLE_SELENIUM") == "1":
        return []
    return scrape_js_reviews(url)
