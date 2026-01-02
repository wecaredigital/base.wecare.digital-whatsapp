# =============================================================================
# SHORT LINKS HANDLER
# =============================================================================
# Independent short link handler for URL redirection
# Can be attached to any Lambda/API Gateway independently
#
# Routes:
#   GET  /                    → Redirect to https://wecare.digital/selfservice
#   GET  /r/{short_code}      → Short link redirect
#   POST /r/create            → Create short link API
#   GET  /r/stats/{code}      → Get short link stats
#   ANY  /*                   → 404 redirect to https://wecare.digital/selfservice
#
# Configuration:
#   - MESSAGES_TABLE_NAME: DynamoDB table for storing links
#   - DEFAULT_REDIRECT_URL: Default redirect for root/404
#   - FAVICON_URL: Favicon URL for pages
#
# Test Links:
#   - Root: https://r.wecare.digital/ → redirects to selfservice
#   - Short link: https://r.wecare.digital/r/abc123 → redirects to target URL
#   - 404: https://r.wecare.digital/unknown → redirects to selfservice
# =============================================================================

import json
import logging
import os
import hashlib
import string
import random
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
DEFAULT_REDIRECT_URL = "https://wecare.digital/selfservice"
FAVICON_URL = "https://selfcare.wecare.digital/wecare-digital.ico"
SHORT_LINK_BASE_URL = os.environ.get("SHORT_LINK_BASE_URL", "https://r.wecare.digital")

# DynamoDB Configuration
MESSAGES_TABLE_NAME = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
MESSAGES_PK_NAME = os.environ.get("MESSAGES_PK_NAME", "pk")

# Short code configuration
SHORT_CODE_LENGTH = 6
SHORT_CODE_CHARS = string.ascii_lowercase + string.digits

# Lazy clients
_clients: Dict[str, Any] = {}


def _get_table():
    if "table" not in _clients:
        _clients["table"] = boto3.resource("dynamodb").Table(MESSAGES_TABLE_NAME)
    return _clients["table"]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# CORS HEADERS
# =============================================================================
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
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
# SHORT CODE GENERATION
# =============================================================================
def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a random short code."""
    return ''.join(random.choices(SHORT_CODE_CHARS, k=length))


def generate_deterministic_code(url: str, length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a deterministic short code based on URL hash."""
    hash_obj = hashlib.sha256(url.encode())
    hash_hex = hash_obj.hexdigest()
    
    # Convert hex to base36-like encoding
    code = ""
    for i in range(0, length * 2, 2):
        byte_val = int(hash_hex[i:i+2], 16)
        code += SHORT_CODE_CHARS[byte_val % len(SHORT_CODE_CHARS)]
    
    return code[:length]


def is_code_available(code: str) -> bool:
    """Check if a short code is available."""
    try:
        response = _get_table().get_item(Key={MESSAGES_PK_NAME: f"SHORTLINK#{code}"})
        return "Item" not in response
    except Exception:
        return True


def get_unique_code(url: str = None, max_attempts: int = 10) -> str:
    """Get a unique short code, trying deterministic first then random."""
    # Try deterministic code first if URL provided
    if url:
        code = generate_deterministic_code(url)
        if is_code_available(code):
            return code
    
    # Fall back to random codes
    for _ in range(max_attempts):
        code = generate_short_code()
        if is_code_available(code):
            return code
    
    # Last resort: longer random code
    return generate_short_code(SHORT_CODE_LENGTH + 2)


# =============================================================================
# SHORT LINK CRUD OPERATIONS
# =============================================================================
def create_short_link(target_url: str, custom_code: str = None, title: str = "",
                      expires_at: str = None, meta_data: Dict = None) -> Dict[str, Any]:
    """Create a new short link.
    
    Args:
        target_url: The destination URL
        custom_code: Optional custom short code
        title: Optional title/description
        expires_at: Optional expiration timestamp (ISO format)
        meta_data: Optional metadata dict
    
    Returns:
        Short link details including short_url
    """
    if not target_url:
        return {"error": "target_url is required"}
    
    # Validate URL
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"
    
    # Get or generate short code
    if custom_code:
        if not is_code_available(custom_code):
            return {"error": f"Short code '{custom_code}' is already in use"}
        code = custom_code
    else:
        code = get_unique_code(target_url)
    
    now = iso_now()
    short_url = f"{SHORT_LINK_BASE_URL}/r/{code}"
    
    # Store in DynamoDB
    item = {
        MESSAGES_PK_NAME: f"SHORTLINK#{code}",
        "itemType": "SHORTLINK",
        "code": code,
        "targetUrl": target_url,
        "shortUrl": short_url,
        "title": title,
        "clicks": 0,
        "createdAt": now,
        "lastClickedAt": None,
        "isActive": True,
    }
    
    if expires_at:
        item["expiresAt"] = expires_at
    
    if meta_data:
        item["metaData"] = meta_data
    
    try:
        _get_table().put_item(Item=item)
        
        return {
            "success": True,
            "code": code,
            "shortUrl": short_url,
            "targetUrl": target_url,
            "title": title,
            "createdAt": now,
        }
    except ClientError as e:
        logger.error(f"Failed to create short link: {e}")
        return {"error": str(e)}


