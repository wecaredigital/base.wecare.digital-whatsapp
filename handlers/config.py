# =============================================================================
# Configuration & Utility Handlers
# =============================================================================
# Configuration, status, and utility handlers.
# All handlers use the unified base utilities from handlers/base.py.
# =============================================================================

import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from handlers.base import (
    table, social, s3, ec2, iam, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    META_API_VERSION, WABA_PHONE_MAP,
    iso_now, jdump, safe, format_wa_number, origination_id_for_api, arn_suffix,
    get_waba_config, get_phone_arn, success_response, error_response,
    SUPPORTED_MEDIA_TYPES, get_supported_mime_types,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# PING
# =============================================================================

def handle_ping(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Health check endpoint.
    
    Returns basic status and timestamp.
    """
    return success_response(
        "ping",
        status="healthy",
        timestamp=iso_now(),
        version="2.0.0",
        architecture="modular-mono-lambda",
    )


# =============================================================================
# GET CONFIG
# =============================================================================

def handle_get_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all configuration.
    
    Returns environment configuration and WABA mappings.
    """
    # Get quality ratings from DynamoDB
    quality_items = []
    try:
        response = table().scan(
            FilterExpression="itemType = :it",
            ExpressionAttributeValues={":it": "QUALITY_RATING"},
        )
        quality_items = response.get("Items", [])
    except ClientError:
        pass
    
    # Get infrastructure config
    infra_item = None
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: "CONFIG#INFRA"})
        infra_item = response.get("Item")
    except ClientError:
        pass
    
    return success_response(
        "get_config",
        wabaPhoneMap=WABA_PHONE_MAP,
        mediaBucket=str(MEDIA_BUCKET),
        mediaPrefix=str(MEDIA_PREFIX),
        metaApiVersion=str(META_API_VERSION),
        qualityRatings=quality_items,
        infrastructure=infra_item,
        supportedMediaTypes=SUPPORTED_MEDIA_TYPES,
    )


# =============================================================================
# GET QUALITY
# =============================================================================

