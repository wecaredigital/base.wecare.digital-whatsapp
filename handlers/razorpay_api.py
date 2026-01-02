# =============================================================================
# RAZORPAY PAYMENT API HANDLER
# =============================================================================
# Independent payment handler for Razorpay integration
# Can be attached to any Lambda/API Gateway independently
#
# Routes:
#   GET  /                    → Redirect to https://wecare.digital/selfservice
#   GET  /p/{payment_id}      → Public payment page redirect
#   GET  /p/pay/{payment_id}  → Payment checkout page
#   POST /razorpay-webhook    → Razorpay webhook handler
#   ANY  /*                   → 404 redirect to https://wecare.digital/selfservice
#
# Configuration:
#   - RAZORPAY_KEY_ID: Razorpay Key ID (from env or Secrets Manager)
#   - RAZORPAY_KEY_SECRET: Razorpay Key Secret (from Secrets Manager)
#   - RAZORPAY_WEBHOOK_SECRET: Webhook signature secret
#   - RAZORPAY_SECRET_ARN: ARN for Secrets Manager secret
#   - FAVICON_URL: Favicon URL for payment pages
#   - DEFAULT_REDIRECT_URL: Default redirect for root/404
#
# Test Links:
#   - Root: https://p.wecare.digital/ → redirects to selfservice
#   - Payment: https://p.wecare.digital/p/pay/test123 → payment page
#   - 404: https://p.wecare.digital/unknown → redirects to selfservice
# =============================================================================

import json
import logging
import os
import hmac
import hashlib
import base64
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# CONFIGURATION
# =============================================================================
DEFAULT_REDIRECT_URL = "https://wecare.digital/selfservice"
FAVICON_URL = "https://selfcare.wecare.digital/wecare-digital.ico"

# Razorpay Configuration (from environment or Secrets Manager)
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_live_CLnEhAF46T9eQm")
RAZORPAY_SECRET_ARN = os.environ.get("RAZORPAY_SECRET_ARN", "arn:aws:secretsmanager:ap-south-1:010526260063:secret:wecare-digital/razorpay-6rCxYB")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "b@c4mk9t9Z8qLq3")
RAZORPAY_MERCHANT_ID = os.environ.get("RAZORPAY_MERCHANT_ID", "acc_HDfub6wOfQybuH")

# DynamoDB Configuration
MESSAGES_TABLE_NAME = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
MESSAGES_PK_NAME = os.environ.get("MESSAGES_PK_NAME", "pk")

# Lazy clients
_clients: Dict[str, Any] = {}
_secrets_cache: Dict[str, Any] = {}


def _get_client(name: str):
    if name not in _clients:
        _clients[name] = boto3.client(name)
    return _clients[name]


def _get_table():
    if "table" not in _clients:
        _clients["table"] = boto3.resource("dynamodb").Table(MESSAGES_TABLE_NAME)
    return _clients["table"]


def _get_razorpay_secrets() -> Dict[str, str]:
    """Get Razorpay secrets from Secrets Manager."""
    if "razorpay" in _secrets_cache:
        return _secrets_cache["razorpay"]
    
    try:
        sm = _get_client("secretsmanager")
        response = sm.get_secret_value(SecretId=RAZORPAY_SECRET_ARN)
        secret = json.loads(response.get("SecretString", "{}"))
        _secrets_cache["razorpay"] = {
            "key_id": secret.get("key_id", RAZORPAY_KEY_ID),
            "key_secret": secret.get("key_secret", ""),
            "webhook_secret": secret.get("webhook_secret", RAZORPAY_WEBHOOK_SECRET),
            "merchant_id": secret.get("merchant_id", RAZORPAY_MERCHANT_ID),
        }
        return _secrets_cache["razorpay"]
    except Exception as e:
        logger.warning(f"Failed to get secrets from Secrets Manager: {e}")
        return {
            "key_id": RAZORPAY_KEY_ID,
            "key_secret": "",
            "webhook_secret": RAZORPAY_WEBHOOK_SECRET,
            "merchant_id": RAZORPAY_MERCHANT_ID,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# CORS HEADERS
# =============================================================================
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Razorpay-Signature, X-Requested-With",
    "Access-Control-Max-Age": "86400",
}


