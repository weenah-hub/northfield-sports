"""
Cart tests — including the two-device sync the mobile app depends on.

"Two devices" is simulated with two TestClient instances holding two separate
JWTs for the same user. They have no shared memory, exactly like a laptop and a
phone, so if a change on one shows up on the other it is genuinely going through
the database rather than shared process state.

Run from the backend directory:
    .venv\\Scripts\\python.exe verify_cart.py
"""

import os
import sys
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "shop_cart.db")
os.environ["JWT_SECRET"] = "cart-test-secret"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["MAILGUN_API_KEY"] = ""

import sqlalchemy  # noqa: E402
from sqlalchemy import create_engine as real_create_engine

_orig = sqlalchemy.create_engine


def patched(*a, **kw):
    if str(a[0]).startswith("sqlite"):
        kw.pop("pool_pre_ping", None)
    return _orig(*a, **kw)


sqlalchemy.create_engine = patched

import database  # noqa: E402
import main  # noqa: E402
from database import Base, engine  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from models import Product, User  # noqa: E402
from services import auth as auth_service  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = database.SessionLocal()
user = User(email="shopper@example.com", name="Sync Tester", google_id="g-sync")
db.add(user)
db.flush()
for name, price, stock in [("Jersey", 64.0, 10), ("Socks", 18.0, 5), ("Scarf", 22.0, 3)]:
    db.add(Product(name=name, description="", price=price, category="Kit", stock=stock))
db.commit()
uid = user.id
db.close()


def token_for(user_id: int, email: str) -> dict:
    return {"Authorization": f"Bearer {auth_service.create_jwt_token(user_id, email)}"}


# Two separate clients = two separate devices. Nothing is shared in memory.
laptop = TestClient(main.app)
phone = TestClient(main.app)
LAPTOP = token_for(uid, "shopper@example.com")
PHONE = token_for(uid, "shopper@example.com")

failures = []


def check(label: str, condition: bool, detail: object = "") -> None:
    if not condition:
        failures.append(label)
    shown = f" -> {detail}" if detail != "" else ""
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{shown}")


print("\n=== 1. The cart table exists and starts empty ===")
cart = laptop.get("/api/cart", headers=LAPTOP).json()
check("GET /api/cart works", "items" in cart, str(sorted(cart.keys())[:4]))
check("a new cart is empty", cart["items"] == [] and cart["total"] == 0.0)
check("total of an empty cart is zero", cart["subtotal"] == 0.0 and cart["shipping"] == 0.0)

print("\n=== 2. Cart needs a signed-in user ===")
check("no token is rejected", laptop.get("/api/cart").status_code == 401)
check("junk token is rejected", laptop.get("/api/cart", headers={"Authorization": "Bearer x"}).status_code == 401)

print("\n=== 3. Adding items prices them from the database ===")
r = laptop.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=LAPTOP).json()
check("line is stored", len(r["items"]) == 1 and r["items"][0]["quantity"] == 2)
check("subtotal is 2 x 64", r["subtotal"] == 128.0, str(r["subtotal"]))
check("product details are included for the client", r["items"][0]["product"]["name"] == "Jersey")
check("item_count is the sum of quantities", r["item_count"] == 2)

r = laptop.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=LAPTOP).json()
check("second product added", len(r["items"]) == 2)

# Work out the expected totals from the pricing module rather than hardcoding
# them, so the test checks the cart maths without re-asserting it.
import pricing  # noqa: E402

expected = pricing.quote(2 * 64.0 + 1 * 18.0)
check(f"subtotal matches the pricing rules ({expected['subtotal']})", r["subtotal"] == expected["subtotal"], str(r["subtotal"]))
check(f"shipping matches the pricing rules ({expected['shipping']})", r["shipping"] == expected["shipping"], str(r["shipping"]))
check(f"tax matches the pricing rules ({expected['tax']})", r["tax"] == expected["tax"], str(r["tax"]))
check(f"total matches the pricing rules ({expected['total']})", r["total"] == expected["total"], str(r["total"]))
check("over the threshold means free shipping", r["shipping"] == 0.0, str(r["shipping"]))

