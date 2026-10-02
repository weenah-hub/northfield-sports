"""
Mailgun setup checker.

Answers one question: "will order receipts actually send?"

Run this from the backend directory any time:

    python check_mailgun.py

It never prints your API key, and it never sends an email unless you ask it to
with --send.
"""

import asyncio
import sys

import httpx

from config import (
    MAILGUN_API_KEY,
    MAILGUN_DOMAIN,
    MAILGUN_FROM_EMAIL,
    validate_settings,
)
from services import email as email_service

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


print("\n=== 1. Is the API key filled in? ===")
if not MAILGUN_API_KEY:
    bad(
        "MAILGUN_API_KEY is empty",
        "Mailgun -> Sending -> API keys -> Create API key. Copy the key and "
        "paste it into backend/.env",
    )
else:
    ok(f"API key looks filled in (starts {MAILGUN_API_KEY[:4]}, {len(MAILGUN_API_KEY)} chars)")
    if len(MAILGUN_API_KEY) < 20:
        bad(
            "API key looks too short - you have probably copied only part of it",
            "Go back to the Mailgun API keys page and copy the whole key",
        )

print("\n=== 2. Is the sending domain right? ===")
if not MAILGUN_DOMAIN:
    bad(
        "MAILGUN_DOMAIN is empty",
        "Mailgun -> Sending -> Domains. You can use the sandbox domain that "
        "Mailgun gave you automatically, or your own domain",
    )
else:
    ok(f"Domain is set to '{MAILGUN_DOMAIN}'")
    # The single most common copy-paste mistake: pasting the whole dashboard
    # URL instead of the domain. The API wants only the host.
    if MAILGUN_DOMAIN.startswith("http") or "/mg/" in MAILGUN_DOMAIN or "?tab=" in MAILGUN_DOMAIN:
        bad(
            f"MAILGUN_DOMAIN looks like a dashboard URL, not a domain",
            "Use only the domain itself. For a sandbox domain that is the part "
            "before the first '@' in your Mailgun address, e.g.\n"
            "           sandbox12345.mailgun.org\n"
            "  (not 'https://app.mailgun.com/mg/sending/...?tab=setup')",
        )
    elif "@" in MAILGUN_DOMAIN:
        bad(
            f"MAILGUN_DOMAIN should not contain '@' (you have '{MAILGUN_DOMAIN}')",
            "Remove the local part and the '@'. For a sandbox domain that is\n"
            "           sandbox12345.mailgun.org",
        )
    else:
        ok("Domain format is correct")
    if MAILGUN_DOMAIN.endswith(".org") and "mailgun.org" not in MAILGUN_DOMAIN:
        warn("Domain ends in .org - is that really your sending domain?")

print("\n=== 3. Is the from-address set? ===")
if not MAILGUN_FROM_EMAIL or "yourdomain.com" in MAILGUN_FROM_EMAIL:
    bad(
        "MAILGUN_FROM_EMAIL is missing or still the placeholder",
        "It must be an address on the domain you are sending from, for example:\n"
        "           Northfield Sports <orders@sandbox12345.mailgun.org>",
    )
else:
    ok(f"From-address is '{MAILGUN_FROM_EMAIL}'")
    domain_part = MAILGUN_FROM_EMAIL.split("<")[-1].rstrip(">")
    if "@" not in domain_part:
        warn("From-address does not look like 'Name <email@domain>' - check the format")
    else:
        ok("From-address format looks right")
        # Mailgun refuses to send if the From domain is not one it manages.
        if MAILGUN_DOMAIN and MAILGUN_DOMAIN not in domain_part:
            warn(
                f"The from-domain does not contain your sending domain "
                f"('{MAILGUN_DOMAIN}'). Mailgun usually rejects that."
            )

