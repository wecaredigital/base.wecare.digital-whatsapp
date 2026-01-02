import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# =============================================================================
# UNIFIED HANDLER SYSTEM
# =============================================================================
# Import the unified dispatcher for ALL handlers (core + extended)
# This provides a single entry point for all action handling
from handlers import unified_dispatch

# ---------- Logger ----------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# LAZY CLIENT INITIALIZATION (Import-safe pattern)
# =============================================================================
# Clients are created on first access, not at import time.
# This allows the module to be imported without AWS credentials.
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


# Client accessor functions (lazy-loaded)
def get_ddb(): return _get_resource("dynamodb")
def get_s3(): return _get_client("s3")
def get_social(): return _get_client("socialmessaging")
def get_sns(): return _get_client("sns")
def get_ec2(): return _get_client("ec2")
def get_iam(): return _get_client("iam")


# Convenience aliases - call as functions: ddb(), s3(), social(), etc.
def ddb(): return get_ddb()
def s3(): return get_s3()
def social(): return get_social()
def sns(): return get_sns()
def ec2(): return get_ec2()
def iam(): return get_iam()


# =============================================================================
# LAZY ENVIRONMENT CONFIGURATION
# =============================================================================
_env_cache: Dict[str, Any] = {}


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with caching."""
    if key not in _env_cache:
        _env_cache[key] = os.environ.get(key, default)
    return _env_cache[key]


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    return _get_env(key, str(default)).lower() == "true"


def _get_env_json(key: str, default: dict = None) -> dict:
    """Get JSON environment variable."""
    cache_key = f"_json_{key}"
    if cache_key not in _env_cache:
        try:
            _env_cache[cache_key] = json.loads(_get_env(key, "{}") or "{}")
        except json.JSONDecodeError:
            _env_cache[cache_key] = default or {}
    return _env_cache[cache_key]


# Environment variable accessors (lazy-loaded)
def get_messages_table_name(): return _get_env("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
def get_messages_pk_name(): return _get_env("MESSAGES_PK_NAME", "pk")
def get_media_bucket(): return _get_env("MEDIA_BUCKET", "dev.wecare.digital")
def get_media_prefix(): return _get_env("MEDIA_PREFIX", "WhatsApp/")
def get_meta_api_version(): return _get_env("META_API_VERSION", "v20.0")
def get_auto_reply_enabled(): return _get_env_bool("AUTO_REPLY_ENABLED", False)
def get_auto_reply_text(): return _get_env("AUTO_REPLY_TEXT", "Thanks! We received your message.")
def get_echo_media_back(): return _get_env_bool("ECHO_MEDIA_BACK", True)
def get_forward_enabled(): return _get_env_bool("FORWARD_ENABLED", False)
def get_forward_to_wa_id(): return _get_env("FORWARD_TO_WA_ID", "")
def get_forward_delete_uploaded_media(): return _get_env_bool("FORWARD_DELETE_UPLOADED_MEDIA", False)
def get_mark_as_read_enabled(): return _get_env_bool("MARK_AS_READ_ENABLED", True)
def get_react_emoji_enabled(): return _get_env_bool("REACT_EMOJI_ENABLED", True)
def get_email_notification_enabled(): return _get_env_bool("EMAIL_NOTIFICATION_ENABLED", True)
def get_email_sns_topic_arn(): return _get_env("EMAIL_SNS_TOPIC_ARN", "arn:aws:sns:ap-south-1:010526260063:base-wecare-digital")
def get_waba_phone_map(): return _get_env_json("WABA_PHONE_MAP_JSON")
def get_welcome_enabled(): return _get_env_bool("WELCOME_ENABLED", True)
def get_menu_on_keywords_enabled(): return _get_env_bool("MENU_ON_KEYWORDS_ENABLED", True)
def get_bedrock_auto_reply_enabled(): return _get_env_bool("BEDROCK_AUTO_REPLY_ENABLED", False)


# =============================================================================
# MODULE-LEVEL COMPATIBILITY VARIABLES
# =============================================================================
# These are simple string/bool values that are initialized on first access.
# The lazy initialization pattern ensures the module can be imported without AWS credentials.
# =============================================================================
class _LazyEnvVar:
    """Lazy environment variable accessor for backward compatibility."""
    def __init__(self, getter):
        self._getter = getter
        self._value = None
        self._initialized = False
    
    def _ensure_init(self):
        if not self._initialized:
            self._value = self._getter()
            self._initialized = True
        return self._value
    
    def __str__(self):
        return str(self._ensure_init())
    
    def __repr__(self):
        return repr(self._ensure_init())
    
    def __eq__(self, other):
        return self._ensure_init() == other
    
    def __hash__(self):
        return hash(self._ensure_init())
    
    def __bool__(self):
        return bool(self._ensure_init())
    
    def __add__(self, other):
        return str(self._ensure_init()) + other
    
    def __radd__(self, other):
        return other + str(self._ensure_init())
    
    def get(self, key, default=None):
        """Support dict-like access for WABA_PHONE_MAP."""
        val = self._ensure_init()
        if isinstance(val, dict):
            return val.get(key, default)
        return default


# For backward compatibility, these can be used directly in string contexts
MESSAGES_TABLE_NAME = _LazyEnvVar(get_messages_table_name)
MESSAGES_PK_NAME = _LazyEnvVar(get_messages_pk_name)
MEDIA_BUCKET = _LazyEnvVar(get_media_bucket)
MEDIA_PREFIX = _LazyEnvVar(get_media_prefix)
META_API_VERSION = _LazyEnvVar(get_meta_api_version)
AUTO_REPLY_ENABLED = _LazyEnvVar(get_auto_reply_enabled)
AUTO_REPLY_TEXT = _LazyEnvVar(get_auto_reply_text)
ECHO_MEDIA_BACK = _LazyEnvVar(get_echo_media_back)
FORWARD_ENABLED = _LazyEnvVar(get_forward_enabled)
FORWARD_TO_WA_ID = _LazyEnvVar(get_forward_to_wa_id)
FORWARD_DELETE_UPLOADED_MEDIA = _LazyEnvVar(get_forward_delete_uploaded_media)
MARK_AS_READ_ENABLED = _LazyEnvVar(get_mark_as_read_enabled)
REACT_EMOJI_ENABLED = _LazyEnvVar(get_react_emoji_enabled)
EMAIL_NOTIFICATION_ENABLED = _LazyEnvVar(get_email_notification_enabled)
EMAIL_SNS_TOPIC_ARN = _LazyEnvVar(get_email_sns_topic_arn)
WABA_PHONE_MAP = _LazyEnvVar(get_waba_phone_map)
WELCOME_ENABLED = _LazyEnvVar(get_welcome_enabled)
MENU_ON_KEYWORDS_ENABLED = _LazyEnvVar(get_menu_on_keywords_enabled)
BEDROCK_AUTO_REPLY_ENABLED = _LazyEnvVar(get_bedrock_auto_reply_enabled)


# Table accessor with caching
_table = None
def get_table():
    global _table
    if _table is None:
        _table = get_ddb().Table(get_messages_table_name())
    return _table


def table(): return get_table()


# =============================================================================
# REACTION EMOJI CONFIGURATION
# =============================================================================
# Default emoji map by message type - can be overridden via REACT_EMOJI_MAP_JSON env var
# Supported emojis: 👍 ❤️ 😂 😮 😢 🙏 🔥 🎉 ✅ 👋 💯 👀 (or any Unicode emoji)
DEFAULT_REACT_EMOJI_MAP = {
    "text": "👍",      # Thumbs up for text messages
    "image": "❤️",     # Heart for images
    "video": "🔥",     # Fire for videos
    "audio": "🎵",     # Music note for audio
    "document": "✅",  # Check mark for documents
    "sticker": "😂",   # Laughing for stickers
    "location": "📍",  # Pin for location
    "contacts": "👋",  # Wave for contacts
    "default": "👍",   # Default fallback
}


def get_react_emoji_map() -> Dict[str, str]:
    """Get reaction emoji map from env or default."""
    custom_map = _get_env_json("REACT_EMOJI_MAP_JSON")
    return custom_map if custom_map else DEFAULT_REACT_EMOJI_MAP


def get_reaction_emoji(message_type: str) -> str:
    """Get the appropriate reaction emoji for a message type."""
    emoji_map = get_react_emoji_map()
    return emoji_map.get(message_type, emoji_map.get("default", "👍"))


# =============================================================================
# WABA FOLDER MAPPING FOR S3 MEDIA PATHS
# =============================================================================
# S3 Structure:
#   s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}  (inbound)
#   s3://dev.wecare.digital/WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}    (outbound)
# =============================================================================
WABA_FOLDER_MAP = {
    "1347766229904230": "wecare",   # WECARE.DIGITAL
    "1390647332755815": "manish",   # Manish Agarwal
}


def get_waba_folder(meta_waba_id: str) -> str:
    """Get folder name for WABA. Returns mapped name or sanitized fallback."""
    if meta_waba_id in WABA_FOLDER_MAP:
        return WABA_FOLDER_MAP[meta_waba_id]
    # Fallback to last 6 chars of WABA ID
    return f"waba_{meta_waba_id[-6:]}" if meta_waba_id else "unknown"


def generate_secure_filename(base_name: str = "file", mime_type: str = None) -> str:
    """Generate secure filename with UUID to prevent URL guessing.
    
    Format: {base_name}_{uuid}.{ext}
    Example: image_a1b2c3d4e5f6.jpg
    """
    import uuid
    unique_id = uuid.uuid4().hex[:12]  # 12 char hex = 48 bits of randomness
    ext = mime_to_ext(mime_type) if mime_type else ""
    if base_name:
        # Sanitize base name - keep only alphanumeric, dash, underscore
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)[:30]
        return f"{safe_name}_{unique_id}{ext}"
    return f"file_{unique_id}{ext}"


def generate_download_s3_key(meta_waba_id: str, filename: str = "media", mime_type: str = None) -> str:
    """Generate S3 key for downloading inbound media.
    
    Path: WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    """
    waba_folder = get_waba_folder(meta_waba_id)
    secure_filename = generate_secure_filename(filename, mime_type)
    return f"{get_media_prefix()}download/{waba_folder}/{secure_filename}"


def generate_upload_s3_key(meta_waba_id: str, filename: str = "media", mime_type: str = None) -> str:
    """Generate S3 key for uploading outbound media.
    
    Path: WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}
    """
    waba_folder = get_waba_folder(meta_waba_id)
    secure_filename = generate_secure_filename(filename, mime_type)
    return f"{get_media_prefix()}upload/{waba_folder}/{secure_filename}"


# ---------- Helpers ----------
def jdump(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def api_response(data: Dict[str, Any], status_code: int = None) -> Dict[str, Any]:
    """Wrap response for API Gateway HTTP API compatibility.
    
    For HTTP API payload format 2.0, returns proper response format with:
    - statusCode: HTTP status code
    - headers: Content-Type header
    - body: JSON string of the response data
    """
    # Extract statusCode from data if present, otherwise use provided or default to 200
    code = status_code or data.get("statusCode", 200)
    
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(data, ensure_ascii=False, default=str),
    }


def jload_maybe(s: Any) -> Any:
    if not isinstance(s, str):
        return s
    s2 = s.strip()
    try:
        o = json.loads(s2)
    except Exception:
        return s
    if isinstance(o, str):
        try:
            return json.loads(o)
        except Exception:
            return o
    return o


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe(s: Optional[str]) -> str:
    if not s:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9=._\-/#]+", "_", s)


def arn_suffix(arn: str) -> str:
    return arn.split("/")[-1] if arn and "arn:" in arn else arn


def mime_to_ext(m: Optional[str]) -> str:
    if not m:
        return ".bin"
    return {
        "image/jpeg": ".jpeg", "image/png": ".png", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/3gpp": ".3gp",
        "audio/mpeg": ".mp3", "audio/aac": ".aac", "audio/amr": ".amr", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
        "application/pdf": ".pdf", "text/plain": ".txt",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    }.get(m, ".bin")


# WhatsApp Supported Media Types (from AWS/Meta documentation)
SUPPORTED_MEDIA_TYPES = {
    "audio": {
        "formats": [
            {"type": "AAC", "extension": ".aac", "mimeType": "audio/aac", "maxSizeMB": 16},
            {"type": "AMR", "extension": ".amr", "mimeType": "audio/amr", "maxSizeMB": 16},
            {"type": "MP3", "extension": ".mp3", "mimeType": "audio/mpeg", "maxSizeMB": 16},
            {"type": "MP4 Audio", "extension": ".m4a", "mimeType": "audio/mp4", "maxSizeMB": 16},
            {"type": "OGG Audio", "extension": ".ogg", "mimeType": "audio/ogg", "maxSizeMB": 16, "note": "OPUS codecs only; mono input only"},
        ],
        "maxSizeMB": 16,
    },
    "document": {
        "formats": [
            {"type": "Text", "extension": ".txt", "mimeType": "text/plain", "maxSizeMB": 100},
            {"type": "PDF", "extension": ".pdf", "mimeType": "application/pdf", "maxSizeMB": 100},
            {"type": "Microsoft Excel", "extension": ".xls", "mimeType": "application/vnd.ms-excel", "maxSizeMB": 100},
            {"type": "Microsoft Excel", "extension": ".xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "maxSizeMB": 100},
            {"type": "Microsoft Word", "extension": ".doc", "mimeType": "application/msword", "maxSizeMB": 100},
            {"type": "Microsoft Word", "extension": ".docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "maxSizeMB": 100},
            {"type": "Microsoft PowerPoint", "extension": ".ppt", "mimeType": "application/vnd.ms-powerpoint", "maxSizeMB": 100},
            {"type": "Microsoft PowerPoint", "extension": ".pptx", "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "maxSizeMB": 100},
        ],
        "maxSizeMB": 100,
    },
    "image": {
        "formats": [
            {"type": "JPEG", "extension": ".jpeg", "mimeType": "image/jpeg", "maxSizeMB": 5},
            {"type": "PNG", "extension": ".png", "mimeType": "image/png", "maxSizeMB": 5},
        ],
        "maxSizeMB": 5,
        "note": "Images must be 8-bit, RGB or RGBA",
    },
    "sticker": {
        "formats": [
            {"type": "Animated sticker", "extension": ".webp", "mimeType": "image/webp", "maxSizeKB": 500},
            {"type": "Static sticker", "extension": ".webp", "mimeType": "image/webp", "maxSizeKB": 100},
        ],
        "maxSizeKB": 500,
        "note": "WebP images can only be sent in sticker messages",
    },
    "video": {
        "formats": [
            {"type": "3GPP", "extension": ".3gp", "mimeType": "video/3gpp", "maxSizeMB": 16},
            {"type": "MP4 Video", "extension": ".mp4", "mimeType": "video/mp4", "maxSizeMB": 16},
        ],
        "maxSizeMB": 16,
        "note": "H.264 video codec and AAC audio codec only. Use H.264 Main or Baseline profile for Android compatibility.",
    },
}


def get_supported_mime_types() -> List[str]:
    """Get list of all supported MIME types."""
    mime_types = []
    for category in SUPPORTED_MEDIA_TYPES.values():
        for fmt in category.get("formats", []):
            mime_types.append(fmt["mimeType"])
    return mime_types


def is_supported_media(mime_type: str, file_size_bytes: int = 0) -> Dict[str, Any]:
    """Check if a media type is supported and within size limits."""
    for category, info in SUPPORTED_MEDIA_TYPES.items():
        for fmt in info.get("formats", []):
            if fmt["mimeType"] == mime_type:
                max_bytes = fmt.get("maxSizeMB", 0) * 1024 * 1024
                if not max_bytes:
                    max_bytes = fmt.get("maxSizeKB", 0) * 1024
                
                within_limit = file_size_bytes <= max_bytes if file_size_bytes > 0 else True
                return {
                    "supported": True,
                    "category": category,
                    "format": fmt,
                    "withinSizeLimit": within_limit,
                    "maxBytes": max_bytes,
                }
    return {"supported": False, "category": None, "format": None}


def preview(mtype: str, text_body: str, caption: str) -> str:
    if mtype == "text" and text_body:
        return text_body[:200]
    if caption:
        return f"[{mtype}] {caption}"[:200]
    return f"[{mtype}]"


def origination_id_for_api(phone_arn: str) -> str:
    if not phone_arn:
        return ""
    if "phone-number-id/" in phone_arn:
        suffix = phone_arn.split("phone-number-id/")[-1]
        return f"phone-number-id-{suffix}"
    return phone_arn


def format_wa_number(wa_id: str) -> str:
    """Format WhatsApp number for AWS Social Messaging API calls.
    AWS Social Messaging API expects numbers WITH the + prefix.
    Example: +919903300044 (not 919903300044)
    
    Note: This is different from Meta's direct WhatsApp Cloud API which expects
    numbers WITHOUT the + prefix. AWS Social Messaging handles the conversion.
    """
    if not wa_id:
        return ""
    wa_id = wa_id.strip()
    # Add + prefix if not present - AWS Social Messaging API requires +
    if not wa_id.startswith("+"):
        return f"+{wa_id}"
    return wa_id


def generate_s3_presigned_url(bucket: str, key: str, expiry: int = 86400) -> str:
    """Generate presigned URL for S3 object (24 hour expiry)."""
    if not bucket or not key:
        return ""
    try:
        return s3().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiry
        )
    except Exception:
        return f"s3://{bucket}/{key}"


@dataclass(frozen=True)
class AccountInfo:
    business_name: str
    phone_arn: str
    phone: str
    meta_phone_number_id: str


def lookup_account_by_waba_meta_id(waba_meta_id: str) -> Optional[AccountInfo]:
    x = WABA_PHONE_MAP.get(str(waba_meta_id))
    if not x:
        return None
    return AccountInfo(
        business_name=x.get("businessAccountName", ""),
        phone_arn=x.get("phoneArn", ""),
        phone=x.get("phone", ""),
        meta_phone_number_id=x.get("meta_phone_number_id", ""),
    )


# ---------- Template Component Helpers ----------
def build_template_header_component(
    header_type: str = "text",
    text: str = "",
    media_id: str = "",
    media_link: str = "",
    document_filename: str = "",
) -> Dict[str, Any]:
    """Build a header component for template messages.
    
    Args:
        header_type: "text", "image", "video", or "document"
        text: Text for text headers (can include {{1}} placeholders)
        media_id: WhatsApp media ID for media headers
        media_link: URL link for media headers (alternative to media_id)
        document_filename: Filename for document headers
    
    Returns:
        Header component dict ready for template components array
    
    Examples:
        # Text header with variable
        build_template_header_component("text", text="Order #{{1}}")
        
        # Image header with media ID
        build_template_header_component("image", media_id="123456789")
        
        # Document header with link
        build_template_header_component("document", media_link="https://example.com/doc.pdf", document_filename="Invoice.pdf")
    """
    component: Dict[str, Any] = {"type": "header", "parameters": []}
    
    if header_type == "text":
        if text:
            component["parameters"].append({"type": "text", "text": text})
    elif header_type in ("image", "video", "document"):
        param: Dict[str, Any] = {"type": header_type}
        media_obj: Dict[str, Any] = {}
        
        if media_id:
            media_obj["id"] = media_id
        elif media_link:
            media_obj["link"] = media_link
        
        if header_type == "document" and document_filename:
            media_obj["filename"] = document_filename
        
        if media_obj:
            param[header_type] = media_obj
            component["parameters"].append(param)
    
    return component


def build_template_body_component(parameters: List[str]) -> Dict[str, Any]:
    """Build a body component for template messages.
    
    Args:
        parameters: List of text values to replace {{1}}, {{2}}, etc.
    
    Returns:
        Body component dict ready for template components array
    
    Example:
        # For template body: "Hello {{1}}, your order {{2}} is ready"
        build_template_body_component(["John", "ORD-12345"])
    """
    return {
        "type": "body",
        "parameters": [{"type": "text", "text": str(p)} for p in parameters]
    }


def build_template_button_component(
    button_index: int,
    button_type: str = "url",
    url_suffix: str = "",
    payload: str = "",
    coupon_code: str = "",
) -> Dict[str, Any]:
    """Build a button component for template messages with dynamic URL support.
    
    Args:
        button_index: 0-based index of the button in the template
        button_type: "url" for dynamic URL, "quick_reply" for quick reply, "copy_code" for coupon
        url_suffix: Dynamic suffix to append to the template's base URL (for url type)
        payload: Payload for quick_reply buttons
        coupon_code: Code for copy_code (coupon) buttons
    
    Returns:
        Button component dict ready for template components array
    
    Examples:
        # Dynamic URL button (template has: https://example.com/track/{{1}})
        build_template_button_component(0, "url", url_suffix="ORD-12345")
        
        # Quick reply button
        build_template_button_component(1, "quick_reply", payload="confirm_order")
        
        # Copy code (coupon) button
        build_template_button_component(0, "copy_code", coupon_code="SAVE20")
    """
    component: Dict[str, Any] = {
        "type": "button",
        "sub_type": button_type,
        "index": str(button_index),
        "parameters": []
    }
    
    if button_type == "url" and url_suffix:
        component["parameters"].append({"type": "text", "text": url_suffix})
    elif button_type == "quick_reply" and payload:
        component["parameters"].append({"type": "payload", "payload": payload})
    elif button_type == "copy_code" and coupon_code:
        component["parameters"].append({"type": "coupon_code", "coupon_code": coupon_code})
    
    return component


def build_template_components(
    body_params: List[str] = None,
    header_type: str = None,
    header_text: str = None,
    header_media_id: str = None,
    header_media_link: str = None,
    header_document_filename: str = None,
    buttons: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build complete template components array for send_template.
    
    This is a convenience function that combines header, body, and button components.
    
    Args:
        body_params: List of text values for body placeholders {{1}}, {{2}}, etc.
        header_type: "text", "image", "video", or "document" (optional)
        header_text: Text for text headers
        header_media_id: WhatsApp media ID for media headers
        header_media_link: URL for media headers
        header_document_filename: Filename for document headers
        buttons: List of button configs, each with:
            - index: 0-based button index
            - type: "url", "quick_reply", or "copy_code"
            - url_suffix: For dynamic URL buttons
            - payload: For quick_reply buttons
            - coupon_code: For copy_code buttons
    
    Returns:
        Complete components array ready for send_template action
    
    Example:
        # Template with body params and dynamic URL button
        components = build_template_components(
            body_params=["John", "ORD-12345"],
            buttons=[{"index": 0, "type": "url", "url_suffix": "ORD-12345"}]
        )
        
        # Template with image header and body params
        components = build_template_components(
            header_type="image",
            header_media_id="123456789",
            body_params=["Summer Sale", "50% off"]
        )
    """
    components = []
    
    # Add header component if specified
    if header_type:
        header = build_template_header_component(
            header_type=header_type,
            text=header_text or "",
            media_id=header_media_id or "",
            media_link=header_media_link or "",
            document_filename=header_document_filename or "",
        )
        if header.get("parameters"):
            components.append(header)
    
    # Add body component if params provided
    if body_params:
        components.append(build_template_body_component(body_params))
    
    # Add button components
    if buttons:
        for btn in buttons:
            btn_component = build_template_button_component(
                button_index=btn.get("index", 0),
                button_type=btn.get("type", "url"),
                url_suffix=btn.get("url_suffix", ""),
                payload=btn.get("payload", ""),
                coupon_code=btn.get("coupon_code", ""),
            )
            if btn_component.get("parameters"):
                components.append(btn_component)
    
    return components


def build_email_html(sender_name: str, sender_number: str, message_text: str, media_url: str, 
                     business_name: str, message_type: str, received_at: str) -> str:
    """Build HTML email template for notification."""
    media_section = ""
    if media_url:
        if message_type in ("image", "sticker"):
            media_section = f'''
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Media:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="{media_url}" target="_blank">
                        <img src="{media_url}" alt="Image" style="max-width: 300px; max-height: 300px; border-radius: 8px;">
                    </a>
                    <br><a href="{media_url}" target="_blank">Download {message_type}</a>
                </td>
            </tr>'''
        else:
            media_section = f'''
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Media:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="{media_url}" target="_blank" style="color: #25D366; text-decoration: none;">
                        📎 Download {message_type.upper()} file
                    </a>
                </td>
            </tr>'''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>New WhatsApp Message</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="background-color: #25D366; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">📱 New WhatsApp Message</h1>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">{business_name}</p>
        </div>
        <div style="padding: 20px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; width: 120px;"><strong>Sender Name:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{sender_name or "Unknown"}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Sender Number:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">
                        <a href="https://wa.me/{sender_number}" style="color: #25D366; text-decoration: none;">+{sender_number}</a>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Message Type:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{message_type.upper()}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Message:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; white-space: pre-wrap;">{message_text or "[No text content]"}</td>
                </tr>
                {media_section}
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Received At:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{received_at}</td>
                </tr>
            </table>
        </div>
        <div style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666;">
            <p style="margin: 0;">This is an automated notification from {business_name} WhatsApp Integration</p>
        </div>
    </div>
