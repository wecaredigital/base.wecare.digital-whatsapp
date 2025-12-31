# S3 Path Generation for WhatsApp Media
# Centralized S3 path generation with WABA-based folder structure and UUID security
#
# S3 Structure:
#   s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}  (inbound)
#   s3://dev.wecare.digital/WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}    (outbound)

import uuid
import os
from typing import Optional

# WABA to folder name mapping
WABA_FOLDER_MAP = {
    "1347766229904230": "wecare",   # WECARE.DIGITAL
    "1390647332755815": "manish",   # Manish Agarwal
}

# Environment config
MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "dev.wecare.digital")
MEDIA_PREFIX = os.environ.get("MEDIA_PREFIX", "WhatsApp/")

# MIME type to extension mapping
MIME_TO_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
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
}


def get_waba_folder(meta_waba_id: str) -> str:
    """Get folder name for WABA. Returns mapped name or sanitized fallback."""
    if meta_waba_id in WABA_FOLDER_MAP:
        return WABA_FOLDER_MAP[meta_waba_id]
    # Fallback to last 6 chars of WABA ID
    return f"waba_{meta_waba_id[-6:]}" if meta_waba_id else "unknown"


def mime_to_ext(mime_type: Optional[str]) -> str:
    """Convert MIME type to file extension."""
    if not mime_type:
        return ""
    return MIME_TO_EXT.get(mime_type, "")


def generate_secure_filename(base_name: str = "file", mime_type: str = None) -> str:
    """Generate secure filename with UUID to prevent URL guessing.
    
    Format: {base_name}_{uuid}.{ext}
    Example: image_a1b2c3d4e5f6.jpg
    """
    unique_id = uuid.uuid4().hex[:12]  # 12 char hex = 48 bits of randomness
    ext = mime_to_ext(mime_type)
    
    if base_name:
        # Sanitize base name - keep only alphanumeric, dash, underscore
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)[:30]
        return f"{safe_name}_{unique_id}{ext}"
    return f"file_{unique_id}{ext}"


def generate_download_path(meta_waba_id: str, filename: str = "media", mime_type: str = None) -> str:
    """Generate S3 key for downloading inbound media.
    
    Path: WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    """
    waba_folder = get_waba_folder(meta_waba_id)
    secure_filename = generate_secure_filename(filename, mime_type)
    return f"{MEDIA_PREFIX}download/{waba_folder}/{secure_filename}"


def generate_upload_path(meta_waba_id: str, filename: str = "media", mime_type: str = None) -> str:
    """Generate S3 key for uploading outbound media.
    
    Path: WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}
    """
    waba_folder = get_waba_folder(meta_waba_id)
    secure_filename = generate_secure_filename(filename, mime_type)
    return f"{MEDIA_PREFIX}upload/{waba_folder}/{secure_filename}"


def generate_s3_path(meta_waba_id: str, direction: str = "download", 
                     filename: str = "media", mime_type: str = None) -> dict:
    """Generate complete S3 path info for media.
    
    Args:
        meta_waba_id: WABA ID (e.g., "1347766229904230")
        direction: "download" (inbound) or "upload" (outbound)
        filename: Base filename (will be sanitized)
        mime_type: MIME type for extension
    
    Returns:
        dict with bucket, key, uri, folder info
    """
    waba_folder = get_waba_folder(meta_waba_id)
    secure_filename = generate_secure_filename(filename, mime_type)
    s3_key = f"{MEDIA_PREFIX}{direction}/{waba_folder}/{secure_filename}"
    
    return {
        "bucket": MEDIA_BUCKET,
        "key": s3_key,
        "uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
        "wabaFolder": waba_folder,
        "direction": direction,
        "secureFilename": secure_filename,
    }
