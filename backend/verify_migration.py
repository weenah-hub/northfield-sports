"""
Verifies the migration path: a database created by the *older* version of the
app (orders table with no subtotal/shipping/tax columns) must be upgraded in
place, with existing rows preserved.

Run from the backend directory:
    .venv\\Scripts\\python.exe verify_migration.py
"""

import os
import tempfile

DB = "sqlite:///" + os.path.join(tempfile.gettempdir(), "shop_migration.db")
os.environ["DATABASE_URL"] = DB
os.environ["JWT_SECRET"] = "test-secret-for-verification-only"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["MAILGUN_API_KEY"] = ""

import sqlalchemy  # noqa: E402
from sqlalchemy import create_engine as real_create_engine, text  # noqa: E402

_orig = sqlalchemy.create_engine


def patched(*a, **kw):
    kw.pop("pool_pre_ping", None)
    return _orig(*a, **kw)


sqlalchemy.create_engine = patched

from migrations import EXPECTED_COLUMNS, apply_migrations  # noqa: E402

failures = []


def check(label, condition, detail=""):
    if not condition:
        failures.append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' -> ' + detail) if detail else ''}")


if os.path.exists(DB.split("///")[-1]):
    os.remove(DB.split("///")[-1])

engine = patched(DB)

# ---- Step 1: hand-build the OLD schema, as an existing database would have it
print("\n=== Building the old schema by hand ===")
with engine.begin() as c:
    c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), name VARCHAR(255), google_id VARCHAR(255), created_at DATETIME)"))
    c.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, name VARCHAR(255), description TEXT, price FLOAT, image_url VARCHAR(500), category VARCHAR(100), stock INTEGER, created_at DATETIME)"))
    c.execute(
        text(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total FLOAT NOT NULL, status VARCHAR(50), "
            "shipping_name VARCHAR(255), shipping_address TEXT, shipping_city VARCHAR(100), shipping_zip VARCHAR(20), "
            "shipping_country VARCHAR(100), created_at DATETIME)"
        )
    )
    c.execute(text("CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, quantity INTEGER, price FLOAT)"))
    c.execute(
        text(
            "INSERT INTO users (id, email, name, google_id, created_at) "
            "VALUES (1, 'legacy@example.com', 'Old Customer', 'g-old', '2024-01-01')"
        )
    )
    # A real old order that must survive the migration untouched.
    c.execute(
        text(
            "INSERT INTO orders (id, user_id, total, status, shipping_name, shipping_address, "
            "shipping_city, shipping_zip, shipping_country, created_at) "
            "VALUES (1, 1, 100.0, 'pending', 'Old Customer', '9 Legacy Lane', 'Oldtown', '99999', 'Ireland', '2024-01-01')"
        )
    )

before = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(orders)"))}
check("old schema has no subtotal column", "subtotal" not in before)
check("old schema has no shipping column", "shipping" not in before)
check("old schema has no tax column", "tax" not in before)

# ---- Step 2: run the migration, exactly as startup does
print("\n=== Running the migration ===")
apply_migrations(engine)
after = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(orders)"))}
for column in EXPECTED_COLUMNS["orders"]:
    check(f"orders.{column} now exists", column in after)

# ---- Step 3: the existing order must be intact
print("\n=== Existing data is preserved ===")
with engine.connect() as c:
    row = c.execute(
        text("SELECT id, total, shipping_name, shipping_country, subtotal, shipping, tax FROM orders WHERE id = 1")
    ).fetchone()
check("old order still present", row is not None)
check("old total unchanged", row[1] == 100.0, str(row[1]))
check("old customer name unchanged", row[2] == "Old Customer")
check("old country unchanged", row[3] == "Ireland")
check("new columns default to 0", (row[4], row[5], row[6]) == (0, 0, 0), str((row[4], row[5], row[6])))

# ---- Step 4: it must be safe to run twice
print("\n=== Re-running is safe ===")
apply_migrations(engine)
apply_migrations(engine)
with engine.connect() as c:
    count = c.execute(text("SELECT COUNT(*) FROM orders")).fetchone()[0]
check("no duplicate rows or errors", count == 1, str(count))
cols_again = [r[1] for r in engine.connect().execute(text("PRAGMA table_info(orders)"))]
check("no duplicated columns", len(cols_again) == len(set(cols_again)), str(cols_again))

# ---- Step 5: the app can then create a new order on the migrated database
print("\n=== New orders work on the migrated database ===")
import database  # noqa: E402
import main  # noqa: E402
from database import Base  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from models import Product, User  # noqa: E402
from services import auth as auth_service  # noqa: E402

database.engine = engine
Base.metadata.create_all(bind=engine)

client = TestClient(main.app)
db = database.SessionLocal()
user = User(email="new@example.com", name="New Buyer", google_id="g-new")
db.add(user)
db.flush()
db.add(Product(name="Boot", description="", price=40.0, category="Kit", stock=10))
db.commit()
uid = user.id
db.close()

auth = {"Authorization": f"Bearer {auth_service.create_jwt_token(uid, 'new@example.com')}"}
created = client.post(
    "/api/orders",
    json={
        "items": [{"product_id": 1, "quantity": 1}],
        "shipping_name": "New Buyer",
        "shipping_address": "1 New Street",
        "shipping_city": "Newtown",
        "shipping_zip": "12345",
        "shipping_country": "Ireland",
    },
    headers=auth,
)
check("new order is created", created.status_code == 201, str(created.status_code))
check("new user is not the legacy owner", uid != 1, str(uid))
body = created.json()
check("new order stores the breakdown", body["subtotal"] == 40.0 and body["tax"] == 3.3 and body["total"] == 50.25, str(body.get("total")))

# The legacy order belongs to user 1, so the new user must not be able to read it.
old = client.get("/api/orders/1", headers=auth)
check("legacy order is not readable by the new user", old.status_code == 404, str(old.status_code))

print("\n" + "=" * 52)
print(f"{len(failures)} FAILED: {failures}" if failures else "All checks passed.")
print("=" * 52)
raise SystemExit(1 if failures else 0)
