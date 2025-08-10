import os
import json
import time
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv

from config import Config
from extensions import db, login_manager
from models import User
from analysis import scrape, senti, phrases, clusters
from generate import build_prompt, package_json

# Load env vars
load_dotenv()

# === Groq setup ===
try:
    from groq import Groq
    groq_client = Groq()  # reads GROQ_API_KEY from .env

    def generate_with_groq(prompt: str) -> str:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a senior D2C copywriter. Tone: playful, cheeky, premium."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
except Exception as e:
    print("Groq not available:", e)
    generate_with_groq = None

# Flask app setup
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)
with app.app_context():
    db.create_all()

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("main/landing.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = (request.form.get("password") or "").strip()

        if not email or not pw:
            flash("Email & password required", "danger")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
            return redirect(url_for("login"))

        u = User(email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        return redirect(url_for("dashboard"))

    return render_template("auth/signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = (request.form.get("password") or "").strip()

        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(pw):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

        login_user(u)
        return redirect(url_for("dashboard"))

    return render_template("auth/login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        product_name = (request.form.get("product_name") or "MyMuse Product").strip()
        url = (request.form.get("url") or "").strip()
        pasted = (request.form.get("pasted") or "").strip()

        reviews = []
        error = None

        if url:
            try:
                reviews = scrape(url)  # requests → selenium fallback
            except Exception as e:
                error = f"Scrape failed: {e}"

        if not reviews and pasted:
            reviews = [r.strip() for r in pasted.split("\n") if len(r.split()) > 4]

        if not reviews and not pasted and error:
            flash(error, "warning")

        if not reviews:
            demo_reviews = [
                "Exceeded expectations — feels premium and the design is discreet.",
                "Made a real difference for us; simple to use and comfortable.",
                "Battery lasts long and the build quality is excellent.",
                "Packaging was elegant; felt like a luxury gift experience.",
                "Quiet yet powerful. Worth the price and very well made.",
                "Customer support was helpful and shipping was quick."
            ]
            reviews = demo_reviews
            flash("No reviews scraped/pasted — using demo reviews.", "info")

        sentiment = senti(reviews)
        key_phrases = phrases(reviews, k=10)
        theme_groups = clusters(reviews, n=3)

        prompt = build_prompt(product_name, theme_groups, key_phrases, sentiment)
        ai_copy = ""

        # Generate with Groq
        if generate_with_groq:
            try:
                ai_copy = generate_with_groq(prompt)
            except Exception as e:
                flash(f"Groq generation failed: {e}", "warning")
        else:
            flash("AI generation is disabled (no Groq key).", "info")

        data = package_json(product_name, len(reviews), sentiment, key_phrases, theme_groups, prompt, ai_copy)
        ts = int(time.time())
        fname = f"output_{ts}.json"
        path = os.path.join("data", fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return render_template("main/result.html", data=data, file=fname)

    return render_template("main/dashboard.html")

@app.route("/download/<fname>")
@login_required
def download(fname):
    path = os.path.join("data", os.path.basename(fname))
    if os.path.exists(path):
        return send_file(path, as_attachment=True, mimetype="application/json", download_name=fname)
    flash("File not found", "danger")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
