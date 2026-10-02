"""
Verification harness (development aid, not part of the running app).

Boots the real FastAPI app against a local SQLite file so the whole checkout
flow can be exercised without a Neon account or real Google/Mailgun keys.

Run from the backend directory:
    .venv\\Scripts\\python.exe verify_flow.py
"""

import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "shop_verify.db")
os.environ["JWT_SECRET"] = "test-secret-for-verification-only"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["MAILGUN_API_KEY"] = ""

# SQLite rejects the Postgres-only pool_pre_ping argument, so swap it out for
# this run. Everything else uses the app's real code paths.
import sqlalchemy
from sqlalchemy import create_engine as real_create_engine

_orig = sqlalchemy.create_engine


def patched(*a, **kw):
    url = str(a[0]) if a else kw.get("url")
    if url.startswith("sqlite"):
        kw.pop("pool_pre_ping", None)
    return _orig(*a, **kw)


sqlalchemy.create_engine = patched

import database  # noqa: E402
import main  # noqa: E402
import pricing  # noqa: E402
from database import Base, engine  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from models import Order, Product, User  # noqa: E402
from services import auth as auth_service  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = database.SessionLocal()
user = User(email="test@example.com", name="Test Buyer", google_id="g-123")
db.add(user)
db.flush()
for name, price, stock in [("Boot", 40.00, 10), ("Ball", 20.00, 5), ("Scarf", 8.00, 3)]:
    db.add(Product(name=name, description="", price=price, category="Kit", stock=stock))
db.commit()
user_id, user_email = user.id, user.email
db.close()

client = TestClient(main.app)
auth = {"Authorization": f"Bearer {auth_service.create_jwt_token(user_id, user_email)}"}

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition:
        failures.append(label)
    print(f"  [{status}] {label}{(' -> ' + detail) if detail else ''}")


def cart(*pairs):
    return {"items": [{"product_id": p, "quantity": q} for p, q in pairs]}


SHIPPING = {
    "shipping_name": "Test Buyer",
    "shipping_address": "1 Test Street",
    "shipping_city": "Testville",
    "shipping_zip": "12345",
    "shipping_country": "Ireland",
}

print("\n=== 1. Health and catalogue ===")
check("health returns ok", client.get("/api/health").json()["status"] == "ok")
products = client.get("/api/products").json()
check("three products seeded", len(products) == 3, str(len(products)))

print("\n=== 2. Auth is enforced ===")
check("orders without a token are rejected", client.post("/api/orders", json={**cart((1, 1)), **SHIPPING}).status_code == 401)
check("me with a valid token works", client.get("/api/auth/me", headers=auth).json()["email"] == user_email)
check("me with a junk token is rejected", client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401)

print("\n=== 3. Quote endpoint matches the pricing rules ===")
# 1 x Boot ($40) -> under the $100 threshold, so shipping + tax both apply.
q = client.post("/api/orders/quote", json=cart((1, 1))).json()
print(f"      quote = {q}")
check("subtotal is the goods sum", q["subtotal"] == 40.0)
check("flat shipping applied below threshold", q["shipping"] == 6.95)
check("tax is 8.25% of subtotal", q["tax"] == 3.30)
check("total = subtotal + shipping + tax", q["total"] == 50.25, str(q["total"]))
check("threshold sent to the client", q["free_shipping_threshold"] == 100.0)

# Right on the threshold -> free shipping.
q = client.post("/api/orders/quote", json=cart((1, 2), (2, 1))).json()
print(f"      quote = {q}")
check("free shipping at the threshold", q["shipping"] == 0.0)
check("tax still applies when shipping is free", q["tax"] == 8.25)

print("\n=== 4. THE BUG: quoted total must equal stored total ===")
# Exactly the case that used to be wrong: the page showed 108.25, the row said 100.00.
q = client.post("/api/orders/quote", json=cart((1, 2), (2, 1))).json()
order = client.post("/api/orders", json={**cart((1, 2), (2, 1)), **SHIPPING}, headers=auth).json()
print(f"      quoted {q['total']}  stored {order['total']}")
check("quoted total == stored total", q["total"] == order["total"], f"{q['total']} vs {order['total']}")
check("stored subtotal matches quote", order["subtotal"] == q["subtotal"])
check("stored shipping matches quote", order["shipping"] == q["shipping"])
check("stored tax matches quote", order["tax"] == q["tax"])
check("shipping country is persisted", order["shipping_country"] == "Ireland", order["shipping_country"])

# A below-threshold order, which used to lose the shipping charge entirely.
q2 = client.post("/api/orders/quote", json=cart((3, 1))).json()
order2 = client.post("/api/orders", json={**cart((3, 1)), **SHIPPING}, headers=auth).json()
print(f"      quoted {q2['total']}  stored {order2['total']}")
check("below-threshold quoted total == stored total", q2["total"] == order2["total"], f"{q2['total']} vs {order2['total']}")

