"""
Checks that the browser will actually be allowed to talk to the API.

CORS is the thing that silently breaks when the frontend and the API are
hosted on different domains (Netlify + Render). The browser blocks the request
before it ever reaches the server, so the failure looks like the API is down
when it is perfectly healthy.

Run this from the backend directory once you know your live URLs:

    python check_cors.py https://your-site.netlify.app
"""

import sys

import httpx

ORIGINS = sys.argv[1:] or ["http://localhost:5173"]

# Endpoints a signed-out visitor can reach without a token.
PUBLIC_CALLS = [
    ("GET", "/api/health"),
    ("GET", "/api/products"),
    ("POST", "/api/orders/quote"),
]

failures = 0

print("\n=== Which origins does this server allow? ===")
import main  # noqa: E402

for origin in sorted(main.app.user_middleware[0].kwargs["allow_origins"]):
    print(f"  {origin}")

if not ORIGINS:
    print("\nPass an origin to test, e.g.:")
    print("  python check_cors.py https://your-site.netlify.app")
    raise SystemExit(0)

for origin in ORIGINS:
    print(f"\n=== Does it allow {origin}? ===")
    try:
        with httpx.Client(base_url="http://localhost:8000", timeout=10.0) as client:
            for method, path in PUBLIC_CALLS:
                headers = {
                    "Origin": origin,
                    "Content-Type": "application/json",
                }
                if method == "POST":
                    response = client.post(
                        path, json={"items": [{"product_id": 1, "quantity": 1}]}, headers=headers
                    )
                else:
                    response = client.get(path, headers=headers)

                allowed = response.headers.get("access-control-allow-origin")
                if allowed == origin:
                    print(f"  [OK]   {method:4} {path}")
                elif allowed is None:
                    print(f"  [FAIL] {method:4} {path} - no CORS header returned")
                    print("         The browser will block this. Set FRONTEND_URL to your")
                    print("         site's address (no trailing slash) and restart the API.")
                    failures += 1
                else:
                    print(f"  [FAIL] {method:4} {path} - allowed origin is '{allowed}'")
                    failures += 1
    except httpx.ConnectError:
        print(f"  [FAIL] could not reach the API on port 8000 - start it with start.ps1")
        failures += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {type(exc).__name__}: {exc}")
        failures += 1

print("\n" + "=" * 56)
if failures:
    print(f"{failures} CORS problem(s). The browser will refuse these requests.")
else:
    print("CORS looks fine for the origins given.")
print("=" * 56)
raise SystemExit(1 if failures else 0)