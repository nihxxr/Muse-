# generate.py
from __future__ import annotations
from datetime import datetime
from typing import Dict, List


def build_prompt(
    product_name: str,
    themes: Dict[str, List[str]],
    phrases: List[str],
    sentiment: Dict[str, object],
) -> str:
    """
    Build a compact prompt for the copy generator.
    Returns a single formatted string (no f-string backslash pitfalls).
    """
    # Prepare sections safely (avoid expressions like {'\n'.join(...)} inside f-strings)
    theme_lines: List[str] = []
    for k, v in (themes or {}).items():
        example = " | ".join((v or [])[:3]) if v else ""
        theme_lines.append(f"- {k}: {example}")

    theme_text = "\n".join(theme_lines)
    phrases_text = ", ".join((phrases or [])[:10])
    sentiment_text = f"Avg: {sentiment.get('avg')} | Dist: {sentiment.get('distribution')}"

    # Now compose the final prompt
    prompt = (
        "You are a senior D2C copywriter for a playful yet premium brand (MyMuse style).\n"
        f"Write a SHORT script for the product: {product_name}. Tasteful & inclusive; no explicit claims.\n"
        "Themes:\n"
        f"{theme_text}\n"
        f"Phrases: {phrases_text}\n"
        f"Sentiment: {sentiment_text}\n"
        "Return exactly:\n"
        "HEADLINE: <max 8 words>\n"
        "HOOK: <1–2 lines>\n"
        "BODY: <3–5 bullets, benefits/emotions/social proof>\n"
        "CTA: <max 10 words>"
    )
    return prompt


def package_json(
    product_name: str,
    reviews_count: int,
    sentiment: Dict[str, object],
    phrases: List[str],
    themes: Dict[str, List[str]],
    prompt: str,
    ai_copy: str,
) -> Dict[str, object]:
    """
    Package analysis + generation into a JSON‑serializable dict.
    """
    return {
        "product_name": product_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "reviews_count": int(reviews_count or 0),
        "analysis": {
            "sentiment": sentiment or {},
            "phrases": phrases or [],
            "themes": themes or {},
        },
        "prompt": prompt or "",
        "generated": ai_copy or "",
    }
