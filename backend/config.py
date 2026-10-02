"""
Configuration management
=======================
Loads settings from environment variables (.env file).
All sensitive keys are read here — never hardcode them!
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Database (Supabase, Neon, or any PostgreSQL) ----------
# Supabase: dashboard -> Project Settings -> Database -> Connection string.
#
# IMPORTANT for Supabase: pick the *Session pooler* or *Transaction pooler*
# string, not the "URI" one. The URI host (db.<ref>.supabase.co) is IPv6-only
# and often simply will not connect from a home network. The pooler host
# (contains "pooler.supabase.com") works over IPv4.
#
#   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
#
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@host/dbname",  # Replace with your database URL
)

# Set to false only if you have deliberately chosen the direct IPv6 connection.
SUPABASE_USE_POOLER = os.getenv("SUPABASE_USE_POOLER", "true").lower() == "true"

# True when the URL points at Supabase's shared pooler (either mode).
IS_SUPABASE_POOLER = "pooler.supabase.com" in DATABASE_URL

# True only for *transaction* mode (port 6543, PgBouncer). Session mode is
# port 5432 and does support prepared statements.
IS_SUPABASE_TRANSACTION_POOLER = IS_SUPABASE_POOLER and DATABASE_URL.endswith(":6543/postgres")

# ---------- Google OAuth ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# This MUST match an "Authorized redirect URI" in the Google Cloud console,
# character for character, or Google rejects the sign-in with
# `redirect_uri_mismatch`.
#
# The /api prefix is easy to get wrong: the route is registered at
# /api/auth/google/callback in main.py, not /auth/google/callback.
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/auth/google/callback",
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
            "and paste your database connection string (Supabase: Project "
            "Settings -> Database -> Connection string -> Session pooler)."
        )
    elif DATABASE_URL.startswith("postgresql"):
        if "supabase" in DATABASE_URL and "pooler.supabase.com" not in DATABASE_URL:
            problems.append(
                "DATABASE_URL uses Supabase's direct host, which is IPv6-only "
                "and will usually fail to connect. Use the Session pooler "
                "string instead (host contains 'pooler.supabase.com')."
            )
        if "sslmode=" not in DATABASE_URL:
            # Not fatal — database.py adds it — but worth surfacing.
            problems.append(
                "DATABASE_URL has no sslmode; database.py is defaulting it to "
                "'require'. That is correct for Supabase and Neon."
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
