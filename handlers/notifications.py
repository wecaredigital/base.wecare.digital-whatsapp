# =============================================================================
# Email Notifications via SES
# =============================================================================
# Production-grade email notifications using Amazon SES.
# Replaces SNS-based notifications to support HTML emails and avoid duplicates.
#
# Features:
# - HTML email templates for inbound/outbound messages
# - Idempotent sending (no duplicates)
# - Media attachment links
# - Configurable recipients per tenant
# =============================================================================

import json
import logging
import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, MESSAGES_PK_NAME, MEDIA_BUCKET,
    iso_now, store_item, get_item, update_item,
    validate_required_fields, success_response, error_response,
    generate_s3_presigned_url,
)
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# SES Configuration
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "noreply@wecare.digital")
SES_REGION = os.environ.get("SES_REGION", "ap-south-1")

# Default notification recipients
DEFAULT_NOTIFICATION_EMAILS = os.environ.get("NOTIFICATION_EMAILS", "").split(",")

# Lazy SES client
_ses_client = None

def get_ses():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=SES_REGION)
    return _ses_client


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

def build_inbound_email_html(
    sender_name: str,
    sender_number: str,
    message_text: str,
    message_type: str,
    media_url: str,
    business_name: str,
    received_at: str,
) -> str:
    """Build HTML email for inbound message notification."""
    
    media_section = ""
    if media_url:
        if message_type in ("image", "sticker"):
            media_section = f'''
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>📎 Media:</strong></td>
                <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                    <a href="{media_url}" target="_blank">
                        <img src="{media_url}" alt="Image" style="max-width: 300px; max-height: 300px; border-radius: 8px;">
                    </a>
                    <br><a href="{media_url}" target="_blank" style="color: #25D366;">View full image</a>
                </td>
            </tr>'''
        else:
            media_section = f'''
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>📎 Media:</strong></td>
                <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                    <a href="{media_url}" target="_blank" style="color: #25D366; text-decoration: none; padding: 8px 16px; background: #e8f5e9; border-radius: 4px;">
                        📥 Download {message_type.upper()}
                    </a>
                </td>
            </tr>'''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New WhatsApp Message</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); color: white; padding: 24px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px; font-weight: 600;">📱 New WhatsApp Message</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">{business_name}</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 24px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; width: 140px;"><strong>👤 From:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                        {sender_name or "Unknown"}<br>
                        <a href="https://wa.me/{sender_number}" style="color: #25D366; text-decoration: none;">+{sender_number}</a>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>📝 Type:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                        <span style="background: #e3f2fd; color: #1976d2; padding: 4px 12px; border-radius: 12px; font-size: 12px; text-transform: uppercase;">
                            {message_type}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>💬 Message:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; white-space: pre-wrap;">{message_text or "[No text content]"}</td>
                </tr>
                {media_section}
                <tr>
                    <td style="padding: 12px;"><strong>🕐 Received:</strong></td>
                    <td style="padding: 12px;">{received_at}</td>
                </tr>
            </table>
            
            <!-- Quick Reply Button -->
            <div style="text-align: center; margin-top: 24px;">
                <a href="https://wa.me/{sender_number}" target="_blank" 
                   style="display: inline-block; background: #25D366; color: white; padding: 12px 32px; border-radius: 24px; text-decoration: none; font-weight: 600;">
                    Reply on WhatsApp →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9f9f9; padding: 16px; text-align: center; font-size: 12px; color: #666;">
            <p style="margin: 0;">This is an automated notification from {business_name} WhatsApp Integration</p>
            <p style="margin: 8px 0 0 0;">Powered by WECARE.DIGITAL</p>
        </div>
    </div>
</body>
</html>'''


def build_outbound_email_html(
    recipient_number: str,
    message_text: str,
    message_type: str,
    template_name: str,
    business_name: str,
    sent_at: str,
    message_id: str,
) -> str:
    """Build HTML email for outbound message notification."""
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Message Sent</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); color: white; padding: 24px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px; font-weight: 600;">📤 Message Sent</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">{business_name}</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 24px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; width: 140px;"><strong>📱 To:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                        <a href="https://wa.me/{recipient_number.replace('+', '')}" style="color: #1976d2; text-decoration: none;">{recipient_number}</a>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>📝 Type:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">
                        <span style="background: #e3f2fd; color: #1976d2; padding: 4px 12px; border-radius: 12px; font-size: 12px; text-transform: uppercase;">
                            {message_type}
                        </span>
                        {f'<span style="margin-left: 8px; color: #666;">Template: {template_name}</span>' if template_name else ''}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>💬 Content:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; white-space: pre-wrap;">{message_text[:500] if message_text else "[Media/Template message]"}{"..." if message_text and len(message_text) > 500 else ""}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><strong>🆔 Message ID:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-family: monospace; font-size: 12px;">{message_id}</td>
                </tr>
                <tr>
                    <td style="padding: 12px;"><strong>🕐 Sent:</strong></td>
                    <td style="padding: 12px;">{sent_at}</td>
                </tr>
            </table>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9f9f9; padding: 16px; text-align: center; font-size: 12px; color: #666;">
            <p style="margin: 0;">Outbound message notification from {business_name}</p>
        </div>
    </div>
</body>
</html>'''


