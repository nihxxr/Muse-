
# MyMuse AI Copywriter (Production-Ready)

Generate high‑converting scripts (Headline / Hook / Body / CTA) from **real MyMuse reviews**.
Includes **email login/signup**, polished **dark UI**, robust scraping + NLP, and optional **OpenAI** integration.

## Quick Start (Windows 11, VS Code)
1. Open folder in VS Code
2. Create venv
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install deps
   ```bash
   pip install -r requirements.txt
   ```
4. (Optional) set OpenAI key
   ```bash
   set OPENAI_API_KEY=sk-...
   ```
5. Run
   ```bash
   python app.py
   ```
   Visit http://localhost:8000

## Usage
- Sign up (email + password), then log in.
- On Dashboard: enter a **MyMuse product URL** or **paste reviews** (one per line).
- Click **Generate**. You’ll see analysis + AI script (if key set).
- Download JSON or Copy the script.

## Env Vars
- SECRET_KEY — Flask session key
- DATABASE_URL — defaults to sqlite:///app.db
- OPENAI_API_KEY — enable generation
