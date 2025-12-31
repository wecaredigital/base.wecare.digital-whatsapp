# =============================================================================
# Inbound Event Handler
# =============================================================================
# Entry point for SNS/SQS inbound WhatsApp events.
# Processes AWS EUM event destination messages.
# =============================================================================

import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.runtime.envelope import Envelope, EnvelopeKind
from src.runtime.parse_event import parse_event, EventSource
from src.runtime.deps import Deps, create_deps
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def inbound_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Inbound event entry point (SNS/SQS).
    
    Processes WhatsApp events from AWS EUM event destinations:
    - Inbound messages
    - Message status updates
    - Template status updates
    
    Args:
        event: SNS/SQS event with Records[]
        context: Lambda context
        
    Returns:
        Processing summary
    """
    logger.info(f"INBOUND_HANDLER event keys: {list(event.keys())}")
    
    # Parse event into envelopes
    envelopes, source = parse_event(event)
    
    if not envelopes:
        return {
            "statusCode": 200,
            "processed": 0,
            "message": "No records to process",
        }
    
    # Create deps
    deps = create_deps()
    
    # Process each envelope
    results = {
        "processed": 0,
        "messages": 0,
        "statuses": 0,
        "errors": 0,
        "skipped": 0,
    }
    
    for envelope in envelopes:
        try:
            result = _process_inbound_envelope(envelope, deps)
            results["processed"] += 1
            results["messages"] += result.get("messages", 0)
            results["statuses"] += result.get("statuses", 0)
        except Exception as e:
            logger.exception(f"Error processing envelope: {e}")
            results["errors"] += 1
    
    return {
        "statusCode": 200,
        **results,
    }


def _process_inbound_envelope(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Process a single inbound envelope."""
    payload = envelope.payload
    
    # Extract WhatsApp webhook entry
    webhook_entry = payload.get("whatsAppWebhookEntry", {})
    if isinstance(webhook_entry, str):
        try:
            webhook_entry = json.loads(webhook_entry)
        except json.JSONDecodeError:
            webhook_entry = {}
    
    waba_meta_id = str(webhook_entry.get("id", ""))
    
    # Get account info
    account = _lookup_account(waba_meta_id, deps)
    phone_arn = account.get("phoneArn", "") if account else ""
    
    # Get timestamp from metadata
    received_at = envelope.metadata.get("snsTimestamp") or datetime.now(timezone.utc).isoformat()
    
    results = {"messages": 0, "statuses": 0}
    
    # Process changes
    changes = webhook_entry.get("changes", [])
    for change in changes:
        value = change.get("value", {})
        
        # Process messages
        messages = value.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict):
                _process_inbound_message(msg, value, waba_meta_id, phone_arn, account, received_at, deps)
                results["messages"] += 1
        
        # Process status updates
        statuses = value.get("statuses", [])
        for status in statuses:
            if isinstance(status, dict):
                _process_status_update(status, deps)
                results["statuses"] += 1
    
    return results


def _lookup_account(waba_meta_id: str, deps: Deps) -> Optional[Dict[str, Any]]:
    """Look up account by WABA Meta ID."""
    if not waba_meta_id:
        return None
    return deps.get_waba_config(waba_meta_id)


def _generate_idempotency_key(waba_id: str, phone_id: str, msg_id: str, event_type: str) -> str:
    """Generate idempotency key for deduplication."""
    raw = f"{waba_id}:{phone_id}:{msg_id}:{event_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _check_idempotency(idempotency_key: str, deps: Deps) -> bool:
    """Check if event was already processed."""
    try:
        pk = f"EVENT#{idempotency_key}"
        response = deps.table.get_item(Key={deps.config["MESSAGES_PK_NAME"]: pk})
        return "Item" in response
    except ClientError:
        return False


def _mark_processed(idempotency_key: str, event_type: str, deps: Deps) -> None:
    """Mark event as processed for idempotency."""
    try:
        pk = f"EVENT#{idempotency_key}"
        ttl = int((datetime.now(timezone.utc).timestamp()) + 86400 * 7)  # 7 days
        deps.table.put_item(Item={
            deps.config["MESSAGES_PK_NAME"]: pk,
            "itemType": "IDEMPOTENCY",
            "eventType": event_type,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl,
        })
    except ClientError as e:
        logger.warning(f"Failed to mark processed: {e}")