</body>
</html>'''


# ---------- Helper functions (formerly durable steps) ----------
def download_media_to_s3(media_id: str, phone_arn: str, s3_key: str) -> Dict[str, Any]:
    logger.info(f"Downloading mediaId={media_id} to s3://{MEDIA_BUCKET}/{s3_key}")
    try:
        resp = social().get_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            destinationS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        return resp
    except ClientError as e:
        logger.exception(f"get_whatsapp_message_media failed mediaId={media_id}")
        raise


def put_message_item(item: Dict[str, Any]) -> None:
    pk_name = str(MESSAGES_PK_NAME)  # Convert LazyEnvVar to string
    try:
        table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(#pk)",
            ExpressionAttributeNames={"#pk": pk_name},
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return
        raise


def upsert_conversation_item(conv_pk: str, phone_arn: str, from_wa: str, update: Dict[str, Any]) -> None:
    try:
        table().update_item(
            Key={str(MESSAGES_PK_NAME): conv_pk},
            UpdateExpression=(
                "SET itemType=:t, inboxPk=:inboxPk, receivedAt=:ra, "
                "    originationPhoneNumberId=:opn, #from=:f, "
                "    businessAccountName=:ban, businessPhone=:bp, meta_phone_number_id=:mpn, "
                "    lastMessagePk=:lmpk, lastMessageId=:lmid, lastType=:lt, lastPreview=:lp, lastS3Uri=:ls3 "
                "ADD unreadCount :one"
            ),
            ConditionExpression="attribute_not_exists(lastMessageId) OR lastMessageId <> :lmid",
            ExpressionAttributeNames={"#from": "from"},
            ExpressionAttributeValues={
                ":t": "CONVERSATION",
                ":inboxPk": phone_arn,
                ":ra": update["receivedAt"],
                ":opn": phone_arn,
                ":f": from_wa,
                ":ban": update.get("businessAccountName", ""),
                ":bp": update.get("businessPhone", ""),
                ":mpn": update.get("meta_phone_number_id", ""),
                ":lmpk": update.get("lastMessagePk", ""),
                ":lmid": update.get("lastMessageId", ""),
                ":lt": update.get("lastType", ""),
                ":lp": update.get("lastPreview", ""),
                ":ls3": update.get("lastS3Uri", ""),
                ":one": 1,
            },
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return
        raise


def send_text_reply(phone_arn: str, to_wa: str, reply_to_msg_id: Optional[str]) -> Dict[str, Any]:
    if not AUTO_REPLY_ENABLED:
        return {"sent": False, "reason": "AUTO_REPLY_ENABLED=false"}

    to_formatted = format_wa_number(to_wa)
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "text",
        "text": {"preview_url": False, "body": str(AUTO_REPLY_TEXT)},
    }
    if reply_to_msg_id:
        payload["context"] = {"message_id": reply_to_msg_id}

    logger.info(f"Sending text reply to {to_formatted}")
    resp = social().send_whatsapp_message(
        originationPhoneNumberId=origination_id_for_api(phone_arn),
        metaApiVersion=str(META_API_VERSION),
        message=json.dumps(payload).encode("utf-8"),
    )
    return {"sent": True, "messageId": resp.get("messageId")}


def mark_message_as_read(phone_arn: str, wa_msg_id: str, msg_pk: str) -> Dict[str, Any]:
    """Mark inbound message as read (sends blue check marks to sender)."""
    if not MARK_AS_READ_ENABLED:
        return {"marked": False, "reason": "MARK_AS_READ_ENABLED=false"}
    
    payload = {
        "messaging_product": "whatsapp",
        "message_id": wa_msg_id,
        "status": "read",
    }
    
    logger.info(f"Marking message as read: {wa_msg_id}")
    try:
        resp = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Update DynamoDB with read receipt sent status
        now = iso_now()
        try:
            table().update_item(
                Key={str(MESSAGES_PK_NAME): msg_pk},
                UpdateExpression="SET markedAsRead = :mar, markedAsReadAt = :marat",
                ExpressionAttributeValues={
                    ":mar": True,
                    ":marat": now,
                },
            )
        except ClientError as e:
            logger.warning(f"Failed to update markedAsRead in DynamoDB: {e}")
        
        return {"marked": True, "messageId": resp.get("messageId")}
    except ClientError as e:
        logger.exception(f"Failed to mark message as read: {wa_msg_id}")
        return {"marked": False, "error": str(e)}


def react_with_emoji(phone_arn: str, to_wa: str, wa_msg_id: str, msg_pk: str, 
                     message_type: str = "text", emoji: str = None) -> Dict[str, Any]:
    """React to inbound message with emoji based on message type.
    
    Emoji mapping (configurable via REACT_EMOJI_MAP_JSON env var):
    - text: 👍 (thumbs up)
    - image: ❤️ (heart)
    - video: 🔥 (fire)
    - audio: 🎵 (music)
    - document: ✅ (check)
    - sticker: 😂 (laughing)
    - location: 📍 (pin)
    - contacts: 👋 (wave)
    - default: 👍 (thumbs up)
    """
    if not REACT_EMOJI_ENABLED:
        return {"reacted": False, "reason": "REACT_EMOJI_ENABLED=false"}
    
    # Use provided emoji, or get from map based on message type
    reaction_emoji = emoji or get_reaction_emoji(message_type)
    to_formatted = format_wa_number(to_wa)
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_formatted,
        "type": "reaction",
        "reaction": {
            "message_id": wa_msg_id,
            "emoji": reaction_emoji,
        },
    }
    
    logger.info(f"Reacting to {message_type} message {wa_msg_id} with {reaction_emoji}")
    try:
        resp = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Update DynamoDB with reaction sent status
        now = iso_now()
        try:
            table().update_item(
                Key={str(MESSAGES_PK_NAME): msg_pk},
                UpdateExpression="SET reactedWithEmoji = :emoji, reactedAt = :rat",
                ExpressionAttributeValues={
                    ":emoji": reaction_emoji,
                    ":rat": now,
                },
            )
        except ClientError as e:
            logger.warning(f"Failed to update reactedWithEmoji in DynamoDB: {e}")
        
        return {"reacted": True, "emoji": reaction_emoji, "messageType": message_type, "messageId": resp.get("messageId")}
    except ClientError as e:
        logger.exception(f"Failed to react to message: {wa_msg_id}")
        return {"reacted": False, "error": str(e)}


def upload_s3_media_to_whatsapp(phone_arn: str, s3_key: str) -> Dict[str, Any]:
    logger.info(f"Uploading s3://{MEDIA_BUCKET}/{s3_key} to WhatsApp")
    resp = social().post_whatsapp_message_media(
        originationPhoneNumberId=origination_id_for_api(phone_arn),
        sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
    )
    return {"mediaId": resp.get("mediaId")}


def send_media_message(phone_arn: str, to_wa: str, media_type: str, media_id: str, 
                       caption: str = "", filename: str = "") -> Dict[str, Any]:
    to_formatted = format_wa_number(to_wa)
    
    # Map sticker to image for echo back
    send_type = media_type if media_type != "sticker" else "image"
    
    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": send_type,
        send_type: {"id": media_id},
    }
    if caption and send_type in {"image", "video", "document"}:
        payload[send_type]["caption"] = caption
    if filename and send_type == "document":
        payload[send_type]["filename"] = filename

    logger.info(f"Sending {send_type} to {to_formatted}")
    resp = social().send_whatsapp_message(
        originationPhoneNumberId=origination_id_for_api(phone_arn),
        metaApiVersion=str(META_API_VERSION),
        message=json.dumps(payload).encode("utf-8"),
    )
    return {"sent": True, "messageId": resp.get("messageId")}


def delete_uploaded_media(phone_arn: str, media_id: str) -> Dict[str, Any]:
    if not FORWARD_DELETE_UPLOADED_MEDIA:
        return {"deleted": False, "reason": "disabled"}
    resp = social().delete_whatsapp_message_media(
        originationPhoneNumberId=origination_id_for_api(phone_arn),
        mediaId=media_id,
    )
    return {"deleted": bool(resp.get("success"))}


def update_message_status(wa_msg_id: str, status: str, status_timestamp: str,
                          recipient_id: str, errors: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update message delivery status in DynamoDB."""
    msg_pk = f"MSG#{wa_msg_id}"
    now = iso_now()
    pk_name = str(MESSAGES_PK_NAME)  # Convert LazyEnvVar to string
    
    # Build status history entry
    status_entry = {
        "status": status,
        "timestamp": status_timestamp,
        "updatedAt": now,
    }
    if errors:
        status_entry["errors"] = errors
    
    logger.info(f"Updating status for {msg_pk}: {status}")
    
    try:
        # Update the message item with new status using list_append for history
        # Also set direction=OUTBOUND since status updates are for sent messages
        table().update_item(
            Key={pk_name: msg_pk},
            UpdateExpression=(
                "SET deliveryStatus = :status, "
                "    deliveryStatusTimestamp = :ts, "
                "    deliveryStatusUpdatedAt = :now, "
                "    recipientId = :rid, "
                "    direction = if_not_exists(direction, :dir), "
                "    deliveryStatusHistory = list_append(if_not_exists(deliveryStatusHistory, :empty_list), :entry)"
            ),
            ExpressionAttributeValues={
                ":status": status,
                ":ts": status_timestamp,
                ":now": now,
                ":rid": recipient_id,
                ":dir": "OUTBOUND",
                ":entry": [status_entry],
                ":empty_list": [],
            },
        )
        return {"updated": True, "status": status, "messagePk": msg_pk}
    except ClientError as e:
        # If message doesn't exist yet (status arrived before message), create a placeholder
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationException":
            logger.warning(f"Message {msg_pk} not found, creating status-only record")
            try:
                table().put_item(
                    Item={
                        pk_name: msg_pk,
                        "itemType": "MESSAGE_STATUS",
                        "direction": "OUTBOUND",  # Status updates are for outbound messages
                        "deliveryStatus": status,
                        "deliveryStatusTimestamp": status_timestamp,
                        "deliveryStatusUpdatedAt": now,
                        "recipientId": recipient_id,
                        "deliveryStatusHistory": [status_entry],
                    },
                    ConditionExpression="attribute_not_exists(#pk)",
                    ExpressionAttributeNames={"#pk": pk_name},
                )
                return {"updated": True, "status": status, "messagePk": msg_pk, "created": True}
            except ClientError:
                pass
        logger.exception(f"Failed to update status for {msg_pk}")
        return {"updated": False, "error": str(e)}


def send_email_notification(sender_name: str, sender_number: str, message_text: str,
                            media_url: str, business_name: str, message_type: str, received_at: str) -> Dict[str, Any]:
    if not EMAIL_NOTIFICATION_ENABLED:
        return {"sent": False, "reason": "EMAIL_NOTIFICATION_ENABLED=false"}
    
    html_body = build_email_html(sender_name, sender_number, message_text, media_url, 
                                  business_name, message_type, received_at)
    
    subject = f"📱 New WhatsApp Message from +{sender_number} - {business_name}"
    
    logger.info(f"Sending email notification for message from {sender_number}")
    try:
        resp = sns().publish(
            TopicArn=str(EMAIL_SNS_TOPIC_ARN),
            Subject=subject,
            Message=html_body,
            MessageStructure="string",
        )
        return {"sent": True, "messageId": resp.get("MessageId")}
    except ClientError as e:
        logger.exception(f"Failed to send email notification: {e}")
        return {"sent": False, "error": str(e)}


def update_phone_quality_rating(waba_id: str, phone_number_id: str, 
                                 business_name: str, phone_number: str) -> Dict[str, Any]:
    """Fetch and store phone number quality rating and throughput info from AWS Social Messaging API.
    
    Quality Ratings:
    - GREEN: High quality
    - YELLOW: Medium quality (needs attention)
    - RED: Low quality (urgent action needed)
    
    Phone Status:
    - Connected: Can send messages within quota
    - Flagged: Quality is low, needs improvement in 7 days
    - Restricted: Reached 24-hour conversation limit
    
    Throughput (MPS - Messages Per Second):
    - Default: 80 MPS for all phone numbers
    - Max: 1,000 MPS (must request from Meta)
    - Requirements for 1,000 MPS:
      - Quality rating: GREEN or YELLOW
      - Unlimited business-initiated conversations tier
    
    Note: Actual throughput is not exposed via API. It's managed by Meta.
    To request throughput increase, contact Meta support via Business Manager.
    """
    now = iso_now()
    quality_pk = f"QUALITY#{phone_number_id}"
    
    try:
        # Get WABA details including phone quality
        # First, find the WABA AWS ID from the Meta WABA ID
        waba_aws_id = None
        try:
            response = social().list_linked_whatsapp_business_accounts()
            for account in response.get('linkedAccounts', []):
                if account.get('wabaId') == waba_id:
                    waba_aws_id = account.get('id')
                    break
        except ClientError as e:
            logger.warning(f"Failed to list WABA accounts: {e}")
        
        if not waba_aws_id:
            logger.warning(f"Could not find AWS WABA ID for Meta WABA {waba_id}")
            return {"updated": False, "reason": "WABA not found"}
        
        # Get detailed account info with phone quality
        detail = social().get_linked_whatsapp_business_account(id=waba_aws_id)
        account_detail = detail.get('account', {})
        phone_numbers = account_detail.get('phoneNumbers', [])
        
        # Find our phone number and extract all available info
        phone_info = None
        for phone in phone_numbers:
            # Match by phone number ID suffix
            if phone_number_id in phone.get('phoneNumberId', ''):
                phone_info = phone
                break
        
        if not phone_info:
            logger.warning(f"Phone {phone_number_id} not found in WABA {waba_id}")
            return {"updated": False, "reason": "Phone not found"}
        
        # Extract all phone info
        quality_rating = phone_info.get('qualityRating', 'UNKNOWN')
        display_name = phone_info.get('displayPhoneNumberName', '')
        display_phone = phone_info.get('displayPhoneNumber', '')
        meta_phone_id = phone_info.get('metaPhoneNumberId', '')
        phone_arn = phone_info.get('arn', '')
        
        # Throughput info
        # Note: Actual MPS is not exposed via API - default is 80, max is 1000
        # We track eligibility based on quality rating
        # To get actual throughput, check Meta Business Manager or contact Meta support
        throughput_default_mps = 80
        throughput_max_mps = 1000
        throughput_eligible_for_increase = quality_rating in ('GREEN', 'YELLOW')
        
        # Throughput status based on quality
        if quality_rating == 'GREEN':
            throughput_status = "ELIGIBLE_FOR_INCREASE"
            throughput_note = "Quality is GREEN. Contact Meta to request 1,000 MPS if you have unlimited conversations tier."
        elif quality_rating == 'YELLOW':
            throughput_status = "ELIGIBLE_FOR_INCREASE"
            throughput_note = "Quality is YELLOW. Eligible for increase but improve quality to GREEN for best results."
        else:
            throughput_status = "NOT_ELIGIBLE"
            throughput_note = "Quality must be GREEN or YELLOW to request throughput increase."
        
        logger.info(f"Quality rating for {phone_number}: {quality_rating}, Throughput status: {throughput_status}")
        
        # Build quality/throughput history entry
        history_entry = {
            "rating": quality_rating,
            "throughputStatus": throughput_status,
            "checkedAt": now,
        }
        
        # Update or create quality record in DynamoDB
        # Limit history to 10 entries to avoid item size issues (DynamoDB 400KB limit)
        MAX_HISTORY_ENTRIES = 10
        existing_history = []
        try:
            existing = table().get_item(Key={str(MESSAGES_PK_NAME): quality_pk})
            if existing.get("Item"):
                existing_history = existing["Item"].get("qualityHistory", []) or []
        except ClientError:
            pass
        
        # Append new entry and trim to max size
        existing_history.append(history_entry)
        if len(existing_history) > MAX_HISTORY_ENTRIES:
            existing_history = existing_history[-MAX_HISTORY_ENTRIES:]
        
        try:
            table().update_item(
                Key={str(MESSAGES_PK_NAME): quality_pk},
                UpdateExpression=(
                    "SET itemType = :it, "
                    "    wabaId = :waba, "
                    "    wabaAwsId = :wabaAwsId, "
                    "    phoneNumberId = :pnid, "
                    "    phoneNumber = :pn, "
                    "    displayName = :dn, "
                    "    displayPhoneNumber = :dpn, "
                    "    metaPhoneNumberId = :mpnid, "
                    "    phoneArn = :parn, "
                    "    businessName = :bn, "
                    "    qualityRating = :qr, "
                    "    throughputDefaultMps = :tdmps, "
                    "    throughputMaxMps = :tmmps, "
                    "    throughputStatus = :tstatus, "
                    "    throughputNote = :tnote, "
                    "    throughputEligibleForIncrease = :telig, "
                    "    lastCheckedAt = :now, "
                    "    qualityHistory = :history"
                ),
                ExpressionAttributeValues={
                    ":it": "PHONE_QUALITY",
                    ":waba": waba_id,
                    ":wabaAwsId": waba_aws_id,
                    ":pnid": phone_number_id,
                    ":pn": phone_number,
                    ":dn": display_name or business_name,
                    ":dpn": display_phone,
                    ":mpnid": meta_phone_id,
                    ":parn": phone_arn,
                    ":bn": business_name,
                    ":qr": quality_rating,
                    ":tdmps": throughput_default_mps,
                    ":tmmps": throughput_max_mps,
                    ":tstatus": throughput_status,
                    ":tnote": throughput_note,
                    ":telig": throughput_eligible_for_increase,
                    ":now": now,
                    ":history": existing_history,
                },
            )
        except ClientError as e:
            logger.exception(f"Failed to update quality in DynamoDB: {e}")
            return {"updated": False, "error": str(e)}
        
        return {
            "updated": True, 
            "qualityRating": quality_rating,
            "throughputStatus": throughput_status,
            "throughputEligibleForIncrease": throughput_eligible_for_increase,
            "phoneNumber": phone_number,
            "businessName": business_name,
        }
        
    except ClientError as e:
        logger.exception(f"Failed to get quality rating: {e}")
        return {"updated": False, "error": str(e)}


def update_infrastructure_config() -> Dict[str, Any]:
    """Track VPC endpoint and service-linked role configuration for AWS Social Messaging.
    
    VPC Interface Endpoint (AWS PrivateLink):
    - Service: com.amazonaws.{region}.social-messaging
    - Enables private connection without internet gateway
    - Lower latency, enhanced security
    
    Service-Linked Role:
    - Role: AWSServiceRoleForSocialMessaging
    - Automatically created when linking WABA
    - Used by AWS to manage WhatsApp resources
    """
    now = iso_now()
    config_pk = "CONFIG#INFRASTRUCTURE"
    region = os.environ.get("AWS_REGION", "ap-south-1")
    service_name = f"com.amazonaws.{region}.social-messaging"
    
    vpc_endpoints = []
    service_linked_role = None
    
    # Check VPC endpoints for social-messaging
    try:
        response = ec2().describe_vpc_endpoints(
            Filters=[{"Name": "service-name", "Values": [service_name]}]
        )
        for ep in response.get("VpcEndpoints", []):
            vpc_endpoints.append({
                "vpcEndpointId": ep.get("VpcEndpointId", ""),
                "vpcId": ep.get("VpcId", ""),
                "state": ep.get("State", ""),
                "serviceName": ep.get("ServiceName", ""),
                "vpcEndpointType": ep.get("VpcEndpointType", ""),
                "privateDnsEnabled": ep.get("PrivateDnsEnabled", False),
                "subnetIds": ep.get("SubnetIds", []),
                "securityGroupIds": [sg.get("GroupId") for sg in ep.get("Groups", [])],
                "creationTimestamp": str(ep.get("CreationTimestamp", "")),
            })
        logger.info(f"Found {len(vpc_endpoints)} VPC endpoint(s) for {service_name}")
    except ClientError as e:
        logger.warning(f"Failed to describe VPC endpoints: {e}")
    
    # Check service-linked role
    try:
        response = iam().get_role(RoleName="AWSServiceRoleForSocialMessaging")
        role = response.get("Role", {})
        service_linked_role = {
            "roleName": role.get("RoleName", ""),
            "roleArn": role.get("Arn", ""),
            "createDate": str(role.get("CreateDate", "")),
            "description": role.get("Description", ""),
            "path": role.get("Path", ""),
        }
        logger.info(f"Service-linked role found: {service_linked_role['roleName']}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchEntity":
            logger.info("Service-linked role not found (will be created when WABA is linked)")
        else:
            logger.warning(f"Failed to get service-linked role: {e}")
    
    # Update DynamoDB with infrastructure config
    try:
        item = {
            str(MESSAGES_PK_NAME): config_pk,
            "itemType": "INFRASTRUCTURE_CONFIG",
            "region": region,
            "lastCheckedAt": now,
            # VPC Endpoint info
            "vpcEndpointServiceName": service_name,
            "vpcEndpointCount": len(vpc_endpoints),
            "vpcEndpoints": vpc_endpoints,
            "vpcEndpointConfigured": len(vpc_endpoints) > 0,
            # Service-linked role info
            "serviceLinkedRoleName": "AWSServiceRoleForSocialMessaging",
            "serviceLinkedRoleConfigured": service_linked_role is not None,
            "serviceLinkedRole": service_linked_role,
            # Recommendations
            "recommendations": [],
        }
        
        # Add recommendations
        if not vpc_endpoints:
            item["recommendations"].append({
                "type": "VPC_ENDPOINT",
                "priority": "MEDIUM",
                "message": f"Consider creating VPC endpoint for {service_name} for private connectivity and lower latency",
                "command": f"aws ec2 create-vpc-endpoint --vpc-id <VPC_ID> --service-name {service_name} --vpc-endpoint-type Interface --subnet-ids <SUBNET_IDS> --security-group-ids <SG_ID> --private-dns-enabled --region {region}",
            })
        
        table().put_item(Item=item)
        
        return {
            "updated": True,
            "vpcEndpointCount": len(vpc_endpoints),
            "serviceLinkedRoleConfigured": service_linked_role is not None,
        }
        
    except ClientError as e:
        logger.exception(f"Failed to update infrastructure config: {e}")
        return {"updated": False, "error": str(e)}


def update_media_types_config() -> Dict[str, Any]:
    """Store supported media types configuration in DynamoDB.
    
    WhatsApp supported media types from AWS/Meta documentation:
    - Audio: AAC, AMR, MP3, M4A, OGG (max 16 MB)
    - Document: TXT, PDF, XLS, XLSX, DOC, DOCX, PPT, PPTX (max 100 MB)
    - Image: JPEG, PNG (max 5 MB, 8-bit RGB/RGBA)
    - Sticker: WebP (animated max 500 KB, static max 100 KB)
    - Video: 3GP, MP4 (max 16 MB, H.264 + AAC codec)
    """
    now = iso_now()
    config_pk = "CONFIG#MEDIA_TYPES"
    
    try:
        # Build summary stats
        total_formats = sum(len(cat.get("formats", [])) for cat in SUPPORTED_MEDIA_TYPES.values())
        all_mime_types = get_supported_mime_types()
        
        item = {
            str(MESSAGES_PK_NAME): config_pk,
            "itemType": "MEDIA_TYPES_CONFIG",
            "lastUpdatedAt": now,
            "totalFormats": total_formats,
            "totalMimeTypes": len(all_mime_types),
            "supportedMimeTypes": all_mime_types,
            "mediaTypes": SUPPORTED_MEDIA_TYPES,
            # Size limits summary
            "sizeLimits": {
                "audio": {"maxMB": 16},
                "document": {"maxMB": 100},
                "image": {"maxMB": 5},
                "sticker": {"maxKB": 500},
                "video": {"maxMB": 16},
            },
            # Quick reference
            "quickReference": {
                "audio": ["audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"],
                "document": ["text/plain", "application/pdf", "application/msword", 
                            "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation"],
                "image": ["image/jpeg", "image/png"],
                "sticker": ["image/webp"],
                "video": ["video/mp4", "video/3gpp"],
            },
            # Notes
            "notes": {
                "image": "Images must be 8-bit, RGB or RGBA",
                "sticker": "WebP images can only be sent in sticker messages",
                "video": "H.264 video codec and AAC audio codec only. Use H.264 Main or Baseline profile for Android compatibility.",
                "audio_ogg": "OPUS codecs only; mono input only",
            },
        }
        
        table().put_item(Item=item)
        logger.info(f"Updated media types config: {total_formats} formats, {len(all_mime_types)} MIME types")
        
        return {
            "updated": True,
            "totalFormats": total_formats,
            "totalMimeTypes": len(all_mime_types),
        }
        
    except ClientError as e:
        logger.exception(f"Failed to update media types config: {e}")
        return {"updated": False, "error": str(e)}


def update_message_templates(waba_aws_id: str, waba_meta_id: str, 
                              business_name: str) -> Dict[str, Any]:
    """Fetch and store WhatsApp message templates for a WABA.
    
    Template Status:
    - APPROVED: Template is approved and can be used
    - PENDING: Template is pending review
    - REJECTED: Template was rejected (check rejection reason)
    - PAUSED: Template is paused due to quality issues
    - DISABLED: Template is disabled
    
    Template Categories:
    - MARKETING: Promotional messages
    - UTILITY: Transactional messages (order updates, etc.)
    - AUTHENTICATION: OTP/verification messages
    
    Template Quality Score:
    - GREEN: High quality
    - YELLOW: Medium quality
    - RED: Low quality
    - UNKNOWN: Not enough data
    
    Pacing:
    - Templates may be subject to pacing limits based on quality
    - Low quality templates may have reduced sending capacity
    """
    now = iso_now()
    templates_pk = f"TEMPLATES#{waba_aws_id}"
    
    try:
        # Fetch templates from AWS Social Messaging API
        templates = []
        template_stats = {
            "total": 0,
            "approved": 0,
            "pending": 0,
            "rejected": 0,
            "paused": 0,
            "disabled": 0,
            "byCategory": {"MARKETING": 0, "UTILITY": 0, "AUTHENTICATION": 0, "OTHER": 0},
            "byQuality": {"GREEN": 0, "YELLOW": 0, "RED": 0, "UNKNOWN": 0},
            "byLanguage": {},
        }
        
        try:
            response = social().list_whatsapp_message_templates(id=waba_aws_id)
            raw_templates = response.get("templates", [])
            
            for t in raw_templates:
                template = {
                    "templateName": t.get("templateName", ""),
                    "metaTemplateId": t.get("metaTemplateId", ""),
                    "templateStatus": t.get("templateStatus", "UNKNOWN"),
                    "templateQualityScore": t.get("templateQualityScore", "UNKNOWN"),
                    "templateLanguage": t.get("templateLanguage", ""),
                    "templateCategory": t.get("templateCategory", "OTHER"),
                }
                templates.append(template)
                
                # Update stats
                template_stats["total"] += 1
                status = template["templateStatus"].upper()
                if status == "APPROVED":
                    template_stats["approved"] += 1
                elif status == "PENDING":
                    template_stats["pending"] += 1
                elif status == "REJECTED":
                    template_stats["rejected"] += 1
                elif status == "PAUSED":
                    template_stats["paused"] += 1
                elif status == "DISABLED":
                    template_stats["disabled"] += 1
                
                # Category stats
                category = template["templateCategory"].upper()
                if category in template_stats["byCategory"]:
                    template_stats["byCategory"][category] += 1
                else:
                    template_stats["byCategory"]["OTHER"] += 1
                
                # Quality stats
                quality = template["templateQualityScore"].upper()
                if quality in template_stats["byQuality"]:
                    template_stats["byQuality"][quality] += 1
                
                # Language stats
                lang = template["templateLanguage"]
                template_stats["byLanguage"][lang] = template_stats["byLanguage"].get(lang, 0) + 1
            
            logger.info(f"Found {len(templates)} templates for WABA {waba_aws_id}")
            
        except ClientError as e:
            logger.warning(f"Failed to list templates for WABA {waba_aws_id}: {e}")
            return {"updated": False, "error": str(e)}
        
        # Store in DynamoDB
        item = {
            str(MESSAGES_PK_NAME): templates_pk,
            "itemType": "MESSAGE_TEMPLATES",
            "wabaAwsId": waba_aws_id,
            "wabaMetaId": waba_meta_id,
            "businessName": business_name,
            "lastUpdatedAt": now,
            "templateCount": len(templates),
            "templates": templates,
            "stats": template_stats,
            # Template status reference
            "statusReference": {
                "APPROVED": "Template is approved and can be used for sending messages",
                "PENDING": "Template is pending Meta review (usually 24-48 hours)",
                "REJECTED": "Template was rejected - check rejection reason and resubmit",
                "PAUSED": "Template is paused due to quality issues - improve quality to resume",
                "DISABLED": "Template is disabled and cannot be used",
            },
            # Category reference
            "categoryReference": {
                "MARKETING": "Promotional messages, offers, announcements",
                "UTILITY": "Transactional messages - order updates, shipping, appointments",
                "AUTHENTICATION": "OTP, verification codes, login confirmations",
            },
            # Pacing info
            "pacingInfo": {
                "description": "Templates may be subject to pacing limits based on quality",
                "lowQualityImpact": "Low quality templates may have reduced sending capacity",
                "recommendation": "Maintain GREEN quality score for maximum throughput",
            },
        }
        
        table().put_item(Item=item)
        
        return {
            "updated": True,
            "templateCount": len(templates),
            "stats": template_stats,
        }
        
    except ClientError as e:
        logger.exception(f"Failed to update templates: {e}")
        return {"updated": False, "error": str(e)}


# ---------- Template Admin Functions ----------
def get_waba_aws_id(meta_waba_id: str) -> Optional[str]:
    """Get AWS WABA ID from Meta WABA ID."""
    try:
        response = social().list_linked_whatsapp_business_accounts()
        for acc in response.get('linkedAccounts', []):
            if acc.get('wabaId') == meta_waba_id:
                return acc.get('id')
    except ClientError:
        pass
    return None


def handle_template_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle template admin actions (list, create, delete, get).
    
    Test Event Examples:
    
    1. List templates:
    {
        "action": "templates",
        "op": "list",
        "metaWabaId": "1347766229904230"
    }
    
    2. Create template:
    {
        "action": "templates",
        "op": "create",
        "metaWabaId": "1347766229904230",
        "templateDefinition": {
            "name": "order_update",
            "language": "en_US",
            "category": "UTILITY",
            "components": [
                {"type": "BODY", "text": "Your order {{1}} has been shipped!"}
            ]
        }
    }
    
    3. Delete template:
    {
        "action": "templates",
        "op": "delete",
        "metaWabaId": "1347766229904230",
        "templateName": "order_update"
    }
    
    4. Get template status:
    {
        "action": "templates",
        "op": "get",
        "metaWabaId": "1347766229904230",
        "templateName": "order_update"
    }
    
    5. Create template with header media:
    {
        "action": "templates",
        "op": "create_with_media",
        "metaWabaId": "1347766229904230",
        "s3Key": "WhatsApp/templates/header.jpg",
        "templateDefinition": {
            "name": "promo_with_image",
            "language": "en_US",
            "category": "MARKETING",
            "components": [
                {"type": "HEADER", "format": "IMAGE"},
                {"type": "BODY", "text": "Check out our new {{1}}!"}
            ]
        }
    }
    """
    op = event.get("op", "list")
    meta_waba_id = event.get("metaWabaId", "")
    
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    waba_aws_id = get_waba_aws_id(meta_waba_id)
    if not waba_aws_id:
        return {"statusCode": 404, "error": f"WABA not found for Meta ID: {meta_waba_id}"}
    
    logger.info(f"Template action: op={op}, metaWabaId={meta_waba_id}, wabaAwsId={waba_aws_id}")
    
    if op == "list":
        return list_templates(waba_aws_id, meta_waba_id)
    elif op == "create":
        template_def = event.get("templateDefinition", {})
        return create_template(waba_aws_id, meta_waba_id, template_def)
    elif op == "create_with_media":
        template_def = event.get("templateDefinition", {})
        s3_key = event.get("s3Key", "")
        return create_template_with_media(waba_aws_id, meta_waba_id, template_def, s3_key)
    elif op == "delete":
        template_name = event.get("templateName", "")
        return delete_template(waba_aws_id, meta_waba_id, template_name)
    elif op == "get":
        template_name = event.get("templateName", "")
        return get_template_status(waba_aws_id, meta_waba_id, template_name)
    else:
        return {"statusCode": 400, "error": f"Unknown operation: {op}"}


def list_templates(waba_aws_id: str, meta_waba_id: str) -> Dict[str, Any]:
    """List all templates for a WABA."""
    try:
        response = social().list_whatsapp_message_templates(id=waba_aws_id)
        templates = response.get("templates", [])
        
        # Store in DynamoDB
        now = iso_now()
        templates_pk = f"TEMPLATES#{waba_aws_id}"
        
        template_list = []
        stats = {"total": 0, "approved": 0, "pending": 0, "rejected": 0, "paused": 0}
        
        for t in templates:
            template = {
                "templateName": t.get("templateName", ""),
                "metaTemplateId": t.get("metaTemplateId", ""),
                "templateStatus": t.get("templateStatus", "UNKNOWN"),
                "templateQualityScore": t.get("templateQualityScore", "UNKNOWN"),
                "templateLanguage": t.get("templateLanguage", ""),
                "templateCategory": t.get("templateCategory", "OTHER"),
            }
            template_list.append(template)
            stats["total"] += 1
            status = template["templateStatus"].upper()
            if status in stats:
                stats[status] += 1
        
        # Update DynamoDB
        table().put_item(Item={
            str(MESSAGES_PK_NAME): templates_pk,
            "itemType": "MESSAGE_TEMPLATES",
            "wabaAwsId": waba_aws_id,
            "wabaMetaId": meta_waba_id,
            "lastUpdatedAt": now,
            "templateCount": len(template_list),
            "templates": template_list,
            "stats": stats,
        })
        
        return {
            "statusCode": 200,
            "operation": "list",
            "wabaAwsId": waba_aws_id,
            "wabaMetaId": meta_waba_id,
            "templateCount": len(template_list),
            "templates": template_list,
            "stats": stats,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def create_template(waba_aws_id: str, meta_waba_id: str, template_def: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new message template.
    
    Template Definition Example:
    {
        "name": "order_update",
        "language": "en_US",
        "category": "UTILITY",
        "components": [
            {"type": "BODY", "text": "Your order {{1}} has been shipped! Track: {{2}}"}
        ]
    }
    
    Categories: MARKETING, UTILITY, AUTHENTICATION
    
    Common Rejection Reasons:
    - Bad/mismatched variables {{1}}
    - Special characters in variables
    - Policy violations
    - Missing required components
    """
    if not template_def:
        return {"statusCode": 400, "error": "templateDefinition is required"}
    
    template_name = template_def.get("name", "")
    if not template_name:
        return {"statusCode": 400, "error": "template name is required"}
    
    try:
        # Convert template definition to bytes
        template_bytes = json.dumps(template_def).encode("utf-8")
        
        response = social().create_whatsapp_message_template(
            id=waba_aws_id,
            templateDefinition=template_bytes,
        )
        
        # Store template creation in DynamoDB
        now = iso_now()
        template_pk = f"TEMPLATE#{waba_aws_id}#{template_name}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): template_pk,
            "itemType": "TEMPLATE_CREATED",
            "wabaAwsId": waba_aws_id,
            "wabaMetaId": meta_waba_id,
            "templateName": template_name,
            "templateDefinition": template_def,
            "createdAt": now,
            "status": "PENDING",
            "note": "Template submitted for Meta review. Usually takes 24-48 hours.",
        })
        
        return {
            "statusCode": 200,
            "operation": "create",
            "templateName": template_name,
            "status": "PENDING",
            "message": "Template created and submitted for Meta review",
            "response": response,
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {
            "statusCode": 500, 
            "error": error_msg,
            "errorCode": error_code,
            "rejectionHelp": {
                "commonReasons": [
                    "Bad/mismatched variables {{1}}",
                    "Special characters in variables",
                    "Policy violations",
                    "Missing required components",
                ],
                "tips": [
                    "Use sequential variables: {{1}}, {{2}}, {{3}}",
                    "Avoid special characters in variable placeholders",
                    "Ensure category matches content type",
                    "Check Meta's template guidelines",
                ],
            },
        }


def create_template_with_media(waba_aws_id: str, meta_waba_id: str, 
                                template_def: Dict[str, Any], s3_key: str) -> Dict[str, Any]:
    """Create a template with header media (image/video).
    
    Steps:
    1. Upload media from S3 to WhatsApp using CreateWhatsAppMessageTemplateMedia
    2. Get metaHeaderHandle from response
    3. Create template with header handle
    
    Note: S3 bucket must be in same account and region as WABA.
    """
    if not s3_key:
        return {"statusCode": 400, "error": "s3Key is required for media templates"}
    
    template_name = template_def.get("name", "")
    if not template_name:
        return {"statusCode": 400, "error": "template name is required"}
    
    try:
        # Step 1: Upload media to get header handle
        media_response = social().create_whatsapp_message_template_media(
            originationPhoneNumberId=origination_id_for_api(
                WABA_PHONE_MAP.get(meta_waba_id, {}).get("phoneArn", "")
            ),
            sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        
        header_handle = media_response.get("metaHeaderHandle", "")
        if not header_handle:
            return {"statusCode": 500, "error": "Failed to get header handle from media upload"}
        
        # Step 2: Add header handle to template definition
        components = template_def.get("components", [])
        for comp in components:
            if comp.get("type") == "HEADER":
                comp["example"] = {"header_handle": [header_handle]}
        
        # Step 3: Create template
        template_bytes = json.dumps(template_def).encode("utf-8")
        
        response = social().create_whatsapp_message_template(
            id=waba_aws_id,
            templateDefinition=template_bytes,
        )
        
        # Store in DynamoDB
        now = iso_now()
        template_pk = f"TEMPLATE#{waba_aws_id}#{template_name}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): template_pk,
            "itemType": "TEMPLATE_CREATED",
            "wabaAwsId": waba_aws_id,
            "wabaMetaId": meta_waba_id,
            "templateName": template_name,
            "templateDefinition": template_def,
            "headerHandle": header_handle,
            "s3Key": s3_key,
            "createdAt": now,
            "status": "PENDING",
            "hasMedia": True,
        })
        
        return {
            "statusCode": 200,
            "operation": "create_with_media",
            "templateName": template_name,
            "headerHandle": header_handle,
            "status": "PENDING",
            "message": "Template with media created and submitted for Meta review",
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def delete_template(waba_aws_id: str, meta_waba_id: str, template_name: str) -> Dict[str, Any]:
    """Delete a message template."""
    if not template_name:
        return {"statusCode": 400, "error": "templateName is required"}
    
    try:
        response = social().delete_whatsapp_message_template(
            id=waba_aws_id,
            templateName=template_name,
        )
        
        # Update DynamoDB
        now = iso_now()
        template_pk = f"TEMPLATE#{waba_aws_id}#{template_name}"
        
        try:
            table().update_item(
                Key={str(MESSAGES_PK_NAME): template_pk},
                UpdateExpression="SET #s = :s, deletedAt = :d",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "DELETED", ":d": now},
            )
        except ClientError:
            pass
        
        return {
            "statusCode": 200,
            "operation": "delete",
            "templateName": template_name,
            "message": "Template deleted successfully",
            "response": response,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def get_template_status(waba_aws_id: str, meta_waba_id: str, template_name: str) -> Dict[str, Any]:
    """Get status of a specific template."""
    if not template_name:
        return {"statusCode": 400, "error": "templateName is required"}
    
    try:
        response = social().list_whatsapp_message_templates(id=waba_aws_id)
        templates = response.get("templates", [])
        
        for t in templates:
            if t.get("templateName") == template_name:
                return {
                    "statusCode": 200,
                    "operation": "get",
                    "template": {
                        "templateName": t.get("templateName", ""),
                        "metaTemplateId": t.get("metaTemplateId", ""),
                        "templateStatus": t.get("templateStatus", "UNKNOWN"),
                        "templateQualityScore": t.get("templateQualityScore", "UNKNOWN"),
                        "templateLanguage": t.get("templateLanguage", ""),
                        "templateCategory": t.get("templateCategory", ""),
                    },
                    "statusInfo": {
                        "APPROVED": "Template is approved and can be used",
                        "PENDING": "Template is pending Meta review (24-48 hours)",
                        "REJECTED": "Template was rejected - check WhatsApp Manager for reason",
                        "PAUSED": "Template is paused due to quality issues",
                        "DISABLED": "Template is disabled",
                    },
                }
        
        return {"statusCode": 404, "error": f"Template not found: {template_name}"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a template message with support for dynamic URLs and media headers.
    
    WhatsApp templates support dynamic content through components:
    - Header: Text with variables, or media (image/video/document)
    - Body: Text with {{1}}, {{2}}, etc. placeholders
    - Buttons: Dynamic URL suffix, quick reply payload, or coupon code
    
    Test Event - Simple text template:
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "hello_world",
        "languageCode": "en_US"
    }
    
    Test Event - Template with body parameters:
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "order_update",
        "languageCode": "en_US",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "John"},
                    {"type": "text", "text": "ORD-12345"}
                ]
            }
        ]
    }
    
    Test Event - Template with DYNAMIC URL button:
    (Template has button URL: https://example.com/track/{{1}})
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "order_tracking",
        "languageCode": "en_US",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "ORD-12345"}
                ]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [
                    {"type": "text", "text": "ORD-12345"}
                ]
            }
        ]
    }
    
    Test Event - Template with image header:
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "promo_image",
        "languageCode": "en_US",
        "components": [
            {
                "type": "header",
                "parameters": [
                    {"type": "image", "image": {"id": "123456789"}}
                ]
            },
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Summer Sale"},
                    {"type": "text", "text": "50%"}
                ]
            }
        ]
    }
    
    Test Event - Using helper (simplified format):
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "order_tracking",
        "languageCode": "en_US",
        "bodyParams": ["John", "ORD-12345"],
        "buttons": [{"index": 0, "type": "url", "url_suffix": "ORD-12345"}]
    }
    
    Test Event - Template with coupon code button:
    {
        "action": "send_template",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "templateName": "discount_offer",
        "languageCode": "en_US",
        "components": [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": "20%"}]
            },
            {
                "type": "button",
                "sub_type": "copy_code",
                "index": "0",
                "parameters": [{"type": "coupon_code", "coupon_code": "SAVE20"}]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    components = event.get("components", [])
    
    # Support simplified format with bodyParams and buttons
    body_params = event.get("bodyParams", [])
    buttons = event.get("buttons", [])
    header_type = event.get("headerType")
    header_text = event.get("headerText")
    header_media_id = event.get("headerMediaId")
    header_media_link = event.get("headerMediaLink")
    header_document_filename = event.get("headerDocumentFilename")
    
    if not meta_waba_id or not to_number or not template_name:
        return {"statusCode": 400, "error": "metaWabaId, to, and templateName are required"}
    
    # Get phone ARN from WABA map
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build components from simplified format if not provided directly
        if not components and (body_params or buttons or header_type):
            components = build_template_components(
                body_params=body_params,
                header_type=header_type,
                header_text=header_text,
                header_media_id=header_media_id,
                header_media_link=header_media_link,
                header_document_filename=header_document_filename,
                buttons=buttons,
            )
        
        # Build template message payload
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        
        if components:
            payload["template"]["components"] = components
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#TEMPLATE#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "TEMPLATE_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "templateName": template_name,
            "languageCode": language_code,
            "sentAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_template",
            "messageId": msg_id,
            "to": to_number,
            "templateName": template_name,
            "message": "Template message sent successfully",
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_text(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a text message.
    
    Test Event:
    {
        "action": "send_text",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "text": "Hello from Lambda!"
    }
    """
    logger.info("=== HANDLE_SEND_TEXT CALLED ===")
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    text = event.get("text", "")
    
    logger.info(f"handle_send_text: metaWabaId={meta_waba_id}, to={to_number}")
    
    if not meta_waba_id or not to_number or not text:
        return {"statusCode": 400, "error": "metaWabaId, to, and text are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    logger.info(f"handle_send_text: waba_config={waba_config}, phone_arn={phone_arn}")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        formatted_to = format_wa_number(to_number)
        origination_id = origination_id_for_api(phone_arn)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_to,
            "type": "text",
            "text": {"body": text},
        }
        
        logger.info(f"send_text: origination_id={origination_id}, to={formatted_to}, payload={json.dumps(payload)}")
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id,
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "text",
            "textBody": text,
            "preview": text[:200],
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_text",
            "messageId": msg_id,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a media message (image, video, audio, document).
    
    Test Event (with S3 key - will upload to WhatsApp first):
    {
        "action": "send_media",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "mediaType": "image",
        "s3Key": "WhatsApp/test/image.jpg",
        "caption": "Check this out!"
    }
    
    Test Event (with existing WhatsApp media ID):
    {
        "action": "send_media",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "mediaType": "image",
        "mediaId": "123456789",
        "caption": "Check this out!"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    media_type = event.get("mediaType", "image")
    s3_key = event.get("s3Key", "")
    media_id = event.get("mediaId", "")
    caption = event.get("caption", "")
    filename = event.get("filename", "")
    
    if not meta_waba_id or not to_number:
        return {"statusCode": 400, "error": "metaWabaId and to are required"}
    
    if not s3_key and not media_id:
        return {"statusCode": 400, "error": "Either s3Key or mediaId is required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Upload to WhatsApp if s3Key provided
        if s3_key and not media_id:
            upload_resp = social().post_whatsapp_message_media(
                originationPhoneNumberId=origination_id_for_api(phone_arn),
                sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
            )
            media_id = upload_resp.get("mediaId", "")
            if not media_id:
                return {"statusCode": 500, "error": "Failed to upload media to WhatsApp"}
        
        # Build message payload
        to_formatted = format_wa_number(to_number)
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_formatted,
            "type": media_type,
            media_type: {"id": media_id},
        }
        
        if caption and media_type in {"image", "video", "document"}:
            payload[media_type]["caption"] = caption
        if filename and media_type == "document":
            payload[media_type]["filename"] = filename
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": media_type,
            "mediaId": media_id,
            "s3Key": s3_key,
            "caption": caption,
            "preview": f"[{media_type}] {caption}" if caption else f"[{media_type}]",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_media",
            "messageId": msg_id,
            "mediaId": media_id,
            "mediaType": media_type,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_reaction(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a reaction to a message.
    
    Test Event:
    {
        "action": "send_reaction",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "messageId": "wamid.xxx",
        "emoji": "👍"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    wa_msg_id = event.get("messageId", "")
    emoji = event.get("emoji", "👍")
    
    if not meta_waba_id or not to_number or not wa_msg_id:
        return {"statusCode": 400, "error": "metaWabaId, to, and messageId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": format_wa_number(to_number),
            "type": "reaction",
            "reaction": {
                "message_id": wa_msg_id,
                "emoji": emoji,
            },
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        return {
            "statusCode": 200,
            "operation": "send_reaction",
            "messageId": response.get("messageId"),
            "emoji": emoji,
            "reactedTo": wa_msg_id,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_location(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a location message.
    
    Test Event:
    {
        "action": "send_location",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "name": "New Delhi",
        "address": "New Delhi, India"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    latitude = event.get("latitude")
    longitude = event.get("longitude")
    name = event.get("name", "")
    address = event.get("address", "")
    
    if not meta_waba_id or not to_number or latitude is None or longitude is None:
        return {"statusCode": 400, "error": "metaWabaId, to, latitude, and longitude are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "location",
            "location": {
                "latitude": str(latitude),
                "longitude": str(longitude),
            },
        }
        if name:
            payload["location"]["name"] = name
        if address:
            payload["location"]["address"] = address
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "location",
            "latitude": str(latitude),
            "longitude": str(longitude),
            "locationName": name,
            "locationAddress": address,
            "preview": f"[location] {name or address or f'{latitude},{longitude}'}",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_location",
            "messageId": msg_id,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_contact(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a contact card.
    
    Test Event:
    {
        "action": "send_contact",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "contacts": [{
            "name": {"formatted_name": "John Doe", "first_name": "John", "last_name": "Doe"},
            "phones": [{"phone": "+1234567890", "type": "MOBILE"}],
            "emails": [{"email": "john@example.com", "type": "WORK"}]
        }]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    contacts = event.get("contacts", [])
    
    if not meta_waba_id or not to_number or not contacts:
        return {"statusCode": 400, "error": "metaWabaId, to, and contacts are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "contacts",
            "contacts": contacts,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        contact_names = [c.get("name", {}).get("formatted_name", "Unknown") for c in contacts]
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "contacts",
            "contacts": contacts,
            "preview": f"[contacts] {', '.join(contact_names)}",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_contact",
            "messageId": msg_id,
            "to": to_number,
            "contactCount": len(contacts),
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_interactive(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an interactive message (buttons or list).
    
    Test Event (Button):
    {
        "action": "send_interactive",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "interactiveType": "button",
        "body": "Please choose an option:",
        "buttons": [
            {"id": "btn1", "title": "Option 1"},
            {"id": "btn2", "title": "Option 2"}
        ]
    }
    
    Test Event (List):
    {
        "action": "send_interactive",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "interactiveType": "list",
        "body": "Please select from the menu:",
        "buttonText": "View Options",
        "sections": [{
            "title": "Section 1",
            "rows": [
                {"id": "row1", "title": "Item 1", "description": "Description 1"},
                {"id": "row2", "title": "Item 2", "description": "Description 2"}
            ]
        }]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    interactive_type = event.get("interactiveType", "button")
    body = event.get("body", "")
    header = event.get("header", "")
    footer = event.get("footer", "")
    
    if not meta_waba_id or not to_number or not body:
        return {"statusCode": 400, "error": "metaWabaId, to, and body are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        interactive: Dict[str, Any] = {
            "type": interactive_type,
            "body": {"text": body},
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        
        if interactive_type == "button":
            buttons = event.get("buttons", [])
            if not buttons:
                return {"statusCode": 400, "error": "buttons are required for button type"}
            interactive["action"] = {
                "buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons[:3]]
            }
        elif interactive_type == "list":
            sections = event.get("sections", [])
            button_text = event.get("buttonText", "Menu")
            if not sections:
                return {"statusCode": 400, "error": "sections are required for list type"}
            interactive["action"] = {
                "button": button_text,
                "sections": sections,
            }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "interactive",
            "interactiveType": interactive_type,
            "interactiveBody": body,
            "preview": f"[interactive:{interactive_type}] {body[:100]}",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_interactive",
            "messageId": msg_id,
            "interactiveType": interactive_type,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_cta_url(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a Call-To-Action URL button message.
    
    CTA URL buttons allow you to map any URL to a button without including
    the raw URL in the message body. This is different from template buttons.
    
    Test Event:
    {
        "action": "send_cta_url",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "body": "Check out our latest products!",
        "buttonText": "Shop Now",
        "url": "https://example.com/shop",
        "header": "🛍️ New Arrivals",
        "footer": "Limited time offer"
    }
    
    Test Event (with image header):
    {
        "action": "send_cta_url",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "body": "Summer collection is here!",
        "buttonText": "View Collection",
        "url": "https://example.com/summer",
        "headerType": "image",
        "headerMediaId": "123456789"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body = event.get("body", "")
    button_text = event.get("buttonText", "")
    url = event.get("url", "")
    header = event.get("header", "")
    header_type = event.get("headerType", "text")
    header_media_id = event.get("headerMediaId", "")
    header_media_link = event.get("headerMediaLink", "")
    footer = event.get("footer", "")
    
    if not meta_waba_id or not to_number or not body or not button_text or not url:
        return {"statusCode": 400, "error": "metaWabaId, to, body, buttonText, and url are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build interactive CTA URL message
        interactive: Dict[str, Any] = {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": url,
                },
            },
        }
        
        # Add header if provided
        if header_type == "text" and header:
            interactive["header"] = {"type": "text", "text": header}
        elif header_type in ("image", "video", "document"):
            header_obj: Dict[str, Any] = {"type": header_type}
            if header_media_id:
                header_obj[header_type] = {"id": header_media_id}
            elif header_media_link:
                header_obj[header_type] = {"link": header_media_link}
            if header_obj.get(header_type):
                interactive["header"] = header_obj
        
        # Add footer if provided
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "interactive",
            "interactiveType": "cta_url",
            "interactiveBody": body,
            "ctaButtonText": button_text,
            "ctaUrl": url,
            "preview": f"[cta_url] {body[:80]}... [{button_text}]",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_cta_url",
            "messageId": msg_id,
            "buttonText": button_text,
            "url": url,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_mark_read(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Manually mark a message as read.
    
    Test Event:
    {
        "action": "mark_read",
        "metaWabaId": "1347766229904230",
        "messageId": "wamid.xxx"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    wa_msg_id = event.get("messageId", "")
    
    if not meta_waba_id or not wa_msg_id:
        return {"statusCode": 400, "error": "metaWabaId and messageId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        payload = {
            "messaging_product": "whatsapp",
            "message_id": wa_msg_id,
            "status": "read",
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Update DynamoDB
        now = iso_now()
        msg_pk = f"MSG#{wa_msg_id}"
        try:
            table().update_item(
                Key={str(MESSAGES_PK_NAME): msg_pk},
                UpdateExpression="SET markedAsRead = :mar, markedAsReadAt = :marat",
                ExpressionAttributeValues={":mar": True, ":marat": now},
            )
        except ClientError:
            pass
        
        return {
            "statusCode": 200,
            "operation": "mark_read",
            "messageId": wa_msg_id,
            "marked": True,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query messages from DynamoDB.
    
    Test Event:
    {
        "action": "get_messages",
        "direction": "INBOUND",
        "limit": 20,
        "fromNumber": "447447840003"
    }
    """
    direction = event.get("direction")
    from_number = event.get("fromNumber")
    to_number = event.get("toNumber")
    limit = event.get("limit", 50)
    
    try:
        # Use GSI if filtering by direction
        if direction:
            response = table().query(
                IndexName="gsi_direction",
                KeyConditionExpression="direction = :d",
                ExpressionAttributeValues={":d": direction},
                ScanIndexForward=False,
                Limit=limit,
            )
        elif from_number:
            response = table().query(
                IndexName="gsi_from",
                KeyConditionExpression="fromPk = :f",
                ExpressionAttributeValues={":f": from_number},
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            # Scan with filter
            scan_kwargs = {"Limit": limit}
            if to_number:
                scan_kwargs["FilterExpression"] = "contains(#to, :to)"
                scan_kwargs["ExpressionAttributeNames"] = {"#to": "to"}
                scan_kwargs["ExpressionAttributeValues"] = {":to": to_number}
            response = table().scan(**scan_kwargs)
        
        items = response.get("Items", [])
        messages = [i for i in items if i.get("itemType") in ("MESSAGE", "MESSAGE_STATUS")]
        
        return {
            "statusCode": 200,
            "operation": "get_messages",
            "count": len(messages),
            "messages": messages,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_conversations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query conversations from DynamoDB.
    
    Test Event:
    {
        "action": "get_conversations",
        "limit": 20
    }
    """
    limit = event.get("limit", 50)
    inbox_pk = event.get("inboxPk")
    
    try:
        if inbox_pk:
            response = table().query(
                IndexName="gsi_inbox",
                KeyConditionExpression="inboxPk = :pk",
                ExpressionAttributeValues={":pk": inbox_pk},
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            response = table().scan(
                FilterExpression="itemType = :t",
                ExpressionAttributeValues={":t": "CONVERSATION"},
                Limit=limit,
            )
        
        items = response.get("Items", [])
        conversations = [i for i in items if i.get("itemType") == "CONVERSATION"]
        
        return {
            "statusCode": 200,
            "operation": "get_conversations",
            "count": len(conversations),
            "conversations": conversations,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_quality(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get phone quality ratings.
    
    Test Event:
    {
        "action": "get_quality"
    }
    """
    try:
        response = table().scan(
            FilterExpression="itemType = :t",
            ExpressionAttributeValues={":t": "PHONE_QUALITY"},
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_quality",
            "count": len(items),
            "qualityRatings": items,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_stats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get message statistics.
    
    Test Event:
    {
        "action": "get_stats"
    }
    """
    try:
        response = table().scan()
        items = response.get("Items", [])
        
        messages = [i for i in items if i.get("itemType") in ("MESSAGE", "MESSAGE_STATUS")]
        conversations = [i for i in items if i.get("itemType") == "CONVERSATION"]
        
        inbound = len([m for m in messages if m.get("direction") == "INBOUND"])
        outbound = len([m for m in messages if m.get("direction") == "OUTBOUND"])
        
        # Type counts
        type_counts = {}
        for m in messages:
            t = m.get("type", m.get("itemType", "unknown"))
            type_counts[t] = type_counts.get(t, 0) + 1
        
        # Status counts
        status_counts = {}
        for m in messages:
            s = m.get("deliveryStatus")
            if s:
                status_counts[s] = status_counts.get(s, 0) + 1
        
        return {
            "statusCode": 200,
            "operation": "get_stats",
            "stats": {
                "totalMessages": len(messages),
                "inbound": inbound,
                "outbound": outbound,
                "conversations": len(conversations),
                "byType": type_counts,
                "byStatus": status_counts,
                "readReceiptsSent": len([m for m in messages if m.get("markedAsRead")]),
                "reactionsSent": len([m for m in messages if m.get("reactedWithEmoji")]),
            },
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_upload_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload media from S3 to WhatsApp (get media ID for later use).
    
    Test Event:
    {
        "action": "upload_media",
        "metaWabaId": "1347766229904230",
        "s3Key": "WhatsApp/test/image.jpg"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    s3_key = event.get("s3Key", "")
    
    if not meta_waba_id or not s3_key:
        return {"statusCode": 400, "error": "metaWabaId and s3Key are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        response = social().post_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        
        return {
            "statusCode": 200,
            "operation": "upload_media",
            "mediaId": response.get("mediaId"),
            "s3Key": s3_key,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_delete_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete uploaded media from WhatsApp.
    
    Test Event:
    {
        "action": "delete_media",
        "metaWabaId": "1347766229904230",
        "mediaId": "123456789"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    media_id = event.get("mediaId", "")
    
    if not meta_waba_id or not media_id:
        return {"statusCode": 400, "error": "metaWabaId and mediaId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        response = social().delete_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            mediaId=media_id,
        )
        
        return {
            "statusCode": 200,
            "operation": "delete_media",
            "mediaId": media_id,
            "deleted": bool(response.get("success")),
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_wabas(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List all linked WhatsApp Business Accounts.
    
    Test Event:
    {
        "action": "get_wabas"
    }
    """
    try:
        response = social().list_linked_whatsapp_business_accounts()
        accounts = response.get("linkedAccounts", [])
        
        result = []
        for acc in accounts:
            waba_aws_id = acc.get("id", "")
            waba_meta_id = acc.get("wabaId", "")
            
            # Get detailed info
            try:
                detail = social().get_linked_whatsapp_business_account(id=waba_aws_id)
                account_detail = detail.get("account", {})
                phone_numbers = account_detail.get("phoneNumbers", [])
                
                result.append({
                    "wabaAwsId": waba_aws_id,
                    "wabaMetaId": waba_meta_id,
                    "arn": acc.get("arn", ""),
                    "linkDate": str(acc.get("linkDate", "")),
                    "registrationStatus": acc.get("registrationStatus", ""),
                    "phoneNumbers": [{
                        "phoneNumberId": p.get("phoneNumberId", ""),
                        "metaPhoneNumberId": p.get("metaPhoneNumberId", ""),
                        "displayPhoneNumber": p.get("displayPhoneNumber", ""),
                        "displayPhoneNumberName": p.get("displayPhoneNumberName", ""),
                        "qualityRating": p.get("qualityRating", ""),
                        "arn": p.get("arn", ""),
                    } for p in phone_numbers],
                })
            except ClientError:
                result.append({
                    "wabaAwsId": waba_aws_id,
                    "wabaMetaId": waba_meta_id,
                    "arn": acc.get("arn", ""),
                })
        
        return {
            "statusCode": 200,
            "operation": "get_wabas",
            "count": len(result),
            "wabas": result,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_phone_info(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get detailed phone number information.
    
    Test Event:
    {
        "action": "get_phone_info",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    if not meta_waba_id:
        # Return all configured phones
        phones = []
        for waba_id, config in WABA_PHONE_MAP.items():
            phones.append({
                "metaWabaId": waba_id,
                "businessAccountName": config.get("businessAccountName", ""),
                "phone": config.get("phone", ""),
                "phoneArn": config.get("phoneArn", ""),
                "metaPhoneNumberId": config.get("meta_phone_number_id", ""),
            })
        return {
            "statusCode": 200,
            "operation": "get_phone_info",
            "count": len(phones),
            "phones": phones,
        }
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    if not waba_config:
        return {"statusCode": 404, "error": f"WABA not found: {meta_waba_id}"}
    
    # Get quality from DynamoDB
    phone_arn = waba_config.get("phoneArn", "")
    phone_number_id = arn_suffix(phone_arn)
    quality_pk = f"QUALITY#{phone_number_id}"
    
    quality_info = {}
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): quality_pk})
        quality_info = response.get("Item", {})
    except ClientError:
        pass
    
    return {
        "statusCode": 200,
        "operation": "get_phone_info",
        "phone": {
            "metaWabaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
            "phone": waba_config.get("phone", ""),
            "phoneArn": phone_arn,
            "metaPhoneNumberId": waba_config.get("meta_phone_number_id", ""),
            "qualityRating": quality_info.get("qualityRating", "UNKNOWN"),
            "throughputStatus": quality_info.get("throughputStatus", "UNKNOWN"),
            "lastCheckedAt": quality_info.get("lastCheckedAt", ""),
        },
    }


def handle_send_sticker(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a sticker message.
    
    Test Event (with S3 key - WebP format required):
    {
        "action": "send_sticker",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "s3Key": "WhatsApp/stickers/smile.webp"
    }
    
    Test Event (with existing WhatsApp media ID):
    {
        "action": "send_sticker",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "mediaId": "123456789"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    s3_key = event.get("s3Key", "")
    media_id = event.get("mediaId", "")
    
    if not meta_waba_id or not to_number:
        return {"statusCode": 400, "error": "metaWabaId and to are required"}
    
    if not s3_key and not media_id:
        return {"statusCode": 400, "error": "Either s3Key or mediaId is required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Upload to WhatsApp if s3Key provided
        if s3_key and not media_id:
            upload_resp = social().post_whatsapp_message_media(
                originationPhoneNumberId=origination_id_for_api(phone_arn),
                sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
            )
            media_id = upload_resp.get("mediaId", "")
            if not media_id:
                return {"statusCode": 500, "error": "Failed to upload sticker to WhatsApp"}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "sticker",
            "sticker": {"id": media_id},
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": "sticker",
            "mediaId": media_id,
            "s3Key": s3_key,
            "preview": "[sticker]",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_sticker",
            "messageId": msg_id,
            "mediaId": media_id,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_refresh_quality(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Force refresh phone quality rating.
    
    Test Event:
    {
        "action": "refresh_quality",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    if not waba_config:
        return {"statusCode": 404, "error": f"WABA not found: {meta_waba_id}"}
    
    phone_arn = waba_config.get("phoneArn", "")
    phone_number_id = arn_suffix(phone_arn)
    
    # Call the function to update quality
    result = update_phone_quality_rating(
        waba_id=meta_waba_id,
        phone_number_id=phone_number_id,
        business_name=waba_config.get("businessAccountName", ""),
        phone_number=waba_config.get("phone", "")
    )
    
    return {
        "statusCode": 200,
        "operation": "refresh_quality",
        "result": result,
    }


def handle_refresh_infra(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Force refresh infrastructure configuration.
    
    Test Event:
    {
        "action": "refresh_infra"
    }
    """
    # Call the function to update infrastructure config
    result = update_infrastructure_config()
    
    return {
        "statusCode": 200,
        "operation": "refresh_infra",
        "result": result,
    }


def handle_refresh_media_types(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Force refresh media types configuration.
    
    Test Event:
    {
        "action": "refresh_media_types"
    }
    """
    # Call the function to update media types config
    result = update_media_types_config()
    
    return {
        "statusCode": 200,
        "operation": "refresh_media_types",
        "result": result,
    }


def handle_get_infra(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get infrastructure configuration from DynamoDB.
    
    Test Event:
    {
        "action": "get_infra"
    }
    """
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): "CONFIG#INFRASTRUCTURE"})
        item = response.get("Item", {})
        
        if not item:
            return {"statusCode": 404, "error": "Infrastructure config not found. Run refresh_infra first."}
        
        return {
            "statusCode": 200,
            "operation": "get_infra",
            "infra": item,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_media_types(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get supported media types from DynamoDB.
    
    Test Event:
    {
        "action": "get_media_types"
    }
    """
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): "CONFIG#MEDIA_TYPES"})
        item = response.get("Item", {})
        
        if not item:
            return {"statusCode": 404, "error": "Media types config not found. Run refresh_media_types first."}
        
        return {
            "statusCode": 200,
            "operation": "get_media_types",
            "mediaTypes": item,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a single message by ID.
    
    Test Event:
    {
        "action": "get_message",
        "messageId": "wamid.xxx"
    }
    
    Or by PK:
    {
        "action": "get_message",
        "pk": "MSG#wamid.xxx"
    }
    """
    message_id = event.get("messageId", "")
    pk = event.get("pk", "")
    
    if not message_id and not pk:
        return {"statusCode": 400, "error": "messageId or pk is required"}
    
    if not pk:
        pk = f"MSG#{message_id}"
    
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): pk})
        item = response.get("Item")
        
        if not item:
            return {"statusCode": 404, "error": f"Message not found: {pk}"}
        
        return {
            "statusCode": 200,
            "operation": "get_message",
            "message": item,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a single conversation.
    
    Test Event:
    {
        "action": "get_conversation",
        "conversationPk": "CONV#phone#from"
    }
    
    Or by phone and from:
    {
        "action": "get_conversation",
        "phoneId": "3f8934395ae24a4583a413087a3d3fb0",
        "fromNumber": "447447840003"
    }
    """
    conv_pk = event.get("conversationPk", "")
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    
    if not conv_pk and (not phone_id or not from_number):
        return {"statusCode": 400, "error": "conversationPk or (phoneId + fromNumber) is required"}
    
    if not conv_pk:
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): conv_pk})
        item = response.get("Item")
        
        if not item:
            return {"statusCode": 404, "error": f"Conversation not found: {conv_pk}"}
        
        return {
            "statusCode": 200,
            "operation": "get_conversation",
            "conversation": item,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get templates for a WABA (shortcut to templates op=list).
    
    Test Event:
    {
        "action": "get_templates",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    if not meta_waba_id:
        # Return all templates from DynamoDB
        try:
            response = table().scan(
                FilterExpression="itemType = :t",
                ExpressionAttributeValues={":t": "MESSAGE_TEMPLATES"},
            )
            items = response.get("Items", [])
            return {
                "statusCode": 200,
                "operation": "get_templates",
                "count": len(items),
                "templates": items,
            }
        except ClientError as e:
            return {"statusCode": 500, "error": str(e)}
    
    # Get templates for specific WABA
    waba_aws_id = get_waba_aws_id(meta_waba_id)
    if not waba_aws_id:
        return {"statusCode": 404, "error": f"WABA not found: {meta_waba_id}"}
    
    return list_templates(waba_aws_id, meta_waba_id)


def handle_remove_reaction(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Remove a reaction from a message.
    
    Test Event:
    {
        "action": "remove_reaction",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "messageId": "wamid.xxx"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    wa_msg_id = event.get("messageId", "")
    
    if not meta_waba_id or not to_number or not wa_msg_id:
        return {"statusCode": 400, "error": "metaWabaId, to, and messageId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Send empty emoji to remove reaction
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": format_wa_number(to_number),
            "type": "reaction",
            "reaction": {
                "message_id": wa_msg_id,
                "emoji": "",  # Empty emoji removes reaction
            },
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        return {
            "statusCode": 200,
            "operation": "remove_reaction",
            "messageId": response.get("messageId"),
            "removedFrom": wa_msg_id,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_reply(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a reply to a specific message (with context/quote).
    
    Test Event:
    {
        "action": "send_reply",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "replyToMessageId": "wamid.xxx",
        "text": "This is a reply to your message"
    }
    
    Or with media:
    {
        "action": "send_reply",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "replyToMessageId": "wamid.xxx",
        "mediaType": "image",
        "s3Key": "WhatsApp/test/image.jpg",
        "caption": "Reply with image"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    reply_to_msg_id = event.get("replyToMessageId", "")
    text = event.get("text", "")
    media_type = event.get("mediaType", "")
    s3_key = event.get("s3Key", "")
    media_id = event.get("mediaId", "")
    caption = event.get("caption", "")
    
    if not meta_waba_id or not to_number or not reply_to_msg_id:
        return {"statusCode": 400, "error": "metaWabaId, to, and replyToMessageId are required"}
    
    if not text and not media_type:
        return {"statusCode": 400, "error": "Either text or mediaType is required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        to_formatted = format_wa_number(to_number)
        
        if text:
            # Text reply
            payload = {
                "messaging_product": "whatsapp",
                "to": to_formatted,
                "type": "text",
                "context": {"message_id": reply_to_msg_id},
                "text": {"body": text},
            }
            msg_type = "text"
            preview = text[:200]
        else:
            # Media reply
            if s3_key and not media_id:
                upload_resp = social().post_whatsapp_message_media(
                    originationPhoneNumberId=origination_id_for_api(phone_arn),
                    sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
                )
                media_id = upload_resp.get("mediaId", "")
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to_formatted,
                "type": media_type,
                "context": {"message_id": reply_to_msg_id},
                media_type: {"id": media_id},
            }
            if caption:
                payload[media_type]["caption"] = caption
            msg_type = media_type
            preview = f"[{media_type}] {caption}" if caption else f"[{media_type}]"
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "MESSAGE",
            "direction": "OUTBOUND",
            "to": to_number,
            "type": msg_type,
            "textBody": text if text else "",
            "mediaId": media_id if media_id else "",
            "s3Key": s3_key if s3_key else "",
            "caption": caption if caption else "",
            "preview": preview,
            "replyToMessageId": reply_to_msg_id,
            "isReply": True,
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
            "originationPhoneNumberId": phone_arn,
            "wabaMetaId": meta_waba_id,
            "businessAccountName": waba_config.get("businessAccountName", ""),
        })
        
        return {
            "statusCode": 200,
            "operation": "send_reply",
            "messageId": msg_id,
            "replyTo": reply_to_msg_id,
            "to": to_number,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_download_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Download media from WhatsApp to S3.
    
    S3 Path: s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    
    Test Event:
    {
        "action": "download_media",
        "metaWabaId": "1347766229904230",
        "mediaId": "123456789",
        "filename": "document",
        "mimeType": "application/pdf"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    media_id = event.get("mediaId", "")
    s3_key = event.get("s3Key", "")
    filename = event.get("filename", "media")
    mime_type = event.get("mimeType", "")
    filename = event.get("filename", "media")
    mime_type = event.get("mimeType", "")
    
    if not meta_waba_id or not media_id:
        return {"statusCode": 400, "error": "metaWabaId and mediaId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    # Generate S3 key with WABA folder and secure UUID filename
    if not s3_key:
        s3_key = generate_download_s3_key(meta_waba_id, filename, mime_type)
    
    waba_folder = get_waba_folder(meta_waba_id)
    
    try:
        response = social().get_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            destinationS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        
        return {
            "statusCode": 200,
            "operation": "download_media",
            "mediaId": media_id,
            "wabaFolder": waba_folder,
            "s3Bucket": str(MEDIA_BUCKET),
            "s3Key": s3_key,
            "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
            "fileSize": response.get("fileSize"),
            "mimeType": response.get("mimeType"),
            "note": "Downloaded to WhatsApp/download/{waba_folder}/ with secure UUID filename"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_delivery_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get delivery status for a message.
    
    Test Event:
    {
        "action": "get_delivery_status",
        "messageId": "wamid.xxx"
    }
    """
    message_id = event.get("messageId", "")
    
    if not message_id:
        return {"statusCode": 400, "error": "messageId is required"}
    
    msg_pk = f"MSG#{message_id}"
    
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): msg_pk})
        item = response.get("Item")
        
        if not item:
            return {"statusCode": 404, "error": f"Message not found: {message_id}"}
        
        return {
            "statusCode": 200,
            "operation": "get_delivery_status",
            "messageId": message_id,
            "status": {
                "deliveryStatus": item.get("deliveryStatus", "unknown"),
                "deliveryStatusTimestamp": item.get("deliveryStatusTimestamp", ""),
                "deliveryStatusUpdatedAt": item.get("deliveryStatusUpdatedAt", ""),
                "deliveryStatusHistory": item.get("deliveryStatusHistory", []),
                "markedAsRead": item.get("markedAsRead", False),
                "markedAsReadAt": item.get("markedAsReadAt", ""),
                "reactedWithEmoji": item.get("reactedWithEmoji", ""),
                "reactedAt": item.get("reactedAt", ""),
            },
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update conversation (mark as read/unread, archive, etc.).
    
    Test Event:
    {
        "action": "update_conversation",
        "conversationPk": "CONV#phone#from",
        "markAsRead": true,
        "unreadCount": 0
    }
    """
    conv_pk = event.get("conversationPk", "")
    mark_as_read = event.get("markAsRead")
    unread_count = event.get("unreadCount")
    archived = event.get("archived")
    
    if not conv_pk:
        return {"statusCode": 400, "error": "conversationPk is required"}
    
    try:
        update_expr_parts = []
        expr_values = {}
        
        if mark_as_read is not None:
            update_expr_parts.append("markedAsRead = :mar")
            expr_values[":mar"] = mark_as_read
            if mark_as_read:
                update_expr_parts.append("markedAsReadAt = :marat")
                expr_values[":marat"] = iso_now()
        
        if unread_count is not None:
            update_expr_parts.append("unreadCount = :uc")
            expr_values[":uc"] = unread_count
        
        if archived is not None:
            update_expr_parts.append("archived = :arch")
            expr_values[":arch"] = archived
        
        if not update_expr_parts:
            return {"statusCode": 400, "error": "No update fields provided"}
        
        table().update_item(
            Key={str(MESSAGES_PK_NAME): conv_pk},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeValues=expr_values,
        )
        
        return {
            "statusCode": 200,
            "operation": "update_conversation",
            "conversationPk": conv_pk,
            "updated": True,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_delete_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete a message from DynamoDB (soft delete by default).
    
    Test Event:
    {
        "action": "delete_message",
        "messageId": "wamid.xxx",
        "hardDelete": false
    }
    """
    message_id = event.get("messageId", "")
    hard_delete = event.get("hardDelete", False)
    
    if not message_id:
        return {"statusCode": 400, "error": "messageId is required"}
    
    msg_pk = f"MSG#{message_id}"
    
    try:
        if hard_delete:
            table().delete_item(Key={str(MESSAGES_PK_NAME): msg_pk})
        else:
            # Soft delete - mark as deleted
            table().update_item(
                Key={str(MESSAGES_PK_NAME): msg_pk},
                UpdateExpression="SET deleted = :d, deletedAt = :dat",
                ExpressionAttributeValues={":d": True, ":dat": iso_now()},
            )
        
        return {
            "statusCode": 200,
            "operation": "delete_message",
            "messageId": message_id,
            "hardDelete": hard_delete,
            "deleted": True,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_search_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Search messages by text content.
    
    Test Event:
    {
        "action": "search_messages",
        "query": "hello",
        "limit": 20
    }
    """
    query = event.get("query", "")
    limit = event.get("limit", 50)
    direction = event.get("direction")
    from_number = event.get("fromNumber")
    
    if not query:
        return {"statusCode": 400, "error": "query is required"}
    
    try:
        # Scan with filter (not efficient for large tables, but works for now)
        filter_parts = ["(contains(textBody, :q) OR contains(preview, :q) OR contains(caption, :q))"]
        expr_values = {":q": query}
        expr_names = {}
        
        if direction:
            filter_parts.append("direction = :d")
            expr_values[":d"] = direction
        
        if from_number:
            filter_parts.append("contains(#from, :f)")
            expr_values[":f"] = from_number
            expr_names["#from"] = "from"
        
        scan_kwargs = {
            "FilterExpression": " AND ".join(filter_parts),
            "ExpressionAttributeValues": expr_values,
            "Limit": limit * 3,  # Scan more to account for filtering
        }
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table().scan(**scan_kwargs)
        
        items = response.get("Items", [])
        messages = [i for i in items if i.get("itemType") in ("MESSAGE", "MESSAGE_STATUS")][:limit]
        
        return {
            "statusCode": 200,
            "operation": "search_messages",
            "query": query,
            "count": len(messages),
            "messages": messages,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_refresh_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Force refresh templates for a WABA.
    
    Test Event:
    {
        "action": "refresh_templates",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    waba_aws_id = get_waba_aws_id(meta_waba_id)
    if not waba_aws_id:
        return {"statusCode": 404, "error": f"WABA not found: {meta_waba_id}"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    business_name = waba_config.get("businessAccountName", "")
    
    # Call the function to update templates
    result = update_message_templates(
        waba_aws_id=waba_aws_id,
        waba_meta_id=meta_waba_id,
        business_name=business_name
    )
    
    return {
        "statusCode": 200,
        "operation": "refresh_templates",
        "result": result,
    }


def handle_get_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all configuration.
    
    Test Event:
    {
        "action": "get_config"
    }
    """
    return {
        "statusCode": 200,
        "operation": "get_config",
        "config": {
            "messagesTableName": str(MESSAGES_TABLE_NAME),
            "messagesPkName": str(MESSAGES_PK_NAME),
            "mediaBucket": str(MEDIA_BUCKET),
            "mediaPrefix": str(MEDIA_PREFIX),
            "metaApiVersion": str(META_API_VERSION),
            "autoReplyEnabled": bool(AUTO_REPLY_ENABLED),
            "autoReplyText": str(AUTO_REPLY_TEXT),
            "echoMediaBack": bool(ECHO_MEDIA_BACK),
            "markAsReadEnabled": bool(MARK_AS_READ_ENABLED),
            "reactEmojiEnabled": bool(REACT_EMOJI_ENABLED),
            "reactEmojiMap": get_react_emoji_map(),
            "forwardEnabled": bool(FORWARD_ENABLED),
            "forwardToWaId": str(FORWARD_TO_WA_ID),
            "emailNotificationEnabled": bool(EMAIL_NOTIFICATION_ENABLED),
            "emailSnsTopicArn": str(EMAIL_SNS_TOPIC_ARN),
            "wabaPhoneMap": get_waba_phone_map(),
            # Welcome Menu & Bedrock config
            "welcomeEnabled": bool(WELCOME_ENABLED),
            "menuOnKeywordsEnabled": bool(MENU_ON_KEYWORDS_ENABLED),
            "bedrockAutoReplyEnabled": bool(BEDROCK_AUTO_REPLY_ENABLED),
            "timezone": os.environ.get("TZ", "UTC"),
        },
    }


def handle_bulk_send(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send messages to multiple recipients.
    
    Test Event:
    {
        "action": "bulk_send",
        "metaWabaId": "1347766229904230",
        "recipients": ["+447447840003", "+919876543210"],
        "type": "text",
        "text": "Hello everyone!"
    }
    
    Or with template:
    {
        "action": "bulk_send",
        "metaWabaId": "1347766229904230",
        "recipients": ["+447447840003", "+919876543210"],
        "type": "template",
        "templateName": "hello_world",
        "languageCode": "en_US"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    recipients = event.get("recipients", [])
    msg_type = event.get("type", "text")
    text = event.get("text", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    components = event.get("components", [])
    
    if not meta_waba_id or not recipients:
        return {"statusCode": 400, "error": "metaWabaId and recipients are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    results = []
    success_count = 0
    error_count = 0
    
    for recipient in recipients:
        try:
            to_formatted = format_wa_number(recipient)
            
            if msg_type == "text":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to_formatted,
                    "type": "text",
                    "text": {"body": text},
                }
            elif msg_type == "template":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to_formatted,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language_code},
                    },
                }
                if components:
                    payload["template"]["components"] = components
            else:
                results.append({"recipient": recipient, "error": f"Unsupported type: {msg_type}"})
                error_count += 1
                continue
            
            response = social().send_whatsapp_message(
                originationPhoneNumberId=origination_id_for_api(phone_arn),
                metaApiVersion=str(META_API_VERSION),
                message=json.dumps(payload).encode("utf-8"),
            )
            
            msg_id = response.get("messageId", "")
            results.append({"recipient": recipient, "messageId": msg_id, "success": True})
            success_count += 1
            
            # Store in DynamoDB
            now = iso_now()
            msg_pk = f"MSG#{msg_id}"
            table().put_item(Item={
                str(MESSAGES_PK_NAME): msg_pk,
                "itemType": "MESSAGE",
                "direction": "OUTBOUND",
                "to": recipient,
                "type": msg_type,
                "textBody": text if msg_type == "text" else "",
                "templateName": template_name if msg_type == "template" else "",
                "preview": text[:200] if text else f"[template:{template_name}]",
                "sentAt": now,
                "receivedAt": now,
                "messageId": msg_id,
                "originationPhoneNumberId": phone_arn,
                "wabaMetaId": meta_waba_id,
                "businessAccountName": waba_config.get("businessAccountName", ""),
                "isBulkSend": True,
            })
            
        except ClientError as e:
            results.append({"recipient": recipient, "error": str(e), "success": False})
            error_count += 1
    
    return {
        "statusCode": 200,
        "operation": "bulk_send",
        "totalRecipients": len(recipients),
        "successCount": success_count,
        "errorCount": error_count,
        "results": results,
    }


def handle_send_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an image message (convenience wrapper for send_media).
    
    Test Event:
    {
        "action": "send_image",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "s3Key": "WhatsApp/images/photo.jpg",
        "caption": "Check out this image!"
    }
    """
    event["mediaType"] = "image"
    event["action"] = "send_media"
    return handle_send_media(event, context)


def handle_send_video(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a video message (convenience wrapper for send_media).
    
    Test Event:
    {
        "action": "send_video",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "s3Key": "WhatsApp/videos/clip.mp4",
        "caption": "Watch this video!"
    }
    """
    event["mediaType"] = "video"
    event["action"] = "send_media"
    return handle_send_media(event, context)


def handle_send_audio(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an audio message (convenience wrapper for send_media).
    
    Test Event:
    {
        "action": "send_audio",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "s3Key": "WhatsApp/audio/voice.mp3"
    }
    """
    event["mediaType"] = "audio"
    event["action"] = "send_media"
    return handle_send_media(event, context)


def handle_send_document(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a document message (convenience wrapper for send_media).
    
    Test Event:
    {
        "action": "send_document",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "s3Key": "WhatsApp/docs/report.pdf",
        "caption": "Here is the report",
        "filename": "Monthly_Report.pdf"
    }
    """
    event["mediaType"] = "document"
    event["action"] = "send_media"
    return handle_send_media(event, context)


def handle_get_media_url(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get presigned URL for media stored in S3.
    
    Test Event:
    {
        "action": "get_media_url",
        "s3Key": "WhatsApp/business=Test/wabaMetaId=123/phone=456/from=789/waMessageId=abc/mediaId=xyz.jpg",
        "expirySeconds": 3600
    }
    
    Or by message ID:
    {
        "action": "get_media_url",
        "messageId": "wamid.xxx"
    }
    """
    s3_key = event.get("s3Key", "")
    message_id = event.get("messageId", "")
    expiry = event.get("expirySeconds", 86400)  # Default 24 hours
    
    if not s3_key and not message_id:
        return {"statusCode": 400, "error": "s3Key or messageId is required"}
    
    # If messageId provided, look up the s3Key from DynamoDB
    if message_id and not s3_key:
        msg_pk = f"MSG#{message_id}"
        try:
            response = table().get_item(Key={str(MESSAGES_PK_NAME): msg_pk})
            item = response.get("Item")
            if not item:
                return {"statusCode": 404, "error": f"Message not found: {message_id}"}
            s3_key = item.get("s3Key", "")
            if not s3_key:
                return {"statusCode": 404, "error": f"No media found for message: {message_id}"}
        except ClientError as e:
            return {"statusCode": 500, "error": str(e)}
    
    try:
        url = generate_s3_presigned_url(str(MEDIA_BUCKET), s3_key, expiry)
        return {
            "statusCode": 200,
            "operation": "get_media_url",
            "s3Key": s3_key,
            "url": url,
            "expiresIn": expiry,
            "bucket": str(MEDIA_BUCKET),
        }
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_resend_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Resend a failed message.
    
    Test Event:
    {
        "action": "resend_message",
        "messageId": "wamid.xxx"
    }
    
    Or with new recipient:
    {
        "action": "resend_message",
        "messageId": "wamid.xxx",
        "to": "+447447840004"
    }
    """
    message_id = event.get("messageId", "")
    new_to = event.get("to", "")
    
    if not message_id:
        return {"statusCode": 400, "error": "messageId is required"}
    
    msg_pk = f"MSG#{message_id}"
    
    try:
        # Get original message
        response = table().get_item(Key={str(MESSAGES_PK_NAME): msg_pk})
        item = response.get("Item")
        
        if not item:
            return {"statusCode": 404, "error": f"Message not found: {message_id}"}
        
        # Only resend outbound messages
        if item.get("direction") != "OUTBOUND":
            return {"statusCode": 400, "error": "Can only resend outbound messages"}
        
        # Build resend event based on original message type
        msg_type = item.get("type", "text")
        meta_waba_id = item.get("wabaMetaId", "")
        to_number = new_to or item.get("to", "")
        
        if not meta_waba_id or not to_number:
            return {"statusCode": 400, "error": "Missing wabaMetaId or recipient"}
        
        resend_event = {
            "metaWabaId": meta_waba_id,
            "to": to_number,
        }
        
        if msg_type == "text":
            resend_event["action"] = "send_text"
            resend_event["text"] = item.get("textBody", "")
            return handle_send_text(resend_event, context)
        
        elif msg_type in ("image", "video", "audio", "document"):
            resend_event["action"] = "send_media"
            resend_event["mediaType"] = msg_type
            resend_event["s3Key"] = item.get("s3Key", "")
            resend_event["caption"] = item.get("caption", "")
            resend_event["filename"] = item.get("filename", "")
            return handle_send_media(resend_event, context)
        
        elif msg_type == "sticker":
            resend_event["action"] = "send_sticker"
            resend_event["s3Key"] = item.get("s3Key", "")
            return handle_send_sticker(resend_event, context)
        
        elif msg_type == "location":
            resend_event["action"] = "send_location"
            resend_event["latitude"] = float(item.get("latitude", 0))
            resend_event["longitude"] = float(item.get("longitude", 0))
            resend_event["name"] = item.get("locationName", "")
            resend_event["address"] = item.get("locationAddress", "")
            return handle_send_location(resend_event, context)
        
        elif msg_type == "contacts":
            resend_event["action"] = "send_contact"
            resend_event["contacts"] = item.get("contacts", [])
            return handle_send_contact(resend_event, context)
        
        elif msg_type == "interactive":
            return {"statusCode": 400, "error": "Interactive messages cannot be resent automatically"}
        
        else:
            return {"statusCode": 400, "error": f"Unsupported message type for resend: {msg_type}"}
        
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_conversation_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all messages in a conversation.
    
    Test Event:
    {
        "action": "get_conversation_messages",
        "conversationPk": "CONV#phone#from",
        "limit": 50
    }
    
    Or by phone and from:
    {
        "action": "get_conversation_messages",
        "phoneId": "3f8934395ae24a4583a413087a3d3fb0",
        "fromNumber": "447447840003",
        "limit": 50
    }
    """
    conv_pk = event.get("conversationPk", "")
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    limit = event.get("limit", 100)
    
    if not conv_pk and (not phone_id or not from_number):
        return {"statusCode": 400, "error": "conversationPk or (phoneId + fromNumber) is required"}
    
    if not conv_pk:
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    try:
        # Query messages by conversationPk using GSI
        response = table().query(
            IndexName="gsi_conversation",
            KeyConditionExpression="conversationPk = :cpk",
            ExpressionAttributeValues={":cpk": conv_pk},
            ScanIndexForward=False,  # Most recent first
            Limit=limit,
        )
        
        items = response.get("Items", [])
        messages = [i for i in items if i.get("itemType") == "MESSAGE"]
        
        return {
            "statusCode": 200,
            "operation": "get_conversation_messages",
            "conversationPk": conv_pk,
            "count": len(messages),
            "messages": messages,
        }
    except ClientError as e:
        # If GSI doesn't exist, fall back to scan
        if "ValidationException" in str(e):
            try:
                response = table().scan(
                    FilterExpression="conversationPk = :cpk AND itemType = :it",
                    ExpressionAttributeValues={":cpk": conv_pk, ":it": "MESSAGE"},
                    Limit=limit,
                )
                items = response.get("Items", [])
                return {
                    "statusCode": 200,
                    "operation": "get_conversation_messages",
                    "conversationPk": conv_pk,
                    "count": len(items),
                    "messages": items,
                    "note": "Using scan - consider creating gsi_conversation GSI for better performance",
                }
            except ClientError as e2:
                return {"statusCode": 500, "error": str(e2)}
        return {"statusCode": 500, "error": str(e)}


def handle_get_unread_count(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get unread message count.
    
    Test Event (all unread):
    {
        "action": "get_unread_count"
    }
    
    Or for specific conversation:
    {
        "action": "get_unread_count",
        "conversationPk": "CONV#phone#from"
    }
    
    Or for specific inbox:
    {
        "action": "get_unread_count",
        "inboxPk": "arn:aws:social-messaging:..."
    }
    """
    conv_pk = event.get("conversationPk", "")
    inbox_pk = event.get("inboxPk", "")
    
    try:
        if conv_pk:
            # Get unread count for specific conversation
            response = table().get_item(Key={str(MESSAGES_PK_NAME): conv_pk})
            item = response.get("Item")
            if not item:
                return {"statusCode": 404, "error": f"Conversation not found: {conv_pk}"}
            
            return {
                "statusCode": 200,
                "operation": "get_unread_count",
                "conversationPk": conv_pk,
                "unreadCount": item.get("unreadCount", 0),
            }
        
        elif inbox_pk:
            # Get unread count for all conversations in inbox
            response = table().query(
                IndexName="gsi_inbox",
                KeyConditionExpression="inboxPk = :pk",
                ExpressionAttributeValues={":pk": inbox_pk},
            )
            items = response.get("Items", [])
            conversations = [i for i in items if i.get("itemType") == "CONVERSATION"]
            total_unread = sum(c.get("unreadCount", 0) for c in conversations)
            
            return {
                "statusCode": 200,
                "operation": "get_unread_count",
                "inboxPk": inbox_pk,
                "totalUnread": total_unread,
                "conversationCount": len(conversations),
            }
        
        else:
            # Get total unread count across all conversations
            response = table().scan(
                FilterExpression="itemType = :t",
                ExpressionAttributeValues={":t": "CONVERSATION"},
            )
            items = response.get("Items", [])
            total_unread = sum(c.get("unreadCount", 0) for c in items)
            
            return {
                "statusCode": 200,
                "operation": "get_unread_count",
                "totalUnread": total_unread,
                "conversationCount": len(items),
            }
        
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_mark_conversation_read(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Mark all messages in a conversation as read and reset unread count.
    
    Test Event:
    {
        "action": "mark_conversation_read",
        "conversationPk": "CONV#phone#from"
    }
    
    Or by phone and from:
    {
        "action": "mark_conversation_read",
        "phoneId": "3f8934395ae24a4583a413087a3d3fb0",
        "fromNumber": "447447840003"
    }
    """
    conv_pk = event.get("conversationPk", "")
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    
    if not conv_pk and (not phone_id or not from_number):
        return {"statusCode": 400, "error": "conversationPk or (phoneId + fromNumber) is required"}
    
    if not conv_pk:
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    now = iso_now()
    
    try:
        # Reset unread count on conversation
        table().update_item(
            Key={str(MESSAGES_PK_NAME): conv_pk},
            UpdateExpression="SET unreadCount = :zero, lastReadAt = :now",
            ExpressionAttributeValues={":zero": 0, ":now": now},
        )
        
        return {
            "statusCode": 200,
            "operation": "mark_conversation_read",
            "conversationPk": conv_pk,
            "markedAt": now,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_archive_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Archive a conversation.
    
    Test Event:
    {
        "action": "archive_conversation",
        "conversationPk": "CONV#phone#from"
    }
    """
    conv_pk = event.get("conversationPk", "")
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    
    if not conv_pk and (not phone_id or not from_number):
        return {"statusCode": 400, "error": "conversationPk or (phoneId + fromNumber) is required"}
    
    if not conv_pk:
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    now = iso_now()
    
    try:
        table().update_item(
            Key={str(MESSAGES_PK_NAME): conv_pk},
            UpdateExpression="SET archived = :a, archivedAt = :at",
            ExpressionAttributeValues={":a": True, ":at": now},
        )
        
        return {
            "statusCode": 200,
            "operation": "archive_conversation",
            "conversationPk": conv_pk,
            "archived": True,
            "archivedAt": now,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_unarchive_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Unarchive a conversation.
    
    Test Event:
    {
        "action": "unarchive_conversation",
        "conversationPk": "CONV#phone#from"
    }
    """
    conv_pk = event.get("conversationPk", "")
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    
    if not conv_pk and (not phone_id or not from_number):
        return {"statusCode": 400, "error": "conversationPk or (phoneId + fromNumber) is required"}
    
    if not conv_pk:
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    now = iso_now()
    
    try:
        table().update_item(
            Key={str(MESSAGES_PK_NAME): conv_pk},
            UpdateExpression="SET archived = :a, unarchivedAt = :at REMOVE archivedAt",
            ExpressionAttributeValues={":a": False, ":at": now},
        )
        
        return {
            "statusCode": 200,
            "operation": "unarchive_conversation",
            "conversationPk": conv_pk,
            "archived": False,
            "unarchivedAt": now,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_export_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Export messages to S3 as JSON.
    
    Test Event:
    {
        "action": "export_messages",
        "conversationPk": "CONV#phone#from",
        "s3Key": "exports/conversation_export.json"
    }
    
    Or export all:
    {
        "action": "export_messages",
        "s3Key": "exports/all_messages.json",
        "limit": 1000
    }
    """
    conv_pk = event.get("conversationPk", "")
    s3_key = event.get("s3Key", "")
    limit = event.get("limit", 1000)
    
    if not s3_key:
        # Generate default key
        timestamp = iso_now().replace(":", "-").replace("+", "_")
        s3_key = f"{MEDIA_PREFIX}exports/messages_{timestamp}.json"
    
    try:
        if conv_pk:
            # Export specific conversation
            response = table().query(
                IndexName="gsi_conversation",
                KeyConditionExpression="conversationPk = :cpk",
                ExpressionAttributeValues={":cpk": conv_pk},
                Limit=limit,
            )
        else:
            # Export all messages
            response = table().scan(
                FilterExpression="itemType = :t",
                ExpressionAttributeValues={":t": "MESSAGE"},
                Limit=limit,
            )
        
        items = response.get("Items", [])
        
        # Convert Decimal to float for JSON serialization
        def convert_decimals(obj):
            if isinstance(obj, list):
                return [convert_decimals(i) for i in obj]
            elif isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif hasattr(obj, '__float__'):
                return float(obj)
            return obj
        
        export_data = {
            "exportedAt": iso_now(),
            "conversationPk": conv_pk or "ALL",
            "messageCount": len(items),
            "messages": convert_decimals(items),
        }
        
        # Upload to S3
        s3().put_object(
            Bucket=str(MEDIA_BUCKET),
            Key=s3_key,
            Body=json.dumps(export_data, ensure_ascii=False, default=str),
            ContentType="application/json",
        )
        
        # Generate presigned URL for download
        download_url = generate_s3_presigned_url(str(MEDIA_BUCKET), s3_key, 86400)
        
        return {
            "statusCode": 200,
            "operation": "export_messages",
            "s3Key": s3_key,
            "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
            "downloadUrl": download_url,
            "messageCount": len(items),
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_message_by_wa_id(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get message by WhatsApp message ID (wamid).
    
    Test Event:
    {
        "action": "get_message_by_wa_id",
        "waMessageId": "wamid.HBgLNDQ3NDQ3ODQwMDAzFQIAEhgUM0Y4OTM0Mzk1QUUyNEE0NTgzQTQA"
    }
    """
    wa_msg_id = event.get("waMessageId", "")
    
    if not wa_msg_id:
        return {"statusCode": 400, "error": "waMessageId is required"}
    
    # Try MSG# prefix first
    msg_pk = f"MSG#{wa_msg_id}"
    
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): msg_pk})
        item = response.get("Item")
        
        if item:
            return {
                "statusCode": 200,
                "operation": "get_message_by_wa_id",
                "message": item,
            }
        
        # If not found, try scanning for the waMessageId field
        response = table().scan(
            FilterExpression="contains(#pk, :wamid) OR waMessageId = :wamid",
            ExpressionAttributeNames={"#pk": str(MESSAGES_PK_NAME)},
            ExpressionAttributeValues={":wamid": wa_msg_id},
            Limit=1,
        )
        
        items = response.get("Items", [])
        if items:
            return {
                "statusCode": 200,
                "operation": "get_message_by_wa_id",
                "message": items[0],
            }
        
        return {"statusCode": 404, "error": f"Message not found: {wa_msg_id}"}
        
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_archived_conversations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get archived conversations.
    
    Test Event:
    {
        "action": "get_archived_conversations",
        "limit": 50
    }
    """
    limit = event.get("limit", 50)
    
    try:
        response = table().scan(
            FilterExpression="itemType = :t AND archived = :a",
            ExpressionAttributeValues={":t": "CONVERSATION", ":a": True},
            Limit=limit,
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_archived_conversations",
            "count": len(items),
            "conversations": items,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_failed_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get messages with failed delivery status.
    
    Test Event:
    {
        "action": "get_failed_messages",
        "limit": 50
    }
    """
    limit = event.get("limit", 50)
    
    try:
        response = table().scan(
            FilterExpression="deliveryStatus = :s",
            ExpressionAttributeValues={":s": "failed"},
            Limit=limit,
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_failed_messages",
            "count": len(items),
            "messages": items,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_retry_failed_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Retry all failed messages.
    
    Test Event:
    {
        "action": "retry_failed_messages",
        "limit": 10
    }
    """
    limit = event.get("limit", 10)
    
    try:
        # Get failed messages
        response = table().scan(
            FilterExpression="deliveryStatus = :s AND direction = :d",
            ExpressionAttributeValues={":s": "failed", ":d": "OUTBOUND"},
            Limit=limit,
        )
        
        items = response.get("Items", [])
        results = []
        success_count = 0
        error_count = 0
        
        for item in items:
            msg_pk = item.get(str(MESSAGES_PK_NAME), "")
            # Extract message ID from PK (MSG#wamid.xxx -> wamid.xxx)
            message_id = msg_pk.replace("MSG#", "") if msg_pk.startswith("MSG#") else msg_pk
            
            try:
                result = handle_resend_message({"messageId": message_id}, context)
                if result.get("statusCode") == 200:
                    success_count += 1
                    results.append({"messageId": message_id, "success": True, "newMessageId": result.get("messageId")})
                else:
                    error_count += 1
                    results.append({"messageId": message_id, "success": False, "error": result.get("error")})
            except Exception as e:
                error_count += 1
                results.append({"messageId": message_id, "success": False, "error": str(e)})
        
        return {
            "statusCode": 200,
            "operation": "retry_failed_messages",
            "totalAttempted": len(items),
            "successCount": success_count,
            "errorCount": error_count,
            "results": results,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_validate_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate if a media file is supported by WhatsApp.
    
    Test Event (by MIME type):
    {
        "action": "validate_media",
        "mimeType": "image/jpeg",
        "fileSizeBytes": 1048576
    }
    
    Test Event (by S3 key - will check actual file):
    {
        "action": "validate_media",
        "s3Key": "WhatsApp/test/image.jpg"
    }
    """
    mime_type = event.get("mimeType", "")
    file_size = event.get("fileSizeBytes", 0)
    s3_key = event.get("s3Key", "")
    
    # If S3 key provided, get actual file info
    if s3_key and not mime_type:
        try:
            head = s3().head_object(Bucket=str(MEDIA_BUCKET), Key=s3_key)
            mime_type = head.get("ContentType", "")
            file_size = int(head.get("ContentLength", 0))
        except ClientError as e:
            return {"statusCode": 404, "error": f"S3 object not found: {s3_key}", "details": str(e)}
    
    if not mime_type:
        return {"statusCode": 400, "error": "mimeType or s3Key is required"}
    
    result = is_supported_media(mime_type, file_size)
    
    return {
        "statusCode": 200,
        "operation": "validate_media",
        "mimeType": mime_type,
        "fileSizeBytes": file_size,
        "fileSizeMB": round(file_size / (1024 * 1024), 2) if file_size else 0,
        "supported": result.get("supported", False),
        "category": result.get("category"),
        "format": result.get("format"),
        "withinSizeLimit": result.get("withinSizeLimit", True),
        "maxBytes": result.get("maxBytes", 0),
        "maxMB": round(result.get("maxBytes", 0) / (1024 * 1024), 2) if result.get("maxBytes") else 0,
    }


def handle_get_supported_formats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all supported media formats with size limits.
    
    Test Event:
    {
        "action": "get_supported_formats"
    }
    
    Or filter by category:
    {
        "action": "get_supported_formats",
        "category": "image"
    }
    """
    category = event.get("category", "")
    
    if category:
        if category not in SUPPORTED_MEDIA_TYPES:
            return {
                "statusCode": 400, 
                "error": f"Unknown category: {category}",
                "validCategories": list(SUPPORTED_MEDIA_TYPES.keys())
            }
        return {
            "statusCode": 200,
            "operation": "get_supported_formats",
            "category": category,
            "formats": SUPPORTED_MEDIA_TYPES[category],
        }
    
    # Return all formats with summary
    all_mime_types = get_supported_mime_types()
    
    return {
        "statusCode": 200,
        "operation": "get_supported_formats",
        "totalFormats": sum(len(cat.get("formats", [])) for cat in SUPPORTED_MEDIA_TYPES.values()),
        "totalMimeTypes": len(all_mime_types),
        "categories": list(SUPPORTED_MEDIA_TYPES.keys()),
        "allMimeTypes": all_mime_types,
        "formats": SUPPORTED_MEDIA_TYPES,
        "sizeLimits": {
            "audio": "16 MB (AAC, AMR, MP3, M4A, OGG)",
            "document": "100 MB (TXT, PDF, XLS, XLSX, DOC, DOCX, PPT, PPTX)",
            "image": "5 MB (JPEG, PNG)",
            "sticker": "500 KB animated, 100 KB static (WebP only)",
            "video": "16 MB (3GP, MP4)",
        },
        "notes": {
            "image": "Images must be 8-bit, RGB or RGBA",
            "sticker": "WebP images can only be sent in sticker messages",
            "video": "H.264 video codec and AAC audio codec only",
            "audio_ogg": "OPUS codecs only; mono input only",
        },
    }


def handle_send_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a WhatsApp Flow message.
    
    WhatsApp Flows allow structured interactions like forms, surveys, appointments.
    Flows must be created and published in Meta Business Suite first.
    
    Test Event (navigate mode - opens flow directly):
    {
        "action": "send_flow",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "flowId": "123456789",
        "flowCta": "Book Appointment",
        "body": "Click below to book your appointment",
        "mode": "navigate",
        "flowScreen": "APPOINTMENT_SCREEN"
    }
    
    Test Event (draft mode - for testing unpublished flows):
    {
        "action": "send_flow",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "flowId": "123456789",
        "flowCta": "Start Survey",
        "body": "Please complete our feedback survey",
        "mode": "draft"
    }
    
    Test Event (with header and footer):
    {
        "action": "send_flow",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "flowId": "123456789",
        "flowCta": "Get Quote",
        "header": "Insurance Quote",
        "body": "Get a personalized insurance quote in minutes",
        "footer": "Powered by WECARE.DIGITAL",
        "mode": "navigate",
        "flowScreen": "QUOTE_FORM",
        "flowData": {"product_type": "health", "user_id": "12345"}
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    flow_id = event.get("flowId", "")
    flow_cta = event.get("flowCta", "Open")
    body = event.get("body", "")
    header = event.get("header", "")
    footer = event.get("footer", "")
    mode = event.get("mode", "navigate")  # "navigate" or "draft"
    flow_screen = event.get("flowScreen", "")
    flow_data = event.get("flowData", {})
    flow_token = event.get("flowToken", "")
    
    if not meta_waba_id or not to_number or not flow_id or not body:
        return {"statusCode": 400, "error": "metaWabaId, to, flowId, and body are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build flow action parameters
        flow_action: Dict[str, Any] = {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_id": flow_id,
                "flow_cta": flow_cta,
                "mode": mode,
            }
        }
        
        # Add optional flow parameters
        if flow_token:
            flow_action["parameters"]["flow_token"] = flow_token
        if flow_screen:
            flow_action["parameters"]["flow_action"] = "navigate"
            flow_action["parameters"]["flow_action_payload"] = {
                "screen": flow_screen,
            }
            if flow_data:
                flow_action["parameters"]["flow_action_payload"]["data"] = flow_data
        
        # Build interactive message
        interactive: Dict[str, Any] = {
            "type": "flow",
            "body": {"text": body},
            "action": flow_action,
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#FLOW#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "FLOW_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "type": "interactive",
            "interactiveType": "flow",
            "flowId": flow_id,
            "flowCta": flow_cta,
            "interactiveBody": body,
            "preview": f"[flow] {body[:80]}...",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_flow",
            "messageId": msg_id,
            "flowId": flow_id,
            "to": to_number,
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {"statusCode": 500, "error": f"{error_code}: {error_msg}"}
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_address_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an address collection message.
    
    Address messages allow collecting shipping/delivery addresses from users.
    Currently supported in India (IN) and Singapore (SG).
    
    Test Event:
    {
        "action": "send_address_message",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "body": "Please provide your delivery address",
        "country": "IN",
        "header": "Delivery Address",
        "footer": "Your address will be used for delivery only"
    }
    
    Test Event (with pre-filled values):
    {
        "action": "send_address_message",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "body": "Confirm or update your delivery address",
        "country": "IN",
        "values": {
            "name": "John Doe",
            "phone_number": "+919903300044",
            "in_pin_code": "700001",
            "city": "Kolkata",
            "state": "West Bengal"
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body = event.get("body", "")
    country = event.get("country", "IN")
    header = event.get("header", "")
    footer = event.get("footer", "")
    values = event.get("values", {})
    saved_addresses = event.get("savedAddresses", [])
    
    if not meta_waba_id or not to_number or not body:
        return {"statusCode": 400, "error": "metaWabaId, to, and body are required"}
    
    if country not in ["IN", "SG"]:
        return {"statusCode": 400, "error": "Address messages only supported in IN (India) and SG (Singapore)"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build action parameters
        action_params: Dict[str, Any] = {
            "country": country,
        }
        if values:
            action_params["values"] = values
        if saved_addresses:
            action_params["saved_addresses"] = saved_addresses
        
        # Build interactive message
        interactive: Dict[str, Any] = {
            "type": "address_message",
            "body": {"text": body},
            "action": {
                "name": "address_message",
                "parameters": action_params,
            },
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Store in DynamoDB
        now = iso_now()
        msg_id = response.get("messageId", "")
        msg_pk = f"MSG#ADDRESS#{msg_id}"
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): msg_pk,
            "itemType": "ADDRESS_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "type": "interactive",
            "interactiveType": "address_message",
            "country": country,
            "interactiveBody": body,
            "preview": f"[address] {body[:80]}...",
            "sentAt": now,
            "receivedAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_address_message",
            "messageId": msg_id,
            "country": country,
            "to": to_number,
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {"statusCode": 500, "error": f"{error_code}: {error_msg}"}
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_product(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a single product message from catalog.
    
    Requires a Facebook Commerce catalog linked to your WABA.
    
    Test Event:
    {
        "action": "send_product",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "catalogId": "123456789",
        "productRetailerId": "SKU-001",
        "body": "Check out this product!"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    catalog_id = event.get("catalogId", "")
    product_retailer_id = event.get("productRetailerId", "")
    body = event.get("body", "")
    footer = event.get("footer", "")
    
    if not meta_waba_id or not to_number or not catalog_id or not product_retailer_id:
        return {"statusCode": 400, "error": "metaWabaId, to, catalogId, and productRetailerId are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        interactive: Dict[str, Any] = {
            "type": "product",
            "action": {
                "catalog_id": catalog_id,
                "product_retailer_id": product_retailer_id,
            },
        }
        
        if body:
            interactive["body"] = {"text": body}
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        now = iso_now()
        msg_id = response.get("messageId", "")
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MSG#PRODUCT#{msg_id}",
            "itemType": "PRODUCT_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "type": "interactive",
            "interactiveType": "product",
            "catalogId": catalog_id,
            "productRetailerId": product_retailer_id,
            "sentAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_product",
            "messageId": msg_id,
            "catalogId": catalog_id,
            "productRetailerId": product_retailer_id,
            "to": to_number,
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {"statusCode": 500, "error": f"{error_code}: {error_msg}"}
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_product_list(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a multi-product message from catalog.
    
    Requires a Facebook Commerce catalog linked to your WABA.
    
    Test Event:
    {
        "action": "send_product_list",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "catalogId": "123456789",
        "header": "Our Products",
        "body": "Browse our collection",
        "sections": [
            {
                "title": "Popular Items",
                "productItems": [
                    {"productRetailerId": "SKU-001"},
                    {"productRetailerId": "SKU-002"}
                ]
            },
            {
                "title": "New Arrivals",
                "productItems": [
                    {"productRetailerId": "SKU-003"}
                ]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    catalog_id = event.get("catalogId", "")
    header = event.get("header", "")
    body = event.get("body", "")
    footer = event.get("footer", "")
    sections = event.get("sections", [])
    
    if not meta_waba_id or not to_number or not catalog_id or not sections:
        return {"statusCode": 400, "error": "metaWabaId, to, catalogId, and sections are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Convert sections to API format
        api_sections = []
        for section in sections:
            api_section = {
                "title": section.get("title", ""),
                "product_items": [
                    {"product_retailer_id": item.get("productRetailerId", item.get("product_retailer_id", ""))}
                    for item in section.get("productItems", section.get("product_items", []))
                ]
            }
            api_sections.append(api_section)
        
        interactive: Dict[str, Any] = {
            "type": "product_list",
            "action": {
                "catalog_id": catalog_id,
                "sections": api_sections,
            },
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if body:
            interactive["body"] = {"text": body}
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        now = iso_now()
        msg_id = response.get("messageId", "")
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MSG#PRODUCT_LIST#{msg_id}",
            "itemType": "PRODUCT_LIST_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "type": "interactive",
            "interactiveType": "product_list",
            "catalogId": catalog_id,
            "sectionCount": len(sections),
            "sentAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_product_list",
            "messageId": msg_id,
            "catalogId": catalog_id,
            "sectionCount": len(sections),
            "to": to_number,
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {"statusCode": 500, "error": f"{error_code}: {error_msg}"}
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_location_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a location request message.
    
    Prompts the user to share their current location.
    
    Test Event:
    {
        "action": "send_location_request",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "body": "Please share your location for delivery"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body = event.get("body", "")
    
    if not meta_waba_id or not to_number or not body:
        return {"statusCode": 400, "error": "metaWabaId, to, and body are required"}
    
    waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = waba_config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        interactive: Dict[str, Any] = {
            "type": "location_request_message",
            "body": {"text": body},
            "action": {"name": "send_location"},
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive,
        }
        
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        
        now = iso_now()
        msg_id = response.get("messageId", "")
        
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MSG#LOCATION_REQ#{msg_id}",
            "itemType": "LOCATION_REQUEST_MESSAGE",
            "direction": "OUTBOUND",
            "wabaMetaId": meta_waba_id,
            "to": to_number,
            "type": "interactive",
            "interactiveType": "location_request_message",
            "interactiveBody": body,
            "sentAt": now,
            "messageId": msg_id,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_location_request",
            "messageId": msg_id,
            "to": to_number,
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return {"statusCode": 500, "error": f"{error_code}: {error_msg}"}
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_ping(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Health check / ping endpoint.
    
    Test Event:
    {
        "action": "ping"
    }
    """
    return {
        "statusCode": 200,
        "operation": "ping",
        "status": "healthy",
        "timestamp": iso_now(),
        "version": "2.0.0",
        "features": {
            "markAsRead": bool(MARK_AS_READ_ENABLED),
            "reactEmoji": bool(REACT_EMOJI_ENABLED),
            "autoReply": bool(AUTO_REPLY_ENABLED),
            "emailNotification": bool(EMAIL_NOTIFICATION_ENABLED),
            "echoMediaBack": bool(ECHO_MEDIA_BACK),
            "forwardEnabled": bool(FORWARD_ENABLED),
        },
    }


def handle_list_actions(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List all available actions grouped by category.
    
    Test Event:
    {
        "action": "list_actions"
    }
    """
    actions_by_category = {
        "send_messages": [
            "send_text", "send_image", "send_video", "send_audio", "send_document",
            "send_media", "send_sticker", "send_location", "send_contact",
            "send_interactive", "send_cta_url", "send_reaction", "send_reply", "send_template", "bulk_send",
            "send_flow", "send_address_message", "send_product", "send_product_list", "send_location_request"
        ],
        "message_actions": [
            "mark_read", "remove_reaction", "delete_message", "resend_message", "retry_failed_messages"
        ],
        "conversation_actions": [
            "update_conversation", "mark_conversation_read", "archive_conversation", "unarchive_conversation"
        ],
        "media_management": [
            "upload_media", "download_media", "delete_media", "get_media_url", "validate_media", "get_supported_formats"
        ],
        "template_management": [
            "templates", "get_templates", "refresh_templates"
        ],
        "query_single": [
            "get_message", "get_message_by_wa_id", "get_conversation", "get_delivery_status"
        ],
        "query_lists": [
            "get_messages", "get_conversations", "get_conversation_messages",
            "get_archived_conversations", "get_failed_messages", "search_messages", "get_unread_count"
        ],
        "query_config": [
            "get_quality", "get_stats", "get_wabas", "get_phone_info",
            "get_infra", "get_media_types", "get_config"
        ],
        "export": [
            "export_messages"
        ],
        "refresh_sync": [
            "refresh_quality", "refresh_infra", "refresh_media_types", "refresh_templates"
        ],
        "utility": [
            "help", "ping", "list_actions", "get_best_practices"
        ],
    }
    
    # Add extended handlers if available
    if EXTENDED_HANDLERS_AVAILABLE and get_extended_actions_by_category:
        extended_categories = get_extended_actions_by_category()
        for category, actions in extended_categories.items():
            category_key = category.lower().replace(" ", "_").replace("&", "and")
            actions_by_category[f"extended_{category_key}"] = actions
    
    total_actions = sum(len(actions) for actions in actions_by_category.values())
    
    return {
        "statusCode": 200,
        "operation": "list_actions",
        "totalActions": total_actions,
        "categories": list(actions_by_category.keys()),
        "actionsByCategory": actions_by_category,
        "extendedHandlersAvailable": EXTENDED_HANDLERS_AVAILABLE,
    }


def handle_get_best_practices(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get best practices for using Lambda handlers.
    
    Test Event:
    {
        "action": "get_best_practices"
    }
    
    Or filter by category:
    {
        "action": "get_best_practices",
        "category": "media"
    }
    """
    category = event.get("category", "")
    
    best_practices = {
        "health_checks": {
            "tip": "Use 'ping' for health checks before operations",
            "why": "Verify Lambda is responsive and check enabled features before sending messages",
            "example": {"action": "ping"},
            "benefit": "Early detection of issues, feature status visibility",
            "priority": "HIGH",
        },
        "media_validation": {
            "tip": "Use 'validate_media' before uploading to check format/size",
            "why": "WhatsApp has strict media requirements - validate before upload to avoid failures",
            "example": {"action": "validate_media", "mimeType": "image/jpeg", "fileSizeBytes": 1048576},
            "benefit": "Avoid upload failures, better user experience",
            "priority": "HIGH",
            "supported_formats": {
                "audio": "AAC, AMR, MP3, M4A, OGG (max 16 MB)",
                "document": "TXT, PDF, XLS, XLSX, DOC, DOCX, PPT, PPTX (max 100 MB)",
                "image": "JPEG, PNG (max 5 MB, 8-bit RGB/RGBA)",
                "sticker": "WebP only (animated max 500 KB, static max 100 KB)",
                "video": "3GP, MP4 (max 16 MB, H.264 + AAC codec)",
            },
        },
        "convenience_wrappers": {
            "tip": "Use convenience wrappers (send_image, send_video, etc.) for cleaner code",
            "why": "Simpler API with automatic mediaType setting, less error-prone",
            "examples": {
                "send_image": {"action": "send_image", "metaWabaId": "xxx", "to": "+xxx", "s3Key": "path/image.jpg"},
                "send_video": {"action": "send_video", "metaWabaId": "xxx", "to": "+xxx", "s3Key": "path/video.mp4"},
                "send_audio": {"action": "send_audio", "metaWabaId": "xxx", "to": "+xxx", "s3Key": "path/audio.mp3"},
                "send_document": {"action": "send_document", "metaWabaId": "xxx", "to": "+xxx", "s3Key": "path/doc.pdf"},
            },
            "benefit": "Cleaner code, automatic type detection, fewer parameters",
            "priority": "MEDIUM",
        },
        "supported_formats_display": {
            "tip": "Use 'get_supported_formats' to show users what they can upload",
            "why": "Users need to know allowed file types and size limits before uploading",
            "example": {"action": "get_supported_formats", "category": "image"},
            "benefit": "Better UX, reduced support requests, fewer failed uploads",
            "priority": "MEDIUM",
        },
        "bulk_operations": {
            "tip": "Use 'bulk_send' for multiple recipients instead of looping send_text",
            "why": "Single Lambda invocation handles multiple messages efficiently",
            "example": {"action": "bulk_send", "metaWabaId": "xxx", "recipients": ["+111", "+222", "+333"], "type": "text", "text": "Hello!"},
            "benefit": "Better performance, reduced Lambda invocations, cost savings",
            "priority": "HIGH",
            "supports": ["text", "image", "video", "audio", "document", "template"],
        },
        "gsi_queries": {
            "tip": "Use GSI queries (get_conversation_messages) instead of scans for better performance",
            "why": "DynamoDB scans are expensive and slow; GSI queries are fast and efficient",
            "examples": {
                "conversation_messages": {"action": "get_conversation_messages", "phoneId": "xxx", "fromNumber": "447447840003"},
                "messages_by_direction": {"action": "get_messages", "direction": "INBOUND", "limit": 50},
            },
            "benefit": "10-100x faster queries, lower DynamoDB costs",
            "priority": "HIGH",
            "available_gsis": ["gsi_conversation", "gsi_from", "gsi_direction", "gsi_inbox"],
        },
        "error_handling": {
            "tip": "Use 'get_failed_messages' and 'retry_failed_messages' for error recovery",
            "why": "Messages can fail due to network issues, rate limits, or invalid numbers",
            "examples": {
                "get_failed": {"action": "get_failed_messages", "limit": 50},
                "retry_all": {"action": "retry_failed_messages", "limit": 10},
                "resend_one": {"action": "resend_message", "messageId": "wamid.xxx"},
            },
            "benefit": "Automatic error recovery, improved delivery rates",
            "priority": "HIGH",
        },
        "conversation_management": {
            "tip": "Use 'mark_conversation_read' to reset unread counts efficiently",
            "why": "Single operation marks all messages in conversation as read",
            "example": {"action": "mark_conversation_read", "phoneId": "xxx", "fromNumber": "447447840003"},
            "benefit": "Efficient unread count management, better inbox UX",
            "priority": "MEDIUM",
        },
        "archiving": {
            "tip": "Use 'archive_conversation' to organize old conversations",
            "why": "Keep active inbox clean while preserving conversation history",
            "examples": {
                "archive": {"action": "archive_conversation", "conversationPk": "CONV#phone#from"},
                "get_archived": {"action": "get_archived_conversations", "limit": 50},
                "unarchive": {"action": "unarchive_conversation", "conversationPk": "CONV#phone#from"},
            },
            "benefit": "Organized inbox, faster queries on active conversations",
            "priority": "LOW",
        },
        "export_backup": {
            "tip": "Use 'export_messages' for data backup and analysis",
            "why": "Export conversation data to S3 for backup, compliance, or analytics",
            "example": {"action": "export_messages", "conversationPk": "CONV#phone#from"},
            "benefit": "Data backup, compliance, offline analysis",
            "priority": "LOW",
        },
    }
    
    # Filter by category if specified
    if category:
        category_map = {
            "media": ["media_validation", "supported_formats_display", "convenience_wrappers"],
            "performance": ["bulk_operations", "gsi_queries"],
            "errors": ["error_handling"],
            "conversations": ["conversation_management", "archiving"],
            "utility": ["health_checks", "export_backup"],
        }
        
        if category not in category_map:
            return {
                "statusCode": 400,
                "error": f"Unknown category: {category}",
                "validCategories": list(category_map.keys()),
            }
        
        filtered = {k: best_practices[k] for k in category_map[category] if k in best_practices}
        return {
            "statusCode": 200,
            "operation": "get_best_practices",
            "category": category,
            "practices": filtered,
        }
    
    return {
        "statusCode": 200,
        "operation": "get_best_practices",
        "totalPractices": len(best_practices),
        "practices": best_practices,
        "categories": ["media", "performance", "errors", "conversations", "utility"],
        "priorityLevels": {
            "HIGH": "Critical for production use",
            "MEDIUM": "Recommended for better UX",
            "LOW": "Nice to have",
        },
    }


# =============================================================================
# EXTENDED HANDLERS SECTION - Business Profile, Marketing, Webhooks, Calling,
# Groups, Analytics, Catalogs, Payments, AWS EUM Media
# =============================================================================

# AWS EUM Supported Media Types (from AWS documentation)
EUM_SUPPORTED_MEDIA = {
    "audio": {"formats": ["audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"], "maxSizeMB": 16},
    "document": {"formats": ["text/plain", "application/pdf", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"], "maxSizeMB": 100},
    "image": {"formats": ["image/jpeg", "image/png"], "maxSizeMB": 5},
    "sticker": {"formats": ["image/webp"], "maxSizeKB": 500},
    "video": {"formats": ["video/mp4", "video/3gpp"], "maxSizeMB": 16},
}


def handle_get_business_profile(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get business profile details."""
    meta_waba_id = event.get("metaWabaId", "")
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    profile_pk = f"PROFILE#{meta_waba_id}"
    try:
        response = table().get_item(Key={str(MESSAGES_PK_NAME): profile_pk})
        cached = response.get("Item")
        if cached:
            return {"statusCode": 200, "operation": "get_business_profile", "profile": cached, "cached": True}
    except ClientError:
        pass
    
    profile_data = {
        str(MESSAGES_PK_NAME): profile_pk, "itemType": "BUSINESS_PROFILE", "wabaMetaId": meta_waba_id,
        "businessName": config.get("businessAccountName", ""), "phone": config.get("phone", ""),
        "phoneArn": phone_arn, "lastFetchedAt": iso_now(),
    }
    table().put_item(Item=profile_data)
    return {"statusCode": 200, "operation": "get_business_profile", "profile": profile_data, "cached": False}


def handle_update_business_profile(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update business profile details."""
    meta_waba_id = event.get("metaWabaId", "")
    data = event.get("data", {})
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    if not config.get("phoneArn"):
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    profile_pk = f"PROFILE#{meta_waba_id}"
    update_data = {str(MESSAGES_PK_NAME): profile_pk, "itemType": "BUSINESS_PROFILE", "wabaMetaId": meta_waba_id, "lastUpdatedAt": iso_now()}
    for field in ["about", "address", "description", "email", "websites", "vertical"]:
        if field in data:
            update_data[field] = data[field]
    table().put_item(Item=update_data)
    return {"statusCode": 200, "operation": "update_business_profile", "updated": True, "profilePk": profile_pk}


def handle_create_marketing_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a marketing message template."""
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    if not meta_waba_id or not template_name:
        return {"statusCode": 400, "error": "metaWabaId and templateName are required"}
    
    language = event.get("language", "en_US")
    category = event.get("category", "MARKETING")
    components = event.get("components", [])
    
    template_pk = f"TEMPLATE#{meta_waba_id}#{template_name}#{language}"
    template_data = {
        str(MESSAGES_PK_NAME): template_pk, "itemType": "TEMPLATE_DEFINITION", "wabaMetaId": meta_waba_id,
        "templateName": template_name, "language": language, "category": category,
        "components": components, "status": "PENDING", "createdAt": iso_now(),
    }
    table().put_item(Item=template_data)
    return {"statusCode": 200, "operation": "create_marketing_template", "templatePk": template_pk, "status": "PENDING"}


def handle_send_marketing_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a marketing message using approved template."""
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    if not meta_waba_id or not to_number or not template_name:
        return {"statusCode": 400, "error": "metaWabaId, to, and templateName are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    language_code = event.get("languageCode", "en_US")
    body_params = event.get("bodyParams", [])
    
    components = []
    if body_params:
        components.append({"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in body_params]})
    
    payload = {
        "messaging_product": "whatsapp", "to": format_wa_number(to_number), "type": "template",
        "template": {"name": template_name, "language": {"code": language_code}, "components": components}
    }
    
    try:
        resp = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION), message=json.dumps(payload).encode("utf-8"),
        )
        msg_id = resp.get("messageId", "")
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MSG#MARKETING#{msg_id}", "itemType": "MARKETING_MESSAGE",
            "direction": "OUTBOUND", "wabaMetaId": meta_waba_id, "to": to_number,
            "templateName": template_name, "messageId": msg_id, "sentAt": iso_now(),
        })
        return {"statusCode": 200, "operation": "send_marketing_message", "success": True, "messageId": msg_id}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_register_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Register webhook endpoint configuration."""
    meta_waba_id = event.get("metaWabaId", "")
    webhook_url = event.get("webhookUrl", "")
    verify_token = event.get("verifyToken", "")
    if not meta_waba_id or not webhook_url or not verify_token:
        return {"statusCode": 400, "error": "metaWabaId, webhookUrl, and verifyToken are required"}
    
    webhook_pk = f"WEBHOOK#{meta_waba_id}"
    table().put_item(Item={
        str(MESSAGES_PK_NAME): webhook_pk, "itemType": "WEBHOOK_CONFIG", "wabaMetaId": meta_waba_id,
        "webhookUrl": webhook_url, "verifyToken": verify_token, "status": "ACTIVE", "createdAt": iso_now(),
    })
    return {"statusCode": 200, "operation": "register_webhook", "webhookPk": webhook_pk, "status": "ACTIVE"}


def handle_process_wix_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Wix e-commerce webhook for order notifications."""
    meta_waba_id = event.get("metaWabaId", "")
    wix_event = event.get("wixEvent", {})
    if not meta_waba_id or not wix_event:
        return {"statusCode": 400, "error": "metaWabaId and wixEvent are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    order_id = wix_event.get("orderId", "")
    customer_phone = wix_event.get("customerPhone", "")
    customer_name = wix_event.get("customerName", "")
    order_total = wix_event.get("orderTotal", "")
    event_type = wix_event.get("eventType", "order_created")
    
    if not customer_phone:
        return {"statusCode": 400, "error": "customerPhone is required in wixEvent"}
    
    order_pk = f"WIX_ORDER#{order_id}"
    table().put_item(Item={
        str(MESSAGES_PK_NAME): order_pk, "itemType": "WIX_ORDER", "wabaMetaId": meta_waba_id,
        "orderId": order_id, "eventType": event_type, "customerPhone": customer_phone,
        "customerName": customer_name, "orderTotal": order_total, "receivedAt": iso_now(),
    })
    
    template_map = {"order_created": "order_confirmation", "order_shipped": "shipping_notification", "order_delivered": "delivery_confirmation"}
    template_name = template_map.get(event_type, "order_confirmation")
    
    payload = {
        "messaging_product": "whatsapp", "to": format_wa_number(customer_phone), "type": "template",
        "template": {"name": template_name, "language": {"code": "en_US"}, "components": [
            {"type": "body", "parameters": [{"type": "text", "text": customer_name}, {"type": "text", "text": order_id}, {"type": "text", "text": order_total}]}
        ]}
    }
    
    try:
        resp = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION), message=json.dumps(payload).encode("utf-8"),
        )
        return {"statusCode": 200, "operation": "process_wix_webhook", "orderId": order_id, "notificationSent": True, "messageId": resp.get("messageId", "")}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_initiate_call(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initiate a WhatsApp call (business-initiated)."""
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    if not meta_waba_id or not to_number:
        return {"statusCode": 400, "error": "metaWabaId and to are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    if not config.get("phoneArn"):
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    call_id = f"CALL_{iso_now().replace(':', '').replace('-', '').replace('.', '')}"
    call_pk = f"CALL#{call_id}"
    table().put_item(Item={
        str(MESSAGES_PK_NAME): call_pk, "itemType": "CALL", "callId": call_id, "wabaMetaId": meta_waba_id,
        "toNumber": to_number, "callType": event.get("callType", "business_initiated"),
        "agentId": event.get("agentId", ""), "status": "initiated", "initiatedAt": iso_now(),
    })
    return {"statusCode": 200, "operation": "initiate_call", "callId": call_id, "status": "initiated"}


def handle_get_call_logs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get call logs."""
    meta_waba_id = event.get("metaWabaId", "")
    limit = event.get("limit", 50)
    
    filter_expr = "itemType = :it"
    expr_values = {":it": "CALL"}
    if meta_waba_id:
        filter_expr += " AND wabaMetaId = :waba"
        expr_values[":waba"] = meta_waba_id
    
    response = table().scan(FilterExpression=filter_expr, ExpressionAttributeValues=expr_values, Limit=limit)
    return {"statusCode": 200, "operation": "get_call_logs", "count": len(response.get("Items", [])), "calls": response.get("Items", [])}


def handle_create_group(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a WhatsApp group."""
    meta_waba_id = event.get("metaWabaId", "")
    group_name = event.get("groupName", "")
    if not meta_waba_id or not group_name:
        return {"statusCode": 400, "error": "metaWabaId and groupName are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    if not config.get("phoneArn"):
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    group_id = f"GROUP_{iso_now().replace(':', '').replace('-', '').replace('.', '')}"
    group_pk = f"GROUP#{group_id}"
    participants = event.get("participants", [])
    
    table().put_item(Item={
        str(MESSAGES_PK_NAME): group_pk, "itemType": "GROUP", "groupId": group_id, "wabaMetaId": meta_waba_id,
        "groupName": group_name, "participants": [format_wa_number(p) for p in participants],
        "participantCount": len(participants), "createdAt": iso_now(), "status": "active",
    })
    return {"statusCode": 200, "operation": "create_group", "groupId": group_id, "participantCount": len(participants)}


def handle_get_groups(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all groups for a WABA."""
    meta_waba_id = event.get("metaWabaId", "")
    limit = event.get("limit", 50)
    
    filter_expr = "itemType = :it"
    expr_values = {":it": "GROUP"}
    if meta_waba_id:
        filter_expr += " AND wabaMetaId = :waba"
        expr_values[":waba"] = meta_waba_id
    
    response = table().scan(FilterExpression=filter_expr, ExpressionAttributeValues=expr_values, Limit=limit)
    return {"statusCode": 200, "operation": "get_groups", "count": len(response.get("Items", [])), "groups": response.get("Items", [])}


def handle_get_analytics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get comprehensive analytics for a WABA."""
    meta_waba_id = event.get("metaWabaId", "")
    if not meta_waba_id:
        return {"statusCode": 400, "error": "metaWabaId is required"}
    
    response = table().scan(
        FilterExpression="wabaMetaId = :waba AND itemType = :it",
        ExpressionAttributeValues={":waba": meta_waba_id, ":it": "MESSAGE"}, Limit=10000
    )
    items = response.get("Items", [])
    
    inbound = [i for i in items if i.get("direction") == "INBOUND"]
    outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
    
    return {
        "statusCode": 200, "operation": "get_analytics", "wabaMetaId": meta_waba_id,
        "analytics": {
            "totalMessages": len(items), "inboundMessages": len(inbound), "outboundMessages": len(outbound),
            "uniqueContacts": len(set(i.get("from", "") for i in items if i.get("from"))),
        }
    }


def handle_upload_catalog(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload product catalog."""
    meta_waba_id = event.get("metaWabaId", "")
    catalog_name = event.get("catalogName", "")
    products = event.get("products", [])
    if not meta_waba_id or not catalog_name or not products:
        return {"statusCode": 400, "error": "metaWabaId, catalogName, and products are required"}
    
    catalog_id = f"CATALOG_{iso_now().replace(':', '').replace('-', '').replace('.', '')}"
    catalog_pk = f"CATALOG#{meta_waba_id}#{catalog_id}"
    
    table().put_item(Item={
        str(MESSAGES_PK_NAME): catalog_pk, "itemType": "CATALOG", "catalogId": catalog_id,
        "wabaMetaId": meta_waba_id, "catalogName": catalog_name, "productCount": len(products),
        "createdAt": iso_now(), "status": "active",
    })
    
    for product in products:
        product_pk = f"PRODUCT#{catalog_id}#{product.get('retailerId', '')}"
        table().put_item(Item={
            str(MESSAGES_PK_NAME): product_pk, "itemType": "PRODUCT", "catalogId": catalog_id,
            "wabaMetaId": meta_waba_id, **product, "createdAt": iso_now(),
        })
    
    return {"statusCode": 200, "operation": "upload_catalog", "catalogId": catalog_id, "productCount": len(products)}


def handle_get_catalog_products(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get products from a catalog."""
    catalog_id = event.get("catalogId", "")
    if not catalog_id:
        return {"statusCode": 400, "error": "catalogId is required"}
    
    response = table().scan(
        FilterExpression="itemType = :it AND catalogId = :cid",
        ExpressionAttributeValues={":it": "PRODUCT", ":cid": catalog_id}, Limit=event.get("limit", 50)
    )
    return {"statusCode": 200, "operation": "get_catalog_products", "catalogId": catalog_id, "count": len(response.get("Items", [])), "products": response.get("Items", [])}


def handle_payment_onboarding(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Onboard payment gateway for a WABA."""
    meta_waba_id = event.get("metaWabaId", "")
    provider = event.get("provider", "")
    if not meta_waba_id or not provider:
        return {"statusCode": 400, "error": "metaWabaId and provider are required"}
    
    payment_config_pk = f"PAYMENT_CONFIG#{meta_waba_id}#{provider}"
    table().put_item(Item={
        str(MESSAGES_PK_NAME): payment_config_pk, "itemType": "PAYMENT_CONFIG", "wabaMetaId": meta_waba_id,
        "provider": provider, "webhookUrl": event.get("webhookUrl", ""), "status": "active", "onboardedAt": iso_now(),
    })
    return {"statusCode": 200, "operation": "payment_onboarding", "provider": provider, "status": "active"}


def handle_create_payment_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a payment request and send to customer."""
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    order_id = event.get("orderId", "")
    amount = event.get("amount", 0)
    if not meta_waba_id or not to_number or not order_id or not amount:
        return {"statusCode": 400, "error": "metaWabaId, to, orderId, and amount are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    payment_id = f"PAY_{iso_now().replace(':', '').replace('-', '').replace('.', '')}"
    payment_pk = f"PAYMENT#{payment_id}"
    currency = event.get("currency", "INR")
    payment_link = f"https://pay.example.com/{payment_id}"
    
    table().put_item(Item={
        str(MESSAGES_PK_NAME): payment_pk, "itemType": "PAYMENT", "paymentId": payment_id,
        "wabaMetaId": meta_waba_id, "customerPhone": to_number, "orderId": order_id,
        "amount": amount, "currency": currency, "status": "pending", "createdAt": iso_now(),
    })
    
    payload = {
        "messaging_product": "whatsapp", "to": format_wa_number(to_number), "type": "interactive",
        "interactive": {
            "type": "cta_url", "body": {"text": f"Payment Request\n\nOrder: {order_id}\nAmount: {currency} {amount}"},
            "action": {"name": "cta_url", "parameters": {"display_text": "Pay Now", "url": payment_link}}
        }
    }
    
    try:
        resp = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION), message=json.dumps(payload).encode("utf-8"),
        )
        return {"statusCode": 200, "operation": "create_payment_request", "paymentId": payment_id, "paymentLink": payment_link, "messageSent": True}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_payments(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get payments list."""
    meta_waba_id = event.get("metaWabaId", "")
    limit = event.get("limit", 50)
    
    filter_expr = "itemType = :it"
    expr_values = {":it": "PAYMENT"}
    if meta_waba_id:
        filter_expr += " AND wabaMetaId = :waba"
        expr_values[":waba"] = meta_waba_id
    
    response = table().scan(FilterExpression=filter_expr, ExpressionAttributeValues=expr_values, Limit=limit)
    items = response.get("Items", [])
    total_amount = sum(i.get("amount", 0) for i in items if i.get("status") == "completed")
    return {"statusCode": 200, "operation": "get_payments", "count": len(items), "totalCompletedAmount": total_amount, "payments": items}


def handle_eum_download_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Download media from WhatsApp to S3 using AWS EUM Social API."""
    meta_waba_id = event.get("metaWabaId", "")
    media_id = event.get("mediaId", "")
    if not meta_waba_id or not media_id:
        return {"statusCode": 400, "error": "metaWabaId and mediaId are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    s3_key = event.get("s3Key", f"{MEDIA_PREFIX}downloads/{media_id}_{iso_now().replace(':', '').replace('-', '')}")
    
    try:
        response = social().get_whatsapp_message_media(
            mediaId=media_id, originationPhoneNumberId=origination_id_for_api(phone_arn),
            destinationS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key}
        )
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MEDIA_DOWNLOAD#{media_id}", "itemType": "MEDIA_DOWNLOAD",
            "mediaId": media_id, "wabaMetaId": meta_waba_id, "s3Bucket": str(MEDIA_BUCKET),
            "s3Key": s3_key, "downloadedAt": iso_now(),
        })
        return {"statusCode": 200, "operation": "eum_download_media", "mediaId": media_id, "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_eum_upload_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload media from S3 to WhatsApp using AWS EUM Social API."""
    meta_waba_id = event.get("metaWabaId", "")
    s3_key = event.get("s3Key", "")
    if not meta_waba_id or not s3_key:
        return {"statusCode": 400, "error": "metaWabaId and s3Key are required"}
    
    config = WABA_PHONE_MAP.get(meta_waba_id, {})
    phone_arn = config.get("phoneArn", "")
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        response = social().post_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key}
        )
        media_id = response.get("mediaId", "")
        table().put_item(Item={
            str(MESSAGES_PK_NAME): f"MEDIA_UPLOAD#{media_id}", "itemType": "MEDIA_UPLOAD",
            "mediaId": media_id, "wabaMetaId": meta_waba_id, "s3Key": s3_key, "uploadedAt": iso_now(),
        })
        return {"statusCode": 200, "operation": "eum_upload_media", "mediaId": media_id, "s3Key": s3_key}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_eum_get_supported_formats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get AWS EUM supported media formats."""
    category = event.get("category", "")
    if category:
        if category not in EUM_SUPPORTED_MEDIA:
            return {"statusCode": 400, "error": f"Invalid category. Valid: {list(EUM_SUPPORTED_MEDIA.keys())}"}
        return {"statusCode": 200, "operation": "eum_get_supported_formats", "category": category, "formats": EUM_SUPPORTED_MEDIA[category]}
    return {"statusCode": 200, "operation": "eum_get_supported_formats", "supportedMedia": EUM_SUPPORTED_MEDIA, "note": "All formats comply with AWS EUM Social documentation recommendations for robust media handling"}


# All in all, we have integrated the AWS EUM Social documentation recommendations in our design for robust media handling.

# =============================================================================
# END OF EXTENDED HANDLERS SECTION
# =============================================================================


def handle_help(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get list of all available actions.
    
    Test Event:
    {
        "action": "help"
    }
    """
    actions = {
        # Send messages - specific types
        "send_text": "Send a text message",
        "send_image": "Send an image (convenience wrapper)",
        "send_video": "Send a video (convenience wrapper)",
        "send_audio": "Send an audio file (convenience wrapper)",
        "send_document": "Send a document (convenience wrapper)",
        "send_media": "Send image/video/audio/document (generic)",
        "send_sticker": "Send a sticker (WebP format)",
        "send_location": "Send a location with coordinates",
        "send_contact": "Send contact cards",
        "send_interactive": "Send buttons or list menus",
        "send_cta_url": "Send CTA URL button message",
        "send_flow": "Send WhatsApp Flow (forms, surveys, appointments)",
        "send_address_message": "Send address collection message (IN/SG only)",
        "send_product": "Send single product from catalog",
        "send_product_list": "Send multi-product list from catalog",
        "send_location_request": "Request user's location",
        "send_reaction": "Send emoji reaction to a message",
        "send_reply": "Reply to a specific message (with context/quote)",
        "send_template": "Send a pre-approved template message",
        "bulk_send": "Send messages to multiple recipients",
        # Message actions
        "mark_read": "Mark a message as read (blue check marks)",
        "remove_reaction": "Remove a reaction from a message",
        "delete_message": "Delete a message from DynamoDB",
        "resend_message": "Resend a failed message",
        "retry_failed_messages": "Retry all failed messages",
        # Media management
        "upload_media": "Upload S3 file to WhatsApp, get mediaId",
        "download_media": "Download media from WhatsApp to S3",
        "delete_media": "Delete uploaded media from WhatsApp",
        "get_media_url": "Get presigned URL for media in S3",
        "validate_media": "Validate if media file is supported by WhatsApp",
        "get_supported_formats": "Get all supported media formats with size limits",
        # Template management
        "templates": "Template admin (list, create, delete, get)",
        "get_templates": "Get templates for a WABA",
        "refresh_templates": "Force refresh templates",
        # Query data - single items
        "get_message": "Get a single message by ID",
        "get_message_by_wa_id": "Get message by WhatsApp message ID",
        "get_conversation": "Get a single conversation",
        "get_delivery_status": "Get delivery status for a message",
        # Query data - lists
        "get_messages": "Query messages from DynamoDB",
        "get_conversations": "Query conversations from DynamoDB",
        "get_conversation_messages": "Get all messages in a conversation",
        "get_archived_conversations": "Get archived conversations",
        "get_failed_messages": "Get messages with failed delivery",
        "search_messages": "Search messages by text content",
        "get_unread_count": "Get unread message count",
        # Query data - config/status
        "get_quality": "Get phone quality ratings",
        "get_stats": "Get message statistics",
        "get_wabas": "List linked WhatsApp Business Accounts",
        "get_phone_info": "Get phone number details",
        "get_infra": "Get infrastructure configuration",
        "get_media_types": "Get supported media types from DynamoDB",
        "get_config": "Get all Lambda configuration",
        # Update/modify conversations
        "update_conversation": "Update conversation (mark read, archive)",
        "mark_conversation_read": "Mark all messages in conversation as read",
        "archive_conversation": "Archive a conversation",
        "unarchive_conversation": "Unarchive a conversation",
        # Export
        "export_messages": "Export messages to S3 as JSON",
        # Refresh/sync
        "refresh_quality": "Force refresh phone quality rating",
        "refresh_infra": "Force refresh infrastructure config",
        "refresh_media_types": "Force refresh media types config",
        "refresh_templates": "Force refresh templates for a WABA",
        # Utility
        "ping": "Health check / ping endpoint",
        "list_actions": "List all actions grouped by category",
        "get_best_practices": "Get best practices for using handlers",
        "help": "Show this help message",
        # === EXTENDED HANDLERS ===
        # Business Profile
        "get_business_profile": "Get business profile details",
        "update_business_profile": "Update business profile details",
        # Marketing & Templates
        "create_marketing_template": "Create a marketing message template",
        "send_marketing_message": "Send marketing message using template",
        # Webhooks
        "register_webhook": "Register webhook endpoint configuration",
        "process_wix_webhook": "Process Wix e-commerce webhook",
        # Calling
        "initiate_call": "Initiate a WhatsApp call",
        "get_call_logs": "Get call logs",
        # Groups
        "create_group": "Create a WhatsApp group",
        "get_groups": "Get all groups for a WABA",
        # Analytics
        "get_analytics": "Get comprehensive analytics for a WABA",
        # Catalogs
        "upload_catalog": "Upload product catalog",
        "get_catalog_products": "Get products from a catalog",
        # Payments
        "payment_onboarding": "Onboard payment gateway",
        "create_payment_request": "Create payment request",
        "get_payments": "Get payments list",
        # AWS EUM Media
        "eum_download_media": "Download media using AWS EUM API",
        "eum_upload_media": "Upload media using AWS EUM API",
        "eum_get_supported_formats": "Get AWS EUM supported formats",
    }
    
    best_practices = {
        "health_checks": {
            "tip": "Use 'ping' for health checks before operations",
            "example": {"action": "ping"},
            "benefit": "Verify Lambda is responsive and check enabled features",
        },
        "media_validation": {
            "tip": "Use 'validate_media' before uploading to check format/size",
            "example": {"action": "validate_media", "mimeType": "image/jpeg", "fileSizeBytes": 1048576},
            "benefit": "Avoid upload failures by pre-validating media files",
        },
        "convenience_wrappers": {
            "tip": "Use convenience wrappers (send_image, send_video, etc.) for cleaner code",
            "example": {"action": "send_image", "metaWabaId": "xxx", "to": "+xxx", "s3Key": "path/to/image.jpg"},
            "benefit": "Simpler API calls with automatic mediaType setting",
        },
        "supported_formats": {
            "tip": "Use 'get_supported_formats' to show users what they can upload",
            "example": {"action": "get_supported_formats", "category": "image"},
            "benefit": "Display allowed file types and size limits to users",
        },
        "bulk_operations": {
            "tip": "Use 'bulk_send' for multiple recipients instead of looping send_text",
            "example": {"action": "bulk_send", "metaWabaId": "xxx", "recipients": ["+111", "+222"], "type": "text", "text": "Hello!"},
            "benefit": "Single Lambda invocation for multiple messages, better performance",
        },
        "gsi_queries": {
            "tip": "Use GSI queries (get_conversation_messages) instead of scans for better performance",
            "example": {"action": "get_conversation_messages", "phoneId": "xxx", "fromNumber": "447447840003"},
            "benefit": "Faster queries using DynamoDB Global Secondary Indexes",
        },
        "error_handling": {
            "tip": "Use 'get_failed_messages' and 'retry_failed_messages' for error recovery",
            "example": {"action": "retry_failed_messages", "limit": 10},
            "benefit": "Automatic retry of failed outbound messages",
        },
        "conversation_management": {
            "tip": "Use 'mark_conversation_read' to reset unread counts efficiently",
            "example": {"action": "mark_conversation_read", "phoneId": "xxx", "fromNumber": "447447840003"},
            "benefit": "Single operation to mark all messages in conversation as read",
        },
    }
    
    return {
        "statusCode": 200,
        "operation": "help",
        "totalActions": len(actions),
        "actions": actions,
        "bestPractices": best_practices,
        "usage": "Invoke Lambda with {\"action\": \"<action_name>\", ...params}",
        "examples": {
            "send_text": {"action": "send_text", "metaWabaId": "1347766229904230", "to": "+447447840003", "text": "Hello!"},
            "send_image": {"action": "send_image", "metaWabaId": "1347766229904230", "to": "+447447840003", "s3Key": "WhatsApp/test/image.jpg", "caption": "Check this out!"},
            "send_video": {"action": "send_video", "metaWabaId": "1347766229904230", "to": "+447447840003", "s3Key": "WhatsApp/test/video.mp4"},
            "send_audio": {"action": "send_audio", "metaWabaId": "1347766229904230", "to": "+447447840003", "s3Key": "WhatsApp/test/audio.mp3"},
            "send_document": {"action": "send_document", "metaWabaId": "1347766229904230", "to": "+447447840003", "s3Key": "WhatsApp/test/doc.pdf", "filename": "Report.pdf"},
            "send_media": {"action": "send_media", "metaWabaId": "1347766229904230", "to": "+447447840003", "mediaType": "image", "s3Key": "WhatsApp/test/image.jpg"},
            "send_reply": {"action": "send_reply", "metaWabaId": "1347766229904230", "to": "+447447840003", "replyToMessageId": "wamid.xxx", "text": "Reply text"},
            "bulk_send": {"action": "bulk_send", "metaWabaId": "1347766229904230", "recipients": ["+447447840003"], "type": "text", "text": "Hello!"},
            "validate_media": {"action": "validate_media", "mimeType": "image/jpeg", "fileSizeBytes": 1048576},
            "get_supported_formats": {"action": "get_supported_formats", "category": "image"},
            "get_message": {"action": "get_message", "messageId": "wamid.xxx"},
            "ping": {"action": "ping"},
            "list_actions": {"action": "list_actions"},
            "get_best_practices": {"action": "get_best_practices"},
        },
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.info("RAW_EVENT=%s", jdump(event))

    # ==========================================================================
    # HTTP PATH ROUTING - Short Links & Payments (Independent Handlers)
    # ==========================================================================
    # Route requests to independent handlers based on path
    # These handlers work independently and can be attached to any project
    # ==========================================================================
    http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", ""))
    raw_path = event.get("rawPath", event.get("path", ""))
    
    if raw_path:
        # Short Links: r.wecare.digital routes
        # /r/{code} - redirect, /r/create - create, /r/stats/{code} - stats
        if raw_path.startswith("/r/") or raw_path == "/r":
            from handlers.shortlinks import lambda_handler as shortlinks_handler
            return shortlinks_handler(event, context)
        
        # Payments: p.wecare.digital routes
        # /p/{id}, /p/pay/{id}, /p/test, /p/success, /p/create-link, /razorpay-webhook
        if raw_path.startswith("/p/") or raw_path == "/p" or raw_path == "/razorpay-webhook":
            from handlers.razorpay_api import lambda_handler as payments_handler
            return payments_handler(event, context)
        
        # Root path redirect to selfservice (for both r.wecare.digital and p.wecare.digital)
        if raw_path == "/" or raw_path == "":
            # Check host header to determine which domain
            headers = event.get("headers", {})
            host = headers.get("host", headers.get("Host", ""))
            
            redirect_url = "https://wecare.digital/selfservice"
            return {
                "statusCode": 302,
                "headers": {
                    "Location": redirect_url,
                    "Content-Type": "text/html",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": f'<html><head><meta http-equiv="refresh" content="0;url={redirect_url}"></head></html>',
            }
        
        # Check if this is an HTTP request from r.wecare.digital or p.wecare.digital
        # Unknown paths should redirect to selfservice (404 handling)
        headers = event.get("headers", {})
        host = headers.get("host", headers.get("Host", ""))
        if host and ("r.wecare.digital" in host or "p.wecare.digital" in host):
            redirect_url = "https://wecare.digital/selfservice"
            return {
                "statusCode": 302,
                "headers": {
                    "Location": redirect_url,
                    "Content-Type": "text/html",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": f'''<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Not Found - WECARE.DIGITAL</title>
