import json
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    generations = db.relationship("Generation", backref="user", lazy="dynamic",
                                  order_by="Generation.created_at.desc()")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Generation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    payload = db.Column(db.Text, nullable=False)

    @property
    def data(self) -> dict:
        return json.loads(self.payload)

    @property
    def headline(self) -> str:
        script = self.data.get("script") or {}
        return script.get("headline", "")
