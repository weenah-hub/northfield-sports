"""
Database setup
=============
Creates the SQLAlchemy engine and session factory for Neon PostgreSQL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# Create the engine — this manages the connection pool
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
