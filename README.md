# Muse Copywriter

A Flask app that writes short ad scripts for MyMuse products from real customer reviews. I built it during my product internship at MyMuse.

You give it a product page or paste some reviews. It scores sentiment, pulls out the phrases customers repeat, groups reviews into themes, and asks Llama 3.1 (on Groq) for a headline, hook, three body lines and a call to action. The result page puts the script next to the evidence, with every repeated phrase highlighted in the reviews, so you can check each line of copy against something a customer actually wrote.

## What it does

- **Collects reviews** from a mymuse.in product page. It reads the Okendo widget over plain HTTP first, then falls back to headless Chrome if you install the optional scraping extras. You can always paste reviews instead.
- **Analyses them** with VADER sentiment, TF-IDF key phrases (bigrams only if customers wrote them that way) and k-means themes, each with the review closest to its centre.
- **Writes the script** with Groq and parses it into headline, hook, body and CTA. If the model ignores the format you get its raw answer; if there's no API key you still get the analysis plus the exact prompt to paste elsewhere.
- **Saves every run** to your account. Download any run as JSON, or delete it.

## Project layout

```
app/
  __init__.py      App factory, auth and routes
  analysis.py      Sentiment, phrases, themes, highlight helper
  copywriter.py    Prompt, Groq client, script parser
  scraper.py       Okendo/Shopify review scraper with optional Selenium
  models.py        User and Generation tables (SQLAlchemy)
  templates/       Jinja templates
  static/          CSS, JS, self hosted Bricolage Grotesque and Newsreader
tests/
  test_app.py      Analysis, parsing, routes, access control
wsgi.py
```

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then add your GROQ_API_KEY

python wsgi.py                     # http://localhost:8000
pytest
```

For the headless Chrome fallback, install `requirements-scrape.txt` and remove `DISABLE_SELENIUM=1` from `.env`.

## Deploy

`render.yaml` sets up a Render web service. Add `GROQ_API_KEY` in the dashboard; `SECRET_KEY` is generated for you. SQLite is fine for a demo, but Render's disk resets on deploy, so point `DATABASE_URL` at Postgres to keep accounts and scripts.

## Design notes

The interface works like a copywriter's proof sheet:

- Customer words are set in Newsreader, a text serif, and marked with a yellow highlighter. Anything Muse writes is set in Bricolage Grotesque.
- The highlighter is the one accent that carries meaning. A highlighted phrase means a customer said it, and the same yellow marks the script's bullets and call to action.
- Lilac paper and plum ink sit close to MyMuse's own tone: playful, a little cheeky, still premium.
- Fonts are self hosted, so the app makes no third party requests.

Generated copy is a first draft. Read it before it ships.
