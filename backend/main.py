"""
Shop API - Backend
==================
Products, Google sign-in, and order checkout for the storefront.
Serves the React frontend in production.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

import models  # noqa: F401  (registers tables with Base before create_all)
import pricing
from config import FRONTEND_URL, GOOGLE_CLIENT_ID, validate_settings
from database import Base, engine, get_db
from deps import get_current_user, get_optional_user
from models import Order, Product, User
from migrations import apply_migrations
from schemas import (
    OrderCreate,
    OrderResponse,
    ProductResponse,
    QuoteRequest,
    QuoteResponse,
    UserResponse,
)
from services import auth as auth_service
from services import email as email_service
from services.orders import create_order, list_orders_for_user, quote_cart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHOP_NAME = os.getenv("SHOP_NAME", "Northfield Sports")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on boot and warn loudly about missing configuration."""
    problems = validate_settings()
    if problems:
        logger.warning("Configuration problems detected:")
        for problem in problems:
            logger.warning("  - %s", problem)
    else:
        logger.info("Configuration looks complete.")

    Base.metadata.create_all(bind=engine)
    # create_all only creates whole tables, so add any newly added columns.
    apply_migrations(engine)
    logger.info("Database ready.")
    yield


app = FastAPI(title=f"{SHOP_NAME} API", lifespan=lifespan)

# Only the storefront is allowed to call this API.
#
# The login token travels in an `Authorization` header rather than a cookie, so
# a wide-open origin cannot steal it — but leaving CORS open still lets any
# website anyone visits use this server, and lets a page read the response.
# In production the frontend is served by this same app, so it needs no CORS at
# all; these entries only matter for `npm run dev` on a different port.
ALLOWED_ORIGINS = [
    FRONTEND_URL.rstrip("/"),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in ALLOWED_ORIGINS if origin],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------- Products ----------

@app.get("/api/products", response_model=list[ProductResponse])
def list_products(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return the storefront catalogue, optionally filtered."""
    query = db.query(Product)

    if category and category.lower() != "all":
        query = query.filter(Product.category == category)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(Product.name.ilike(term) | Product.description.ilike(term))

    return query.order_by(Product.id).all()


@app.get("/api/products/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """Distinct categories for the filter bar."""
    rows = db.query(Product.category).distinct().order_by(Product.category).all()
    return [row[0] for row in rows if row[0]]


@app.get("/api/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------- Auth ----------

def _safe_redirect_path(candidate: str | None) -> str:
    """Allow only same-site relative paths through, to prevent open redirects."""
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


@app.get("/api/auth/google")
def google_sign_in(redirect: str = Query(default="/")):
    """Redirect the browser to Google's consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured on this server.",
        )
    safe = _safe_redirect_path(redirect)
    return RedirectResponse(auth_service.get_google_auth_url(state=safe))


@app.get("/api/auth/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(default="/"),
    db: Session = Depends(get_db),
):
    """Exchange the auth code, upsert the user, then hand a JWT to the SPA."""
    try:
        tokens = await auth_service.exchange_code_for_token(code)
        profile = await auth_service.get_google_user_info(tokens["access_token"])
    except Exception as exc:
        logger.error("Google OAuth exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Google sign-in failed. Please try again.")

    email = profile.get("email")
    google_id = profile.get("id")
    if not email or not google_id:
        raise HTTPException(
            status_code=502,
            detail="Google did not return an email address for this account.",
        )

    user = db.query(User).filter(User.google_id == google_id).one_or_none()
    if user is None:
        user = db.query(User).filter(User.email == email).one_or_none()

    if user is None:
        user = User(
            email=email,
            name=profile.get("name") or email.split("@")[0],
            google_id=google_id,
        )
        db.add(user)
    else:
        # Keep the profile fresh and bind the account to this Google identity.
        user.google_id = google_id
        if profile.get("name"):
            user.name = profile["name"]

    db.commit()
    db.refresh(user)

    jwt_token = auth_service.create_jwt_token(user.id, user.email)
    logger.info("Signed in user %s (id=%s)", user.email, user.id)

    # The SPA reads the token from the URL, stores it, then scrubs the address bar.
    return RedirectResponse(
        url=f"{FRONTEND_URL}/signin-callback?token={jwt_token}"
        f"&redirect={_safe_redirect_path(state)}"
    )


@app.get("/api/auth/me", response_model=UserResponse)
def read_me(user: User = Depends(get_current_user)):
    return user


@app.post("/api/auth/signout")
def sign_out():
    """Stateless JWT sign-out: the client discards the token."""
    return {"message": "Signed out"}


# ---------- Orders / Checkout ----------

@app.post("/api/orders/quote", response_model=QuoteResponse)
def quote_order(payload: QuoteRequest, db: Session = Depends(get_db)):
    """Price a cart for display, without saving it.

    The checkout page calls this so the total it shows is the server's own
    figure. No sign-in required: the customer has to see a price before they
    commit to signing in.
    """
    quantities: dict[int, int] = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    subtotal = 0.0
    out_of_stock: list[str] = []
    max_quantities: dict[int, int] = {}

    for product_id, quantity in quantities.items():
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} no longer exists.",
            )
        subtotal += product.price * quantity
        max_quantities[product_id] = product.stock
        if product.stock < quantity:
            out_of_stock.append(
                f'{product.name} — only {product.stock} left'
                if product.stock > 0
                else f"{product.name} is out of stock"
            )

    return QuoteResponse(
        **quote_cart(db, QuoteRequest(items=payload.items)),
        free_shipping_threshold=pricing.FREE_SHIPPING_THRESHOLD,
        out_of_stock=out_of_stock,
        max_quantities=max_quantities,
    )


@app.post("/api/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    payload: OrderCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Checkout. Requires sign-in, prices the cart server-side, emails a receipt."""
    order = create_order(db, user, payload)

    # Receipt is sent after the response so a slow mail server never delays checkout.
    background.add_task(email_service.send_order_confirmation, order, user.email)

    logger.info("Order %s placed by user %s for $%.2f", order.id, user.id, order.total)
    return order


@app.get("/api/orders", response_model=list[OrderResponse])
def get_my_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_orders_for_user(db, user)


@app.get("/api/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch one order. Scoped to the owner so customers cannot read each other's."""
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "shop": SHOP_NAME}


# ---------- Serve React Frontend (Production) ----------
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    # Serve static files (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """Serve the React app for any non-API route."""
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # If no file found, serve index.html (React handles routing)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