def handle_get_quality(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get phone quality ratings.
    
    Optional: metaWabaId
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    try:
        if meta_waba_id:
            pk = f"QUALITY#{meta_waba_id}"
            response = table().get_item(Key={MESSAGES_PK_NAME: pk})
            item = response.get("Item")
            if item:
                return success_response("get_quality", quality=item)
            return error_response(f"Quality rating not found for WABA: {meta_waba_id}", 404)
        
        # Get all quality ratings
        response = table().scan(
            FilterExpression="itemType = :it",
            ExpressionAttributeValues={":it": "QUALITY_RATING"},
        )
        items = response.get("Items", [])
        
        return success_response("get_quality", count=len(items), qualityRatings=items)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET STATS
# =============================================================================

def handle_get_stats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get message statistics.
    
    Optional: metaWabaId
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    try:
        # Count messages by direction
        inbound_count = 0
        outbound_count = 0
        
        # Scan for message counts (limited for performance)
        response = table().scan(
            FilterExpression="itemType = :it",
            ExpressionAttributeValues={":it": "MESSAGE"},
            Select="COUNT",
            Limit=10000,
        )
        total_messages = response.get("Count", 0)
        
        # Count conversations
        conv_response = table().scan(
            FilterExpression="itemType = :it",
            ExpressionAttributeValues={":it": "CONVERSATION"},
            Select="COUNT",
        )
        total_conversations = conv_response.get("Count", 0)
        
        # Get inbound/outbound counts
        try:
            inbound_resp = table().query(
                IndexName="gsi_direction",
                KeyConditionExpression="direction = :d",
                ExpressionAttributeValues={":d": "INBOUND"},
                Select="COUNT",
            )
            inbound_count = inbound_resp.get("Count", 0)
        except ClientError:
            pass
        
        try:
            outbound_resp = table().query(
                IndexName="gsi_direction",
                KeyConditionExpression="direction = :d",
                ExpressionAttributeValues={":d": "OUTBOUND"},
                Select="COUNT",
            )
            outbound_count = outbound_resp.get("Count", 0)
        except ClientError:
            pass
        
        return success_response(
            "get_stats",
            totalMessages=total_messages,
            totalConversations=total_conversations,
            inboundMessages=inbound_count,
            outboundMessages=outbound_count,
            timestamp=iso_now(),
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET WABAS
# =============================================================================

def handle_get_wabas(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List all linked WhatsApp Business Accounts.
    
    Returns WABAs from AWS EUM Social API.
    """
    try:
        response = social().list_linked_whatsapp_business_accounts()
        accounts = response.get("linkedAccounts", [])
        
        # Enrich with local config
        enriched = []
        for acc in accounts:
            waba_meta_id = acc.get("wabaId", "")
            local_config = WABA_PHONE_MAP.get(waba_meta_id, {})
            enriched.append({
                **acc,
                "localConfig": local_config,
            })
        
        return success_response("get_wabas", count=len(enriched), wabas=enriched)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET PHONE INFO
# =============================================================================

def handle_get_phone_info(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get detailed phone number information.
    
    Required: metaWabaId (or phoneArn)
    """
    meta_waba_id = event.get("metaWabaId", "")
    phone_arn = event.get("phoneArn", "")
    
    if not meta_waba_id and not phone_arn:
        return error_response("metaWabaId or phoneArn is required")
    
    if meta_waba_id and not phone_arn:
        config = get_waba_config(meta_waba_id)
        phone_arn = config.get("phoneArn", "")
    
    if not phone_arn:
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    try:
        # Get phone number metadata from AWS
        phone_id = origination_id_for_api(phone_arn)
        response = social().get_whatsapp_message_media(
            originationPhoneNumberId=phone_id,
        )
        
        return success_response(
            "get_phone_info",
            phoneArn=phone_arn,
            phoneId=phone_id,
            metaWabaId=meta_waba_id,
            localConfig=get_waba_config(meta_waba_id),
        )
    except ClientError as e:
        # Return local config even if AWS call fails
        return success_response(
            "get_phone_info",
            phoneArn=phone_arn,
            metaWabaId=meta_waba_id,
            localConfig=get_waba_config(meta_waba_id),
            awsError=str(e),
        )


# =============================================================================
# GET INFRA
# =============================================================================

def handle_get_infra(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get infrastructure configuration from DynamoDB.
    
    Returns VPC endpoint, service-linked role, and other infra details.
    """
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: "CONFIG#INFRA"})
        item = response.get("Item")
        
        if not item:
            return success_response("get_infra", infrastructure=None, message="No infrastructure config stored")
        
        return success_response("get_infra", infrastructure=item)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET MEDIA TYPES
# =============================================================================

def handle_get_media_types(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get supported media types from DynamoDB.
    
    Returns cached media type configuration.
    """
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: "CONFIG#MEDIA_TYPES"})
        item = response.get("Item")
        
        if item:
            return success_response("get_media_types", mediaTypes=item)
        
        # Return default if not cached
        return success_response("get_media_types", mediaTypes=SUPPORTED_MEDIA_TYPES)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET SUPPORTED FORMATS
# =============================================================================

def handle_get_supported_formats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all supported media formats with size limits.
    
    Optional: category (image, video, audio, document, sticker)
    """
    category = event.get("category", "")
    
    if category:
        if category not in SUPPORTED_MEDIA_TYPES:
            return error_response(f"Invalid category: {category}. Valid: {list(SUPPORTED_MEDIA_TYPES.keys())}")
        return success_response("get_supported_formats", category=category, formats=SUPPORTED_MEDIA_TYPES[category])
    
    return success_response("get_supported_formats", supportedFormats=SUPPORTED_MEDIA_TYPES)


# =============================================================================
# LIST ACTIONS
# =============================================================================

def handle_list_actions(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List all available actions.
    
    Returns categorized list of all handler actions.
    """
    # Import here to avoid circular imports
    from handlers.extended import get_extended_actions_by_category, get_extended_handler_count
    
    categories = get_extended_actions_by_category()
    total = get_extended_handler_count()
    
    return success_response(
        "list_actions",
        totalActions=total,
        categories=categories,
    )


# =============================================================================
# GET BEST PRACTICES
# =============================================================================

def handle_get_best_practices(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get best practices for using Lambda handlers.
    
    Returns tips and recommendations.
    """
    return success_response(
        "get_best_practices",
        bestPractices={
            "messaging": {
                "tip": "Use send_template for marketing messages to avoid rate limits",
                "example": {"action": "send_template", "templateName": "hello_world"},
            },
            "media": {
                "tip": "Upload media to S3 first, then use s3Key for sending",
                "example": {"action": "send_image", "s3Key": "WhatsApp/media/image.jpg"},
            },
            "queries": {
                "tip": "Use specific GSI queries instead of scans for better performance",
                "example": {"action": "get_messages", "direction": "INBOUND", "limit": 20},
            },
            "conversations": {
                "tip": "Use mark_conversation_read to reset unread counts efficiently",
                "example": {"action": "mark_conversation_read", "phoneId": "xxx", "fromNumber": "447447840003"},
            },
        },
    )


# =============================================================================
# HANDLER MAPPING
# =============================================================================

CONFIG_HANDLERS = {
    "ping": handle_ping,
    "get_config": handle_get_config,
    "get_quality": handle_get_quality,
    "get_stats": handle_get_stats,
    "get_wabas": handle_get_wabas,
    "get_phone_info": handle_get_phone_info,
    "get_infra": handle_get_infra,
    "get_media_types": handle_get_media_types,
    "get_supported_formats": handle_get_supported_formats,
    "list_actions": handle_list_actions,
    "get_best_practices": handle_get_best_practices,
}
