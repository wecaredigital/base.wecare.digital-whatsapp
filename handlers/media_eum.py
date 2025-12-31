# AWS EUM Social Media Handlers
# Ref: https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-media-files-s3.html
# Ref: https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_GetWhatsAppMessageMedia.html
# Ref: https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/post-whatsapp-message-media.html

import json
import logging
import uuid
from typing import Any, Dict
from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    iso_now, store_item, get_item, validate_required_fields,
    get_phone_arn, get_business_name, origination_id_for_api, mime_to_ext
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# WABA to folder name mapping
# S3 Structure:
#   s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
#   s3://dev.wecare.digital/WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}
WABA_FOLDER_MAP = {
    "1347766229904230": "wecare",   # WECARE.DIGITAL
    "1390647332755815": "manish",   # Manish Agarwal
}


def _get_waba_folder(meta_waba_id: str) -> str:
    """Get folder name for WABA. Returns sanitized business name if not in map."""
    if meta_waba_id in WABA_FOLDER_MAP:
        return WABA_FOLDER_MAP[meta_waba_id]
    # Fallback to sanitized business name
    biz_name = get_business_name(meta_waba_id)
    if biz_name:
        return biz_name.lower().replace(" ", "_").replace(".", "")[:20]
    return f"waba_{meta_waba_id[-6:]}"


def _generate_secure_filename(base_name: str, mime_type: str = None) -> str:
    """Generate secure filename with UUID to prevent guessing.
    
    Format: {base_name}_{uuid}.{ext}
    Example: image_a1b2c3d4e5f6.jpg
    """
    unique_id = uuid.uuid4().hex[:12]  # 12 char hex = 48 bits of randomness
    ext = mime_to_ext(mime_type) if mime_type else ""
    if base_name:
        # Sanitize base name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)[:30]
        return f"{safe_name}_{unique_id}{ext}"
    return f"file_{unique_id}{ext}"

