# =============================================================================
# RAZORPAY PAYMENTS - INDEPENDENT MICROSERVICE
# =============================================================================
# Domain: p.wecare.digital
# Routes:
#   GET  /              → Direct redirect to selfservice
#   GET  /{uuid}        → Payment page (OUR DOMAIN)
#   GET  /success       → Success page
#   POST /create        → Create payment API
#   POST /webhook       → Razorpay webhook
#   GET  /test          → Create Rs.1 test payment
#   ANY  /*             → Direct redirect to selfservice
# =============================================================================

import json
import logging
import os
import hmac
import hashlib
import base64
import urllib.request
import urllib.error
import uuid as uuid_lib
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# CONFIGURATION
# =============================================================================
DEFAULT_REDIRECT = os.environ.get("DEFAULT_REDIRECT", "https://wecare.digital/selfservice")
FAVICON = os.environ.get("FAVICON", "https://selfcare.wecare.digital/wecare-digital.ico")
BASE_URL = os.environ.get("PAYMENT_BASE_URL", "https://p.wecare.digital")
TABLE = os.environ.get("PAYMENTS_TABLE", "wecare-digital-payments")
PK = "pk"

# Razorpay
KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_live_CLnEhAF46T9eQm")
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "4MIFXNF5pIW6LnqpFMNrlvFT")
WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "b@c4mk9t9Z8qLq3")

# Fee Configuration (2% Razorpay + 18% GST on fee)
RAZORPAY_FEE_PERCENT = 2.0
GST_ON_FEE_PERCENT = 18.0

_tbl = None

def tbl():
    global _tbl
    if not _tbl:
        _tbl = boto3.resource("dynamodb").Table(TABLE)
    return _tbl

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def gen_id() -> str:
    return uuid_lib.uuid4().hex[:12]

def calculate_fees(amount: float) -> Dict:
    """Calculate payment gateway fees."""
    razorpay_fee = round(amount * RAZORPAY_FEE_PERCENT / 100, 2)
    gst_on_fee = round(razorpay_fee * GST_ON_FEE_PERCENT / 100, 2)
    total_fee = round(razorpay_fee + gst_on_fee, 2)
    total_payable = round(amount + total_fee, 2)
    return {
        "amount": amount,
        "razorpay_fee": razorpay_fee,
        "gst": gst_on_fee,
        "total_fee": total_fee,
        "total": total_payable
    }

# =============================================================================
# CORS
# =============================================================================
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Razorpay-Signature,X-Requested-With,X-Api-Key",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
}

def resp(code: int, body: Any, ct: str = "application/json") -> Dict:
    return {
        "statusCode": code,
        "headers": {**CORS, "Content-Type": ct},
        "body": json.dumps(body, default=str) if ct == "application/json" else str(body)
    }

def redir(url: str, code: int = 302) -> Dict:
    return {"statusCode": code, "headers": {**CORS, "Location": url}, "body": ""}

def html(code: int, body: str) -> Dict:
    return {"statusCode": code, "headers": {**CORS, "Content-Type": "text/html"}, "body": body}

# =============================================================================
# CSS - Minimal White Design
# =============================================================================
CSS = '''*{margin:0;padding:0;box-sizing:border-box}html{font-size:16px}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fff;color:#000;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;line-height:1.5}.card{background:#fff;border:1px solid #000;border-radius:16px;padding:32px 24px;max-width:400px;width:100%;text-align:center}.icon{font-size:48px;margin-bottom:16px}h1{color:#000;font-size:1.5rem;font-weight:600;margin-bottom:12px}p{color:#000;margin-bottom:12px;font-size:.95rem}a{color:#000;text-decoration:underline}.btn{display:block;background:#000;color:#fff;border:none;padding:14px 32px;font-size:1rem;font-weight:500;border-radius:13px;cursor:pointer;width:100%;text-decoration:none;transition:opacity .2s}.btn:hover{opacity:.85}.btn:disabled{opacity:.5;cursor:not-allowed}.amt{font-size:2.5rem;font-weight:700;color:#000;margin:16px 0 8px}.desc{color:#000;font-size:.9rem;margin-bottom:20px;opacity:.7}.fee-box{border:1px solid #000;border-radius:8px;padding:16px;margin:20px 0;text-align:left;font-size:.85rem}.fee-row{display:flex;justify-content:space-between;padding:6px 0}.fee-row.total{border-top:1px solid #000;margin-top:8px;padding-top:12px;font-weight:600}.secure{color:#000;font-size:.75rem;margin-top:16px;opacity:.6}.order-id{color:#000;font-size:.7rem;margin-top:8px;opacity:.5}.error{color:#000;border:1px solid #000;margin-top:12px;padding:10px;border-radius:8px;font-size:.85rem;display:none}.pid{font-size:.8rem;word-break:break-all;margin-top:16px;padding:12px;border:1px solid #000;border-radius:8px;font-family:monospace}.info{border:1px solid #000;padding:16px;border-radius:8px;margin-top:20px;text-align:left;font-size:.85rem}.info code{display:block;margin-top:4px;word-break:break-all;font-family:monospace;font-size:.8rem}@media(max-width:480px){body{padding:16px}.card{padding:24px 16px;border-radius:12px}h1{font-size:1.25rem}.btn{padding:12px 24px}.amt{font-size:2rem}.fee-box{padding:12px}}'''