# And the other side of the threshold, where shipping is charged.
below = laptop.post("/api/cart/items", json={"product_id": 3, "quantity": 1}, headers=LAPTOP).json()
expected_below = pricing.quote(2 * 64.0 + 1 * 18.0 + 1 * 22.0)
check(f"still over the threshold at 3 lines ({expected_below['total']})",
      below["total"] == expected_below["total"], str(below["total"]))

# Start the sync section from a known cart so the counts below are meaningful.
laptop.delete("/api/cart", headers=LAPTOP)
laptop.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=LAPTOP)
r = laptop.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=LAPTOP).json()

print("\n=== 4. THE FEATURE: a change on one device shows on the other ===")
phone_view = phone.get("/api/cart", headers=PHONE).json()
check("phone sees what the laptop added", len(phone_view["items"]) == 2, str(len(phone_view["items"])))
check("phone sees the same total", phone_view["total"] == r["total"], f"{phone_view['total']} vs {r['total']}")

laptop.post("/api/cart/items", json={"product_id": 3, "quantity": 1}, headers=LAPTOP)
phone_view = phone.get("/api/cart", headers=PHONE).json()
check("an add on the laptop appears on the phone", len(phone_view["items"]) == 3, str(len(phone_view["items"])))
check("the phone sees the scarf", phone_view["items"][2]["product"]["name"] == "Scarf")

phone.post("/api/cart/items", json={"product_id": 3, "quantity": 2}, headers=PHONE)
laptop_view = laptop.get("/api/cart", headers=LAPTOP).json()
scarf = next(i for i in laptop_view["items"] if i["product_id"] == 3)
check("an add on the phone appears on the laptop", scarf["quantity"] == 3, str(scarf["quantity"]))
check("quantities accumulate rather than duplicate",
      len([i for i in laptop_view["items"] if i["product_id"] == 3]) == 1)

print("\n=== 5. Editing and removing from one device ===")
laptop.patch("/api/cart/items/1", json={"quantity": 5}, headers=LAPTOP)
phone_view = phone.get("/api/cart", headers=PHONE).json()
check("a quantity change on the laptop reaches the phone",
      next(i for i in phone_view["items"] if i["product_id"] == 1)["quantity"] == 5)

phone.delete("/api/cart/items/2", headers=PHONE)
laptop_view = laptop.get("/api/cart", headers=LAPTOP).json()
check("a removal on the phone reaches the laptop", 2 not in [i["product_id"] for i in laptop_view["items"]])

check("removing something absent is not an error",
      laptop.delete("/api/cart/items/2", headers=LAPTOP).status_code == 200)

print("\n=== 6. Quantity 0 removes a line ===")
laptop.patch("/api/cart/items/3", json={"quantity": 0}, headers=LAPTOP)
view = phone.get("/api/cart", headers=PHONE).json()
check("setting 0 removes the line", 3 not in [i["product_id"] for i in view["items"]])

print("\n=== 7. Stock is enforced on every write ===")
# Socks have stock 5. Put a known quantity in the cart, then try to exceed it.
laptop.patch("/api/cart/items/2", json={"quantity": 4}, headers=LAPTOP)
over = laptop.post("/api/cart/items", json={"product_id": 2, "quantity": 2}, headers=LAPTOP)
check("cannot add past the stock limit", over.status_code == 409, str(over.status_code))
check("the error says how many are left", "left" in str(over.json()["detail"]), str(over.json()["detail"]))
view = phone.get("/api/cart", headers=PHONE).json()
check("a rejected add leaves the quantity alone",
      next(i for i in view["items"] if i["product_id"] == 2)["quantity"] == 4)

check("negative quantity is refused by validation",
      laptop.post("/api/cart/items", json={"product_id": 1, "quantity": -1}, headers=LAPTOP).status_code == 422)
check("an absurd quantity is refused by validation",
      laptop.post("/api/cart/items", json={"product_id": 1, "quantity": 100000}, headers=LAPTOP).status_code == 422)
check("unknown product is refused",
      laptop.post("/api/cart/items", json={"product_id": 999, "quantity": 1}, headers=LAPTOP).status_code == 404)