def _process_inbound_message(
    msg: Dict[str, Any],
    value: Dict[str, Any],
    waba_meta_id: str,
    phone_arn: str,
    account: Optional[Dict[str, Any]],
    received_at: str,
    deps: Deps,
) -> None:
    """Process a single inbound WhatsApp message."""
    from_wa = str(msg.get("from", "unknown"))
    wa_msg_id = str(msg.get("id", ""))
    mtype = str(msg.get("type", "unknown"))
    wa_ts = str(msg.get("timestamp", ""))
    
    # Check idempotency
    idempotency_key = _generate_idempotency_key(waba_meta_id, phone_arn, wa_msg_id, "message")
    if _check_idempotency(idempotency_key, deps):
        logger.info(f"Skipping duplicate message: {wa_msg_id}")
        return
    
    # Extract metadata
    meta = value.get("metadata", {})
    meta_phone_number_id = str(meta.get("phone_number_id", ""))
    
    # Get sender name from contacts
    contacts = value.get("contacts", [])
    sender_name = ""
    if contacts and isinstance(contacts[0], dict):
        profile = contacts[0].get("profile", {})
        sender_name = profile.get("name", "")
    
    # Extract message content
    text_body = ""
    caption = ""
    filename = ""
    inbound_media_id = ""
    mime_type = ""
    
    if mtype == "text":
        text_body = (msg.get("text", {}).get("body", ""))
    
    if mtype in {"image", "video", "audio", "document", "sticker"}:
        media_block = msg.get(mtype, {})
        inbound_media_id = media_block.get("id", "")
        mime_type = media_block.get("mime_type", "")
        caption = media_block.get("caption", "")
        filename = media_block.get("filename", "")
    
    # Handle interactive messages
    if mtype == "interactive":
        interactive = msg.get("interactive", {})
        interactive_type = interactive.get("type", "")
        
        if interactive_type == "list_reply":
            list_reply = interactive.get("list_reply", {})
            text_body = f"[List Reply] {list_reply.get('title', '')} (id: {list_reply.get('id', '')})"
        elif interactive_type == "button_reply":
            button_reply = interactive.get("button_reply", {})
            text_body = f"[Button Reply] {button_reply.get('title', '')} (id: {button_reply.get('id', '')})"
    
    # Build preview
    preview = _build_preview(mtype, text_body, caption)
    
    # Download media to S3 if present
    s3_key = ""
    s3_uri = ""
    if inbound_media_id and phone_arn:
        s3_key = _download_media_to_s3(
            inbound_media_id, phone_arn, waba_meta_id, from_wa, wa_msg_id,
            mime_type, account, deps
        )
        if s3_key:
            s3_uri = f"s3://{deps.config['MEDIA_BUCKET']}/{s3_key}"
    
    # Build message item
    pk_name = deps.config["MESSAGES_PK_NAME"]
    msg_pk = f"MSG#{wa_msg_id}"
    conv_pk = f"CONV#{_arn_suffix(phone_arn)}#{from_wa}"
    
    item = {
        pk_name: msg_pk,
        "itemType": "MESSAGE",
        "direction": "INBOUND",
        "receivedAt": received_at,
        "waTimestamp": wa_ts,
        "from": from_wa,
        "to": account.get("phone", "") if account else "",
        "fromPk": from_wa,
        "senderName": sender_name,
        "originationPhoneNumberId": phone_arn,
        "wabaMetaId": waba_meta_id,
        "businessAccountName": account.get("businessAccountName", "") if account else "",
        "businessPhone": account.get("phone", "") if account else "",
        "meta_phone_number_id": meta_phone_number_id or (account.get("meta_phone_number_id", "") if account else ""),
        "conversationPk": conv_pk,
        "type": mtype,
        "preview": preview,
        "textBody": text_body,
        "caption": caption,
        "filename": filename,
        "mediaId": inbound_media_id,
        "mimeType": mime_type,
        "s3Bucket": deps.config["MEDIA_BUCKET"] if s3_key else "",
        "s3Key": s3_key,
        "s3Uri": s3_uri,
    }
    
    # Store message
    try:
        deps.table.put_item(
            Item=item,
            ConditionExpression=f"attribute_not_exists({pk_name})",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
    
    # Update conversation
    _upsert_conversation(conv_pk, phone_arn, from_wa, {
        "receivedAt": received_at,
        "businessAccountName": account.get("businessAccountName", "") if account else "",
        "businessPhone": account.get("phone", "") if account else "",
        "meta_phone_number_id": meta_phone_number_id,
        "lastMessagePk": msg_pk,
        "lastMessageId": wa_msg_id,
        "lastType": mtype,
        "lastPreview": preview,
        "lastS3Uri": s3_uri,
    }, deps)
    
    # Mark as read
    if deps.config["MARK_AS_READ_ENABLED"] and phone_arn and wa_msg_id:
        _mark_message_as_read(phone_arn, wa_msg_id, msg_pk, deps)
    
    # React with emoji
    if deps.config["REACT_EMOJI_ENABLED"] and phone_arn and from_wa and wa_msg_id:
        _react_with_emoji(phone_arn, from_wa, wa_msg_id, msg_pk, mtype, deps)
    
    # Auto-reply
    if deps.config["AUTO_REPLY_ENABLED"] and phone_arn and from_wa:
        _send_auto_reply(phone_arn, from_wa, wa_msg_id, deps)
    
    # Mark processed
    _mark_processed(idempotency_key, "message", deps)
    
    logger.info(f"Processed inbound message: {wa_msg_id} from {from_wa}")


def _process_status_update(status: Dict[str, Any], deps: Deps) -> None:
    """Process message status update."""
    wa_msg_id = str(status.get("id", ""))
    status_value = str(status.get("status", ""))
    status_ts = str(status.get("timestamp", ""))
    recipient_id = str(status.get("recipient_id", ""))
    
    if not wa_msg_id or not status_value:
        return
    
    # Extract errors if present
    errors = status.get("errors", [])
    error_list = []
    for err in errors:
        if isinstance(err, dict):
            error_list.append({
                "code": err.get("code", ""),
                "title": err.get("title", ""),
                "message": err.get("message", ""),
            })
    
    # Update message status
    pk_name = deps.config["MESSAGES_PK_NAME"]
    msg_pk = f"MSG#{wa_msg_id}"
    now = datetime.now(timezone.utc).isoformat()
    
    status_entry = {
        "status": status_value,
        "timestamp": status_ts,
        "updatedAt": now,
    }
    if error_list:
        status_entry["errors"] = error_list
    
    try:
        deps.table.update_item(
            Key={pk_name: msg_pk},
            UpdateExpression=(
                "SET deliveryStatus = :status, "
                "    deliveryStatusTimestamp = :ts, "
                "    deliveryStatusUpdatedAt = :now, "
                "    recipientId = :rid, "
                "    direction = if_not_exists(direction, :dir), "
                "    deliveryStatusHistory = list_append(if_not_exists(deliveryStatusHistory, :empty), :entry)"
            ),
            ExpressionAttributeValues={
                ":status": status_value,
                ":ts": status_ts,
                ":now": now,
                ":rid": recipient_id,
                ":dir": "OUTBOUND",
                ":entry": [status_entry],
                ":empty": [],
            },
        )
        logger.info(f"Updated status for {wa_msg_id}: {status_value}")
    except ClientError as e:
        logger.warning(f"Failed to update status for {wa_msg_id}: {e}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _build_preview(mtype: str, text_body: str, caption: str) -> str:
    """Build message preview."""
    if mtype == "text" and text_body:
        return text_body[:200]
    if caption:
        return f"[{mtype}] {caption}"[:200]
    return f"[{mtype}]"


def _arn_suffix(arn: str) -> str:
    """Extract suffix from ARN."""
    return arn.split("/")[-1] if arn and "arn:" in arn else arn


def _mime_to_ext(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    if not mime_type:
        return ".bin"
    return {
        "image/jpeg": ".jpeg", "image/png": ".png", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/3gpp": ".3gp",
        "audio/mpeg": ".mp3", "audio/aac": ".aac", "audio/amr": ".amr",
        "audio/mp4": ".m4a", "audio/ogg": ".ogg",
        "application/pdf": ".pdf", "text/plain": ".txt",
    }.get(mime_type, ".bin")


def _safe(s: str) -> str:
    """Sanitize string for S3 keys."""
    import re
    if not s:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9=._\-/#]+", "_", s)


def _download_media_to_s3(
    media_id: str,
    phone_arn: str,
    waba_meta_id: str,
    from_wa: str,
    wa_msg_id: str,
    mime_type: str,
    account: Optional[Dict[str, Any]],
    deps: Deps,
) -> str:
    """Download media from WhatsApp to S3."""
    ext = _mime_to_ext(mime_type)
    business_name = account.get("businessAccountName", "unknown") if account else "unknown"
    
    s3_key = (
        f"{deps.config['MEDIA_PREFIX']}"
        f"business={_safe(business_name)}/"
        f"wabaMetaId={_safe(waba_meta_id)}/"
        f"phone={_safe(_arn_suffix(phone_arn))}/"
        f"from={_safe(from_wa)}/"
        f"waMessageId={_safe(wa_msg_id)}/"
        f"mediaId={_safe(media_id)}{ext}"
    )
    
    try:
        deps.social.get_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=deps.origination_id_for_api(phone_arn),
            destinationS3File={
                "bucketName": deps.config["MEDIA_BUCKET"],
                "key": s3_key,
            },
        )
        logger.info(f"Downloaded media {media_id} to s3://{deps.config['MEDIA_BUCKET']}/{s3_key}")
        return s3_key
    except ClientError as e:
        logger.exception(f"Failed to download media {media_id}: {e}")
        return ""


def _upsert_conversation(
    conv_pk: str,
    phone_arn: str,
    from_wa: str,
    update: Dict[str, Any],
    deps: Deps,
) -> None:
    """Update or create conversation item."""
    pk_name = deps.config["MESSAGES_PK_NAME"]
    
    try:
        deps.table.update_item(
            Key={pk_name: conv_pk},
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
        if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            logger.warning(f"Failed to upsert conversation: {e}")


def _mark_message_as_read(phone_arn: str, wa_msg_id: str, msg_pk: str, deps: Deps) -> None:
    """Mark message as read."""
    payload = {
        "messaging_product": "whatsapp",
        "message_id": wa_msg_id,
        "status": "read",
    }
    
    try:
        deps.social.send_whatsapp_message(
            originationPhoneNumberId=deps.origination_id_for_api(phone_arn),
            metaApiVersion=deps.config["META_API_VERSION"],
            message=json.dumps(payload).encode("utf-8"),
        )
        
        # Update DynamoDB
        deps.table.update_item(
            Key={deps.config["MESSAGES_PK_NAME"]: msg_pk},
            UpdateExpression="SET markedAsRead = :mar, markedAsReadAt = :marat",
            ExpressionAttributeValues={
                ":mar": True,
                ":marat": datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError as e:
        logger.warning(f"Failed to mark as read: {e}")


def _react_with_emoji(phone_arn: str, to_wa: str, wa_msg_id: str, msg_pk: str, mtype: str, deps: Deps) -> None:
    """React to message with emoji."""
    emoji_map = {
        "text": "👍", "image": "❤️", "video": "🔥", "audio": "🎵",
        "document": "✅", "sticker": "😂", "location": "📍", "contacts": "👋",
    }
    emoji = emoji_map.get(mtype, "👍")
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": deps.format_wa_number(to_wa),
        "type": "reaction",
        "reaction": {"message_id": wa_msg_id, "emoji": emoji},
    }
    
    try:
        deps.social.send_whatsapp_message(
            originationPhoneNumberId=deps.origination_id_for_api(phone_arn),
            metaApiVersion=deps.config["META_API_VERSION"],
            message=json.dumps(payload).encode("utf-8"),
        )
        
        deps.table.update_item(
            Key={deps.config["MESSAGES_PK_NAME"]: msg_pk},
            UpdateExpression="SET reactedWithEmoji = :emoji, reactedAt = :rat",
            ExpressionAttributeValues={
                ":emoji": emoji,
                ":rat": datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError as e:
        logger.warning(f"Failed to react: {e}")


def _send_auto_reply(phone_arn: str, to_wa: str, reply_to_msg_id: str, deps: Deps) -> None:
    """Send auto-reply text."""
    payload = {
        "messaging_product": "whatsapp",
        "to": deps.format_wa_number(to_wa),
        "type": "text",
        "text": {"preview_url": False, "body": deps.config["AUTO_REPLY_TEXT"]},
    }
    if reply_to_msg_id:
        payload["context"] = {"message_id": reply_to_msg_id}
    
    try:
        deps.social.send_whatsapp_message(
            originationPhoneNumberId=deps.origination_id_for_api(phone_arn),
            metaApiVersion=deps.config["META_API_VERSION"],
            message=json.dumps(payload).encode("utf-8"),
        )
    except ClientError as e:
        logger.warning(f"Failed to send auto-reply: {e}")
