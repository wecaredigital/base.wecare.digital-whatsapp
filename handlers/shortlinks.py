# =============================================================================
# SHORT LINKS - INDEPENDENT MICROSERVICE
# =============================================================================
# Domain: r.wecare.digital
# Lambda: wecare-digital-shortlinks
# DynamoDB: wecare-digital-shortlinks
#
# Routes:
#   GET  /              → Redirect to selfservice
#   GET  /{uuid}        → Short link redirect (PUBLIC)
#   POST /create        → Create short link API
#   GET  /stats/{uuid}  → Get link stats
#   ANY  /*             → 404 → Redirect to selfservice
#
# URLs:
#   https://r.wecare.digital/{uuid}     → target URL redirect
#   https://r.wecare.digital/create     → API endpoint
# =============================================================================

import json
import logging
import os
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# CONFIGURATION
# =============================================================================
DEFAULT_REDIRECT = os.environ.get("DEFAULT_REDIRECT", "https://wecare.digital/selfservice")
FAVICON = os.environ.get("FAVICON", "https://selfcare.wecare.digital/wecare-digital.ico")
BASE_URL = os.environ.get("SHORT_LINK_BASE_URL", "https://r.wecare.digital")
TABLE = os.environ.get("SHORTLINKS_TABLE", "wecare-digital-shortlinks")
PK = "pk"
CODE_LEN = 12

_tbl = None

def tbl():
    global _tbl
    if not _tbl:
        _tbl = boto3.resource("dynamodb").Table(TABLE)
    return _tbl

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

# =============================================================================
# CORS
# =============================================================================
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Requested-With,X-Api-Key",
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
    return {
        "statusCode": code,
        "headers": {**CORS, "Location": url, "Content-Type": "text/html"},
        "body": f'<html><head><meta http-equiv="refresh" content="0;url={url}"></head></html>'
    }

def html(code: int, body: str) -> Dict:
    return {"statusCode": code, "headers": {**CORS, "Content-Type": "text/html"}, "body": body}

# =============================================================================
# UUID CODE GENERATION
# =============================================================================
def gen_code(length: int = CODE_LEN) -> str:
    return uuid.uuid4().hex[:length]

def exists(code: str) -> bool:
    try:
        return "Item" in tbl().get_item(Key={PK: f"LINK#{code}"})
    except:
        return False

def unique() -> str:
    for _ in range(10):
        code = gen_code()
        if not exists(code):
            return code
    return gen_code(16)

# =============================================================================
# CRUD
# =============================================================================
def create(target: str, custom: str = None, title: str = "", expires: str = None) -> Dict:
    if not target:
        return {"error": "target_url required"}
    if not target.startswith(("http://", "https://")):
        target = f"https://{target}"
    
    if custom:
        if exists(custom):
            return {"error": f"Code '{custom}' exists"}
        code = custom
    else:
        code = unique()
    
    item = {
        PK: f"LINK#{code}",
        "type": "LINK",
        "code": code,
        "target": target,
        "shortUrl": f"{BASE_URL}/{code}",
        "title": title,
        "clicks": 0,
        "created": now(),
        "active": True
    }
    if expires:
        item["expires"] = expires
    
    try:
        tbl().put_item(Item=item)
        return {"success": True, "code": code, "shortUrl": item["shortUrl"], "target": target}
    except ClientError as e:
        return {"error": str(e)}

def get(code: str) -> Optional[Dict]:
    try:
        return tbl().get_item(Key={PK: f"LINK#{code}"}).get("Item")
    except:
        return None

def click(code: str, ref: str = "", ua: str = "", ip: str = ""):
    try:
        tbl().update_item(
            Key={PK: f"LINK#{code}"},
            UpdateExpression="SET clicks = if_not_exists(clicks, :z) + :i, lastClick = :n",
            ExpressionAttributeValues={":z": 0, ":i": 1, ":n": now()}
        )
        ts = now().replace(":", "").replace("-", "").replace(".", "")
        tbl().put_item(Item={
            PK: f"CLICK#{code}_{ts}",
            "type": "CLICK",
            "code": code,
            "at": now(),
            "ref": ref[:500] if ref else "",
            "ua": ua[:500] if ua else "",
            "ip": ip
        })
    except:
        pass

def stats(code: str) -> Dict:
    link = get(code)
    if not link:
        return {"error": "Not found"}
    return {
        "code": code,
        "shortUrl": link.get("shortUrl"),
        "target": link.get("target"),
        "clicks": int(link.get("clicks", 0)),
        "created": link.get("created"),
        "active": link.get("active", True)
    }

# =============================================================================
# NO LANDING PAGES - Direct redirects for root, 404, expired
# =============================================================================

# =============================================================================
# RESERVED PATHS (not short codes)
# =============================================================================
RESERVED = ["create", "stats", "api", "health", "favicon.ico", "robots.txt"]

def is_reserved(path: str) -> bool:
    return path.lower() in RESERVED or path.startswith("stats/")

# =============================================================================
# LAMBDA HANDLER
# =============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.info(f"Event: {json.dumps(event, default=str)[:500]}")
    
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = (event.get("rawPath") or event.get("path") or "/").strip("/")
    
    logger.info(f"Route: {method} /{path}")
    
    if method == "OPTIONS":
        return resp(200, {"status": "ok"})
    
    # Root → Redirect to selfservice
    if not path:
        return redir(DEFAULT_REDIRECT)
    
    # POST /create → Create short link
    if path == "create" and method == "POST":
        try:
            body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
        except:
            return resp(400, {"error": "Invalid JSON"})
        result = create(
            body.get("targetUrl") or body.get("target_url") or body.get("url", ""),
            body.get("customCode") or body.get("custom_code"),
            body.get("title", ""),
            body.get("expiresAt") or body.get("expires_at")
        )
        return resp(400 if result.get("error") else 200, result)
    
    # GET /stats/{code} → Stats
    if path.startswith("stats/"):
        code = path.replace("stats/", "").strip("/")
        if code:
            s = stats(code)
            return resp(404 if s.get("error") else 200, s)
        return resp(400, {"error": "Code required"})
    
    # GET /{code} → Redirect (if not reserved)
    if not is_reserved(path):
        code = path
        link = get(code)
        
        # Not found → Direct redirect to selfservice
        if not link:
            return redir(DEFAULT_REDIRECT)
        
        # Inactive → Direct redirect to selfservice
        if not link.get("active", True):
            return redir(DEFAULT_REDIRECT)
        
        # Check expiry → Direct redirect if expired
        exp = link.get("expires")
        if exp:
            try:
                if datetime.now(timezone.utc) > datetime.fromisoformat(exp.replace("Z", "+00:00")):
                    return redir(DEFAULT_REDIRECT)
            except:
                pass
        
        # Track click
        hdrs = event.get("headers", {})
        click(
            code,
            hdrs.get("referer") or hdrs.get("Referer", ""),
            hdrs.get("user-agent") or hdrs.get("User-Agent", ""),
            (hdrs.get("x-forwarded-for") or hdrs.get("X-Forwarded-For", "")).split(",")[0].strip()
        )
        
        return redir(link.get("target", DEFAULT_REDIRECT))
    
    # 404 → Direct redirect to selfservice
    return redir(DEFAULT_REDIRECT)

# Exports
SHORTLINK_HANDLERS = {
    "create_short_link": lambda e, c: create(e.get("targetUrl", ""), e.get("customCode"), e.get("title", "")),
    "get_short_link_stats": lambda e, c: stats(e.get("code", "")),
}