# =============================================================================
# IDEMPOTENCY HELPERS
# =============================================================================

def generate_notification_id(notification_type: str, message_id: str, recipient: str) -> str:
    """Generate unique notification ID for idempotency."""
    raw = f"{notification_type}:{message_id}:{recipient}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def check_notification_sent(notification_id: str) -> bool:
    """Check if notification was already sent (idempotency)."""
    try:
        response = table().get_item(
            Key={MESSAGES_PK_NAME: f"NOTIFICATION#{notification_id}"}
        )
        return "Item" in response
    except ClientError:
        return False


def mark_notification_sent(notification_id: str, notification_type: str, recipient: str, message_id: str) -> None:
    """Mark notification as sent for idempotency."""
    store_item({
        MESSAGES_PK_NAME: f"NOTIFICATION#{notification_id}",
        "itemType": "NOTIFICATION_SENT",
        "notificationType": notification_type,
        "recipient": recipient,
        "messageId": message_id,
        "sentAt": iso_now(),
        "ttl": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),  # Auto-expire after 7 days
    })


# =============================================================================
# NOTIFICATION HANDLERS
# =============================================================================

def handle_send_inbound_notification(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send email notification for inbound WhatsApp message.
    
    Required: messageId, senderNumber, messageText, messageType
    Optional: senderName, mediaUrl, businessName, recipients
    
    Test Event:
    {
        "action": "send_inbound_notification",
        "messageId": "wamid.xxx",
        "senderNumber": "447447840003",
        "senderName": "Test User",
        "messageText": "Hello!",
        "messageType": "text"
    }
    """
    message_id = event.get("messageId", "")
    sender_number = event.get("senderNumber", "")
    sender_name = event.get("senderName", "")
    message_text = event.get("messageText", "")
    message_type = event.get("messageType", "text")
    media_url = event.get("mediaUrl", "")
    business_name = event.get("businessName", "WECARE.DIGITAL")
    recipients = event.get("recipients", DEFAULT_NOTIFICATION_EMAILS)
    
    error = validate_required_fields(event, ["messageId", "senderNumber", "messageType"])
    if error:
        return error
    
    # Filter empty recipients
    recipients = [r.strip() for r in recipients if r.strip()]
    if not recipients:
        return success_response("send_inbound_notification",
            sent=False,
            reason="No recipients configured",
        )
    
    # Check idempotency
    for recipient in recipients:
        notification_id = generate_notification_id("inbound", message_id, recipient)
        if check_notification_sent(notification_id):
            logger.info(f"Notification already sent: {notification_id}")
            continue
        
        # Build email
        html_body = build_inbound_email_html(
            sender_name=sender_name,
            sender_number=sender_number,
            message_text=message_text,
            message_type=message_type,
            media_url=media_url,
            business_name=business_name,
            received_at=iso_now(),
        )
        
        subject = f"📱 New WhatsApp from +{sender_number}"
        if sender_name:
            subject = f"📱 New WhatsApp from {sender_name}"
        
        try:
            get_ses().send_email(
                Source=SES_SENDER_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": f"New message from +{sender_number}: {message_text}", "Charset": "UTF-8"},
                    }
                }
            )
            
            # Mark as sent
            mark_notification_sent(notification_id, "inbound", recipient, message_id)
            logger.info(f"Sent inbound notification to {recipient}")
            
        except ClientError as e:
            logger.error(f"Failed to send notification to {recipient}: {e}")
    
    return success_response("send_inbound_notification",
        sent=True,
        messageId=message_id,
        recipientCount=len(recipients),
    )


def handle_send_outbound_notification(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send email notification for outbound WhatsApp message.
    
    Required: messageId, recipientNumber, messageType
    Optional: messageText, templateName, businessName, recipients
    
    Test Event:
    {
        "action": "send_outbound_notification",
        "messageId": "msg_xxx",
        "recipientNumber": "+447447840003",
        "messageText": "Your order is ready!",
        "messageType": "text"
    }
    """
    message_id = event.get("messageId", "")
    recipient_number = event.get("recipientNumber", "")
    message_text = event.get("messageText", "")
    message_type = event.get("messageType", "text")
    template_name = event.get("templateName", "")
    business_name = event.get("businessName", "WECARE.DIGITAL")
    recipients = event.get("recipients", DEFAULT_NOTIFICATION_EMAILS)
    
    error = validate_required_fields(event, ["messageId", "recipientNumber", "messageType"])
    if error:
        return error
    
    # Filter empty recipients
    recipients = [r.strip() for r in recipients if r.strip()]
    if not recipients:
        return success_response("send_outbound_notification",
            sent=False,
            reason="No recipients configured",
        )
    
    sent_count = 0
    for recipient in recipients:
        notification_id = generate_notification_id("outbound", message_id, recipient)
        if check_notification_sent(notification_id):
            logger.info(f"Notification already sent: {notification_id}")
            continue
        
        # Build email
        html_body = build_outbound_email_html(
            recipient_number=recipient_number,
            message_text=message_text,
            message_type=message_type,
            template_name=template_name,
            business_name=business_name,
            sent_at=iso_now(),
            message_id=message_id,
        )
        
        subject = f"📤 WhatsApp sent to {recipient_number}"
        
        try:
            get_ses().send_email(
                Source=SES_SENDER_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": f"Message sent to {recipient_number}: {message_text[:200]}", "Charset": "UTF-8"},
                    }
                }
            )
            
            mark_notification_sent(notification_id, "outbound", recipient, message_id)
            sent_count += 1
            logger.info(f"Sent outbound notification to {recipient}")
            
        except ClientError as e:
            logger.error(f"Failed to send notification to {recipient}: {e}")
    
    return success_response("send_outbound_notification",
        sent=sent_count > 0,
        messageId=message_id,
        sentCount=sent_count,
    )


