"""
Database setup
==============
Creates the SQLAlchemy engine and session factory for PostgreSQL.

Works with any hosted Postgres — Supabase, Neon, or a local install. The only
per-provider detail that matters is the connection string in `DATABASE_URL`.

Three things that catch people out with Supabase, handled here so you don't
have to think about them:

1. **SSL.** Supabase requires TLS, but the connection string you copy from the
   dashboard often leaves `sslmode` out. We add `sslmode=require` by default
   rather than letting the connection fail with a cryptic error.

2. **IPv6.** The direct connection (`db.<ref>.supabase.co`) is IPv6-only. On a
   home network that is often unreachable, and the failure looks like a hang
   rather than an error. The *pooler* host connects over IPv4, so we prefer it
   when `SUPABASE_USE_POOLER=true`.

3. **The pooler and prepared statements.** Supabase's pooler runs PgBouncer in
   transaction mode, which does not support prepared statements. psycopg
   prepares a statement after 5 uses by default, which then fails with
   "prepared statement ... already exists". Turning preparation off is the
   standard fix, and we do it only for pooled Supabase connections so a direct
   connection keeps the faster path.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from config import (
    DATABASE_URL,
    IS_SUPABASE_POOLER,
    IS_SUPABASE_TRANSACTION_POOLER,
    SUPABASE_USE_POOLER,
)

# Build the kwargs the engine needs for this particular connection string.
engine_kwargs: dict = {"pool_pre_ping": True}

if DATABASE_URL.startswith("postgresql"):
    # sslmode can already be in the URL; only add it if it is missing.
    if "sslmode=" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

    if IS_SUPABASE_TRANSACTION_POOLER:
        # Only *transaction* mode needs this. Port 6543 routes to PgBouncer,
        # which does not support prepared statements; port 5432 is session mode
        # and handles them fine, so we leave the faster path enabled there.
        # See module docstring, point 3.
        engine_kwargs["connect_args"] = {"prepare_threshold": None}

    # Only complain about the IPv6-only host when this really is a Supabase
    # connection. A Neon or self-hosted URL is none of our business, even
    # though it also lacks "pooler.supabase.com".
    is_supabase = "supabase" in DATABASE_URL
    if SUPABASE_USE_POOLER and is_supabase and not IS_SUPABASE_POOLER:
        raise ValueError(
            "SUPABASE_USE_POOLER is true but DATABASE_URL does not point at "
            "Supabase's pooler. In the Supabase dashboard use the "
            "'Session pooler' or 'Transaction pooler' connection string "
            "(the host contains 'pooler.supabase.com', port 5432 or 6543), "
            "not the direct 'db.<ref>.supabase.co' host. "
            "Set SUPABASE_USE_POOLER=false if the direct host is what you want."
        )

# SQLite is only used by the local test scripts, never in production.
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs.pop("pool_pre_ping", None)
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = NullPool

# Create the engine — this manages the connection pool
engine = create_engine(DATABASE_URL, **engine_kwargs)

# Session factory — use this to create individual database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class — all models inherit from this
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
