"""Prompt building, Groq generation and parsing of the returned script."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

SYSTEM = "You are a senior D2C copywriter. Tone: playful, cheeky, premium. Tasteful and inclusive."
SECTIONS = ("HEADLINE", "HOOK", "BODY", "CTA")


def build_prompt(product: str, themes: List[Dict], phrases: List[str], sentiment: Dict) -> str:
    theme_lines = "\n".join(f"- {', '.join(t['terms'])}: \"{t['example']}\"" for t in themes)
    dist = sentiment.get("distribution", {})
    return (
        f"Write a short ad script for the product: {product}.\n"
        "Base it only on what real customers said below. No explicit claims, no medical claims.\n\n"
        f"Themes from reviews:\n{theme_lines or '- (none)'}\n\n"
        f"Phrases customers used: {', '.join(phrases) or '(none)'}\n"
        f"Sentiment: average {sentiment.get('avg')}, "
        f"{dist.get('pos', 0)} positive, {dist.get('neu', 0)} neutral, {dist.get('neg', 0)} negative\n\n"
        "Return exactly this format and nothing else:\n"
        "HEADLINE: <max 8 words>\n"
        "HOOK: <1 to 2 lines>\n"
        "BODY:\n- <benefit, feeling or social proof>\n- <...>\n- <...>\n"
        "CTA: <max 10 words>"
    )


def parse_script(text: str) -> Optional[Dict]:
    """Pull HEADLINE/HOOK/BODY/CTA out of model output. Returns None if the format didn't hold."""
    if not text:
        return None
    clean = text.replace("**", "")
    pattern = re.compile(r"^\s*(HEADLINE|HOOK|BODY|CTA)\s*:\s*", re.IGNORECASE | re.MULTILINE)
    parts = pattern.split(clean)
    found: Dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        found[parts[i].upper()] = parts[i + 1].strip()
    if not all(k in found for k in ("HEADLINE", "CTA")):
        return None
    body = [re.sub(r"^[\-•*\d.)\s]+", "", line).strip() for line in found.get("BODY", "").splitlines()]
    return {
        "headline": found["HEADLINE"].strip('"'),
        "hook": found.get("HOOK", ""),
        "body": [b for b in body if b],
        "cta": found["CTA"].strip('"'),
    }


class Generator:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = None
        if api_key:
            from groq import Groq

            self.client = Groq(api_key=api_key)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def write(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
