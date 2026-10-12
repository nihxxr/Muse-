from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from . import analysis, copywriter
from .models import Generation, User, db
from .scraper import scrape_reviews

SAMPLE_REVIEWS = [
    "Exceeded my expectations. It feels premium and the design is so discreet I leave it on the nightstand.",
    "Made a real difference for us as a couple. Simple to use and really comfortable.",
    "Battery lasts for ages and the build quality is excellent for the price.",
    "The packaging was elegant, it felt like opening a luxury gift rather than an order.",
    "Quiet yet powerful. Worth every rupee and very well made.",
    "Customer support answered my questions without any awkwardness and shipping was quick.",
    "Discreet delivery, no branding on the box, which mattered a lot to me.",
    "Took a while to get used to the settings but now it's my favourite purchase this year.",
    "Silky material, easy to clean, and it charges fast. Would buy again as a gift.",
    "Honestly a bit pricey, but the quality makes up for it and it feels built to last.",
]


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///muse.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        GROQ_API_KEY=os.environ.get("GROQ_API_KEY", ""),
        GROQ_MODEL=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        SCRAPE=scrape_reviews,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    login = LoginManager(app)
    login.login_view = "login"
    login.login_message = "Log in to write copy."

    @login.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    writer = copywriter.Generator(app.config["GROQ_API_KEY"], app.config["GROQ_MODEL"])
    app.jinja_env.globals["highlight"] = analysis.highlight
    app.jinja_env.globals["ai_enabled"] = writer.enabled

    # --- pages ------------------------------------------------------------

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("new"))
        return render_template("main/landing.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            pw = request.form.get("password") or ""
            if "@" not in email or len(pw) < 8:
                flash("Enter a valid email and a password of at least 8 characters.", "error")
                return render_template("auth/signup.html", email=email), 400
            if User.query.filter_by(email=email).first():
                flash("That email already has an account. Log in instead.", "error")
                return redirect(url_for("login"))
            user = User(email=email)
            user.set_password(pw)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("new"))
        return render_template("auth/signup.html")

    @app.route("/login", methods=["GET", "POST"], endpoint="login")
    def login_view():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(request.form.get("password") or ""):
                flash("That email and password don't match.", "error")
                return render_template("auth/login.html", email=email), 401
            login_user(user, remember=True)
            return redirect(request.args.get("next") if (request.args.get("next") or "").startswith("/") else url_for("new"))
        return render_template("auth/login.html")

    @app.get("/logout")
    def logout():
        logout_user()
        return redirect(url_for("home"))

    @app.route("/new", methods=["GET", "POST"])
    @login_required
    def new():
        history = current_user.generations.limit(20).all()
        if request.method == "GET":
            return render_template("main/new.html", history=history, form={}, samples=SAMPLE_REVIEWS)

        form = request.form.to_dict()
        product = (form.get("product") or "").strip()
        url = (form.get("url") or "").strip()
        pasted = form.get("pasted") or ""

        def back(message):
            flash(message, "error")
            return render_template("main/new.html", history=history, form=form, samples=SAMPLE_REVIEWS), 400

        if not product:
            return back("Give the product a name so the copy can mention it.")

        reviews, source = [], "pasted"
        if url:
            try:
                reviews = app.config["SCRAPE"](url)
                source = "url"
            except Exception:  # network, parse or browser errors all mean the same thing here
                reviews = []
        if not reviews:
            reviews = [line for line in pasted.splitlines() if line.strip()]
            source = "pasted"
        reviews = analysis.usable(reviews)

        if len(reviews) < 3:
            if url and not pasted.strip():
                return back("No reviews came back from that page. Its review widget may load in a way the scraper can't read. Paste a few reviews below instead.")
            return back("Add at least 3 reviews, one per line, each 5 words or longer.")

        senti = analysis.sentiment(reviews)
        keys = analysis.phrases(reviews, k=10)
        groups = analysis.themes(reviews, n=3)
        prompt = copywriter.build_prompt(product, groups, keys, senti)

        raw, script, gen_error = "", None, None
        if writer.enabled:
            try:
                raw = writer.write(prompt)
                script = copywriter.parse_script(raw)
            except Exception as exc:
                gen_error = f"Groq request failed: {exc.__class__.__name__}"

        payload = {
            "product": product, "source": source, "url": url,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reviews_count": len(reviews), "reviews": reviews[:40],
            "analysis": {"sentiment": senti, "phrases": keys, "themes": groups},
            "prompt": prompt, "generated": raw, "script": script, "error": gen_error,
        }
        gen = Generation(user_id=current_user.id, product=product, payload=json.dumps(payload))
        db.session.add(gen)
        db.session.commit()
        return redirect(url_for("result", gen_id=gen.id))

    def owned(gen_id: int) -> Generation:
        gen = db.session.get(Generation, gen_id)
        if not gen or gen.user_id != current_user.id:
            abort(404)
        return gen

    @app.get("/g/<int:gen_id>")
    @login_required
    def result(gen_id):
        gen = owned(gen_id)
        return render_template("main/result.html", gen=gen, d=gen.data)

    @app.get("/g/<int:gen_id>.json")
    @login_required
    def download(gen_id):
        gen = owned(gen_id)
        slug = "".join(c if c.isalnum() else "-" for c in gen.product.lower()).strip("-")
        return Response(json.dumps(gen.data, indent=2, ensure_ascii=False), mimetype="application/json",
                        headers={"Content-Disposition": f"attachment; filename=muse-{slug}-{gen.id}.json"})

    @app.post("/g/<int:gen_id>/delete")
    @login_required
    def delete(gen_id):
        gen = owned(gen_id)
        db.session.delete(gen)
        db.session.commit()
        flash(f"Deleted the {gen.product} script.", "info")
        return redirect(url_for("new"))

    @app.errorhandler(404)
    def not_found(_):
        return render_template("main/404.html"), 404

    return app