print("\n=== 5. Stock is decremented and overselling is blocked ===")
db = database.SessionLocal()
scarf_stock = db.get(Product, 3).stock
db.close()
check("stock decremented by qty", scarf_stock == 2, str(scarf_stock))
check("too many is refused", client.post("/api/orders", json={**cart((2, 99)), **SHIPPING}, headers=auth).status_code == 409)
check("unknown product is refused", client.post("/api/orders", json={**cart((999, 1)), **SHIPPING}, headers=auth).status_code == 404)
check("empty cart is refused", client.post("/api/orders", json={**cart(), **SHIPPING}, headers=auth).status_code == 400)
check("zero quantity is refused by validation", client.post("/api/orders", json={**cart((1, 0)), **SHIPPING}, headers=auth).status_code == 422)
check("blank address is refused by validation", client.post("/api/orders", json={**cart((1, 1)), **SHIPPING, "shipping_city": ""}, headers=auth).status_code == 422)

print("\n=== 6. One order cannot read another's ===")
mine = client.get(f"/api/orders/{order['id']}", headers=auth)
check("owner can read own order", mine.status_code == 200)

# A real, different signed-in user — the case that actually matters.
db = database.SessionLocal()
intruder = User(email="intruder@example.com", name="Nosy", google_id="g-999")
db.add(intruder)
db.commit()
intruder_id = intruder.id
db.close()
intruder_auth = {"Authorization": f"Bearer {auth_service.create_jwt_token(intruder_id, 'intruder@example.com')}"}
check("a different user is refused the order", client.get(f"/api/orders/{order['id']}", headers=intruder_auth).status_code == 404)
check("intruder sees none of my orders", client.get("/api/orders", headers=intruder_auth).json() == [])

# A token for a user that no longer exists must fail, not crash.
ghost = {"Authorization": f"Bearer {auth_service.create_jwt_token(9999, 'ghost@example.com')}"}
check("token for a deleted user is rejected", client.get("/api/orders", headers=ghost).status_code == 401)
check("order list only returns own orders", all(o["id"] in {order["id"], order2["id"]} for o in client.get("/api/orders", headers=auth).json()))

print("\n=== 7. Quote reports stock problems ===")
q = client.post("/api/orders/quote", json=cart((3, 5))).json()
check("oversized line is reported", len(q["out_of_stock"]) == 1, str(q["out_of_stock"]))
# JSON object keys are always strings, so compare on "3".
check("max quantity sent to client", q["max_quantities"].get("3") == 2, str(q["max_quantities"]))

print("\n=== 8. Rounding is exact ===")
check("0.005 rounds half up", pricing.money(1.005) == 1.01, str(pricing.money(1.005)))
check("0.004 rounds down", pricing.money(1.004) == 1.0)
check("1.015 rounds half up", pricing.money(1.015) == 1.02, str(pricing.money(1.015)))
# 3 x 0.1 style float drift must not leak into the total.
check("float drift is corrected", pricing.quote(0.1 + 0.2)["subtotal"] == 0.3, str(pricing.quote(0.1 + 0.2)["subtotal"]))
check("an empty cart totals zero", pricing.quote(0) == {"subtotal": 0.0, "shipping": 0.0, "tax": 0.0, "total": 0.0}, str(pricing.quote(0)))

print("\n=== 9. Receipt builds from a real order, after the session closes ===")
# This is the exact production lifecycle: create_order returns an object that a
# background task renders into an email after the request (and its database
# session) is finished. If the receipt needs a lazy load it will fail here.
from schemas import OrderCreate  # noqa: E402
from services.email import build_receipt_html  # noqa: E402
from services.orders import create_order  # noqa: E402

db = database.SessionLocal()
buyer = db.get(User, user_id)
receipt_order = create_order(
    db,
    buyer,
    OrderCreate(
        items=[{"product_id": 1, "quantity": 1}],
        shipping_name="Test Buyer",
        shipping_address="1 Test Street",
        shipping_city="Testville",
        shipping_zip="12345",
        shipping_country="Ireland",
    ),
)
db.close()  # session gone, exactly as it is by the time the receipt is sent

try:
    html = build_receipt_html(receipt_order)
    check("receipt builds with a closed session", "Thanks for your order" in html)
    check("receipt shows the real total", f"{receipt_order.total:,.2f}" in html)
    check("receipt shows the shipping line", "Shipping" in html)
    check("receipt shows the tax line", "Tax" in html)
    check("receipt shows product names", "Boot" in html)
    check("receipt shows the shipping country", "Ireland" in html)
except Exception as exc:  # noqa: BLE001
    check("receipt builds with a closed session", False, f"{type(exc).__name__}: {exc}")

print("\n" + "=" * 52)
if failures:
    print(f"{len(failures)} FAILED: {failures}")
else:
    print("All checks passed.")
print("=" * 52)
raise SystemExit(1 if failures else 0)
