# Base utilities for all handlers
# Production-grade shared utilities with lazy initialization and caching
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar
import boto3
from botocore.exceptions import ClientError
from functools import wraps

logger = logging.getLogger()

# Type definitions
HandlerFunc = Callable[[Dict[str, Any], Any], Dict[str, Any]]
T = TypeVar('T')

# =============================================================================
# LAZY CLIENT INITIALIZATION
# =============================================================================
_clients: Dict[str, Any] = {}


def _get_client(name: str, service: str = None):
    """Lazy client initialization with caching."""
    if name not in _clients:
        _clients[name] = boto3.client(service or name)
    return _clients[name]


def _get_resource(name: str, service: str = None):
    """Lazy resource initialization with caching."""
    key = f"resource_{name}"
    if key not in _clients:
        _clients[key] = boto3.resource(service or name)
    return _clients[key]


# Client accessors
def get_ddb(): return _get_resource("dynamodb")
def get_s3(): return _get_client("s3")
def get_social(): return _get_client("socialmessaging")
def get_sns(): return _get_client("sns")
def get_ec2(): return _get_client("ec2")
def get_iam(): return _get_client("iam")


# Table accessor with caching
_table = None
def get_table():
    global _table
    if _table is None:
        table_name = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
        _table = get_ddb().Table(table_name)
    return _table


# Convenience aliases - call as functions: table(), social(), s3(), sns()
def table(): return get_table()
def social(): return get_social()
def s3(): return get_s3()
def sns(): return get_sns()
def ec2(): return get_ec2()
def iam(): return get_iam()


# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================
def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_env_bool(key: str, default: bool = False) -> bool:
    return _get_env(key, str(default)).lower() == "true"


def _get_env_json(key: str, default: dict = None) -> dict:
    try:
        return json.loads(_get_env(key, "{}") or "{}")
    except json.JSONDecodeError:
        return default or {}


