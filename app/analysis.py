"""Review analysis: sentiment (VADER), key phrases (TF-IDF) and themes (k-means)."""

from __future__ import annotations

import re
from typing import Dict, List

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

MIN_WORDS = 5
_sia = SentimentIntensityAnalyzer()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def usable(reviews: List[str]) -> List[str]:
    seen, out = set(), []
    for r in reviews or []:
        r = clean(r)
        if len(r.split()) >= MIN_WORDS and r.lower() not in seen:
            seen.add(r.lower())
            out.append(r)
    return out


def sentiment(reviews: List[str]) -> Dict:
    """Average compound score plus counts of positive, neutral and negative reviews."""
    docs = usable(reviews)
    dist = {"pos": 0, "neu": 0, "neg": 0}
    if not docs:
        return {"avg": 0.0, "distribution": dist}
    total = 0.0
    for r in docs:
        s = _sia.polarity_scores(r)["compound"]
        total += s
        dist["pos" if s >= 0.05 else "neg" if s <= -0.05 else "neu"] += 1
    return {"avg": round(total / len(docs), 3), "distribution": dist}


def phrases(reviews: List[str], k: int = 10) -> List[str]:
    """Top unigrams and bigrams by mean TF-IDF weight. Drops unigrams already inside a kept bigram."""
    docs = usable(reviews)
    if not docs:
        return []
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=2000)
    X = vec.fit_transform(docs)
    weights = X.mean(axis=0).A1
    ranked = sorted(zip(vec.get_feature_names_out(), weights), key=lambda p: p[1], reverse=True)
    corpus = " ".join(d.lower() for d in docs)
    picked: List[str] = []
    for term, _ in ranked:
        if len(term) <= 2:
            continue
        # TF-IDF drops stop words, so "quiet yet powerful" yields "quiet powerful".
        # Keep a bigram only if customers wrote it that way.
        if " " in term and not re.search(r"\b" + re.escape(term) + r"\b", corpus):
            continue
        picked.append(term)
        if len(picked) == k * 2:
            break
    bigram_words = {w for t in picked if " " in t for w in t.split()}
    out = [t for t in picked if " " in t or t not in bigram_words]
    return out[:k]


def themes(reviews: List[str], n: int = 3) -> List[Dict]:
    """Group reviews into up to n themes. Each theme has its top terms and one representative review."""
    docs = usable(reviews)
    if not docs:
        return []
    n = max(1, min(n, len(docs) // 2 or 1))
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=3000)
    X = vec.fit_transform(docs)
    if n == 1:
        return [{"terms": phrases(docs, 3), "example": docs[0], "size": len(docs)}]

    km = KMeans(n_clusters=n, n_init=10, random_state=42).fit(X)
    terms = vec.get_feature_names_out()
    out = []
    for i in range(n):
        idx = [j for j, label in enumerate(km.labels_) if label == i]
        if not idx:
            continue
        top = [terms[t] for t in km.cluster_centers_[i].argsort()[::-1][:3]]
        # representative = closest review to the centroid
        best = max(idx, key=lambda j: X[j].dot(km.cluster_centers_[i]).item())
        out.append({"terms": top, "example": docs[best], "size": len(idx)})
    return sorted(out, key=lambda t: t["size"], reverse=True)


def highlight(text: str, terms: List[str]) -> List[Dict]:
    """Split text into segments, marking case-insensitive whole-word matches of any term."""
    terms = sorted({t for t in terms if t}, key=len, reverse=True)
    if not terms:
        return [{"text": text, "mark": False}]
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)
    out, pos = [], 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append({"text": text[pos:m.start()], "mark": False})
        out.append({"text": m.group(0), "mark": True})
        pos = m.end()
    if pos < len(text):
        out.append({"text": text[pos:], "mark": False})
    return out
