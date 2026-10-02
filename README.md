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
2. The page asks the server to price the cart (`POST /api/orders/quote`) and
   renders whatever comes back. **The browser never does arithmetic on money.**
3. If they are not signed in, the page sends them through Google and back to
   `/checkout` — the cart is preserved in `localStorage`.
4. On submit, the client sends **product IDs and quantities only**.
5. The server reloads the catalogue, checks stock, computes the total, snapshots
   each price onto the order, and decrements stock.
6. A receipt is emailed in a background task, so a slow mail server never
   delays the response.

### One price, one place

Shipping and tax rules live in exactly one file, `backend/pricing.py`. Both the
quote endpoint and order creation call it, so the figure on the "Place order"
button is by construction the figure written to the database.

This was a real bug once: the checkout page computed shipping and tax in
JavaScript while the server only stored the goods subtotal, so a customer could
be quoted $95.72 and have $82.00 recorded. `backend/verify_flow.py` now asserts
the quoted and stored totals are equal, so it cannot drift back.

Two more details worth knowing:

- Money is `Decimal` internally and rounded half-up **once**, via
  `Decimal(str(x))`. Rounding `Decimal(1.005)` directly would round down to
  `1.00`, because the float `1.005` is really `1.00499999999999989...`.
- Each order stores its own `subtotal`, `shipping` and `tax`, so changing the
  rules later never rewrites what a past customer was told.

## Setup

### Running it

After the one-off setup below, start everything with a single command from the
project root:

```powershell
.\start.ps1
```

It opens two visible PowerShell windows (API on port 8000, website on port
5173) and tells you when each is ready. Open <http://localhost:5173>.

To stop, close both windows. To check the setup at any time:

```bash
cd backend
python check_google_signin.py   # is Google sign-in wired up?
python check_mailgun.py         # will receipts actually send?
python check_mailgun.py --send  # ...and send a test email
```

> **Note:** `--reload` watches `.py` files only. After editing `backend/.env`
> you must restart the backend, or the new values are ignored.

### First-time setup

#### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

`.env` needs five things:

| Variable | Where to get it |
| --- | --- |
| `DATABASE_URL` | Supabase → **Connect** button at the top of the project page → **Session pooler** |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud → APIs & Services → Credentials → OAuth client |
| `MAILGUN_API_KEY` / `MAILGUN_DOMAIN` | Mailgun → Sending → Domains |

The app logs a clear list of anything missing on startup, so you do not have to
guess at silent failures.

### Supabase setup in detail

1. Create a free project at [supabase.com](https://supabase.com).
2. Wait for the database to finish provisioning (a minute or two).
3. **Click the "Connect" button at the top of the project page.** This is the
   current way in — the connection string is *not* under Project Settings
   anymore, which is the usual reason people get stuck.
4. In that dialog choose **Session pooler**. This matters:
   - The **Direct connection** option gives a host like `db.<ref>.supabase.co`,
     which is **IPv6-only** and usually will not connect from a home network.
     The symptom is the app hanging on startup rather than a clear error.
   - **Session pooler** gives a host like
     `aws-0-<region>.pooler.supabase.com`, which works over IPv4.
   - The pooler host cannot be worked out from your region — copy it from the
     dialog rather than typing it.
5. Set the database password: **Project Settings → Database → Reset database
   password**. This is *not* the same as your Supabase login password.
6. Paste the string into `DATABASE_URL` in `backend/.env`:

   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

   If your password contains `@`, `:`, `/`, `&`, `#` or `?`, it must be
   percent-encoded (`@` → `%40`). The dialog's copy button handles this for
   you, so copy the whole string rather than retyping it.

`backend/database.py` handles the rest automatically: it appends
`?sslmode=require` if you left it off, and disables prepared statements if you
ever switch to the **Transaction pooler** (port 6543), which does not support
them. Session mode (port 5432) supports them and is left on.

Neon still works — just paste its SQLAlchemy URI into the same variable.

### Mailgun setup in detail

1. Create a free account at [mailgun.com](https://www.mailgun.com).
2. **Sending → Domains.** Every new account gets a *sandbox* domain
   automatically, something like `sandbox12345@mailgun.org`. You do not need to
   buy a domain or touch DNS records for this project.
3. **Sending → API keys**, and copy the **private** key (the long one starting
   `key-`).
4. **Add yourself as an authorized recipient.** Click the sandbox domain →
   **Setup** tab → **Authorized recipients** → add the email address you will
   test with.

Step 4 is the one that catches people. A free Mailgun account will only send to
addresses on that list, and it does *not* explain itself — the order still saves
and the receipt silently never arrives.

Then set two variables in `backend/.env`:

```
MAILGUN_API_KEY=key-xxxxxxxxxxxx
MAILGUN_DOMAIN=sandbox12345
MAILGUN_FROM_EMAIL=Northfield Sports <orders@sandbox12345.mailgun.org>
```

`MAILGUN_DOMAIN` is just the host with no `@mailgun.org` and no `https://` —
the API rejects the full address, and it is the most common paste mistake.

Verify before placing a real order:

```bash
python check_mailgun.py --send
```

The messages will show *via mailgun.org* until you verify a domain of your own,
which is expected and fine here.

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
| `POST` | `/api/orders/quote` | — | **Price a cart for display** (no sign-in) |
| `POST` | `/api/orders` | ✅ | **Place an order (checkout)** |
| `GET` | `/api/orders` | ✅ | Order history |
| `GET` | `/api/orders/{id}` | ✅ | One order (owner only) |
| `GET` | `/api/health` | — | Health check |

## Tests

Two scripts, no accounts or API keys needed — they run against a local SQLite
file. Run them from `backend/` with the venv activated:

```bash
python verify_flow.py            # pricing, stock, auth, order isolation, receipt
python verify_migration.py       # upgrading an existing database in place
python verify_database_config.py # Supabase/Neon connection-string handling
```

`verify_flow.py` includes the regression test for the pricing bug: it places a
real order and asserts the stored total equals the quoted total.

`verify_migration.py` builds the *old* schema by hand, runs the migration, and
confirms existing orders survive. Worth running once if you already have a
database.

`verify_database_config.py` checks the Supabase-specific traps: missing
`sslmode`, the IPv6-only host, and prepared statements against PgBouncer.

These run on a local SQLite file, so they do not touch your real database.

## Layout

```
backend/
  main.py            API routes
  models.py          SQLAlchemy tables (User, Product, Order, OrderItem)
  database.py        Engine setup; handles Supabase SSL + pooler quirks
  pricing.py         Shipping + tax rules — the only place money is decided
  migrations.py      Adds new columns to an existing database
  schemas.py         Pydantic request/response shapes
  deps.py            Auth dependencies
  seed.py            Starter catalogue
  verify_flow.py       End-to-end checks (no keys needed)
  verify_migration.py  Schema upgrade on an existing database
  verify_database_config.py  Supabase/Neon connection strings
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
- CORS is restricted to `FRONTEND_URL` plus the two local dev origins. The
  storefront is served by the same app in production, so it needs no CORS at
  all; those entries only exist for `npm run dev`.
- New columns are added by `backend/migrations.py` on startup. `create_all()`
  only creates whole tables, so it will never add a column to a table that
  already exists — the migration covers that gap.
