
import os
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