# AWS EUM Supported Media Types (from AWS documentation)
EUM_SUPPORTED_MEDIA = {
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


def handle_eum_download_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Download media from WhatsApp to S3 using AWS EUM Social API.
    
    S3 Path: s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    
    Uses: GetWhatsAppMessageMedia API
    Ref: https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_GetWhatsAppMessageMedia.html
    
    Test Event:
    {
        "action": "eum_download_media",
        "metaWabaId": "1347766229904230",
        "mediaId": "123456789",
        "filename": "document"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    media_id = event.get("mediaId", "")
    filename = event.get("filename", "media")
    mime_type = event.get("mimeType", "")
    
    error = validate_required_fields(event, ["metaWabaId", "mediaId"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    # Generate S3 key with WABA folder and secure filename
    # Structure: WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    waba_folder = _get_waba_folder(meta_waba_id)
    secure_filename = _generate_secure_filename(filename, mime_type)
    s3_key = f"{MEDIA_PREFIX}download/{waba_folder}/{secure_filename}"
    
    try:
        # Use AWS Social Messaging API to download media to S3
        response = social().get_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            destinationS3File={
                "bucketName": MEDIA_BUCKET,
                "key": s3_key
            }
        )
        
        # Store download record
        now = iso_now()
        download_pk = f"MEDIA_DOWNLOAD#{media_id}"
        store_item({
            MESSAGES_PK_NAME: download_pk,
            "itemType": "MEDIA_DOWNLOAD",
            "mediaId": media_id,
            "wabaMetaId": meta_waba_id,
            "wabaFolder": waba_folder,
            "s3Bucket": MEDIA_BUCKET,
            "s3Key": s3_key,
            "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
            "fileSize": response.get("fileSize"),
            "mimeType": response.get("mimeType"),
            "downloadedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "eum_download_media",
            "mediaId": media_id,
            "wabaFolder": waba_folder,
            "s3Bucket": MEDIA_BUCKET,
            "s3Key": s3_key,
            "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
            "fileSize": response.get("fileSize"),
            "mimeType": response.get("mimeType"),
            "note": "Downloaded to WhatsApp/download/{waba_folder}/ with secure UUID filename"
        }
    except ClientError as e:
        logger.exception(f"EUM download failed: {e}")
        return {"statusCode": 500, "error": str(e)}


def handle_eum_upload_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload media from S3 to WhatsApp using AWS EUM Social API.
    
    S3 Path: s3://dev.wecare.digital/WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}
    
    Uses: PostWhatsAppMessageMedia API
    Ref: https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/post-whatsapp-message-media.html
    
    Test Event:
    {
        "action": "eum_upload_media",
        "metaWabaId": "1347766229904230",
        "s3Key": "WhatsApp/upload/wecare/image_abc123.jpg"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    s3_key = event.get("s3Key", "")
    
    error = validate_required_fields(event, ["metaWabaId", "s3Key"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    # Get WABA folder for tracking
    waba_folder = _get_waba_folder(meta_waba_id)
    
    try:
        # Validate media before upload
        validation = _validate_s3_media(s3_key)
        if not validation.get("valid"):
            return {"statusCode": 400, "error": validation.get("error", "Invalid media")}
        
        # Use AWS Social Messaging API to upload media from S3
        response = social().post_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            sourceS3File={
                "bucketName": MEDIA_BUCKET,
                "key": s3_key
            }
        )
        
        media_id = response.get("mediaId", "")
        
        # Store upload record
        now = iso_now()
        upload_pk = f"MEDIA_UPLOAD#{media_id}"
        store_item({
            MESSAGES_PK_NAME: upload_pk,
            "itemType": "MEDIA_UPLOAD",
            "mediaId": media_id,
            "wabaMetaId": meta_waba_id,
            "wabaFolder": waba_folder,
            "s3Bucket": MEDIA_BUCKET,
            "s3Key": s3_key,
            "mimeType": validation.get("mimeType"),
            "fileSize": validation.get("fileSize"),
            "uploadedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "eum_upload_media",
            "mediaId": media_id,
            "wabaFolder": waba_folder,
            "s3Key": s3_key,
            "mimeType": validation.get("mimeType"),
            "fileSize": validation.get("fileSize"),
            "note": "Uploaded from WhatsApp/upload/{waba_folder}/ with secure UUID filename"
        }
    except ClientError as e:
        logger.exception(f"EUM upload failed: {e}")
        return {"statusCode": 500, "error": str(e)}


def _validate_s3_media(s3_key: str) -> Dict[str, Any]:
    """Validate media file in S3 against WhatsApp requirements."""
    try:
        # Get object metadata
        response = s3().head_object(Bucket=MEDIA_BUCKET, Key=s3_key)
        content_type = response.get("ContentType", "")
        content_length = response.get("ContentLength", 0)
        
        # Check if supported
        for media_type, info in EUM_SUPPORTED_MEDIA.items():
            if content_type in info.get("formats", []):
                max_bytes = info.get("maxSizeMB", 0) * 1024 * 1024
                if not max_bytes:
                    max_bytes = info.get("maxSizeKB", 0) * 1024
                
                if content_length > max_bytes:
                    return {
                        "valid": False,
                        "error": f"File size {content_length} exceeds max {max_bytes} bytes for {media_type}"
                    }
                
                return {
                    "valid": True,
                    "mediaType": media_type,
                    "mimeType": content_type,
                    "fileSize": content_length,
                    "maxSize": max_bytes
                }
        
        return {"valid": False, "error": f"Unsupported media type: {content_type}"}
    except ClientError as e:
        return {"valid": False, "error": str(e)}


def handle_eum_validate_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate media file against AWS EUM/WhatsApp requirements.
    
    Test Event:
    {
        "action": "eum_validate_media",
        "s3Key": "WhatsApp/uploads/image.jpg"
    }
    
    Or with MIME type:
    {
        "action": "eum_validate_media",
        "mimeType": "image/jpeg",
        "fileSizeBytes": 1048576
    }
    """
    s3_key = event.get("s3Key", "")
    mime_type = event.get("mimeType", "")
    file_size_bytes = event.get("fileSizeBytes", 0)
    
    if s3_key:
        # Validate from S3
        validation = _validate_s3_media(s3_key)
        return {
            "statusCode": 200 if validation.get("valid") else 400,
            "operation": "eum_validate_media",
            "s3Key": s3_key,
            **validation
        }
    
    if mime_type:
        # Validate by MIME type
        for media_type, info in EUM_SUPPORTED_MEDIA.items():
            if mime_type in info.get("formats", []):
                max_bytes = info.get("maxSizeMB", 0) * 1024 * 1024
                if not max_bytes:
                    max_bytes = info.get("maxSizeKB", 0) * 1024
                
                within_limit = file_size_bytes <= max_bytes if file_size_bytes > 0 else True
                
                return {
                    "statusCode": 200 if within_limit else 400,
                    "operation": "eum_validate_media",
                    "valid": within_limit,
                    "mediaType": media_type,
                    "mimeType": mime_type,
                    "fileSize": file_size_bytes,
                    "maxSize": max_bytes,
                    "withinLimit": within_limit,
                    "notes": info.get("notes", "")
                }
        
        return {
            "statusCode": 400,
            "operation": "eum_validate_media",
            "valid": False,
            "mimeType": mime_type,
            "error": f"Unsupported media type: {mime_type}",
            "supportedTypes": EUM_SUPPORTED_MEDIA
        }
    
    return {"statusCode": 400, "error": "s3Key or mimeType is required"}


def handle_eum_get_supported_formats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get AWS EUM supported media formats.
    
    Test Event:
    {
        "action": "eum_get_supported_formats",
        "category": "image"
    }
    """
    category = event.get("category", "")
    
    if category:
        if category not in EUM_SUPPORTED_MEDIA:
            return {
                "statusCode": 400,
                "error": f"Invalid category. Valid: {list(EUM_SUPPORTED_MEDIA.keys())}"
            }
        
        return {
            "statusCode": 200,
            "operation": "eum_get_supported_formats",
            "category": category,
            "formats": EUM_SUPPORTED_MEDIA[category]
        }
    
    return {
        "statusCode": 200,
        "operation": "eum_get_supported_formats",
        "supportedMedia": EUM_SUPPORTED_MEDIA,
        "note": "All formats comply with AWS EUM Social documentation recommendations for robust media handling"
    }


def handle_eum_setup_s3_lifecycle(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Setup S3 lifecycle rules for media storage.
    
    Test Event:
    {
        "action": "eum_setup_s3_lifecycle",
        "expirationDays": 90,
        "transitionToIADays": 30
    }
    """
    expiration_days = event.get("expirationDays", 90)
    transition_to_ia_days = event.get("transitionToIADays", 30)
    
    try:
        # Define lifecycle configuration
        lifecycle_config = {
            "Rules": [
                {
                    "ID": "WhatsAppMediaLifecycle",
                    "Status": "Enabled",
                    "Filter": {"Prefix": MEDIA_PREFIX},
                    "Transitions": [
                        {
                            "Days": transition_to_ia_days,
                            "StorageClass": "STANDARD_IA"
                        }
                    ],
                    "Expiration": {
                        "Days": expiration_days
                    }
                }
            ]
        }
        
        # Apply lifecycle configuration
        s3().put_bucket_lifecycle_configuration(
            Bucket=MEDIA_BUCKET,
            LifecycleConfiguration=lifecycle_config
        )
        
        # Store configuration record
        now = iso_now()
        store_item({
            MESSAGES_PK_NAME: f"S3_LIFECYCLE#{MEDIA_BUCKET}",
            "itemType": "S3_LIFECYCLE_CONFIG",
            "bucket": MEDIA_BUCKET,
            "prefix": MEDIA_PREFIX,
            "expirationDays": expiration_days,
            "transitionToIADays": transition_to_ia_days,
            "configuredAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "eum_setup_s3_lifecycle",
            "bucket": MEDIA_BUCKET,
            "prefix": MEDIA_PREFIX,
            "expirationDays": expiration_days,
            "transitionToIADays": transition_to_ia_days,
            "note": "S3 lifecycle configured per AWS EUM recommendations"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_eum_get_media_stats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get media storage statistics.
    
    Test Event:
    {
        "action": "eum_get_media_stats",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    try:
        # Query media records
        filter_expr = "itemType IN (:upload, :download)"
        expr_values = {":upload": "MEDIA_UPLOAD", ":download": "MEDIA_DOWNLOAD"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        
        items = response.get("Items", [])
        
        uploads = [i for i in items if i.get("itemType") == "MEDIA_UPLOAD"]
        downloads = [i for i in items if i.get("itemType") == "MEDIA_DOWNLOAD"]
        
        # Calculate stats
        total_upload_size = sum(i.get("fileSize", 0) for i in uploads)
        total_download_size = sum(i.get("fileSize", 0) for i in downloads)
        
        # Type breakdown
        type_breakdown = {}
        for item in items:
            mime = item.get("mimeType", "unknown")
            type_breakdown[mime] = type_breakdown.get(mime, 0) + 1
        
        return {
            "statusCode": 200,
            "operation": "eum_get_media_stats",
            "stats": {
                "totalUploads": len(uploads),
                "totalDownloads": len(downloads),
                "totalUploadSizeBytes": total_upload_size,
                "totalDownloadSizeBytes": total_download_size,
                "totalUploadSizeMB": round(total_upload_size / (1024 * 1024), 2),
                "totalDownloadSizeMB": round(total_download_size / (1024 * 1024), 2),
                "typeBreakdown": type_breakdown
            },
            "note": "Statistics based on AWS EUM Social media handling"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_eum_generate_s3_path(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Generate S3 path for media upload/download with secure UUID filename.
    
    S3 Structure:
    - Download (inbound): s3://dev.wecare.digital/WhatsApp/download/{waba_folder}/{filename}_{uuid}.{ext}
    - Upload (outbound):  s3://dev.wecare.digital/WhatsApp/upload/{waba_folder}/{filename}_{uuid}.{ext}
    
    Test Event:
    {
        "action": "eum_generate_s3_path",
        "metaWabaId": "1347766229904230",
        "direction": "download",
        "filename": "invoice",
        "mimeType": "application/pdf"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    direction = event.get("direction", "download")  # download (inbound) or upload (outbound)
    filename = event.get("filename", "file")
    mime_type = event.get("mimeType", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if direction not in ["download", "upload"]:
        return {"statusCode": 400, "error": "direction must be 'download' or 'upload'"}
    
    waba_folder = _get_waba_folder(meta_waba_id)
    secure_filename = _generate_secure_filename(filename, mime_type)
    s3_key = f"{MEDIA_PREFIX}{direction}/{waba_folder}/{secure_filename}"
    
    return {
        "statusCode": 200,
        "operation": "eum_generate_s3_path",
        "s3Bucket": MEDIA_BUCKET,
        "s3Key": s3_key,
        "s3Uri": f"s3://{MEDIA_BUCKET}/{s3_key}",
        "wabaFolder": waba_folder,
        "direction": direction,
        "secureFilename": secure_filename,
        "structure": {
            "bucket": MEDIA_BUCKET,
            "prefix": MEDIA_PREFIX,
            "direction": direction,
            "wabaFolder": waba_folder,
            "filename": secure_filename
        }
    }


def handle_eum_list_waba_folders(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List WABA folder mappings for S3 media storage.
    
    Test Event:
    {
        "action": "eum_list_waba_folders"
    }
    """
    return {
        "statusCode": 200,
        "operation": "eum_list_waba_folders",
        "wabaFolders": WABA_FOLDER_MAP,
        "s3Structure": {
            "bucket": MEDIA_BUCKET,
            "downloadPath": f"s3://{MEDIA_BUCKET}/{MEDIA_PREFIX}download/{{waba_folder}}/{{filename}}_{{uuid}}.{{ext}}",
            "uploadPath": f"s3://{MEDIA_BUCKET}/{MEDIA_PREFIX}upload/{{waba_folder}}/{{filename}}_{{uuid}}.{{ext}}"
        },
        "note": "Files use UUID suffix to prevent URL guessing. Simple flat structure per WABA."
    }


# Final Statement (as per requirements):
# All in all, we have integrated the AWS EUM Social documentation recommendations 
# in our design for robust media handling.
