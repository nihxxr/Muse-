# analysis.py
import re, json, requests, nltk, numpy as np
from bs4 import BeautifulSoup
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# Ensure VADER once
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def _clean(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "")).strip()
    return t

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

def scrape(url: str, timeout=20):
    # 1) Try simple requests
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        reviews = extract_reviews_from_html(r.text)
        if reviews:
            return reviews
    except Exception:
        pass  # fall back to selenium

    # 2) Selenium fallback for JS-rendered reviews
    try:
        from selenium_scraper import scrape_js_reviews
        return scrape_js_reviews(url)
    except Exception as e:
        raise RuntimeError(f"Selenium fallback failed: {e}")

# ------- NLP -------
def senti(reviews):
    sia = SentimentIntensityAnalyzer()
    scores = [sia.polarity_scores(r)['compound'] for r in reviews] if reviews else []
    avg = float(np.mean(scores)) if scores else 0.0
    dist = {"pos":0,"neu":0,"neg":0}
    for s in scores:
        if s >= 0.2: dist["pos"] += 1
        elif s <= -0.2: dist["neg"] += 1
        else: dist["neu"] += 1
    return {"avg": round(avg, 3), "distribution": dist}

def phrases(reviews, k=12):
    if not reviews: return []
    v = TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=2000)
    X = v.fit_transform(reviews)
    sc = np.asarray(X.mean(axis=0)).ravel()
    idx = sc.argsort()[::-1][:k]
    return np.array(v.get_feature_names_out())[idx].tolist()

def clusters(reviews, n=3):
    if not reviews: return {}
    n = min(max(1, n), len(reviews))
    v = TfidfVectorizer(stop_words="english", max_features=3000)
    X = v.fit_transform(reviews)
    if n == 1: return {"Theme 1": reviews[:5]}
    model = KMeans(n_clusters=n, n_init=10, random_state=42)
    lab = model.fit_predict(X)
    out = {}
    for i in range(n):
        out[f"Theme {i+1}"] = [reviews[j] for j in range(len(reviews)) if lab[j] == i][:5]
    return out
