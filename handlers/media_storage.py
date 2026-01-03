# =============================================================================
# MEDIA STORAGE HANDLER - Wecare Digital Direct Messaging
# =============================================================================
# Handles media storage for WhatsApp, SMS, Voice, Email
# 
# Bucket: d.wecare.digital
# Structure:
#   d/ - Inbound media (received from users)
#   u/ - Outbound media (sent to users)
#
# Key format: {direction}/{source}-{uuid1}{uuid2}-{filename}
# Example: d/wa-in-abc123def456-image.jpg
# =============================================================================

import boto3
import uuid
import logging
import mimetypes
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
CONFIG = {
    "bucket": "d.wecare.digital",
    "region": "ap-south-1",
    "cdn_domain": "d.wecare.digital",
}

# Source prefixes
SOURCE_PREFIXES = {
    "whatsapp_in": "wa-in",
    "whatsapp_out": "wa-out",
    "ses_in": "ses-in",
    "ses_out": "ses-out",
    "email_in": "email-in",
    "email_out": "email-out",
    "sms_out": "sms-out",
    "voice_out": "voice-out",
    "unknown": "unknown",
}


def generate_key(
    direction: str,
    source: str,
    filename: str,
    extension: Optional[str] = None
) -> str:
    """Generate a unique, unguessable S3 key.
    
    Args:
        direction: 'inbound' or 'outbound'
        source: Source identifier (whatsapp, ses, email, sms, voice)
        filename: Original filename or description
        extension: File extension (optional, extracted from filename if not provided)
    
    Returns:
        S3 key in format: {d|u}/{prefix}-{uuid1}{uuid2}-{filename}
    """
    # Determine folder
    folder = "d" if direction == "inbound" else "u"
    
    # Determine source prefix
    if direction == "inbound":
        prefix_key = f"{source}_in"
    else:
        prefix_key = f"{source}_out"
    
    prefix = SOURCE_PREFIXES.get(prefix_key, SOURCE_PREFIXES["unknown"])
    
    # Generate double UUID for unguessability
    uuid1 = uuid.uuid4().hex
    uuid2 = uuid.uuid4().hex
    
    # Clean filename - remove path separators, keep extension
    clean_name = filename.replace("/", "-").replace("\\", "-")
    if not extension:
        extension = clean_name.split(".")[-1] if "." in clean_name else "bin"
    
    # Build key (flat, no subfolders after d/ or u/)
    key = f"{folder}/{prefix}-{uuid1}{uuid2}-{clean_name}"
    
    return key


