"""
Configuration management
=======================
Loads settings from environment variables (.env file).
All sensitive keys are read here — never hardcode them!
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Database (Neon) ----------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@host/dbname",  # Replace with your Neon URL
)

# ---------- Google OAuth ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback",
)

# ---------- Mailgun ----------
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")
MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL", "noreply@yourdomain.com")

# ---------- JWT Settings ----------
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-to-a-random-secret-string")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 1 week

# ---------- Frontend URL ----------
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ---------- Startup checks ----------
def validate_settings() -> list[str]:
    """Return a list of human-readable problems with the current config.

    Called on startup so a missing key produces one clear message instead of an
    obscure failure deep inside a request handler.
    """
    problems = []

    if "user:password@host" in DATABASE_URL:
        problems.append(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and paste your Neon connection string."
        )

    if not GOOGLE_CLIENT_ID:
        problems.append("GOOGLE_CLIENT_ID is missing (Google sign-in will not work).")
    if not GOOGLE_CLIENT_SECRET:
        problems.append("GOOGLE_CLIENT_SECRET is missing (Google sign-in will not work).")

    if not MAILGUN_API_KEY:
        problems.append("MAILGUN_API_KEY is missing (order receipts will not be emailed).")
    if "yourdomain.com" in MAILGUN_FROM_EMAIL:
        problems.append("MAILGUN_FROM_EMAIL is still the placeholder value.")

    if JWT_SECRET == "change-this-to-a-random-secret-string":
        problems.append("JWT_SECRET is using the placeholder value. Set a random string.")

    return problems