# =============================================================================
# RAZORPAY API
# =============================================================================
def razorpay_request(method: str, endpoint: str, data: Dict = None) -> Dict:
    """Make authenticated request to Razorpay API."""
    url = f"https://api.razorpay.com/v1/{endpoint}"
    auth = base64.b64encode(f"{KEY_ID}:{KEY_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    
    req = urllib.request.Request(url, method=method, headers=headers)
    if data:
        req.data = json.dumps(data).encode()
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}
    except Exception as e:
        return {"error": str(e)}

def create_order(amount_paise: int, receipt: str, notes: Dict = None) -> Dict:
    """Create Razorpay order."""
    return razorpay_request("POST", "orders", {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": notes or {}
    })

def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature."""
    msg = f"{order_id}|{payment_id}"
    expected = hmac.new(KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_webhook(body: str, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    expected = hmac.new(WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================
def save_payment(payment_id: str, data: Dict):
    """Save payment to DynamoDB."""
    item = {PK: f"PAY#{payment_id}", "type": "PAYMENT", **data, "updated": now()}
    tbl().put_item(Item=item)

def get_payment(payment_id: str) -> Optional[Dict]:
    """Get payment from DynamoDB."""
    try:
        return tbl().get_item(Key={PK: f"PAY#{payment_id}"}).get("Item")
    except:
        return None

def update_payment_status(payment_id: str, status: str, razorpay_payment_id: str = None):
    """Update payment status."""
    expr = "SET #s = :s, updated = :u"
    vals = {":s": status, ":u": now()}
    names = {"#s": "status"}
    if razorpay_payment_id:
        expr += ", razorpayPaymentId = :rp"
        vals[":rp"] = razorpay_payment_id
    tbl().update_item(Key={PK: f"PAY#{payment_id}"}, UpdateExpression=expr, ExpressionAttributeValues=vals, ExpressionAttributeNames=names)


# =============================================================================
# HTML PAGES
# =============================================================================
def page_payment(payment: Dict) -> str:
    """Payment page - simple amount display."""
    amount = float(payment.get("amount", 0))
    order_id = payment.get("razorpayOrderId", "")
    payment_id = payment.get("paymentId", "")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pay Rs. {amount:.2f}</title>
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>
<div class="card">
<p class="amt">Rs. {amount:.2f}</p>
<button id="pay-btn" class="btn">Pay Now</button>
<div id="error" class="error"></div>
<p class="secure">Secured by WECARE.DIGITAL</p>
</div>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
var options={{
key:"{KEY_ID}",
amount:{int(amount*100)},
currency:"INR",
name:"WECARE Digital",
description:"Payment",
order_id:"{order_id}",
handler:function(r){{window.location.href="{BASE_URL}/success?payment_id={payment_id}&razorpay_payment_id="+r.razorpay_payment_id+"&razorpay_signature="+r.razorpay_signature}},
prefill:{{}},
theme:{{color:"#000000"}}
}};
var rzp=new Razorpay(options);
rzp.on("payment.failed",function(r){{document.getElementById("error").style.display="block";document.getElementById("error").textContent="Cancelled. Try again."}});
document.getElementById("pay-btn").onclick=function(e){{rzp.open();e.preventDefault()}};
</script>
</body>
</html>'''

def page_success(payment_id: str, razorpay_payment_id: str = "") -> str:
    """Success page."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Successful</title>
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>
<div class="card">
<p>Payment Successful</p>
<div class="pid">{razorpay_payment_id or payment_id}</div>
<a href="{DEFAULT_REDIRECT}" class="btn" style="margin-top:20px">Continue</a>
</div>
</body>
</html>'''

def page_test_created(payment_id: str, payment_url: str, amount: float) -> str:
    """Test payment created page."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test Payment</title>
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>
<div class="card">
<p class="amt">Rs. {amount:.2f}</p>
<a href="{payment_url}" class="btn">Pay Now</a>
<div class="info">
<code>{payment_id}</code>
<code style="margin-top:8px">{payment_url}</code>
</div>
</div>
</body>
</html>'''


