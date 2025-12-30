# =============================================================================
# Query Handlers
# =============================================================================
# Query and search handlers for messages, conversations, and data retrieval.
# All handlers use the unified base utilities from handlers/base.py.
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from decimal import Decimal

from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    META_API_VERSION, WABA_PHONE_MAP,
    iso_now, jdump, safe, format_wa_number, origination_id_for_api, arn_suffix,
    get_waba_config, get_phone_arn,
    store_item, get_item, query_items, success_response, error_response,
    generate_s3_presigned_url,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER: Decimal to JSON serializable
# =============================================================================
def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# =============================================================================
# GET MESSAGES
# =============================================================================

def handle_get_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query messages from DynamoDB.
    
    Optional: direction, fromNumber, toNumber, limit
    """
    direction = event.get("direction")
    from_number = event.get("fromNumber")
    to_number = event.get("toNumber")
    limit = event.get("limit", 50)
    
    try:
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
            scan_kwargs = {"Limit": limit}
            if to_number:
                scan_kwargs["FilterExpression"] = "contains(#to, :to)"
                scan_kwargs["ExpressionAttributeNames"] = {"#to": "to"}
                scan_kwargs["ExpressionAttributeValues"] = {":to": to_number}
            response = table().scan(**scan_kwargs)
        
        items = response.get("Items", [])
        messages = [i for i in items if i.get("itemType") in ("MESSAGE", "MESSAGE_STATUS")]
        
        return success_response("get_messages", count=len(messages), messages=messages)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET CONVERSATIONS
# =============================================================================

def handle_get_conversations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query conversations from DynamoDB.
    
    Optional: limit, inboxPk
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
                FilterExpression="itemType = :it",
                ExpressionAttributeValues={":it": "CONVERSATION"},
                Limit=limit,
            )
        
        items = response.get("Items", [])
        conversations = [i for i in items if i.get("itemType") == "CONVERSATION"]
        
        return success_response("get_conversations", count=len(conversations), conversations=conversations)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET MESSAGE (single)
# =============================================================================

def handle_get_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a single message by ID.
    
    Required: messageId
    """
    message_id = event.get("messageId", "")
    
    if not message_id:
        return error_response("messageId is required")
    
    msg_pk = f"MSG#{message_id}" if not message_id.startswith("MSG#") else message_id
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: msg_pk})
        item = response.get("Item")
        
        if not item:
            return error_response(f"Message not found: {message_id}", 404)
        
        # Add presigned URL if media exists
        s3_key = item.get("s3Key", "")
        if s3_key:
            item["presignedUrl"] = generate_s3_presigned_url(MEDIA_BUCKET, s3_key)
        
        return success_response("get_message", message=item)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET MESSAGE BY WA ID
# =============================================================================

def handle_get_message_by_wa_id(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get message by WhatsApp message ID (wamid).
    
    Required: waMessageId
    """
    wa_msg_id = event.get("waMessageId", "")
    
    if not wa_msg_id:
        return error_response("waMessageId is required")
    
    msg_pk = f"MSG#{wa_msg_id}"
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: msg_pk})
        item = response.get("Item")
        
        if not item:
            return error_response(f"Message not found: {wa_msg_id}", 404)
        
        s3_key = item.get("s3Key", "")
        if s3_key:
            item["presignedUrl"] = generate_s3_presigned_url(MEDIA_BUCKET, s3_key)
        
        return success_response("get_message_by_wa_id", message=item)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET CONVERSATION (single)
# =============================================================================

def handle_get_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a single conversation.
    
    Required: phoneId, fromNumber (or conversationPk)
    """
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    conv_pk = event.get("conversationPk", "")
    
    if not conv_pk:
        if not phone_id or not from_number:
            return error_response("phoneId and fromNumber (or conversationPk) are required")
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: conv_pk})
        item = response.get("Item")
        
        if not item:
            return error_response(f"Conversation not found: {conv_pk}", 404)
        
        return success_response("get_conversation", conversation=item)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET CONVERSATION MESSAGES
# =============================================================================