def get_short_link(code: str) -> Optional[Dict[str, Any]]:
    """Get short link by code."""
    try:
        response = _get_table().get_item(Key={MESSAGES_PK_NAME: f"SHORTLINK#{code}"})
        return response.get("Item")
    except Exception as e:
        logger.error(f"Failed to get short link: {e}")
        return None


def increment_click_count(code: str, referrer: str = "", user_agent: str = "", 
                          ip_address: str = "") -> bool:
    """Increment click count and log click event."""
    now = iso_now()
    
    try:
        # Update click count
        _get_table().update_item(
            Key={MESSAGES_PK_NAME: f"SHORTLINK#{code}"},
            UpdateExpression="SET clicks = if_not_exists(clicks, :zero) + :inc, lastClickedAt = :now",
            ExpressionAttributeValues={":zero": 0, ":inc": 1, ":now": now}
        )
        
        # Log click event (for analytics)
        click_id = f"{code}_{now.replace(':', '').replace('-', '').replace('.', '')}"
        _get_table().put_item(Item={
            MESSAGES_PK_NAME: f"SHORTLINK_CLICK#{click_id}",
            "itemType": "SHORTLINK_CLICK",
            "code": code,
            "clickedAt": now,
            "referrer": referrer[:500] if referrer else "",
            "userAgent": user_agent[:500] if user_agent else "",
            "ipAddress": ip_address,
        })
        
        return True
    except Exception as e:
        logger.error(f"Failed to increment click count: {e}")
        return False


def get_short_link_stats(code: str) -> Dict[str, Any]:
    """Get statistics for a short link."""
    link = get_short_link(code)
    if not link:
        return {"error": "Short link not found"}
    
    # Get recent clicks
    try:
        response = _get_table().query(
            KeyConditionExpression=f"{MESSAGES_PK_NAME} BEGINS_WITH :prefix",
            ExpressionAttributeValues={":prefix": f"SHORTLINK_CLICK#{code}_"},
            ScanIndexForward=False,
            Limit=100
        )
        recent_clicks = response.get("Items", [])
    except Exception:
        recent_clicks = []
    
    return {
        "code": code,
        "shortUrl": link.get("shortUrl", ""),
        "targetUrl": link.get("targetUrl", ""),
        "title": link.get("title", ""),
        "clicks": int(link.get("clicks", 0)),
        "createdAt": link.get("createdAt", ""),
        "lastClickedAt": link.get("lastClickedAt"),
        "isActive": link.get("isActive", True),
        "recentClicks": len(recent_clicks),
    }