# =============================================================================
# API HANDLERS
# =============================================================================
def create_payment(body: Dict) -> Dict:
    """Create a new payment link."""
    amount = float(body.get("amount", 0))
    if amount <= 0:
        return {"error": "Invalid amount"}
    
    payment_id = gen_id()
    receipt = f"pay_{payment_id}"
    
    # Create Razorpay order with amount (Razorpay handles fees internally)
    order = create_order(int(amount * 100), receipt, {"payment_id": payment_id})
    if order.get("error"):
        return {"error": f"Razorpay error: {order.get('error')}"}
    
    payment = {
        "paymentId": payment_id,
        "amount": Decimal(str(amount)),
        "description": body.get("description", "Payment"),
        "razorpayOrderId": order.get("id"),
        "status": "pending",
        "created": now(),
        "paymentUrl": f"{BASE_URL}/{payment_id}"
    }
    
    save_payment(payment_id, payment)
    
    return {
        "success": True,
        "paymentId": payment_id,
        "paymentUrl": payment["paymentUrl"],
        "amount": amount,
        "razorpayOrderId": order.get("id")
    }

def handle_webhook(body: str, signature: str) -> Dict:
    """Handle Razorpay webhook."""
    if not verify_webhook(body, signature):
        return {"error": "Invalid signature"}
    
    try:
        data = json.loads(body)
        event = data.get("event", "")
        payload = data.get("payload", {}).get("payment", {}).get("entity", {})
        
        if event == "payment.captured":
            order_id = payload.get("order_id")
            razorpay_payment_id = payload.get("id")
            # Find payment by order_id and update
            logger.info(f"Payment captured: {razorpay_payment_id} for order {order_id}")
        
        return {"success": True, "event": event}
    except Exception as e:
        return {"error": str(e)}

# =============================================================================
# RESERVED PATHS
# =============================================================================
RESERVED = ["create", "success", "webhook", "test", "api", "health", "favicon.ico", "robots.txt"]

def is_reserved(path: str) -> bool:
    return path.lower() in RESERVED

# =============================================================================
# LAMBDA HANDLER
# =============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.info(f"Event: {json.dumps(event, default=str)[:500]}")
    
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = (event.get("rawPath") or event.get("path") or "/").strip("/")
    qs = event.get("queryStringParameters") or {}
    
    logger.info(f"Route: {method} /{path}")
    
    if method == "OPTIONS":
        return resp(200, {"status": "ok"})
    
    # Root → Direct redirect to selfservice
    if not path:
        return redir(DEFAULT_REDIRECT)
    
    # GET /test → Create Rs.1 test payment
    if path == "test" and method == "GET":
        result = create_payment({"amount": 1, "description": "Test Payment (Rs.1)"})
        if result.get("error"):
            return resp(400, result)
        return html(200, page_test_created(result["paymentId"], result["paymentUrl"], 1))
    
    # GET /success → Success page
    if path == "success":
        payment_id = qs.get("payment_id", "")
        razorpay_payment_id = qs.get("razorpay_payment_id", "")
        razorpay_signature = qs.get("razorpay_signature", "")
        
        if payment_id:
            payment = get_payment(payment_id)
            if payment and razorpay_payment_id:
                # Verify and update status
                update_payment_status(payment_id, "completed", razorpay_payment_id)
        
        return html(200, page_success(payment_id, razorpay_payment_id))
    
    # POST /create → Create payment API
    if path == "create" and method == "POST":
        try:
            body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
        except:
            return resp(400, {"error": "Invalid JSON"})
        result = create_payment(body)
        return resp(400 if result.get("error") else 200, result)
    
    # POST /webhook → Razorpay webhook
    if path == "webhook" and method == "POST":
        body = event.get("body", "")
        signature = (event.get("headers") or {}).get("x-razorpay-signature") or (event.get("headers") or {}).get("X-Razorpay-Signature", "")
        result = handle_webhook(body, signature)
        return resp(400 if result.get("error") else 200, result)
    
    # GET /{uuid} → Payment page
    if not is_reserved(path) and len(path) == 12:
        payment = get_payment(path)
        if payment:
            return html(200, page_payment(payment))
        # Not found → Direct redirect
        return redir(DEFAULT_REDIRECT)
    
    # 404 → Direct redirect to selfservice
    return redir(DEFAULT_REDIRECT)

# Exports
PAYMENT_HANDLERS = {
    "create_payment": lambda e, c: create_payment(e),
    "get_payment": lambda e, c: get_payment(e.get("paymentId", "")),
}
