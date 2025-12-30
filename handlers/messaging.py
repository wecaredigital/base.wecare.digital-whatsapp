# =============================================================================
# Core Messaging Handlers
# =============================================================================
# Send WhatsApp messages via AWS End User Messaging Social API.
# All handlers use the unified base utilities from handlers/base.py.
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional

from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    META_API_VERSION, WABA_PHONE_MAP,
    iso_now, jdump, safe, format_wa_number, origination_id_for_api, arn_suffix,
    get_waba_config, get_phone_arn, mime_to_ext,
    store_item, get_item, success_response, error_response,
    generate_s3_presigned_url,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_account_info(meta_waba_id: str) -> Optional[Dict[str, Any]]:
    """Get account info from WABA_PHONE_MAP."""
    config = WABA_PHONE_MAP.get(str(meta_waba_id)) if hasattr(WABA_PHONE_MAP, 'get') else {}
    if not config:
        # Try direct dict access for _LazyEnvVar
        try:
            config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
        except:
            config = {}
    return config if config else None


def _send_whatsapp_message(phone_arn: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send WhatsApp message via AWS Social Messaging API."""
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        return {"success": True, "messageId": response.get("messageId")}
    except ClientError as e:
        logger.exception(f"Failed to send message: {e}")
        return {"success": False, "error": str(e)}


def _upload_s3_to_whatsapp(phone_arn: str, s3_key: str) -> Dict[str, Any]:
    """Upload S3 media to WhatsApp and get media ID."""
    try:
        response = social().post_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        return {"success": True, "mediaId": response.get("mediaId")}
    except ClientError as e:
        logger.exception(f"Failed to upload media: {e}")
        return {"success": False, "error": str(e)}


def _store_outbound_message(msg_pk: str, meta_waba_id: str, phone_arn: str, 
                            to_number: str, msg_type: str, message_id: str,
                            extra_fields: Dict[str, Any] = None) -> None:
    """Store outbound message in DynamoDB."""
    config = _get_account_info(meta_waba_id)
    item = {
        MESSAGES_PK_NAME: msg_pk,
        "itemType": "MESSAGE",
        "direction": "OUTBOUND",
        "sentAt": iso_now(),
        "wabaMetaId": meta_waba_id,
        "originationPhoneNumberId": phone_arn,
        "to": to_number,
        "type": msg_type,
        "messageId": message_id,
        "businessAccountName": config.get("businessAccountName", "") if config else "",
    }
    if extra_fields:
        item.update(extra_fields)
    store_item(item)


# =============================================================================
# SEND TEXT MESSAGE
# =============================================================================

def handle_send_text(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a text message.
    
    Required: metaWabaId, to, text
    Optional: previewUrl, replyToMessageId
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    text = event.get("text", "")
    preview_url = event.get("previewUrl", False)
    reply_to = event.get("replyToMessageId", "")
    
    if not meta_waba_id or not to_number or not text:
        return error_response("metaWabaId, to, and text are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text},
    }
    
    if reply_to:
        payload["context"] = {"message_id": reply_to}
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "text", msg_id,
            {"textBody": text, "preview": text[:200]}
        )
        return success_response("send_text", messageId=msg_id, to=to_formatted)
    
    return error_response(result.get("error", "Failed to send message"), 500)


# =============================================================================
# SEND MEDIA MESSAGE
# =============================================================================

def handle_send_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a media message (image, video, audio, document).
    
    Required: metaWabaId, to, mediaType, (s3Key or mediaId)
    Optional: caption, filename, replyToMessageId
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    media_type = event.get("mediaType", "")
    s3_key = event.get("s3Key", "")
    media_id = event.get("mediaId", "")
    caption = event.get("caption", "")
    filename = event.get("filename", "")
    reply_to = event.get("replyToMessageId", "")
    
    if not meta_waba_id or not to_number or not media_type:
        return error_response("metaWabaId, to, and mediaType are required")
    
    if not s3_key and not media_id:
        return error_response("s3Key or mediaId is required")
    
    if media_type not in ("image", "video", "audio", "document"):
        return error_response(f"Invalid mediaType: {media_type}. Valid: image, video, audio, document")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    # Upload to WhatsApp if s3Key provided
    if s3_key and not media_id:
        upload_result = _upload_s3_to_whatsapp(phone_arn, s3_key)
        if not upload_result.get("success"):
            return error_response(f"Failed to upload media: {upload_result.get('error')}", 500)
        media_id = upload_result["mediaId"]
    
    # Build payload
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": media_type,
        media_type: {"id": media_id},
    }
    
    if caption and media_type in ("image", "video", "document"):
        payload[media_type]["caption"] = caption
    
    if filename and media_type == "document":
        payload[media_type]["filename"] = filename
    
    if reply_to:
        payload["context"] = {"message_id": reply_to}
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, media_type, msg_id,
            {"mediaId": media_id, "s3Key": s3_key, "caption": caption, "filename": filename,
             "preview": f"[{media_type}] {caption}" if caption else f"[{media_type}]"}
        )
        return success_response("send_media", messageId=msg_id, to=to_formatted, 
                               mediaType=media_type, mediaId=media_id)
    
    return error_response(result.get("error", "Failed to send message"), 500)


# Convenience wrappers
def handle_send_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an image message."""
    event["mediaType"] = "image"
    return handle_send_media(event, context)


def handle_send_video(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a video message."""
    event["mediaType"] = "video"
    return handle_send_media(event, context)


def handle_send_audio(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an audio message."""
    event["mediaType"] = "audio"
    return handle_send_media(event, context)


def handle_send_document(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a document message."""
    event["mediaType"] = "document"
    return handle_send_media(event, context)


# =============================================================================
# SEND STICKER
# =============================================================================

def handle_send_sticker(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a sticker message (WebP format).
    
    Required: metaWabaId, to, (s3Key or mediaId)
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    s3_key = event.get("s3Key", "")
    media_id = event.get("mediaId", "")
    
    if not meta_waba_id or not to_number:
        return error_response("metaWabaId and to are required")
    
    if not s3_key and not media_id:
        return error_response("s3Key or mediaId is required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    if s3_key and not media_id:
        upload_result = _upload_s3_to_whatsapp(phone_arn, s3_key)
        if not upload_result.get("success"):
            return error_response(f"Failed to upload sticker: {upload_result.get('error')}", 500)
        media_id = upload_result["mediaId"]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "sticker",
        "sticker": {"id": media_id},
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "sticker", msg_id,
            {"mediaId": media_id, "s3Key": s3_key, "preview": "[sticker]"}
        )
        return success_response("send_sticker", messageId=msg_id, to=to_formatted, mediaId=media_id)
    
    return error_response(result.get("error", "Failed to send sticker"), 500)


# =============================================================================
# SEND LOCATION
# =============================================================================

def handle_send_location(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a location message.
    
    Required: metaWabaId, to, latitude, longitude
    Optional: name, address
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    latitude = event.get("latitude")
    longitude = event.get("longitude")
    name = event.get("name", "")
    address = event.get("address", "")
    
    if not meta_waba_id or not to_number:
        return error_response("metaWabaId and to are required")
    
    if latitude is None or longitude is None:
        return error_response("latitude and longitude are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    location_obj = {"latitude": float(latitude), "longitude": float(longitude)}
    if name:
        location_obj["name"] = name
    if address:
        location_obj["address"] = address
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "location",
        "location": location_obj,
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "location", msg_id,
            {"latitude": latitude, "longitude": longitude, "locationName": name, 
             "locationAddress": address, "preview": f"[location] {name or address or 'Location'}"}
        )
        return success_response("send_location", messageId=msg_id, to=to_formatted)
    
    return error_response(result.get("error", "Failed to send location"), 500)


# =============================================================================
# SEND CONTACT
# =============================================================================

def handle_send_contact(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a contact card.
    
    Required: metaWabaId, to, contacts (array of contact objects)
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    contacts = event.get("contacts", [])
    
    if not meta_waba_id or not to_number:
        return error_response("metaWabaId and to are required")
    
    if not contacts:
        return error_response("contacts array is required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "contacts",
        "contacts": contacts,
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        first_contact = contacts[0] if contacts else {}
        contact_name = first_contact.get("name", {}).get("formatted_name", "Contact")
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "contacts", msg_id,
            {"contacts": contacts, "preview": f"[contact] {contact_name}"}
        )
        return success_response("send_contact", messageId=msg_id, to=to_formatted, 
                               contactCount=len(contacts))
    
    return error_response(result.get("error", "Failed to send contact"), 500)


# =============================================================================
# SEND REACTION
# =============================================================================

def handle_send_reaction(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a reaction to a message.
    
    Required: metaWabaId, to, messageId, emoji
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    message_id = event.get("messageId", "")
    emoji = event.get("emoji", "👍")
    
    if not meta_waba_id or not to_number or not message_id:
        return error_response("metaWabaId, to, and messageId are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_formatted,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": emoji},
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        return success_response("send_reaction", messageId=result["messageId"], 
                               to=to_formatted, emoji=emoji, reactedTo=message_id)
    
    return error_response(result.get("error", "Failed to send reaction"), 500)


def handle_remove_reaction(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Remove a reaction from a message.
    
    Required: metaWabaId, to, messageId
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    message_id = event.get("messageId", "")
    
    if not meta_waba_id or not to_number or not message_id:
        return error_response("metaWabaId, to, and messageId are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    # Empty emoji removes the reaction
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_formatted,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": ""},
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        return success_response("remove_reaction", messageId=result["messageId"], 
                               to=to_formatted, removedFrom=message_id)
    
    return error_response(result.get("error", "Failed to remove reaction"), 500)


# =============================================================================
# SEND INTERACTIVE
# =============================================================================

def handle_send_interactive(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an interactive message (buttons or list).
    
    Required: metaWabaId, to, interactiveType, interactive
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    interactive_type = event.get("interactiveType", "")
    interactive = event.get("interactive", {})
    
    if not meta_waba_id or not to_number:
        return error_response("metaWabaId and to are required")
    
    if not interactive_type or not interactive:
        return error_response("interactiveType and interactive are required")
    
    if interactive_type not in ("button", "list", "product", "product_list", "cta_url", "flow"):
        return error_response(f"Invalid interactiveType: {interactive_type}")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    interactive["type"] = interactive_type
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "interactive",
        "interactive": interactive,
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        body_text = interactive.get("body", {}).get("text", "")
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "interactive", msg_id,
            {"interactiveType": interactive_type, "interactive": interactive,
             "preview": f"[{interactive_type}] {body_text[:100]}"}
        )
        return success_response("send_interactive", messageId=msg_id, to=to_formatted,
                               interactiveType=interactive_type)
    
    return error_response(result.get("error", "Failed to send interactive"), 500)


# =============================================================================
# SEND CTA URL
# =============================================================================

def handle_send_cta_url(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a CTA URL button message.
    
    Required: metaWabaId, to, bodyText, buttonText, url
    Optional: headerText, footerText
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body_text = event.get("bodyText", "")
    button_text = event.get("buttonText", "")
    url = event.get("url", "")
    header_text = event.get("headerText", "")
    footer_text = event.get("footerText", "")
    
    if not meta_waba_id or not to_number or not body_text or not button_text or not url:
        return error_response("metaWabaId, to, bodyText, buttonText, and url are required")
    
    interactive = {
        "type": "cta_url",
        "body": {"text": body_text},
        "action": {
            "name": "cta_url",
            "parameters": {"display_text": button_text, "url": url}
        }
    }
    
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive["footer"] = {"text": footer_text}
    
    event["interactiveType"] = "cta_url"
    event["interactive"] = interactive
    return handle_send_interactive(event, context)


# =============================================================================
# SEND TEMPLATE
# =============================================================================

def handle_send_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a template message.
    
    Required: metaWabaId, to, templateName
    Optional: languageCode, components
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    components = event.get("components", [])
    
    if not meta_waba_id or not to_number or not template_name:
        return error_response("metaWabaId, to, and templateName are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    template_obj = {
        "name": template_name,
        "language": {"code": language_code},
    }
    
    if components:
        template_obj["components"] = components
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "template",
        "template": template_obj,
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        msg_id = result["messageId"]
        _store_outbound_message(
            f"MSG#{msg_id}", meta_waba_id, phone_arn, to_formatted, "template", msg_id,
            {"templateName": template_name, "languageCode": language_code,
             "components": components, "preview": f"[template] {template_name}"}
        )
        return success_response("send_template", messageId=msg_id, to=to_formatted,
                               templateName=template_name, languageCode=language_code)
    
    return error_response(result.get("error", "Failed to send template"), 500)


# =============================================================================
# SEND REPLY
# =============================================================================

def handle_send_reply(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a reply to a specific message (with context/quote).
    
    Required: metaWabaId, to, replyToMessageId, (text or mediaType+s3Key)
    """
    reply_to = event.get("replyToMessageId", "")
    
    if not reply_to:
        return error_response("replyToMessageId is required")
    
    # Add reply context and delegate to appropriate handler
    event["replyToMessageId"] = reply_to
    
    if event.get("text"):
        return handle_send_text(event, context)
    elif event.get("mediaType") or event.get("s3Key"):
        return handle_send_media(event, context)
    else:
        return error_response("text or (mediaType + s3Key) is required for reply")


# =============================================================================
# MARK READ
# =============================================================================

def handle_mark_read(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Manually mark a message as read.
    
    Required: metaWabaId, messageId
    """
    meta_waba_id = event.get("metaWabaId", "")
    message_id = event.get("messageId", "")
    
    if not meta_waba_id or not message_id:
        return error_response("metaWabaId and messageId are required")
    
    config = _get_account_info(meta_waba_id)
    if not config or not config.get("phoneArn"):
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    
    payload = {
        "messaging_product": "whatsapp",
        "message_id": message_id,
        "status": "read",
    }
    
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        # Update DynamoDB
        msg_pk = f"MSG#{message_id}"
        try:
            table().update_item(
                Key={MESSAGES_PK_NAME: msg_pk},
                UpdateExpression="SET markedAsRead = :mar, markedAsReadAt = :at",
                ExpressionAttributeValues={":mar": True, ":at": iso_now()},
            )
        except ClientError:
            pass  # Non-critical
        
        return success_response("mark_read", messageId=message_id, marked=True)
    
    return error_response(result.get("error", "Failed to mark as read"), 500)


# =============================================================================
# HANDLER MAPPING
# =============================================================================

MESSAGING_HANDLERS = {
    "send_text": handle_send_text,
    "send_media": handle_send_media,
    "send_image": handle_send_image,
    "send_video": handle_send_video,
    "send_audio": handle_send_audio,
    "send_document": handle_send_document,
    "send_sticker": handle_send_sticker,
    "send_location": handle_send_location,
    "send_contact": handle_send_contact,
    "send_reaction": handle_send_reaction,
    "remove_reaction": handle_remove_reaction,
    "send_interactive": handle_send_interactive,
    "send_cta_url": handle_send_cta_url,
    "send_template": handle_send_template,
    "send_reply": handle_send_reply,
    "mark_read": handle_mark_read,
}