# =============================================================================
# HTML PAGES
# =============================================================================
def get_404_page_html() -> str:
    """Generate 404 page HTML."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Not Found - WECARE.DIGITAL</title>
    <link rel="icon" href="{FAVICON_URL}" type="image/x-icon">
    <meta http-equiv="refresh" content="3;url={DEFAULT_REDIRECT_URL}">
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
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .message {{ color: #666; margin-bottom: 20px; }}
        .redirect {{ color: #999; font-size: 12px; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🔗</div>
        <h1>Link Not Found</h1>
        <p class="message">This short link doesn't exist or has expired.</p>
        <p class="redirect">Redirecting to <a href="{DEFAULT_REDIRECT_URL}">WECARE.DIGITAL</a> in 3 seconds...</p>
    </div>
</body>
</html>'''


def get_expired_page_html() -> str:
    """Generate expired link page HTML."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Expired - WECARE.DIGITAL</title>
    <link rel="icon" href="{FAVICON_URL}" type="image/x-icon">
    <meta http-equiv="refresh" content="3;url={DEFAULT_REDIRECT_URL}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
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
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #f5576c; margin-bottom: 10px; }}
        .message {{ color: #666; margin-bottom: 20px; }}
        .redirect {{ color: #999; font-size: 12px; }}
        a {{ color: #f5576c; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">⏰</div>
        <h1>Link Expired</h1>
        <p class="message">This short link has expired and is no longer available.</p>
        <p class="redirect">Redirecting to <a href="{DEFAULT_REDIRECT_URL}">WECARE.DIGITAL</a> in 3 seconds...</p>
    </div>
</body>
</html>'''


# =============================================================================
# API HANDLERS
# =============================================================================
def handle_create_short_link_api(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """API handler for creating short links.
    
    POST /r/create
    Body: {
        "targetUrl": "https://example.com/long-url",
        "customCode": "mycode",  // optional
        "title": "My Link",      // optional
        "expiresAt": "2025-12-31T23:59:59Z"  // optional
    }
    """
    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
    except json.JSONDecodeError:
        return cors_response(400, {"error": "Invalid JSON body"})
    
    target_url = body.get("targetUrl", body.get("target_url", body.get("url", "")))
    if not target_url:
        return cors_response(400, {"error": "targetUrl is required"})
    
    result = create_short_link(
        target_url=target_url,
        custom_code=body.get("customCode", body.get("custom_code")),
        title=body.get("title", ""),
        expires_at=body.get("expiresAt", body.get("expires_at")),
        meta_data=body.get("metaData", body.get("meta_data")),
    )
    
    if result.get("error"):
        return cors_response(400, result)
    
    return cors_response(200, result)


def handle_get_stats_api(event: Dict[str, Any], context: Any, code: str) -> Dict[str, Any]:
    """API handler for getting short link stats.
    
    GET /r/stats/{code}
    """
    stats = get_short_link_stats(code)
    
    if stats.get("error"):
        return cors_response(404, stats)
    
    return cors_response(200, stats)


def handle_redirect(event: Dict[str, Any], context: Any, code: str) -> Dict[str, Any]:
    """Handle short link redirect."""
    link = get_short_link(code)
    
    if not link:
        logger.info(f"Short link not found: {code}")
        return {
            "statusCode": 404,
            "headers": {**CORS_HEADERS, "Content-Type": "text/html"},
            "body": get_404_page_html(),
        }
    
    # Check if link is active
    if not link.get("isActive", True):
        return {
            "statusCode": 410,
            "headers": {**CORS_HEADERS, "Content-Type": "text/html"},
            "body": get_expired_page_html(),
        }
    
    # Check expiration
    expires_at = link.get("expiresAt")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expiry:
                return {
                    "statusCode": 410,
                    "headers": {**CORS_HEADERS, "Content-Type": "text/html"},
                    "body": get_expired_page_html(),
                }
        except Exception:
            pass
    
    # Get request metadata for analytics
    headers = event.get("headers", {})
    referrer = headers.get("referer", headers.get("Referer", ""))
    user_agent = headers.get("user-agent", headers.get("User-Agent", ""))
    
    # Get IP from various headers
    ip_address = (
        headers.get("x-forwarded-for", "").split(",")[0].strip() or
        headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        event.get("requestContext", {}).get("identity", {}).get("sourceIp", "")
    )
    
    # Increment click count (async, don't block redirect)
    increment_click_count(code, referrer, user_agent, ip_address)
    
    target_url = link.get("targetUrl", DEFAULT_REDIRECT_URL)
    logger.info(f"Redirecting {code} to {target_url}")
    
    return redirect_response(target_url)


# =============================================================================
# MAIN LAMBDA HANDLER - INDEPENDENT ROUTING
# =============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler with independent routing for short link domain.
    
    Routes:
        GET  /                    → Redirect to selfservice
        GET  /r/{code}            → Short link redirect
        POST /r/create            → Create short link API
        GET  /r/stats/{code}      → Get short link stats
        OPTIONS /*                → CORS preflight
        ANY  /*                   → 404 redirect to selfservice
    """
    logger.info(f"ShortLink Lambda event: {json.dumps(event, default=str)[:1000]}")
    
    # Extract path and method
    http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "GET"))
    raw_path = event.get("rawPath", event.get("path", "/"))
    path = raw_path.rstrip("/") or "/"
    
    # Handle CORS preflight
    if http_method == "OPTIONS":
        return cors_response(200, {"status": "ok"})
    
    logger.info(f"ShortLink route: {http_method} {path}")
    
    # Root path → redirect to selfservice
    if path == "/" or path == "":
        return redirect_response(DEFAULT_REDIRECT_URL)
    
    # Create short link API
    if path == "/r/create" and http_method == "POST":
        return handle_create_short_link_api(event, context)
    
    # Stats API: /r/stats/{code}
    if path.startswith("/r/stats/"):
        code = path.replace("/r/stats/", "").strip("/")
        if code:
            return handle_get_stats_api(event, context, code)
    
    # Short link redirect: /r/{code}
    if path.startswith("/r/"):
        code = path.replace("/r/", "").strip("/")
        if code and not code.startswith("stats") and not code.startswith("create"):
            return handle_redirect(event, context, code)
    
    # 404 - Unknown path → redirect to selfservice
    logger.info(f"404 - Unknown path: {path}")
    return redirect_response(DEFAULT_REDIRECT_URL)


# =============================================================================
# HANDLER EXPORTS FOR DISPATCHER REGISTRATION
# =============================================================================
SHORTLINK_HANDLERS = {
    "create_short_link": handle_create_short_link_api,
    "get_short_link_stats": lambda e, c: handle_get_stats_api(e, c, e.get("code", "")),
}
