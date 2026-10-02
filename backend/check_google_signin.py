"""
Google sign-in setup checker.

Answers one question: "is my Google sign-in actually going to work?"

Run this from the backend directory any time:

    python check_google_signin.py

It never prints your secrets, and it does not need a browser.
"""

import sys
import urllib.error
import urllib.request

import database  # noqa: F401  (loads .env, gives a clear error if the DB is unreachable)
from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    FRONTEND_URL,
    validate_settings,
)

# The exact address Google must be told about, plus the two that are easy to
# get wrong. Google's error for a mismatch is unhelpful, so we check first.
EXPECTED_REDIRECT = "http://localhost:8000/api/auth/google/callback"

problems: list[str] = []
notes: list[str] = []


def ok(label: str) -> None:
    print(f"  [OK]   {label}")


def warn(label: str) -> None:
    print(f"  [WARN] {label}")
    notes.append(label)


def bad(label: str, fix: str) -> None:
    print(f"  [FIX]  {label}")
    print(f"         -> {fix}")
    problems.append(label)


print("\n=== 1. Is the client ID filled in? ===")
if not GOOGLE_CLIENT_ID:
    bad(
        "GOOGLE_CLIENT_ID is empty",
        "Google Cloud console -> Google Auth Platform -> Clients -> Create client "
        "-> Web application. Then paste the Client ID into backend/.env",
    )
else:
    ok(f"Client ID looks filled in (ends ...{GOOGLE_CLIENT_ID[-8:]})")
    if GOOGLE_CLIENT_ID.endswith(".apps.googleusercontent.com"):
        ok("Client ID has the right shape for a Web application client")
    else:
        bad(
            "Client ID does not end in .apps.googleusercontent.com",
            "That suffix is what a Web application client ID looks like. If you "
            "made a Desktop or iOS client by mistake, delete it and create a "
            "Web application instead.",
        )

print("\n=== 2. Is the client secret filled in? ===")
if not GOOGLE_CLIENT_SECRET:
    bad(
        "GOOGLE_CLIENT_SECRET is empty",
        "Open the client in the Google console and click 'Download JSON' or copy "
        "the secret. NOTE: Google only shows the full secret once, at creation "
        "time. If you missed it, click 'Add secret' to make a new one.",
    )
else:
    ok("Client secret looks filled in")
    if len(GOOGLE_CLIENT_SECRET) < 20:
        warn("Client secret looks short - check you copied the whole thing")

print("\n=== 3. Does the redirect URI match Google exactly? ===")
if GOOGLE_REDIRECT_URI == EXPECTED_REDIRECT:
    ok("Redirect URI is correct")
    ok("  " + GOOGLE_REDIRECT_URI)
elif "localhost" in GOOGLE_REDIRECT_URI:
    bad(
        f"Redirect URI has a typo: {GOOGLE_REDIRECT_URI}",
        f"It must be exactly: {EXPECTED_REDIRECT}  "
        "(Google compares this character for character)",
    )
else:
    warn(f"Redirect URI is {GOOGLE_REDIRECT_URI} - fine for a deployed site, "
         "but make sure it matches Google too")

print("\n=== 4. Does the frontend URL look right? ===")
if FRONTEND_URL.rstrip("/") == "http://localhost:5173":
    ok("Frontend URL is correct for local development")
else:
    warn(f"FRONTEND_URL is {FRONTEND_URL} - this is where Google sends the "
         "customer back to after signing in")

print("\n=== 5. Can the app actually sign anyone in? ===")
# Ask our own backend. If the client ID is missing it answers 503.
url = "http://localhost:8000/api/auth/google"
try:
    # redirect=manual stops the browser/urllib following the hop to Google.
    request = urllib.request.Request(url, method="GET")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=10)
        status = response.status
        location = response.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        status = exc.code
        location = exc.headers.get("Location", "") if exc.headers else ""

    if status == 503:
        bad(
            "The backend says Google sign-in is not configured",
            "GOOGLE_CLIENT_ID is still empty. The backend is running, which is "
            "good - it just needs the client ID.",
        )
    elif location and "accounts.google.com" in location:
        ok("The backend built a working 'Sign in with Google' link")
        ok("  " + location[:110] + "...")
    else:
        warn(f"Unexpected response (status {status}) - is the backend running?")

except urllib.error.URLError:
    warn("Could not reach the backend on port 8000 - start it with: "
         "python -m uvicorn main:app --port 8000 --reload")
except Exception as exc:  # noqa: BLE001
    warn(f"Could not check ({type(exc).__name__})")

print("\n=== 6. Anything else the app is complaining about ===")
other = [p for p in validate_settings() if "GOOGLE" not in p]
if other:
    for problem in other:
        warn(problem)
else:
    ok("No other configuration problems")

print("\n" + "=" * 56)
if problems:
    print("NOT READY YET - fix the [FIX] lines above, then run this again.")
elif notes:
    print("LOOKS GOOD. Warnings above are worth a glance but nothing is broken.")
else:
    print("READY. Go to the shop and click 'Sign in'.")
print("=" * 56)
sys.exit(1 if problems else 0)
