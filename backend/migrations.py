"""
Small schema migrations
=======================
`Base.metadata.create_all()` creates missing *tables*, but it never adds a new
*column* to a table that already exists. So if you already have a database from
an earlier version of the shop, the new `orders.subtotal` / `orders.shipping` /
`orders.tax` columns would never appear and every checkout would crash.

These helpers add any missing columns instead. They are safe to run on every
startup: a column that is already there is left alone.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Maps a table to {column name: SQL type}. Anything listed here that is missing
# from the live database gets added.
#
# The column type is chosen per dialect. Production is always PostgreSQL
# (Supabase or Neon), where DOUBLE PRECISION is the correct 8-byte float that
# matches SQLAlchemy's `Float` on those backends. The SQLite spelling is only
# there so the local test scripts exercise the same code path.
EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "orders": {
        "subtotal": "DOUBLE PRECISION",
        "shipping": "DOUBLE PRECISION",
        "tax": "DOUBLE PRECISION",
    },
}

# Dialect-specific spellings for the same logical type.
_TYPE_OVERRIDES: dict[str, dict[str, str]] = {
    "sqlite": {"DOUBLE PRECISION": "REAL"},
}


def _existing_columns(engine: Engine, table: str) -> set[str]:
    """Column names currently present on `table`."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def apply_migrations(engine: Engine) -> None:
    """Add any columns the models expect but the database does not have yet."""
    for table, columns in EXPECTED_COLUMNS.items():
        existing = _existing_columns(engine, table)
        if not existing:
            # Table is brand new; create_all() already made it correctly.
            continue

        for column, sql_type in columns.items():
            if column in existing:
                continue

            # Use the spelling this dialect understands.
            dialect = engine.dialect.name
            sql_type = _TYPE_OVERRIDES.get(dialect, {}).get(sql_type, sql_type)

            # NOT NULL is safe here because existing rows get the default 0,
            # which is the correct historical value for the new columns.
            statement = (
                f"ALTER TABLE {table} ADD COLUMN {column} "
                f"{sql_type} NOT NULL DEFAULT 0"
            )
            logger.info("Migration: adding %s.%s", table, column)
            with engine.begin() as connection:
                connection.execute(text(statement))