<meta http-equiv="refresh" content="3;url={redirect_url}">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}.c{{background:#fff;border-radius:16px;padding:40px;max-width:400px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.3)}}.i{{font-size:64px;margin-bottom:20px}}h1{{color:#333;margin-bottom:10px}}p{{color:#666}}.r{{color:#999;font-size:12px;margin-top:20px}}a{{color:#667eea}}</style>
</head><body><div class="c"><div class="i">🔗</div><h1>Page Not Found</h1><p>The page you're looking for doesn't exist.</p><p class="r">Redirecting to <a href="{redirect_url}">WECARE.DIGITAL</a> in 3 seconds...</p></div></body></html>''',
            }

    # Detect if this is an API Gateway request
    is_api_gateway = "requestContext" in event or "body" in event
    
    # Handle API Gateway HTTP API event format
    # API Gateway sends body as string in event['body']
    if "body" in event and event.get("body"):
        body_str = event.get("body", "")
        if isinstance(body_str, str) and body_str.strip():
            try:
                body = json.loads(body_str)
                logger.info("PARSED_BODY=%s", jdump(body))
                
                # Handle SNS messages (SubscriptionConfirmation, Notification, UnsubscribeConfirmation)
                sns_type = body.get("Type")
                if sns_type == "SubscriptionConfirmation":
                    subscribe_url = body.get("SubscribeURL")
                    if subscribe_url:
                        logger.info(f"Confirming SNS subscription: {subscribe_url}")
                        try:
                            import urllib.request
                            urllib.request.urlopen(subscribe_url, timeout=10)
                            return api_response({"statusCode": 200, "message": "Subscription confirmed"})
                        except Exception as e:
                            logger.exception(f"Failed to confirm SNS subscription: {e}")
                            return api_response({"statusCode": 500, "error": str(e)}, 500)
                
                elif sns_type == "Notification":
                    # SNS Notification via HTTPS - extract the actual message
                    sns_message = body.get("Message", "")
                    if isinstance(sns_message, str):
                        try:
                            body = json.loads(sns_message)
                            logger.info("PARSED_SNS_MESSAGE=%s", jdump(body))
                        except json.JSONDecodeError:
                            pass  # Not JSON, keep original body
                
                # Merge body into event for action processing
                for key, value in body.items():
                    event[key] = value
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Failed to parse body: %s", str(e))

    # Check for admin/send actions FIRST (before processing SNS records)
    action = event.get("action", "")
    
    # Helper to wrap response for API Gateway
    def maybe_wrap(response: Dict[str, Any]) -> Dict[str, Any]:
        if is_api_gateway:
            return api_response(response)
        return response
    
    # Help
    if action == "help":
        return maybe_wrap(handle_help(event, context))
    
    # Template management
    elif action == "templates":
        return maybe_wrap(handle_template_action(event, context))
    elif action == "get_templates":
        return maybe_wrap(handle_get_templates(event, context))
    elif action == "refresh_templates":
        return maybe_wrap(handle_refresh_templates(event, context))
    
    # Send messages - specific types
    elif action == "send_template":
        return maybe_wrap(handle_send_template(event, context))
    elif action == "send_text":
        return maybe_wrap(handle_send_text(event, context))
    elif action == "send_image":
        return maybe_wrap(handle_send_image(event, context))
    elif action == "send_video":
        return maybe_wrap(handle_send_video(event, context))
    elif action == "send_audio":
        return maybe_wrap(handle_send_audio(event, context))
    elif action == "send_document":
        return maybe_wrap(handle_send_document(event, context))
    elif action == "send_media":
        return maybe_wrap(handle_send_media(event, context))
    elif action == "send_sticker":
        return maybe_wrap(handle_send_sticker(event, context))
    elif action == "send_reaction":
        return maybe_wrap(handle_send_reaction(event, context))
    elif action == "send_location":
        return maybe_wrap(handle_send_location(event, context))
    elif action == "send_contact":
        return maybe_wrap(handle_send_contact(event, context))
    elif action == "send_interactive":
        return maybe_wrap(handle_send_interactive(event, context))
    elif action == "send_cta_url":
        return maybe_wrap(handle_send_cta_url(event, context))
    elif action == "send_flow":
        return maybe_wrap(handle_send_flow(event, context))
    elif action == "send_address_message":
        return maybe_wrap(handle_send_address_message(event, context))
    elif action == "send_product":
        return maybe_wrap(handle_send_product(event, context))
    elif action == "send_product_list":
        return maybe_wrap(handle_send_product_list(event, context))
    elif action == "send_location_request":
        return maybe_wrap(handle_send_location_request(event, context))
    elif action == "send_reply":
        return maybe_wrap(handle_send_reply(event, context))
    elif action == "bulk_send":
        return maybe_wrap(handle_bulk_send(event, context))
    
    # Message actions
    elif action == "mark_read":
        return maybe_wrap(handle_mark_read(event, context))
    elif action == "remove_reaction":
        return maybe_wrap(handle_remove_reaction(event, context))
    elif action == "delete_message":
        return maybe_wrap(handle_delete_message(event, context))
    elif action == "resend_message":
        return maybe_wrap(handle_resend_message(event, context))
    elif action == "retry_failed_messages":
        return maybe_wrap(handle_retry_failed_messages(event, context))
    
    # Conversation actions
    elif action == "update_conversation":
        return maybe_wrap(handle_update_conversation(event, context))
    elif action == "mark_conversation_read":
        return maybe_wrap(handle_mark_conversation_read(event, context))
    elif action == "archive_conversation":
        return maybe_wrap(handle_archive_conversation(event, context))
    elif action == "unarchive_conversation":
        return maybe_wrap(handle_unarchive_conversation(event, context))
    
    # Media management
    elif action == "upload_media":
        return maybe_wrap(handle_upload_media(event, context))
    elif action == "download_media":
        return maybe_wrap(handle_download_media(event, context))
    elif action == "delete_media":
        return maybe_wrap(handle_delete_media(event, context))
    elif action == "get_media_url":
        return maybe_wrap(handle_get_media_url(event, context))
    elif action == "validate_media":
        return maybe_wrap(handle_validate_media(event, context))
    elif action == "get_supported_formats":
        return maybe_wrap(handle_get_supported_formats(event, context))
    
    # Query data - single items
    elif action == "get_message":
        return maybe_wrap(handle_get_message(event, context))
    elif action == "get_message_by_wa_id":
        return maybe_wrap(handle_get_message_by_wa_id(event, context))
    elif action == "get_conversation":
        return maybe_wrap(handle_get_conversation(event, context))
    elif action == "get_delivery_status":
        return maybe_wrap(handle_get_delivery_status(event, context))
    
    # Query data - lists
    elif action == "get_messages":
        return maybe_wrap(handle_get_messages(event, context))
    elif action == "get_conversations":
        return maybe_wrap(handle_get_conversations(event, context))
    elif action == "get_conversation_messages":
        return maybe_wrap(handle_get_conversation_messages(event, context))
    elif action == "get_archived_conversations":
        return maybe_wrap(handle_get_archived_conversations(event, context))
    elif action == "get_failed_messages":
        return maybe_wrap(handle_get_failed_messages(event, context))
    elif action == "search_messages":
        return maybe_wrap(handle_search_messages(event, context))
    elif action == "get_unread_count":
        return maybe_wrap(handle_get_unread_count(event, context))
    
    # Query data - config/status
    elif action == "get_quality":
        return maybe_wrap(handle_get_quality(event, context))
    elif action == "get_stats":
        return maybe_wrap(handle_get_stats(event, context))
    elif action == "get_wabas":
        return maybe_wrap(handle_get_wabas(event, context))
    elif action == "get_phone_info":
        return maybe_wrap(handle_get_phone_info(event, context))
    elif action == "get_infra":
        return maybe_wrap(handle_get_infra(event, context))
    elif action == "get_media_types":
        return maybe_wrap(handle_get_media_types(event, context))
    elif action == "get_config":
        return maybe_wrap(handle_get_config(event, context))
    
    # Export
    elif action == "export_messages":
        return maybe_wrap(handle_export_messages(event, context))
    
    # Refresh/sync
    elif action == "refresh_quality":
        return maybe_wrap(handle_refresh_quality(event, context))
    elif action == "refresh_infra":
        return maybe_wrap(handle_refresh_infra(event, context))
    elif action == "refresh_media_types":
        return maybe_wrap(handle_refresh_media_types(event, context))
    
    # Utility
    elif action == "ping":
        return maybe_wrap(handle_ping(event, context))
    elif action == "list_actions":
        return maybe_wrap(handle_list_actions(event, context))
    elif action == "get_best_practices":
        return maybe_wrap(handle_get_best_practices(event, context))
    
    # ==========================================================================
    # UNIFIED HANDLER DISPATCHER
    # ==========================================================================
    # All extended handlers (Business Profile, Marketing, Webhooks, Calling,
    # Groups, Analytics, Catalogs, Payments, AWS EUM Media) are handled here.
    # 
    # To add new handlers:
    # 1. Create handler in handlers/<feature>.py
    # 2. Import and add to EXTENDED_HANDLERS in handlers/extended.py
    # 3. Handler will automatically be available via unified_dispatch
    # ==========================================================================
    else:
        # Try unified dispatcher for all registered handlers
        result = unified_dispatch(action, event, context)
        if result is not None:
            return maybe_wrap(result)

    processed = 0
    media_downloads = 0
    replies_sent = 0
    statuses_processed = 0
    messages_marked_read = 0
    messages_reacted = 0

    records: List[Dict[str, Any]] = event.get("Records", []) or []
    for r in records:
        sns_record = (r or {}).get("Sns") or {}
        msg_obj = jload_maybe(sns_record.get("Message", ""))
        
        # Ensure msg_obj is a dict before calling .get()
        if not isinstance(msg_obj, dict):
            logger.warning(f"msg_obj is not a dict: {type(msg_obj)}")
            msg_obj = {}

        entry = jload_maybe(msg_obj.get("whatsAppWebhookEntry", "")) or {}
        waba_meta_id = str(entry.get("id", ""))
        account = lookup_account_by_waba_meta_id(waba_meta_id)

        phone_arn = ""
        if account:
            phone_arn = account.phone_arn
        else:
            ctx = msg_obj.get("context") or {}
            phones = ctx.get("MetaPhoneNumberIds") or []
            if phones and isinstance(phones[0], dict):
                phone_arn = phones[0].get("arn", "")

        received_at = sns_record.get("Timestamp") or iso_now()

        changes = entry.get("changes") or []
        for ch in changes:
            value = (ch or {}).get("value") or {}
            meta = value.get("metadata") or {}
            meta_phone_number_id = str(meta.get("phone_number_id", ""))
            
            # Get sender name from contacts
            contacts = value.get("contacts") or []
            sender_name = ""
            if contacts and isinstance(contacts[0], dict):
                profile = contacts[0].get("profile") or {}
                sender_name = profile.get("name", "")

            messages = value.get("messages") or []
            for m in messages:
                if not isinstance(m, dict):
                    continue

                processed += 1

                from_wa = str(m.get("from", "unknown"))
                wa_msg_id = str(m.get("id", sns_record.get("MessageId", "unknown")))
                mtype = str(m.get("type", "unknown"))
                wa_ts = str(m.get("timestamp", ""))

                msg_pk = f"MSG#{wa_msg_id}"
                conv_pk = f"CONV#{arn_suffix(phone_arn)}#{from_wa}"

                text_body = ""
                caption = ""
                filename = ""
                inbound_media_id = ""
                mime_type = ""

                if mtype == "text":
                    text_body = ((m.get("text") or {}).get("body")) or ""

                if mtype in {"image", "video", "audio", "document", "sticker"}:
                    media_block = m.get(mtype) or {}
                    inbound_media_id = media_block.get("id") or ""
                    mime_type = media_block.get("mime_type") or ""
                    caption = media_block.get("caption") or ""
                    filename = media_block.get("filename") or ""

                prev = preview(mtype, text_body, caption)

                s3_key = ""
                s3_uri = ""
                if inbound_media_id and phone_arn:
                    ext = mime_to_ext(mime_type)
                    s3_key = (
                        f"{MEDIA_PREFIX}"
                        f"business={safe(account.business_name if account else 'unknown')}/"
                        f"wabaMetaId={safe(waba_meta_id)}/"
                        f"phone={safe(arn_suffix(phone_arn))}/"
                        f"from={safe(from_wa)}/"
                        f"waMessageId={safe(wa_msg_id)}/"
                        f"mediaId={safe(inbound_media_id)}{ext}"
                    )
                    download_media_to_s3(inbound_media_id, phone_arn, s3_key)
                    media_downloads += 1
                    s3_uri = f"s3://{MEDIA_BUCKET}/{s3_key}"

                # Save message to DynamoDB (INBOUND message)
                item: Dict[str, Any] = {
                    str(MESSAGES_PK_NAME): msg_pk,
                    "itemType": "MESSAGE",
                    "direction": "INBOUND",  # Message received from customer
                    "receivedAt": received_at,
                    "waTimestamp": wa_ts,
                    "from": from_wa,
                    "to": account.phone if account else "",  # Our WABA number
                    "fromPk": from_wa,
                    "senderName": sender_name,
                    "originationPhoneNumberId": phone_arn,
                    "wabaMetaId": waba_meta_id,
                    "businessAccountName": account.business_name if account else "",
                    "businessPhone": account.phone if account else "",
                    "meta_phone_number_id": meta_phone_number_id or (account.meta_phone_number_id if account else ""),
                    "conversationPk": conv_pk,
                    "type": mtype,
                    "preview": prev,
                    "textBody": text_body,
                    "caption": caption,
                    "filename": filename,
                    "mediaId": inbound_media_id,
                    "mimeType": mime_type,
                    "s3Bucket": str(MEDIA_BUCKET) if s3_key else "",
                    "s3Key": s3_key,
                    "s3Uri": s3_uri,
                    "snsMessageId": sns_record.get("MessageId", ""),
                    "snsTopicArn": sns_record.get("TopicArn", ""),
                }
                put_message_item(item)

                # Mark message as read (blue check marks for sender)
                if phone_arn and wa_msg_id and MARK_AS_READ_ENABLED:
                    mark_message_as_read(phone_arn, wa_msg_id, msg_pk)
                    messages_marked_read += 1

                # React to message with emoji (based on message type)
                if phone_arn and from_wa and wa_msg_id and REACT_EMOJI_ENABLED:
                    react_with_emoji(phone_arn, from_wa, wa_msg_id, msg_pk, mtype)
                    messages_reacted += 1

                # Update conversation
                convo_update = {
                    "receivedAt": received_at,
                    "businessAccountName": account.business_name if account else "",
                    "businessPhone": account.phone if account else "",
                    "meta_phone_number_id": meta_phone_number_id or (account.meta_phone_number_id if account else ""),
                    "lastMessagePk": msg_pk,
                    "lastMessageId": wa_msg_id,
                    "lastType": mtype,
                    "lastPreview": prev,
                    "lastS3Uri": s3_uri,
                }
                upsert_conversation_item(conv_pk, phone_arn, from_wa, convo_update)

                # Send auto-reply text
                if phone_arn and from_wa and AUTO_REPLY_ENABLED:
                    send_text_reply(phone_arn, from_wa, wa_msg_id)
                    replies_sent += 1

                # Echo media back to sender
                if phone_arn and from_wa and ECHO_MEDIA_BACK and inbound_media_id and s3_key:
                    if mtype in {"image", "video", "audio", "document", "sticker"}:
                        up = upload_s3_media_to_whatsapp(phone_arn, s3_key)
                        out_media_id = up.get("mediaId") or ""
                        if out_media_id:
                            echo_caption = f"✅ Received your {mtype}!"
                            send_media_message(phone_arn, from_wa, mtype, out_media_id, 
                                                           caption=echo_caption, filename=filename)
                            replies_sent += 1

                # Send email notification
                if EMAIL_NOTIFICATION_ENABLED:
                    media_url = generate_s3_presigned_url(str(MEDIA_BUCKET), s3_key) if s3_key else ""
                    message_content = text_body or caption or ""
                    send_email_notification(
                        sender_name=sender_name,
                        sender_number=from_wa,
                        message_text=message_content,
                        media_url=media_url,
                        business_name=account.business_name if account else "Unknown",
                        message_type=mtype,
                        received_at=received_at
                    )

                # Forward media to another number (optional)
                if FORWARD_ENABLED and FORWARD_TO_WA_ID and inbound_media_id and phone_arn and s3_key:
                    up = upload_s3_media_to_whatsapp(phone_arn, s3_key)
                    out_media_id = up.get("mediaId") or ""
                    if out_media_id:
                        send_media_message(phone_arn, str(FORWARD_TO_WA_ID), mtype, out_media_id, 
                                                       caption=caption, filename=filename)
                        delete_uploaded_media(phone_arn, out_media_id)

                # =============================================================
                # WELCOME MESSAGE & MENU AUTO-SEND
                # =============================================================
                # Check if we should send welcome message (first contact or cooldown expired)
                if WELCOME_ENABLED and waba_meta_id and from_wa:
                    try:
                        from handlers.welcome_menu import handle_check_auto_welcome
                        welcome_result = handle_check_auto_welcome({
                            "metaWabaId": waba_meta_id,
                            "from": from_wa,
                        }, context)
                        if welcome_result.get("sent"):
                            logger.info(f"Welcome message sent to {from_wa}")
                            replies_sent += 1
                    except Exception as e:
                        logger.warning(f"Failed to send welcome message: {e}")

                # Check if message matches menu keywords (menu, help, start, etc.)
                if MENU_ON_KEYWORDS_ENABLED and waba_meta_id and from_wa and text_body:
                    try:
                        from handlers.welcome_menu import handle_check_auto_menu
                        menu_result = handle_check_auto_menu({
                            "metaWabaId": waba_meta_id,
                            "from": from_wa,
                            "messageText": text_body,
                        }, context)
                        if menu_result.get("sent"):
                            logger.info(f"Menu sent to {from_wa} (keyword: {text_body})")
                            replies_sent += 1
                    except Exception as e:
                        logger.warning(f"Failed to send menu: {e}")

                # =============================================================
                # BEDROCK AI AUTO-REPLY
                # =============================================================
                # Send message to Bedrock for AI-powered response
                if BEDROCK_AUTO_REPLY_ENABLED and waba_meta_id and from_wa and text_body:
                    try:
                        # Invoke Bedrock worker via SQS (async)
                        sqs = boto3.client("sqs")
                        queue_url = os.environ.get("BEDROCK_QUEUE_URL", "")
                        if queue_url:
                            sqs.send_message(
                                QueueUrl=queue_url,
                                MessageBody=json.dumps({
                                    "action": "bedrock_reply",
                                    "metaWabaId": waba_meta_id,
                                    "from": from_wa,
                                    "messageText": text_body,
                                    "messageId": wa_msg_id,
                                    "senderName": sender_name,
                                }),
                            )
                            logger.info(f"Bedrock request queued for {from_wa}")
                    except Exception as e:
                        logger.warning(f"Failed to queue Bedrock request: {e}")

            # Process message status updates (delivery receipts)
            statuses = value.get("statuses") or []
            for s in statuses:
                if not isinstance(s, dict):
                    continue
                
                # Extract status fields
                wa_msg_id = str(s.get("id", ""))
                status = str(s.get("status", ""))
                status_ts = str(s.get("timestamp", ""))
                recipient_id = str(s.get("recipient_id", ""))
                
                if not wa_msg_id or not status:
                    continue
                
                # Extract errors if present (for failed status)
                errors = s.get("errors") or []
                error_list = []
                for err in errors:
                    if isinstance(err, dict):
                        error_list.append({
                            "code": err.get("code", ""),
                            "title": err.get("title", ""),
                            "message": err.get("message", ""),
                            "error_data": err.get("error_data", {}),
                        })
                
                # Update message status in DynamoDB
                update_message_status(
                    wa_msg_id=wa_msg_id,
                    status=status,
                    status_timestamp=status_ts,
                    recipient_id=recipient_id,
                    errors=error_list if error_list else None
                )
                statuses_processed += 1
                
                logger.info(f"Status update: msgId={wa_msg_id} status={status} recipient={recipient_id}")

    # Update phone quality rating and templates (once per invocation if we processed messages)
    # Track which phone numbers we've already checked this invocation
    quality_checked = set()
    templates_checked = set()
    
    for r in records:
        sns_record = (r or {}).get("Sns") or {}
        msg_obj = jload_maybe(sns_record.get("Message", "")) or {}
        
        # Ensure msg_obj is a dict before calling .get()
        if not isinstance(msg_obj, dict):
            continue
        
        entry = jload_maybe(msg_obj.get("whatsAppWebhookEntry", "")) or {}
        waba_meta_id = str(entry.get("id", ""))
        
        if not waba_meta_id or waba_meta_id in quality_checked:
            continue
        
        account = lookup_account_by_waba_meta_id(waba_meta_id)
        if account:
            quality_checked.add(waba_meta_id)
            phone_number_id = arn_suffix(account.phone_arn)
            
            # Update quality rating
            quality_result = update_phone_quality_rating(
                waba_id=waba_meta_id,
                phone_number_id=phone_number_id,
                business_name=account.business_name,
                phone_number=account.phone
            )
            
            # Update templates (using WABA AWS ID from quality check)
            waba_aws_id = quality_result.get("wabaAwsId") if quality_result else None
            if not waba_aws_id:
                # Try to find WABA AWS ID
                try:
                    response = social().list_linked_whatsapp_business_accounts()
                    for acc in response.get('linkedAccounts', []):
                        if acc.get('wabaId') == waba_meta_id:
                            waba_aws_id = acc.get('id')
                            break
                except Exception:
                    pass
            
            if waba_aws_id and waba_aws_id not in templates_checked:
                templates_checked.add(waba_aws_id)
                update_message_templates(
                    waba_aws_id=waba_aws_id,
                    waba_meta_id=waba_meta_id,
                    business_name=account.business_name
                )

    # Update infrastructure config (VPC endpoint, service-linked role) - once per invocation
    if processed > 0 or statuses_processed > 0:
        update_infrastructure_config()
        update_media_types_config()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed, 
            "mediaDownloads": media_downloads, 
            "repliesSent": replies_sent,
            "statusesProcessed": statuses_processed,
            "messagesMarkedRead": messages_marked_read,
            "messagesReacted": messages_reacted,
            "qualityChecked": len(quality_checked),
            "templatesChecked": len(templates_checked)
        }),
    }