# Core environment variables
MESSAGES_TABLE_NAME = _get_env("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
MESSAGES_PK_NAME = _get_env("MESSAGES_PK_NAME", "pk")
MEDIA_BUCKET = _get_env("MEDIA_BUCKET", "dev.wecare.digital")
MEDIA_PREFIX = _get_env("MEDIA_PREFIX", "WhatsApp/")
META_API_VERSION = _get_env("META_API_VERSION", "v20.0")
WABA_PHONE_MAP = _get_env_json("WABA_PHONE_MAP_JSON")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def iso_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def jdump(x: Any) -> str:
    """JSON dump with defaults for non-serializable types."""
    return json.dumps(x, ensure_ascii=False, default=str)


def safe(s: Optional[str]) -> str:
    """Sanitize string for use in S3 keys and identifiers."""
    if not s:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9=._\-/#]+", "_", s)


def format_wa_number(wa_id: str) -> str:
    """Format WhatsApp number with + prefix for AWS Social Messaging API."""
    if not wa_id:
        return ""
    wa_id = wa_id.strip()
    if not wa_id.startswith("+"):
        return f"+{wa_id}"
    return wa_id


def origination_id_for_api(phone_arn: str) -> str:
    """Convert phone ARN to API format."""
    if not phone_arn:
        return ""
    if "phone-number-id/" in phone_arn:
        suffix = phone_arn.split("phone-number-id/")[-1]
        return f"phone-number-id-{suffix}"
    return phone_arn


def arn_suffix(arn: str) -> str:
    """Extract suffix from ARN."""
    return arn.split("/")[-1] if arn and "arn:" in arn else arn


# =============================================================================
# WABA CONFIGURATION
# =============================================================================
def get_waba_config(meta_waba_id: str) -> Dict[str, Any]:
    """Get WABA configuration from environment."""
    return WABA_PHONE_MAP.get(str(meta_waba_id), {})


def get_phone_arn(meta_waba_id: str) -> str:
    """Get phone ARN for a WABA."""
    return get_waba_config(meta_waba_id).get("phoneArn", "")


def get_business_name(meta_waba_id: str) -> str:
    """Get business name for a WABA."""
    return get_waba_config(meta_waba_id).get("businessAccountName", "")


# =============================================================================
# VALIDATION HELPERS
# =============================================================================
def validate_required_fields(event: Dict[str, Any], fields: List[str]) -> Optional[Dict[str, Any]]:
    """Validate required fields in event. Returns error response if validation fails."""
    missing = [f for f in fields if not event.get(f)]
    if missing:
        return {
            "statusCode": 400,
            "error": f"Missing required fields: {', '.join(missing)}"
        }
    return None


def validate_enum(value: str, valid_values: List[str], field_name: str) -> Optional[Dict[str, Any]]:
    """Validate value is in allowed list. Returns error response if validation fails."""
    if value and value not in valid_values:
        return {
            "statusCode": 400,
            "error": f"Invalid {field_name}. Valid values: {valid_values}"
        }
    return None


# =============================================================================
# DYNAMODB OPERATIONS
# =============================================================================
def store_item(item: Dict[str, Any]) -> bool:
    """Store item in DynamoDB."""
    try:
        get_table().put_item(Item=item)
        return True
    except ClientError as e:
        logger.exception(f"Failed to store item: {e}")
        return False


def update_item(pk: str, updates: Dict[str, Any]) -> bool:
    """Update item in DynamoDB."""
    try:
        update_expr_parts = []
        expr_values = {}
        expr_names = {}
        
        for key, value in updates.items():
            safe_key = key.replace("#", "").replace(":", "").replace("-", "_")
            update_expr_parts.append(f"#{safe_key} = :{safe_key}")
            expr_names[f"#{safe_key}"] = key
            expr_values[f":{safe_key}"] = value
        
        get_table().update_item(
            Key={MESSAGES_PK_NAME: pk},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        return True
    except ClientError as e:
        logger.exception(f"Failed to update item: {e}")
        return False


def get_item(pk: str) -> Optional[Dict[str, Any]]:
    """Get item from DynamoDB."""
    try:
        response = get_table().get_item(Key={MESSAGES_PK_NAME: pk})
        return response.get("Item")
    except ClientError as e:
        logger.exception(f"Failed to get item: {e}")
        return None


def query_items(
    index_name: str = None,
    key_condition: str = None,
    filter_expr: str = None,
    expr_values: Dict[str, Any] = None,
    expr_names: Dict[str, str] = None,
    limit: int = 50,
    scan_forward: bool = False
) -> List[Dict[str, Any]]:
    """Query items from DynamoDB using GSI or scan."""
    try:
        kwargs = {
            "Limit": limit,
            "ScanIndexForward": scan_forward,
        }
        
        if expr_values:
            kwargs["ExpressionAttributeValues"] = expr_values
        if expr_names:
            kwargs["ExpressionAttributeNames"] = expr_names
        
        if index_name and key_condition:
            kwargs["IndexName"] = index_name
            kwargs["KeyConditionExpression"] = key_condition
            if filter_expr:
                kwargs["FilterExpression"] = filter_expr
            response = get_table().query(**kwargs)
        else:
            if filter_expr:
                kwargs["FilterExpression"] = filter_expr
            response = get_table().scan(**kwargs)
        
        return response.get("Items", [])
    except ClientError as e:
        logger.exception(f"Failed to query items: {e}")
        return []


def delete_item(pk: str) -> bool:
    """Delete item from DynamoDB."""
    try:
        get_table().delete_item(Key={MESSAGES_PK_NAME: pk})
        return True
    except ClientError as e:
        logger.exception(f"Failed to delete item: {e}")
        return False


# =============================================================================
# WHATSAPP MESSAGING
# =============================================================================
def send_whatsapp_message(phone_arn: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send WhatsApp message via AWS Social Messaging API."""
    try:
        response = get_social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        return {"success": True, "messageId": response.get("messageId")}
    except ClientError as e:
        logger.exception(f"Failed to send message: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# S3 OPERATIONS
# =============================================================================
def generate_s3_presigned_url(bucket: str, key: str, expiry: int = 86400) -> str:
    """Generate presigned URL for S3 object (default 24 hour expiry)."""
    if not bucket or not key:
        return ""
    try:
        return get_s3().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiry
        )
    except Exception:
        return f"s3://{bucket}/{key}"


# =============================================================================
# RESPONSE HELPERS
# =============================================================================
def success_response(operation: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
    """Create a standardized success response."""
    response = {"statusCode": 200, "operation": operation}
    if data:
        response.update(data)
    response.update(kwargs)
    return response


def error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {"statusCode": status_code, "error": message}


def not_found_response(resource: str, identifier: str) -> Dict[str, Any]:
    """Create a standardized not found response."""
    return {"statusCode": 404, "error": f"{resource} not found: {identifier}"}


# =============================================================================
# HANDLER REGISTRY - Unified registration system
# =============================================================================
_HANDLERS: Dict[str, HandlerFunc] = {}
_HANDLER_METADATA: Dict[str, Dict[str, Any]] = {}


def register_handler(action: str, category: str = "general", description: str = None):
    """
    Decorator to register a handler for an action.
    
    Usage:
        @register_handler("my_action", category="messaging", description="Send a message")
        def handle_my_action(event, context):
            return {"statusCode": 200, "result": "success"}
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        _HANDLERS[action] = func
        _HANDLER_METADATA[action] = {
            "category": category,
            "description": description or (func.__doc__ or "No description").split("\n")[0].strip(),
            "module": func.__module__,
        }
        return func
    return decorator


def get_handler(action: str) -> Optional[HandlerFunc]:
    """Get handler for an action."""
    return _HANDLERS.get(action)


def list_handlers() -> Dict[str, str]:
    """List all registered handlers with their descriptions."""
    return {
        action: meta["description"]
        for action, meta in _HANDLER_METADATA.items()
    }


def get_handlers_by_category() -> Dict[str, List[str]]:
    """Get handlers grouped by category."""
    categories: Dict[str, List[str]] = {}
    for action, meta in _HANDLER_METADATA.items():
        cat = meta.get("category", "general")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(action)
    return categories


def dispatch_handler(action: str, event: Dict[str, Any], context: Any) -> Optional[Dict[str, Any]]:
    """Dispatch to registered handler if action exists."""
    handler = get_handler(action)
    if handler:
        return handler(event, context)
    return None


# =============================================================================
# MEDIA TYPE DEFINITIONS
# =============================================================================
SUPPORTED_MEDIA_TYPES = {
    "audio": {
        "formats": ["audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"],
        "maxSizeMB": 16,
        "notes": "OGG requires OPUS codec, mono input only"
    },
    "document": {
        "formats": [
            "text/plain", "application/pdf",
            "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ],
        "maxSizeMB": 100
    },
    "image": {
        "formats": ["image/jpeg", "image/png"],
        "maxSizeMB": 5,
        "notes": "8-bit RGB or RGBA only"
    },
    "sticker": {
        "formats": ["image/webp"],
        "maxSizeKB": 500,
        "notes": "Animated max 500KB, static max 100KB"
    },
    "video": {
        "formats": ["video/mp4", "video/3gpp"],
        "maxSizeMB": 16,
        "notes": "H.264 video codec, AAC audio codec"
    }
}


def get_supported_mime_types() -> List[str]:
    """Get list of all supported MIME types."""
    mime_types = []
    for category in SUPPORTED_MEDIA_TYPES.values():
        mime_types.extend(category.get("formats", []))
    return mime_types


def is_supported_media(mime_type: str, file_size_bytes: int = 0) -> Dict[str, Any]:
    """Check if a media type is supported and within size limits."""
    for category, info in SUPPORTED_MEDIA_TYPES.items():
        if mime_type in info.get("formats", []):
            max_bytes = info.get("maxSizeMB", 0) * 1024 * 1024
            if not max_bytes:
                max_bytes = info.get("maxSizeKB", 0) * 1024
            
            within_limit = file_size_bytes <= max_bytes if file_size_bytes > 0 else True
            return {
                "supported": True,
                "category": category,
                "withinSizeLimit": within_limit,
                "maxBytes": max_bytes,
            }
    return {"supported": False, "category": None}


def mime_to_ext(m: Optional[str]) -> str:
    """Convert MIME type to file extension."""
    if not m:
        return ".bin"
    return {
        "image/jpeg": ".jpeg", "image/png": ".png", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/3gpp": ".3gp",
        "audio/mpeg": ".mp3", "audio/aac": ".aac", "audio/amr": ".amr", 
        "audio/mp4": ".m4a", "audio/ogg": ".ogg",
        "application/pdf": ".pdf", "text/plain": ".txt",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    }.get(m, ".bin")
