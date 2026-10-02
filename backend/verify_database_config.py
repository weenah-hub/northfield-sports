"""
Checks the connection-string handling in database.py / config.py.

These are the Supabase-specific failure modes that are hard to debug because
the symptom is a hang or an obscure driver error rather than a clear message:

  * missing sslmode
  * the IPv6-only direct host instead of the pooler
  * prepared statements against PgBouncer in transaction mode

Run from the backend directory:
    .venv\\Scripts\\python.exe verify_database_config.py
"""

import os
import sys
import tempfile

failures = []


def check(label, condition, detail=""):
    if not condition:
        failures.append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' -> ' + detail) if detail else ''}")


def load_config(url: str, use_pooler: str = "true"):
    """Import config fresh with a given DATABASE_URL."""
    for module in ("config", "database"):
        sys.modules.pop(module, None)
    os.environ["DATABASE_URL"] = url
    os.environ["SUPABASE_USE_POOLER"] = use_pooler
    import config
    return config


POOLER = (
    "postgresql://postgres.abcdefgh:secretpw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
)
DIRECT = "postgresql://postgres:secretpw@db.abcdefghijkl.supabase.co:5432/postgres"
NEON = "postgresql://user:pw@ep-cool-name-a1b2c3.us-east-2.aws.neon.tech/neondb?sslmode=require"
TRANSACTION_POOLER = POOLER.replace(":5432/", ":6543/")

print("\n=== 1. Supabase session pooler (port 5432, the one you should use) ===")
config = load_config(POOLER)
check("recognised as a Supabase pooler", config.IS_SUPABASE_POOLER is True)
check("session mode is not transaction mode", config.IS_SUPABASE_TRANSACTION_POOLER is False)
import database

url = database.engine.url.render_as_string(hide_password=False)
check("sslmode=require is added", "sslmode=require" in url, url.split("@")[-1])

# `create_connect_args` takes the URL, not the engine, so ask the dialect
# what a psycopg connection would actually receive.
_, conn_args = database.engine.dialect.create_connect_args(database.engine.url)
check(
    "prepared statements left ENABLED (session mode supports them)",
    "prepare_threshold" not in conn_args,
    str(conn_args),
)
check("pool_pre_ping still on", database.engine.pool._pre_ping is True)

print("\n=== 2. Supabase transaction pooler (port 6543) ===")
config = load_config(TRANSACTION_POOLER)
check("detected as transaction mode", config.IS_SUPABASE_TRANSACTION_POOLER is True)
import database

_, conn_args = database.engine.dialect.create_connect_args(database.engine.url)
check(
    "prepared statements disabled for PgBouncer",
    conn_args.get("prepare_threshold") is None,
    str(conn_args),
)
check("still detected as a Supabase pooler", config.IS_SUPABASE_POOLER is True)

print("\n=== 3. Supabase direct (IPv6) host is rejected with a clear message ===")
try:
    load_config(DIRECT)
    import database  # noqa: F401
    check("raises a helpful error", False, "no error raised")
except ValueError as exc:
    message = str(exc)
    check("raises a helpful error", "pooler.supabase.com" in message, message[:90] + "...")

print("\n=== 4. Deliberately choosing the direct host is allowed ===")
config = load_config(DIRECT, use_pooler="false")
import database

url = database.engine.url.render_as_string(hide_password=False)
check("direct host is accepted", "db.abcdefghijkl.supabase.co" in url)
check("sslmode still added", "sslmode=require" in url)
_, conn_args = database.engine.dialect.create_connect_args(database.engine.url)
check("prepared statements left enabled on a direct connection", "prepare_threshold" not in conn_args, str(conn_args))

print("\n=== 5. Validation warning points at the IPv6 problem ===")
config = load_config(DIRECT, use_pooler="false")
problems = config.validate_settings()
check("warns about the direct host", any("IPv6" in p for p in problems), str([p for p in problems if "IPv6" in p]))

print("\n=== 6. An existing sslmode is not overwritten ===")
load_config("postgresql://user:pw@host.example.com/db?sslmode=require")
import database

url = database.engine.url.render_as_string(hide_password=False)
check("sslmode=require kept", url.count("sslmode=") == 1, url)
load_config("postgresql://user:pw@host.example.com/db?sslmode=disable")
import database

url = database.engine.url.render_as_string(hide_password=False)
check("an explicit sslmode=disable is respected", "sslmode=disable" in url and "require" not in url, url)

print("\n=== 7. Neon still works ===")
config = load_config(NEON)
import database

url = database.engine.url.render_as_string(hide_password=False)
check("Neon URL is not a Supabase pooler", config.IS_SUPABASE_POOLER is False)
check("existing sslmode preserved", url.count("sslmode=require") == 1, url)
check("no fatal error for Neon", not any("IPv6" in p for p in config.validate_settings()))

print("\n=== 8. SQLite still works for the test scripts ===")
sqlite_url = "sqlite:///" + os.path.join(tempfile.gettempdir(), "cfg_test.db")
load_config(sqlite_url, use_pooler="false")
import database

check("sqlite engine is created", database.engine.dialect.name == "sqlite")
check("sqlite keeps NullPool", database.engine.pool.__class__.__name__ == "NullPool", database.engine.pool.__class__.__name__)
check("sqlite is never treated as a pooler", config.IS_SUPABASE_POOLER is False)

if os.path.exists(os.path.join(tempfile.gettempdir(), "cfg_test.db")):
    os.remove(os.path.join(tempfile.gettempdir(), "cfg_test.db"))

print("\n" + "=" * 52)
print(f"{len(failures)} FAILED: {failures}" if failures else "All checks passed.")
print("=" * 52)
raise SystemExit(1 if failures else 0)