def cors_response(status_code: int, body: Any, content_type: str = "application/json") -> Dict[str, Any]:
    """Return response with CORS headers."""
    headers = {**CORS_HEADERS, "Content-Type": content_type}
    
    if content_type == "application/json":
        body_str = json.dumps(body, ensure_ascii=False, default=str)
    else:
        body_str = str(body)
    
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": body_str,
    }


def redirect_response(url: str, status_code: int = 302) -> Dict[str, Any]:
    """Return redirect response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            **CORS_HEADERS,
            "Location": url,
            "Content-Type": "text/html",
        },
        "body": f'<html><head><meta http-equiv="refresh" content="0;url={url}"></head><body>Redirecting to <a href="{url}">{url}</a></body></html>',
    }


# =============================================================================
# PAYMENT PAGE HTML TEMPLATES
# =============================================================================
def get_payment_page_html(payment_id: str, amount: float, currency: str = "INR", 
                          description: str = "", order_id: str = "") -> str:
    """Generate payment checkout page HTML."""
    secrets = _get_razorpay_secrets()
    key_id = secrets.get("key_id", RAZORPAY_KEY_ID)
    
    amount_paise = int(amount * 100)  # Convert to paise
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment - WECARE.DIGITAL</title>
    <link rel="icon" href="{FAVICON_URL}" type="image/x-icon">
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .logo {{ font-size: 48px; margin-bottom: 20px; }}
        h1 {{ color: #333; margin-bottom: 10px; font-size: 24px; }}
        .amount {{
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
            margin: 20px 0;
        }}
        .description {{ color: #666; margin-bottom: 30px; }}
        .pay-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 16px 40px;
            font-size: 18px;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .pay-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }}
        .secure {{ color: #888; font-size: 12px; margin-top: 20px; }}
        .order-id {{ color: #999; font-size: 11px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">💳</div>
        <h1>Complete Payment</h1>
        <div class="amount">{currency} {amount:.2f}</div>
        <p class="description">{description or 'Payment to WECARE.DIGITAL'}</p>
        <button class="pay-btn" onclick="openRazorpay()">Pay Now</button>
        <p class="secure">🔒 Secured by Razorpay</p>
        <p class="order-id">Order: {order_id or payment_id}</p>
    </div>
    <script>
        function openRazorpay() {{
            var options = {{
                "key": "{key_id}",
                "amount": "{amount_paise}",
                "currency": "{currency}",
                "name": "WECARE.DIGITAL",
                "description": "{description or 'Payment'}",
                "order_id": "{order_id}",
                "handler": function(response) {{
                    window.location.href = "/p/success?payment_id=" + response.razorpay_payment_id;
                }},
                "prefill": {{}},
                "theme": {{ "color": "#667eea" }},
                "modal": {{ "ondismiss": function() {{ console.log("Payment cancelled"); }} }}
            }};
            var rzp = new Razorpay(options);
            rzp.open();
        }}
        // Auto-open payment modal
        setTimeout(openRazorpay, 500);
    </script>
</body>
</html>'''


def get_success_page_html(payment_id: str) -> str:
    """Generate payment success page HTML."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Successful - WECARE.DIGITAL</title>
    <link rel="icon" href="{FAVICON_URL}" type="image/x-icon">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .checkmark {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #11998e; margin-bottom: 10px; }}
        .message {{ color: #666; margin-bottom: 20px; }}
        .payment-id {{ color: #999; font-size: 12px; word-break: break-all; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✅</div>
        <h1>Payment Successful!</h1>
        <p class="message">Thank you for your payment. You will receive a confirmation shortly.</p>
        <p class="payment-id">Payment ID: {payment_id}</p>
    </div>
</body>
</html>'''


def get_error_page_html(error: str) -> str:
    """Generate payment error page HTML."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Error - WECARE.DIGITAL</title>
    <link rel="icon" href="{FAVICON_URL}" type="image/x-icon">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .error-icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #eb3349; margin-bottom: 10px; }}
        .message {{ color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">❌</div>
        <h1>Payment Error</h1>
        <p class="message">{error}</p>
    </div>
</body>
</html>'''


# =============================================================================
# WEBHOOK SIGNATURE VERIFICATION
# =============================================================================
def verify_razorpay_signature(payload: str, signature: str, secret: str = None) -> bool:
    """Verify Razorpay webhook signature."""
    if not signature:
        return False
    
    if not secret:
        secrets = _get_razorpay_secrets()
        secret = secrets.get("webhook_secret", RAZORPAY_WEBHOOK_SECRET)
    
    try:
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


# =============================================================================
# RAZORPAY WEBHOOK HANDLER
# =============================================================================
def handle_razorpay_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Razorpay webhook events.
    
    Webhook URL: https://p.wecare.digital/razorpay-webhook
    
    Supported Events:
    - payment.authorized
    - payment.captured
    - payment.failed
    - order.paid
    - refund.created
    """
    body = event.get("body", "")
    signature = event.get("headers", {}).get("x-razorpay-signature", "")
    
    # Also check lowercase headers (API Gateway normalizes)
    if not signature:
        headers = event.get("headers", {})
        signature = headers.get("X-Razorpay-Signature", headers.get("x-razorpay-signature", ""))
    
    logger.info(f"Razorpay webhook received, signature present: {bool(signature)}")
    
    # Verify signature
    if not verify_razorpay_signature(body, signature):
        logger.warning("Invalid Razorpay webhook signature")
        return cors_response(401, {"error": "Invalid signature"})
    
    try:
        payload = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        return cors_response(400, {"error": "Invalid JSON payload"})
    
    event_type = payload.get("event", "")
    event_payload = payload.get("payload", {})
    
    logger.info(f"Razorpay event: {event_type}")
    
    now = iso_now()
    
    # Store webhook event
    webhook_pk = f"RAZORPAY_WEBHOOK#{payload.get('event_id', now)}"
    try:
        _get_table().put_item(Item={
            MESSAGES_PK_NAME: webhook_pk,
            "itemType": "RAZORPAY_WEBHOOK",
            "eventType": event_type,
            "eventId": payload.get("event_id", ""),
            "payload": payload,
            "receivedAt": now,
            "processed": False,
        })
    except Exception as e:
        logger.error(f"Failed to store webhook: {e}")
    
    # Process based on event type
    result = {"event": event_type, "status": "received"}
    
    if event_type == "payment.captured":
        payment = event_payload.get("payment", {}).get("entity", {})
        result = process_payment_captured(payment, now)
    
    elif event_type == "payment.failed":
        payment = event_payload.get("payment", {}).get("entity", {})
        result = process_payment_failed(payment, now)
    
    elif event_type == "payment.authorized":
        payment = event_payload.get("payment", {}).get("entity", {})
        result = process_payment_authorized(payment, now)
    
    elif event_type == "order.paid":
        order = event_payload.get("order", {}).get("entity", {})
        result = process_order_paid(order, now)
    
    elif event_type == "refund.created":
        refund = event_payload.get("refund", {}).get("entity", {})
        result = process_refund_created(refund, now)
    
    # Mark webhook as processed
    try:
        _get_table().update_item(
            Key={MESSAGES_PK_NAME: webhook_pk},
            UpdateExpression="SET processed = :p, processedAt = :pa, processResult = :pr",
            ExpressionAttributeValues={":p": True, ":pa": now, ":pr": result}
        )
    except Exception as e:
        logger.error(f"Failed to update webhook status: {e}")
    
    return cors_response(200, {"status": "ok", "event": event_type, **result})


def process_payment_captured(payment: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Process payment.captured event."""
    payment_id = payment.get("id", "")
    order_id = payment.get("order_id", "")
    amount = payment.get("amount", 0) / 100  # Convert from paise
    currency = payment.get("currency", "INR")
    method = payment.get("method", "")
    email = payment.get("email", "")
    contact = payment.get("contact", "")
    
    logger.info(f"Payment captured: {payment_id}, amount: {amount} {currency}")
    
    # Store payment record
    payment_pk = f"RAZORPAY_PAYMENT#{payment_id}"
    try:
        _get_table().put_item(Item={
            MESSAGES_PK_NAME: payment_pk,
            "itemType": "RAZORPAY_PAYMENT",
            "paymentId": payment_id,
            "orderId": order_id,
            "amount": amount,
            "currency": currency,
            "status": "captured",
            "method": method,
            "email": email,
            "contact": contact,
            "capturedAt": timestamp,
            "rawPayment": payment,
        })
    except Exception as e:
        logger.error(f"Failed to store payment: {e}")
    
    # Update order status if exists
    if order_id:
        try:
            _get_table().update_item(
                Key={MESSAGES_PK_NAME: f"RAZORPAY_ORDER#{order_id}"},
                UpdateExpression="SET #st = :st, paymentId = :pid, paidAt = :pa",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":st": "paid", ":pid": payment_id, ":pa": timestamp}
            )
        except Exception:
            pass  # Order might not exist
    
    # TODO: Trigger WhatsApp confirmation message
    # This would call the main Lambda to send confirmation
    
    return {
        "paymentId": payment_id,
        "orderId": order_id,
        "amount": amount,
        "status": "captured"
    }


def process_payment_failed(payment: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Process payment.failed event."""
    payment_id = payment.get("id", "")
    order_id = payment.get("order_id", "")
    error_code = payment.get("error_code", "")
    error_description = payment.get("error_description", "")
    
    logger.info(f"Payment failed: {payment_id}, error: {error_code}")
    
    payment_pk = f"RAZORPAY_PAYMENT#{payment_id}"
    try:
        _get_table().put_item(Item={
            MESSAGES_PK_NAME: payment_pk,
            "itemType": "RAZORPAY_PAYMENT",
            "paymentId": payment_id,
            "orderId": order_id,
            "status": "failed",
            "errorCode": error_code,
            "errorDescription": error_description,
            "failedAt": timestamp,
            "rawPayment": payment,
        })
    except Exception as e:
        logger.error(f"Failed to store payment: {e}")
    
    return {
        "paymentId": payment_id,
        "status": "failed",
        "errorCode": error_code
    }


def process_payment_authorized(payment: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Process payment.authorized event."""
    payment_id = payment.get("id", "")
    order_id = payment.get("order_id", "")
    amount = payment.get("amount", 0) / 100
    
    logger.info(f"Payment authorized: {payment_id}, amount: {amount}")
    
    return {
        "paymentId": payment_id,
        "orderId": order_id,
        "amount": amount,
        "status": "authorized"
    }


def process_order_paid(order: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Process order.paid event."""
    order_id = order.get("id", "")
    amount = order.get("amount_paid", 0) / 100
    
    logger.info(f"Order paid: {order_id}, amount: {amount}")
    
    order_pk = f"RAZORPAY_ORDER#{order_id}"
    try:
        _get_table().update_item(
            Key={MESSAGES_PK_NAME: order_pk},
            UpdateExpression="SET #st = :st, amountPaid = :ap, paidAt = :pa",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "paid", ":ap": amount, ":pa": timestamp}
        )
    except Exception:
        pass
    
    return {"orderId": order_id, "amount": amount, "status": "paid"}


def process_refund_created(refund: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Process refund.created event."""
    refund_id = refund.get("id", "")
    payment_id = refund.get("payment_id", "")
    amount = refund.get("amount", 0) / 100
    
    logger.info(f"Refund created: {refund_id}, payment: {payment_id}, amount: {amount}")
    
    refund_pk = f"RAZORPAY_REFUND#{refund_id}"
    try:
        _get_table().put_item(Item={
            MESSAGES_PK_NAME: refund_pk,
            "itemType": "RAZORPAY_REFUND",
            "refundId": refund_id,
            "paymentId": payment_id,
            "amount": amount,
            "status": "created",
            "createdAt": timestamp,
            "rawRefund": refund,
        })
    except Exception as e:
        logger.error(f"Failed to store refund: {e}")
    
    return {"refundId": refund_id, "paymentId": payment_id, "amount": amount}


# =============================================================================
# PAYMENT LINK CREATION
# =============================================================================
def create_payment_link(amount: float, currency: str = "INR", description: str = "",
                        customer_name: str = "", customer_email: str = "",
                        customer_phone: str = "", order_id: str = "",
                        callback_url: str = "", expire_by: int = None) -> Dict[str, Any]:
    """Create a Razorpay payment link.
    
    Args:
        amount: Amount in rupees (will be converted to paise)
        currency: Currency code (default INR)
        description: Payment description
        customer_name: Customer name
        customer_email: Customer email
        customer_phone: Customer phone
        order_id: Reference order ID
        callback_url: URL to redirect after payment
        expire_by: Unix timestamp for link expiry
    
    Returns:
        Payment link details including short_url
    """
    import urllib.request
    import urllib.error
    
    secrets = _get_razorpay_secrets()
    key_id = secrets.get("key_id", RAZORPAY_KEY_ID)
    key_secret = secrets.get("key_secret", "")
    
    if not key_secret:
        return {"error": "Razorpay key secret not configured"}
    
    # Build request payload
    payload = {
        "amount": int(amount * 100),  # Convert to paise
        "currency": currency,
        "accept_partial": False,
        "description": description or "Payment",
        "customer": {},
        "notify": {"sms": True, "email": True},
        "reminder_enable": True,
        "callback_url": callback_url or "https://p.wecare.digital/p/success",
        "callback_method": "get",
    }
    
    if customer_name:
        payload["customer"]["name"] = customer_name
    if customer_email:
        payload["customer"]["email"] = customer_email
    if customer_phone:
        payload["customer"]["contact"] = customer_phone
    if order_id:
        payload["reference_id"] = order_id
    if expire_by:
        payload["expire_by"] = expire_by
    
    # Make API request
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            
            # Store payment link in DynamoDB
            link_id = result.get("id", "")
            link_pk = f"RAZORPAY_LINK#{link_id}"
            try:
                _get_table().put_item(Item={
                    MESSAGES_PK_NAME: link_pk,
                    "itemType": "RAZORPAY_LINK",
                    "linkId": link_id,
                    "shortUrl": result.get("short_url", ""),
                    "amount": amount,
                    "currency": currency,
                    "description": description,
                    "orderId": order_id,
                    "status": result.get("status", "created"),
                    "createdAt": iso_now(),
                    "rawResponse": result,
                })
            except Exception as e:
                logger.error(f"Failed to store payment link: {e}")
            
            return {
                "success": True,
                "linkId": link_id,
                "shortUrl": result.get("short_url", ""),
                "amount": amount,
                "currency": currency,
                "status": result.get("status", "created"),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        logger.error(f"Razorpay API error: {e.code} - {error_body}")
        return {"error": f"Razorpay API error: {e.code}", "details": error_body}
    except Exception as e:
        logger.error(f"Failed to create payment link: {e}")
        return {"error": str(e)}


def handle_create_payment_link_api(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """API handler for creating payment links.
    
    POST /p/create-link
    Body: {
        "amount": 100,
        "currency": "INR",
        "description": "Test payment",
        "customerName": "John Doe",
        "customerEmail": "john@example.com",
        "customerPhone": "+919876543210",
        "orderId": "ORD-123"
    }
    """
    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
    except json.JSONDecodeError:
        return cors_response(400, {"error": "Invalid JSON body"})
    
    amount = body.get("amount", 0)
    if not amount or amount <= 0:
        return cors_response(400, {"error": "Valid amount is required"})
    
    result = create_payment_link(
        amount=float(amount),
        currency=body.get("currency", "INR"),
        description=body.get("description", ""),
        customer_name=body.get("customerName", ""),
        customer_email=body.get("customerEmail", ""),
        customer_phone=body.get("customerPhone", ""),
        order_id=body.get("orderId", ""),
        callback_url=body.get("callbackUrl", ""),
        expire_by=body.get("expireBy"),
    )
    
    if result.get("error"):
        return cors_response(500, result)
    
    return cors_response(200, result)


# =============================================================================
# MAIN LAMBDA HANDLER - INDEPENDENT ROUTING
# =============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler with independent routing for payment domain.
    
    Routes:
        GET  /                    → Redirect to selfservice
        GET  /p/{id}              → Payment link redirect
        GET  /p/pay/{id}          → Payment checkout page
        GET  /p/success           → Payment success page
        POST /razorpay-webhook    → Razorpay webhook
        POST /p/create-link       → Create payment link API
        OPTIONS /*                → CORS preflight
        ANY  /*                   → 404 redirect to selfservice
    """
    logger.info(f"Payment Lambda event: {json.dumps(event, default=str)[:1000]}")
    
    # Extract path and method
    http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "GET"))
    raw_path = event.get("rawPath", event.get("path", "/"))
    path = raw_path.rstrip("/") or "/"
    
    # Handle CORS preflight
    if http_method == "OPTIONS":
        return cors_response(200, {"status": "ok"})
    
    logger.info(f"Payment route: {http_method} {path}")
    
    # Root path → redirect to selfservice
    if path == "/" or path == "":
        return redirect_response(DEFAULT_REDIRECT_URL)
    
    # Razorpay webhook
    if path == "/razorpay-webhook" and http_method == "POST":
        return handle_razorpay_webhook(event, context)
    
    # Payment success page
    if path == "/p/success" or path.startswith("/p/success"):
        query_params = event.get("queryStringParameters", {}) or {}
        payment_id = query_params.get("payment_id", "unknown")
        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "text/html"},
            "body": get_success_page_html(payment_id),
        }
    
    # Create payment link API
    if path == "/p/create-link" and http_method == "POST":
        return handle_create_payment_link_api(event, context)
    
    # Payment checkout page: /p/pay/{payment_id}
    if path.startswith("/p/pay/"):
        payment_id = path.replace("/p/pay/", "").strip("/")
        if payment_id:
            # For test, show Rs. 1 payment page
            return {
                "statusCode": 200,
                "headers": {**CORS_HEADERS, "Content-Type": "text/html"},
                "body": get_payment_page_html(
                    payment_id=payment_id,
                    amount=1.0,  # Rs. 1 for testing
                    currency="INR",
                    description=f"Test Payment #{payment_id}",
                    order_id=payment_id,
                ),
            }
    
    # Payment link redirect: /p/{payment_id}
    if path.startswith("/p/") and not path.startswith("/p/pay/") and not path.startswith("/p/success"):
        payment_id = path.replace("/p/", "").strip("/")
        if payment_id:
            # Look up payment link and redirect to Razorpay
            try:
                link_pk = f"RAZORPAY_LINK#{payment_id}"
                response = _get_table().get_item(Key={MESSAGES_PK_NAME: link_pk})
                item = response.get("Item")
                if item and item.get("shortUrl"):
                    return redirect_response(item["shortUrl"])
            except Exception as e:
                logger.error(f"Failed to lookup payment link: {e}")
            
            # If not found, redirect to payment page
            return redirect_response(f"/p/pay/{payment_id}")
    
    # 404 - Unknown path → redirect to selfservice
    logger.info(f"404 - Unknown path: {path}")
    return redirect_response(DEFAULT_REDIRECT_URL)


# =============================================================================
# HANDLER EXPORTS FOR DISPATCHER REGISTRATION
# =============================================================================
RAZORPAY_HANDLERS = {
    "razorpay_webhook": handle_razorpay_webhook,
    "create_razorpay_link": handle_create_payment_link_api,
}