print("\n=== 4. Does Mailgun accept these credentials? ===")
if MAILGUN_API_KEY and MAILGUN_DOMAIN and "@" not in MAILGUN_DOMAIN:
    async def verify() -> None:
        url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, auth=("api", MAILGUN_API_KEY))
            if response.status_code == 200:
                data = response.json()
                state = data.get("state", "unknown")
                ok("Mailgun accepted the key and domain")
                if state == "active":
                    ok("  Domain state: active (good)")
                else:
                    warn(f"  Domain state: {state}")
                    if state == "unverified":
                        warn("  An unverified domain usually still sends, but "
                             "your messages will show 'via mailgun.org'")
            elif response.status_code == 401:
                bad("Mailgun rejected the API key", "Check you copied the whole key")
            elif response.status_code == 404:
                # Before blaming the config, ask Mailgun what it actually calls
                # this domain. The dashboard shows a shortened form in some
                # places and the full hostname in others, and guessing between
                # them is the whole problem.
                domain = MAILGUN_DOMAIN
                async with httpx.AsyncClient(timeout=15.0) as client:
                    listing = await client.get(
                        "https://api.mailgun.net/v3/domains",
                        auth=("api", MAILGUN_API_KEY),
                    )
                actual = []
                if listing.status_code == 200:
                    actual = [d.get("name") for d in listing.json().get("items", [])]

                if domain not in actual:
                    matches = [name for name in actual if domain in (name or "")]
                    if len(matches) == 1:
                        bad(
                            f"MAILGUN_DOMAIN should be '{matches[0]}', not '{domain}'",
                            "Mailgun lists your domains as: " + ", ".join(actual),
                        )
                    else:
                        bad(
                            "Mailgun does not recognise that domain",
                            "Mailgun lists your domains as: "
                            + (", ".join(actual) if actual else "(none found)"),
                        )
                else:
                    ok("Domain is recognised")
            else:
                warn(f"Mailgun replied {response.status_code}: {response.text[:120]}")
        except Exception as exc:  # noqa: BLE001
            warn(f"Could not reach Mailgun ({type(exc).__name__}) - check your internet")

    asyncio.run(verify())
else:
    warn("Skipped - the key or domain is not usable yet")

print("\n=== 5. Can the app build a receipt? ===")
# Build a fake order and render the email, so we know the template works even
# before a real order exists.
try:
    class FakeProduct:
        name = "Matchday Home Jersey"
        image_url = ""

    class FakeItem:
        product = FakeProduct()
        product_id = 1
        quantity = 2
        price = 64.0

    class FakeOrder:
        id = 999
        status = "pending"
        shipping_name = "Test Buyer"
        shipping_address = "1 Test Street"
        shipping_city = "Testville"
        shipping_zip = "12345"
        shipping_country = "United States"
        subtotal = 128.0
        shipping = 0.0
        tax = 10.56
        total = 138.56
        items = [FakeItem()]

    html = email_service.build_receipt_html(FakeOrder())
    ok("Receipt template renders")
    if "$138.56" in html:
        ok("  Receipt shows the correct total")
    else:
        bad("Receipt total looks wrong", "The template may be broken")
except Exception as exc:  # noqa: BLE001
    bad(f"Receipt template failed: {type(exc).__name__}", str(exc))

print("\n=== 6. Anything else the app is complaining about ===")
other = [p for p in validate_settings() if "MAILGUN" not in p]
if other:
    for problem in other:
        warn(problem)
else:
    ok("No other configuration problems")

# ---------- Optional live send ----------
if "--send" in sys.argv:
    recipient = None
    if "-t" in sys.argv:
        recipient = sys.argv[sys.argv.index("-t") + 1]
    recipient = recipient or input("Send a test email to which address? ")

    print(f"\n=== 7. Live send to {recipient} ===")

    class P2:
        name = "Matchday Home Jersey"
        image_url = ""

    class I2:
        product = P2()
        product_id = 1
        quantity = 2
        price = 64.0

    class O2:
        id = 999
        status = "pending"
        shipping_name = "Test Buyer"
        shipping_address = "1 Test Street"
        shipping_city = "Testville"
        shipping_zip = "12345"
        shipping_country = "United States"
        subtotal = 128.0
        shipping = 0.0
        tax = 10.56
        total = 138.56
        items = [I2()]

    if not email_service.is_configured():
        bad("Mailgun is not configured, so nothing can be sent", "Fix the [FIX] lines above")
    else:
        sent = asyncio.run(email_service.send_order_confirmation(O2(), recipient))
        if sent:
            ok(f"Mailgun accepted the message for {recipient}")
            print("         Check the inbox (and spam) in a minute or two.")
        else:
            bad(
                "Mailgun refused the message",
                "The log line above says why. The usual cause on a free "
                "account is that the recipient is not an authorized recipient - "
                "add them under Sending -> Domains -> your sandbox domain",
            )

print("\n" + "=" * 56)
if problems:
    print("NOT READY YET - fix the [FIX] lines above, then run this again.")
elif notes:
    print("LOOKS GOOD. Warnings above are worth a glance but nothing is broken.")
else:
    print("READY. Place an order and the receipt will be emailed.")
print("=" * 56)
sys.exit(1 if problems else 0)