def handle_get_conversation_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all messages in a conversation.
    
    Required: phoneId, fromNumber (or conversationPk)
    Optional: limit
    """
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    conv_pk = event.get("conversationPk", "")
    limit = event.get("limit", 100)
    
    if not conv_pk:
        if not phone_id or not from_number:
            return error_response("phoneId and fromNumber (or conversationPk) are required")
        conv_pk = f"CONV#{phone_id}#{from_number}"
    
    try:
        response = table().query(
            IndexName="gsi_conversation",
            KeyConditionExpression="conversationPk = :cpk",
            ExpressionAttributeValues={":cpk": conv_pk},
            ScanIndexForward=False,
            Limit=limit,
        )
        
        items = response.get("Items", [])
        
        # Add presigned URLs for media
        for item in items:
            s3_key = item.get("s3Key", "")
            if s3_key:
                item["presignedUrl"] = generate_s3_presigned_url(MEDIA_BUCKET, s3_key)
        
        return success_response("get_conversation_messages", count=len(items), messages=items)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET UNREAD COUNT
# =============================================================================

def handle_get_unread_count(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get unread message count.
    
    Optional: phoneId, fromNumber
    """
    phone_id = event.get("phoneId", "")
    from_number = event.get("fromNumber", "")
    
    try:
        if phone_id and from_number:
            conv_pk = f"CONV#{phone_id}#{from_number}"
            response = table().get_item(Key={MESSAGES_PK_NAME: conv_pk})
            item = response.get("Item", {})
            unread = item.get("unreadCount", 0)
            return success_response("get_unread_count", unreadCount=unread, conversationPk=conv_pk)
        
        # Get total unread across all conversations
        response = table().scan(
            FilterExpression="itemType = :it AND unreadCount > :zero",
            ExpressionAttributeValues={":it": "CONVERSATION", ":zero": 0},
            ProjectionExpression="unreadCount",
        )
        
        items = response.get("Items", [])
        total_unread = sum(int(i.get("unreadCount", 0)) for i in items)
        
        return success_response("get_unread_count", totalUnread=total_unread, conversationCount=len(items))
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# SEARCH MESSAGES
# =============================================================================

def handle_search_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Search messages by text content.
    
    Required: query
    Optional: limit
    """
    query = event.get("query", "")
    limit = event.get("limit", 50)
    
    if not query:
        return error_response("query is required")
    
    try:
        response = table().scan(
            FilterExpression="contains(textBody, :q) OR contains(preview, :q) OR contains(caption, :q)",
            ExpressionAttributeValues={":q": query},
            Limit=limit,
        )
        
        items = response.get("Items", [])
        messages = [i for i in items if i.get("itemType") == "MESSAGE"]
        
        return success_response("search_messages", count=len(messages), query=query, messages=messages)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET ARCHIVED CONVERSATIONS
# =============================================================================

def handle_get_archived_conversations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get archived conversations.
    
    Optional: limit
    """
    limit = event.get("limit", 50)
    
    try:
        response = table().scan(
            FilterExpression="itemType = :it AND archived = :arc",
            ExpressionAttributeValues={":it": "CONVERSATION", ":arc": True},
            Limit=limit,
        )
        
        items = response.get("Items", [])
        
        return success_response("get_archived_conversations", count=len(items), conversations=items)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET FAILED MESSAGES
# =============================================================================

def handle_get_failed_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get messages with failed delivery status.
    
    Optional: limit
    """
    limit = event.get("limit", 50)
    
    try:
        response = table().query(
            IndexName="gsi_status",
            KeyConditionExpression="deliveryStatus = :s",
            ExpressionAttributeValues={":s": "failed"},
            ScanIndexForward=False,
            Limit=limit,
        )
        
        items = response.get("Items", [])
        
        return success_response("get_failed_messages", count=len(items), messages=items)
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET DELIVERY STATUS
# =============================================================================

def handle_get_delivery_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get delivery status for a message.
    
    Required: messageId
    """
    message_id = event.get("messageId", "")
    
    if not message_id:
        return error_response("messageId is required")
    
    msg_pk = f"MSG#{message_id}" if not message_id.startswith("MSG#") else message_id
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: msg_pk})
        item = response.get("Item")
        
        if not item:
            return error_response(f"Message not found: {message_id}", 404)
        
        return success_response(
            "get_delivery_status",
            messageId=message_id,
            deliveryStatus=item.get("deliveryStatus", "unknown"),
            sentAt=item.get("sentAt"),
            deliveredAt=item.get("deliveredAt"),
            readAt=item.get("readAt"),
            failedAt=item.get("failedAt"),
            errors=item.get("errors", []),
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# HANDLER MAPPING
# =============================================================================

QUERY_HANDLERS = {
    "get_messages": handle_get_messages,
    "get_conversations": handle_get_conversations,
    "get_message": handle_get_message,
    "get_message_by_wa_id": handle_get_message_by_wa_id,
    "get_conversation": handle_get_conversation,
    "get_conversation_messages": handle_get_conversation_messages,
    "get_unread_count": handle_get_unread_count,
    "search_messages": handle_search_messages,
    "get_archived_conversations": handle_get_archived_conversations,
    "get_failed_messages": handle_get_failed_messages,
    "get_delivery_status": handle_get_delivery_status,
}
