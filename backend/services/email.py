"""
Email service
=============
Sends order confirmation receipts through the Mailgun HTTP API.

Mail failures are logged and swallowed: a customer must still get their order
confirmation screen even if the receipt email does not go out.
"""

import logging

import httpx

from config import MAILGUN_API_KEY, MAILGUN_DOMAIN, MAILGUN_FROM_EMAIL

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """True when Mailgun has enough settings to attempt a send."""
    return bool(MAILGUN_API_KEY) and bool(MAILGUN_DOMAIN)


def build_receipt_html(order) -> str:
    """Render the order receipt as a simple HTML email."""
    rows = []
    for item in order.items:
        product = item.product
        name = product.name if product else f"Product #{item.product_id}"
        image_cell = ""
        if product and product.image_url:
            image_cell = (
                f'<img src="{product.image_url}" alt="" '
                f'style="width:56px;height:56px;object-fit:cover;border-radius:8px;" />'
            )
        rows.append(
            f"""
            <tr>
              <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;">
                <table width="100%" cellpadding="0" cellspacing="0"><tr>
                  <td width="72" valign="middle">{image_cell}</td>
                  <td valign="middle">
                    <div style="color:#111827;font-weight:600;">{name}</div>
                    <div style="color:#6b7280;font-size:13px;">
                      Qty {item.quantity} &times; ${item.price:,.2f}
                    </div>
                  </td>
                  <td valign="middle" align="right" style="color:#111827;white-space:nowrap;">
                    ${item.price * item.quantity:,.2f}
                  </td>
                </tr></table>
              </td>
            </tr>
            """
        )

    return f"""
    <!DOCTYPE html>
    <html>
      <body style="margin:0;padding:24px;background:#f3f4f6;
                   font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;
               background:#ffffff;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="background:#111827;padding:24px 28px;">
              <div style="color:#ffffff;font-size:19px;font-weight:700;">Thanks for your order!</div>
              <div style="color:#9ca3af;font-size:14px;margin-top:4px;">
                Order #{order.id} &middot; {order.status.upper()}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 28px;">
              <div style="color:#111827;font-size:15px;line-height:1.6;">
                Hi {order.shipping_name},<br />
                We have received your order and will email you again when it ships.
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:8px 0;color:#6b7280;font-size:13px;
                             text-transform:uppercase;letter-spacing:.05em;">Items</td>
                </tr>
                {''.join(rows)}
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">
                    Subtotal
                  </td>
                  <td align="right" style="padding:6px 0;color:#111827;font-size:14px;">
                    ${order.subtotal:,.2f}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Shipping</td>
                  <td align="right" style="padding:6px 0;color:#111827;font-size:14px;">
                    {'Free' if order.shipping == 0 else f'${order.shipping:,.2f}'}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Tax</td>
                  <td align="right" style="padding:6px 0;color:#111827;font-size:14px;">
                    ${order.tax:,.2f}
                  </td>
                </tr>
                <tr>
                  <td align="right" style="padding:16px 0 0;color:#111827;font-size:16px;font-weight:700;">
                    Total&nbsp;&nbsp;${order.total:,.2f}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 28px;">
              <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:16px;">
                <div style="color:#111827;font-weight:600;font-size:14px;margin-bottom:6px;">
                  Shipping to
                </div>
                <div style="color:#4b5563;font-size:14px;line-height:1.6;">
                  {order.shipping_name}<br />
                  {order.shipping_address}<br />
                  {order.shipping_city}, {order.shipping_zip}<br />
                  {order.shipping_country}
                </div>
              </div>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


async def send_order_confirmation(order, to_email: str) -> bool:
    """Email the receipt. Returns True on success, False on failure."""
    if not is_configured():
        logger.warning("Mailgun is not configured; skipping receipt for order %s", order.id)
        return False

    payload = {
        "from": MAILGUN_FROM_EMAIL,
        "to": to_email,
        "subject": f"Your order #{order.id} is confirmed",
        "html": build_receipt_html(order),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
                auth=("api", MAILGUN_API_KEY),
                data=payload,
            )
        if response.status_code >= 300:
            logger.error(
                "Mailgun rejected the receipt for order %s (%s): %s",
                order.id,
                response.status_code,
                response.text[:400],
            )
            return False
    except Exception:
        logger.exception("Failed to send receipt for order %s", order.id)
        return False

    logger.info("Sent receipt for order %s to %s", order.id, to_email)
    return True