def handle_get_notification_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get notification configuration for a tenant.
    
    Required: tenantId (or metaWabaId)
    
    Test Event:
    {
        "action": "get_notification_config",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    config_pk = f"TENANT#{tenant_id}#NOTIFICATION#config"
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: config_pk})
        config = response.get("Item")
        
        if not config:
            # Return default config
            return success_response("get_notification_config",
                tenantId=tenant_id,
                config={
                    "enabled": True,
                    "inboundEnabled": True,
                    "outboundEnabled": False,
                    "recipients": DEFAULT_NOTIFICATION_EMAILS,
                    "senderEmail": SES_SENDER_EMAIL,
                    "isDefault": True,
                }
            )
        
        return success_response("get_notification_config",
            tenantId=tenant_id,
            config={
                "enabled": config.get("enabled", True),
                "inboundEnabled": config.get("inboundEnabled", True),
                "outboundEnabled": config.get("outboundEnabled", False),
                "recipients": config.get("recipients", []),
                "senderEmail": config.get("senderEmail", SES_SENDER_EMAIL),
                "isDefault": False,
                "updatedAt": config.get("updatedAt", ""),
            }
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_update_notification_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update notification configuration for a tenant.
    
    Required: tenantId
    Optional: enabled, inboundEnabled, outboundEnabled, recipients, senderEmail
    
    Test Event:
    {
        "action": "update_notification_config",
        "tenantId": "wecare-digital",
        "recipients": ["admin@wecare.digital"],
        "inboundEnabled": true,
        "outboundEnabled": true
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    now = iso_now()
    config_pk = f"TENANT#{tenant_id}#NOTIFICATION#config"
    
    config_item = {
        MESSAGES_PK_NAME: config_pk,
        "itemType": "NOTIFICATION_CONFIG",
        "tenantId": tenant_id,
        "enabled": event.get("enabled", True),
        "inboundEnabled": event.get("inboundEnabled", True),
        "outboundEnabled": event.get("outboundEnabled", False),
        "recipients": event.get("recipients", DEFAULT_NOTIFICATION_EMAILS),
        "senderEmail": event.get("senderEmail", SES_SENDER_EMAIL),
        "updatedAt": now,
        "createdAt": now,
    }
    
    try:
        store_item(config_item)
        
        return success_response("update_notification_config",
            tenantId=tenant_id,
            message="Notification config updated",
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_test_notification(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a test notification email.
    
    Required: recipient
    Optional: notificationType (inbound/outbound)
    
    Test Event:
    {
        "action": "test_notification",
        "recipient": "test@example.com",
        "notificationType": "inbound"
    }
    """
    recipient = event.get("recipient", "")
    notification_type = event.get("notificationType", "inbound")
    
    if not recipient:
        return error_response("recipient is required")
    
    if notification_type == "inbound":
        html_body = build_inbound_email_html(
            sender_name="Test User",
            sender_number="447447840003",
            message_text="This is a test notification from WECARE.DIGITAL WhatsApp integration.",
            message_type="text",
            media_url="",
            business_name="WECARE.DIGITAL",
            received_at=iso_now(),
        )
        subject = "🧪 Test: Inbound WhatsApp Notification"
    else:
        html_body = build_outbound_email_html(
            recipient_number="+447447840003",
            message_text="This is a test outbound notification.",
            message_type="text",
            template_name="",
            business_name="WECARE.DIGITAL",
            sent_at=iso_now(),
            message_id="test_msg_123",
        )
        subject = "🧪 Test: Outbound WhatsApp Notification"
    
    try:
        get_ses().send_email(
            Source=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": "Test notification from WECARE.DIGITAL", "Charset": "UTF-8"},
                }
            }
        )
        
        return success_response("test_notification",
            sent=True,
            recipient=recipient,
            notificationType=notification_type,
        )
    except ClientError as e:
        return error_response(f"Failed to send test notification: {e}", 500)


# =============================================================================
# HANDLER MAPPING
# =============================================================================

NOTIFICATION_HANDLERS = {
    "send_inbound_notification": handle_send_inbound_notification,
    "send_outbound_notification": handle_send_outbound_notification,
    "get_notification_config": handle_get_notification_config,
    "update_notification_config": handle_update_notification_config,
    "test_notification": handle_test_notification,
}