def store_media(
    data: bytes,
    direction: str,
    source: str,
    filename: str,
    mime_type: Optional[str] = None,
    metadata: Optional[Dict] = None,
    whatsapp_identity: Optional[str] = None,
    message_id: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> Dict:
    """Store media file in S3 with proper structure and metadata.
    
    Args:
        data: File content as bytes
        direction: 'inbound' or 'outbound'
        source: Source (whatsapp, ses, email, sms, voice)
        filename: Original filename
        mime_type: MIME type (auto-detected if not provided)
        metadata: Additional metadata dict
        whatsapp_identity: 'manish' or 'wecare-digital'
        message_id: Message ID if available
        conversation_id: Conversation ID if available
    
    Returns:
        Dict with key, url, and metadata
    """
    s3 = boto3.client("s3", region_name=CONFIG["region"])
    
    # Generate key
    key = generate_key(direction, source, filename)
    
    # Auto-detect MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"
    
    # Build S3 metadata
    s3_metadata = {
        "direction": direction,
        "source": source,
        "mime-type": mime_type,
        "created-at": datetime.utcnow().isoformat(),
        "original-filename": filename[:256],  # S3 metadata limit
    }
    
    if whatsapp_identity:
        s3_metadata["whatsapp-identity"] = whatsapp_identity
    if message_id:
        s3_metadata["message-id"] = message_id[:256]
    if conversation_id:
        s3_metadata["conversation-id"] = conversation_id[:256]
    if metadata:
        for k, v in metadata.items():
            s3_metadata[k.replace("_", "-")[:128]] = str(v)[:256]
    
    # Upload to S3
    s3.put_object(
        Bucket=CONFIG["bucket"],
        Key=key,
        Body=data,
        ContentType=mime_type,
        Metadata=s3_metadata,
        # Set content disposition for proper downloads
        ContentDisposition=f'inline; filename="{filename}"'
    )
    
    # Generate URL
    url = f"https://{CONFIG['cdn_domain']}/{key}"
    
    logger.info(f"Stored media: {key} ({mime_type}, {len(data)} bytes)")
    
    return {
        "key": key,
        "url": url,
        "bucket": CONFIG["bucket"],
        "mime_type": mime_type,
        "size": len(data),
        "direction": direction,
        "source": source,
        "metadata": s3_metadata
    }


def store_inbound_whatsapp(
    data: bytes,
    filename: str,
    mime_type: Optional[str] = None,
    whatsapp_identity: str = "wecare-digital",
    message_id: Optional[str] = None
) -> Dict:
    """Store inbound WhatsApp media (received from user)."""
    return store_media(
        data=data,
        direction="inbound",
        source="whatsapp",
        filename=filename,
        mime_type=mime_type,
        whatsapp_identity=whatsapp_identity,
        message_id=message_id
    )


def store_outbound_whatsapp(
    data: bytes,
    filename: str,
    mime_type: Optional[str] = None,
    whatsapp_identity: str = "wecare-digital",
    message_id: Optional[str] = None
) -> Dict:
    """Store outbound WhatsApp media (sent to user)."""
    return store_media(
        data=data,
        direction="outbound",
        source="whatsapp",
        filename=filename,
        mime_type=mime_type,
        whatsapp_identity=whatsapp_identity,
        message_id=message_id
    )


def store_voice_audio(
    data: bytes,
    filename: str = "voice.mp3",
    message_id: Optional[str] = None
) -> Dict:
    """Store voice TTS audio (always outbound)."""
    return store_media(
        data=data,
        direction="outbound",
        source="voice",
        filename=filename,
        mime_type="audio/mpeg",
        message_id=message_id
    )


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for secure access.
    
    Args:
        key: S3 object key
        expires_in: URL expiration in seconds (default 1 hour)
    
    Returns:
        Presigned URL string
    """
    s3 = boto3.client("s3", region_name=CONFIG["region"])
    
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": CONFIG["bucket"], "Key": key},
        ExpiresIn=expires_in
    )
    
    return url


def get_media_metadata(key: str) -> Optional[Dict]:
    """Get metadata for a stored media file.
    
    Args:
        key: S3 object key
    
    Returns:
        Metadata dict or None if not found
    """
    s3 = boto3.client("s3", region_name=CONFIG["region"])
    
    try:
        response = s3.head_object(Bucket=CONFIG["bucket"], Key=key)
        return {
            "key": key,
            "size": response["ContentLength"],
            "mime_type": response["ContentType"],
            "last_modified": response["LastModified"].isoformat(),
            "metadata": response.get("Metadata", {})
        }
    except s3.exceptions.ClientError:
        return None


def list_media(direction: str = None, prefix: str = None, limit: int = 100) -> list:
    """List media files.
    
    Args:
        direction: 'inbound' or 'outbound' (optional)
        prefix: Additional prefix filter (optional)
        limit: Max results (default 100)
    
    Returns:
        List of media objects
    """
    s3 = boto3.client("s3", region_name=CONFIG["region"])
    
    # Build prefix
    if direction == "inbound":
        s3_prefix = "d/"
    elif direction == "outbound":
        s3_prefix = "u/"
    else:
        s3_prefix = ""
    
    if prefix:
        s3_prefix += prefix
    
    response = s3.list_objects_v2(
        Bucket=CONFIG["bucket"],
        Prefix=s3_prefix,
        MaxKeys=limit
    )
    
    objects = []
    for obj in response.get("Contents", []):
        objects.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": obj["LastModified"].isoformat(),
            "url": f"https://{CONFIG['cdn_domain']}/{obj['Key']}"
        })
    
    return objects
