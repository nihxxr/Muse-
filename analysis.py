# analysis.py
from __future__ import annotations
import math
import re
from typing import Dict, List, Tuple

# --- Scraper (MyMuse/Okendo tuned, with JS fallback) ---
from selenium_scraper import scrape_reviews

# --- NLP / ML ---
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


# -------------------- Utils --------------------

def _clean(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t

def _ensure_vader() -> None:
    """
    Make sure VADER lexicon is available. Safe to call multiple times.
    """
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)


# -------------------- Public API --------------------

def scrape(url: str, timeout: int = 20) -> List[str]:
    """
    Return a list of raw review texts from a MyMuse product page.
    Uses fast HTML first; falls back to Selenium if needed.
    """
    return scrape_reviews(url, timeout=timeout)


def senti(reviews: List[str]) -> Dict[str, object]:
    """
    Simple sentiment summary using VADER.
    Returns: {"avg": float, "distribution": {"pos": x, "neu": y, "neg": z}}
    """
    reviews = [_clean(r) for r in (reviews or []) if r and len(r.split()) >= 5]
    if not reviews:
        return {"avg": 0.0, "distribution": {"pos": 0, "neu": 0, "neg": 0}}

    _ensure_vader()
    sia = SentimentIntensityAnalyzer()

    total = 0.0
    dist = {"pos": 0, "neu": 0, "neg": 0}
    for r in reviews:
        s = sia.polarity_scores(r)["compound"]
        total += s
        if s >= 0.05:
            dist["pos"] += 1
        elif s <= -0.05:
            dist["neg"] += 1
        else:
            dist["neu"] += 1

    avg = total / max(len(reviews), 1)
    # Rounded for display
    return {"avg": round(avg, 3), "distribution": dist}


def phrases(reviews: List[str], k: int = 12) -> List[str]:
    """
    Extract top unigrams/bigrams via TF‑IDF across reviews.
    Returns a list of key phrases for prompting / display.
    """
    docs = [_clean(r) for r in (reviews or []) if r and len(r.split()) >= 5]
    if not docs:
        return []

    vec = TfidfVectorizer(
        max_features=2000,
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1
    )
    X = vec.fit_transform(docs)
    # Average tf‑idf weight per feature across docs
    weights = X.mean(axis=0).A1
    feats = vec.get_feature_names_out()
    pairs = sorted(zip(feats, weights), key=lambda x: x[1], reverse=True)
    out = [p[0] for p in pairs[:k]]
    # remove super short tokens
    out = [p for p in out if len(p) > 2]
    return out


def clusters(reviews: List[str], n: int = 3) -> Dict[str, List[str]]:
    """
    Very light clustering of reviews using KMeans on TF‑IDF.
    Returns a dict: {"Theme 1": [bullets...], ...}
    Each theme has a couple of representative phrases/summaries.
    """
    docs = [_clean(r) for r in (reviews or []) if r and len(r.split()) >= 5]
    if not docs:
        return {"Themes (sample reviews)": []}

    # Bound number of clusters
    n = max(1, min(n, len(docs)))
    if n == 1:
        # Just return a couple of compact bullets from the corpus
        return {"Theme 1": _compact_bullets(docs)}

    vec = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), stop_words="english")
    X = vec.fit_transform(docs)

    # Handle small corpora robustly
    try:
        km = KMeans(n_clusters=n, n_init=10, random_state=42)
        km.fit(X)
    except Exception:
        # If KMeans fails (e.g., sparse tiny data), fallback to one theme
        return {"Theme 1": _compact_bullets(docs)}

    terms = vec.get_feature_names_out()
    order_centroids = km.cluster_centers_.argsort()[:, ::-1]

    themes: Dict[str, List[str]] = {}
    for i in range(n):
        label = f"Theme {i+1}"
        # top terms per cluster
        top_terms = [terms[idx] for idx in order_centroids[i, :6]]
        summary = " • ".join(top_terms[:3])
        # pick one representative review (first in cluster)
        reps = [docs[j] for j in range(len(docs)) if km.labels_[j] == i]
        bullet = reps[0] if reps else ""
        themes[label] = [summary, _shorten(bullet)]
    return themes


# -------------------- Internals --------------------

def _shorten(s: str, words: int = 22) -> str:
    toks = s.split()
    if len(toks) <= words:
        return s
    return " ".join(toks[:words]) + "…"

def _compact_bullets(docs: List[str]) -> List[str]:
    if not docs:
        return []
    # Take 2‑3 compact bullets from corpus
    out = []
    for r in docs[:3]:
        out.append(_shorten(r, 20))
    return out
