# 🏬 Northfield Sports — Shop & Checkout

A football kit storefront with Google sign-in and a full checkout flow.
**FastAPI + PostgreSQL (Neon) + React.**

## Features

- 🛍️ **Storefront** — product grid with category filter and search
- 🛒 **Cart** — persisted in `localStorage`, so it survives the sign-in redirect
- 💳 **Checkout** — shipping form with validation, server-side pricing, stock checks
- 🔐 **Google sign-in** — OAuth 2.0, JWT sessions
- 🧾 **Order history** — past orders with a confirmation screen
- 📧 **Email receipts** — sent through Mailgun after the order is placed

## How checkout works

1. The customer adds items and opens `/checkout`.
2. If they are not signed in, the page sends them through Google and back to
   `/checkout` — the cart is preserved in `localStorage`.
3. On submit, the client sends **product IDs and quantities only**.
4. The server reloads the catalogue, checks stock, computes the total, snapshots
   each price onto the order, and decrements stock.
5. A receipt is emailed in a background task, so a slow mail server never
   delays the response.

Pricing is never trusted from the browser — see `backend/services/orders.py`.

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

`.env` needs five things:

| Variable | Where to get it |
| --- | --- |
| `DATABASE_URL` | Neon dashboard → Connection Details → SQLAlchemy |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud → APIs & Services → Credentials → OAuth client |
| `MAILGUN_API_KEY` / `MAILGUN_DOMAIN` | Mailgun → Sending → Domains |

The app logs a clear list of anything missing on startup, so you do not have to
guess at silent failures.

Seed the catalogue (safe to re-run, it skips if products already exist):

```bash
cd backend
python seed.py
python -m uvicorn main:app --port 8000 --reload
```

### 2. Google OAuth setup

In the Google Cloud console, add this **exact** redirect URI to your OAuth
client:

```
http://localhost:8000/api/auth/google/callback
```

This must match `GOOGLE_REDIRECT_URI` in your `.env`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## API

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/products` | — | Catalogue; `?category=`, `?search=` |
| `GET` | `/api/products/categories` | — | Distinct categories |
| `GET` | `/api/products/{id}` | — | One product |
| `GET` | `/api/auth/google` | — | Redirect to Google sign-in |
| `GET` | `/api/auth/google/callback` | — | OAuth callback → JWT |
| `GET` | `/api/auth/me` | ✅ | Current user |
| `POST` | `/api/orders` | ✅ | **Place an order (checkout)** |
| `GET` | `/api/orders` | ✅ | Order history |
| `GET` | `/api/orders/{id}` | ✅ | One order (owner only) |
| `GET` | `/api/health` | — | Health check |

## Layout

```
backend/
  main.py            API routes
  models.py          SQLAlchemy tables (User, Product, Order, OrderItem)
  schemas.py         Pydantic request/response shapes
  deps.py            Auth dependencies
  seed.py            Starter catalogue
  services/
    auth.py          Google OAuth + JWT
    orders.py        Checkout rules, server-side pricing
    email.py         Mailgun receipts
frontend/src/
  pages/             Shop, Checkout, OrderConfirmation, Orders
  components/        Header, Footer, ProductCard, OrderSummary
  api.js             API client + token storage
  CartContext.jsx    Cart state
  AuthContext.jsx    Signed-in user
```

## Deploying to Render

1. Push this project to GitHub.
2. Render picks up `render.yaml` — it seeds the catalogue and serves the built
   React app from FastAPI.
3. Set the secrets marked `sync: false` in the dashboard.
4. Update `GOOGLE_REDIRECT_URI` and `FRONTEND_URL` to your live domain, and add
   the live callback URL to your Google OAuth client.

## Notes

- Payment is intentionally a placeholder — orders are recorded as `pending` and
  no card is charged. Wire in Stripe before selling anything real.
- `JWT_SECRET` must be set to a random value in production:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