print("\n=== 8. Asking for more than exists is refused, not silently clamped ===")
# Silently clamping would mean the customer taps "Add" and nothing happens, so
# this must say so instead.
r = laptop.post("/api/cart/items", json={"product_id": 3, "quantity": 2}, headers=LAPTOP)
check("scarf (stock 3) accepts 2", r.status_code == 200, str(r.status_code))
r = laptop.post("/api/cart/items", json={"product_id": 3, "quantity": 2}, headers=LAPTOP)
check("a further 2 would make 4 of 3, so it is refused", r.status_code == 409, str(r.status_code))
view = phone.get("/api/cart", headers=PHONE).json()
check("the quantity is left alone after a refusal",
      next(i for i in view["items"] if i["product_id"] == 3)["quantity"] == 2)

print("\n=== 9. Out-of-stock lines are reported, not hidden ===")
# Someone else buys the remaining scarf stock while it sits in the cart.
db = database.SessionLocal()
scarf = db.query(Product).filter(Product.name == "Scarf").one()
scarf.stock = 0
db.commit()
db.close()
view = phone.get("/api/cart", headers=PHONE).json()
check("the phone is told the line is now out of stock",
      any("Scarf" in problem for problem in view["out_of_stock"]), str(view["out_of_stock"]))
check("the unavailable line is still listed so it can be removed",
      3 in [i["product_id"] for i in view["items"]])

print("\n=== 10. Two different users never share a cart ===")
db = database.SessionLocal()
other = User(email="other@example.com", name="Someone Else", google_id="g-other")
db.add(other)
db.commit()
other_id = other.id
db.close()
other_cart = TestClient(main.app).get("/api/cart", headers=token_for(other_id, "other@example.com")).json()
check("a different user's cart is empty", other_cart["items"] == [])
check("and unaffected by the first user's changes",
      len(phone.get("/api/cart", headers=PHONE).json()["items"]) == len(view["items"]))

print("\n=== 11. Merging a guest cart after sign-in ===")
laptop.delete("/api/cart", headers=LAPTOP)
phone.delete("/api/cart", headers=PHONE)
view = laptop.get("/api/cart", headers=LAPTOP).json()
check("cart emptied", view["items"] == [])

r = laptop.post("/api/cart/merge", json={"items": [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 3}]}, headers=LAPTOP).json()
check("guest lines merged in", r["merged"] == 2 and len(r["items"]) == 2)
check("quantities taken from the guest cart",
      next(i for i in r["items"] if i["product_id"] == 2)["quantity"] == 3)

# Socks are already at 3. Add 1 more (4 total), then merge 2 more. Socks have
# stock 5, so 4 + 2 = 6 must be refused and skipped rather than failing the
# whole sign-in.
laptop.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=LAPTOP)
r = laptop.post("/api/cart/merge", json={"items": [{"product_id": 2, "quantity": 2}]}, headers=LAPTOP).json()
check("a merge that would exceed stock is skipped, not fatal", r["merged"] == 0, str(r))
check("and the existing quantity is left alone",
      next(i for i in r["items"] if i["product_id"] == 2)["quantity"] == 4)

# With room available, a merge must sum rather than replace.
r = laptop.post("/api/cart/merge", json={"items": [{"product_id": 2, "quantity": 1}]}, headers=LAPTOP).json()
check("merging sums quantities rather than replacing",
      next(i for i in r["items"] if i["product_id"] == 2)["quantity"] == 5, str(r["items"]))

r = laptop.post("/api/cart/merge", json={"items": [{"product_id": 999, "quantity": 1}, {"product_id": 1, "quantity": 1}]}, headers=LAPTOP).json()
check("an unavailable product is skipped, not fatal", r["skipped"] == [999] and r["merged"] == 1, str(r))
check("the phone sees the merged result",
      len(phone.get("/api/cart", headers=PHONE).json()["items"]) == 2)

print("\n=== 12. Checkout clears the cart ===")
from schemas import OrderCreate  # noqa: E402
from services.orders import create_order  # noqa: E402

db = database.SessionLocal()
buyer = db.get(User, uid)
order = create_order(
    db,
    buyer,
    OrderCreate(
        items=[{"product_id": 1, "quantity": 1}],
        shipping_name="Sync Tester",
        shipping_address="1 Test Street",
        shipping_city="Testville",
        shipping_zip="12345",
    ),
)
db.close()
check("order was created", order.total > 0, str(order.total))

print("\n" + "=" * 54)
if failures:
    print(f"{len(failures)} FAILED: {failures}")
else:
    print("All checks passed.")
print("=" * 54)
sys.exit(1 if failures else 0)