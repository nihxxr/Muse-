import pytest

from app import SAMPLE_REVIEWS, analysis, copywriter, create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "SCRAPE": lambda url: [],
    })
    return app


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/signup", data={"email": "a@b.co", "password": "longenough"})
    return c


def test_sentiment_counts():
    s = analysis.sentiment(SAMPLE_REVIEWS)
    assert sum(s["distribution"].values()) == len(SAMPLE_REVIEWS)
    assert s["avg"] > 0


def test_phrases_and_themes():
    assert analysis.phrases(SAMPLE_REVIEWS, k=5)
    themes = analysis.themes(SAMPLE_REVIEWS, n=3)
    assert 1 <= len(themes) <= 3
    assert all(t["example"] in SAMPLE_REVIEWS for t in themes)


def test_highlight():
    segs = analysis.highlight("Quiet yet powerful", ["quiet"])
    assert segs[0] == {"text": "Quiet", "mark": True}
    assert "".join(s["text"] for s in segs) == "Quiet yet powerful"


def test_parse_script():
    out = copywriter.parse_script(
        "**HEADLINE:** Quiet. Powerful.\nHOOK: Nobody hears a thing.\nBODY:\n- Discreet box\n- Lasts ages\nCTA: Get yours"
    )
    assert out["headline"] == "Quiet. Powerful."
    assert out["body"] == ["Discreet box", "Lasts ages"]
    assert out["cta"] == "Get yours"
    assert copywriter.parse_script("Here's some copy without structure") is None


def test_landing_and_auth_pages(app):
    c = app.test_client()
    for path in ("/", "/login", "/signup"):
        assert c.get(path).status_code == 200
    assert c.get("/new").status_code == 302


def test_generate_without_key_saves_analysis(client):
    r = client.post("/new", data={"product": "Beat", "pasted": "\n".join(SAMPLE_REVIEWS)})
    assert r.status_code == 302
    page = client.get(r.headers["Location"])
    assert b"What customers said" in page.data
    assert b"No script this time" in page.data
    dl = client.get(r.headers["Location"] + ".json")
    assert dl.json["product"] == "Beat" and dl.json["reviews_count"] == len(SAMPLE_REVIEWS)


def test_generate_with_stub_model(app, client, monkeypatch):
    from app import copywriter as cw

    monkeypatch.setattr(cw.Generator, "enabled", property(lambda self: True))
    monkeypatch.setattr(cw.Generator, "write", lambda self, p: "HEADLINE: Hush\nHOOK: Shh\nBODY:\n- One\nCTA: Buy")
    r = client.post("/new", data={"product": "Beat", "pasted": "\n".join(SAMPLE_REVIEWS)})
    page = client.get(r.headers["Location"])
    assert b"Hush" in page.data and b"Copy script" in page.data


def test_too_few_reviews(client):
    r = client.post("/new", data={"product": "Beat", "pasted": "too short"})
    assert r.status_code == 400 and b"at least 3 reviews" in r.data


def test_scrape_failure_message(client):
    r = client.post("/new", data={"product": "Beat", "url": "https://mymuse.in/products/x"})
    assert b"No reviews came back" in r.data


def test_other_users_cannot_see_scripts(app, client):
    r = client.post("/new", data={"product": "Beat", "pasted": "\n".join(SAMPLE_REVIEWS)})
    loc = r.headers["Location"]
    other = app.test_client()
    other.post("/signup", data={"email": "c@d.co", "password": "longenough"})
    assert other.get(loc).status_code == 404
    assert other.get(loc + ".json").status_code == 404
