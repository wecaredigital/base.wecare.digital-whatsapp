# =============================================================================
# Email Notifier - HTML emails via SES
# =============================================================================
# Sends exactly 1 inbound email + 1 outbound email per message (idempotent)
# =============================================================================

import json
import logging
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Lazy clients
_ses_client = None
_dynamodb = None
_s3_client = None

def get_ses_client():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    return _ses_client

def get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    return _dynamodb

def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    return _s3_client


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS messages and send email notifications.
    Handles both inbound and outbound notification queues.
    """
    processed = 0
    errors = 0
    
    for record in event.get('Records', []):
        try:
            body = json.loads(record['body'])
            
            # Determine notification type from queue
            queue_arn = record.get('eventSourceARN', '')
            is_inbound = 'inbound-notify' in queue_arn
            
            if is_inbound:
                send_inbound_notification(body)
            else:
                send_outbound_notification(body)
            
            processed += 1
            
        except Exception as e:
            logger.exception(f"Error processing notification: {e}")
            errors += 1
    
    return {
        'statusCode': 200,
        'processed': processed,
        'errors': errors
    }


def check_idempotency(event_id: str) -> bool:
    """Check if email was already sent for this event."""
    table_name = os.environ.get('MESSAGES_TABLE_NAME', 'base-wecare-digital-whatsapp')
    table = get_dynamodb().Table(table_name)
    
    try:
        response = table.get_item(
            Key={'pk': f'EMAIL#{event_id}', 'sk': 'SENT'},
            ProjectionExpression='pk'
        )
        return 'Item' in response
    except ClientError:
        return False


def mark_email_sent(event_id: str, email_type: str):
    """Mark email as sent for idempotency."""
    table_name = os.environ.get('MESSAGES_TABLE_NAME', 'base-wecare-digital-whatsapp')
    table = get_dynamodb().Table(table_name)
    
    # TTL: 7 days
    ttl = int((datetime.now(timezone.utc).timestamp()) + (7 * 24 * 60 * 60))
    
    table.put_item(Item={
        'pk': f'EMAIL#{event_id}',
        'sk': 'SENT',
        'itemType': 'EMAIL_IDEMPOTENCY',
        'emailType': email_type,
        'sentAt': datetime.now(timezone.utc).isoformat(),
        'ttl': ttl
    })


def generate_presigned_url(s3_key: str, bucket: str = None) -> Optional[str]:
    """Generate presigned URL for S3 media."""
    if not s3_key:
        return None
    
    bucket = bucket or os.environ.get('MEDIA_BUCKET', 'dev.wecare.digital')
    
    try:
        url = get_s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=86400  # 24 hours
        )
        return url
    except ClientError:
        return None


def send_inbound_notification(event_data: Dict[str, Any]):
    """Send HTML email for inbound message."""
    message_id = event_data.get('messageId', 'unknown')
    event_id = f"inbound-{message_id}"
    
    # Idempotency check
    if check_idempotency(event_id):
        logger.info(f"Email already sent for {event_id}")
        return
    
    # Extract data (redact sensitive info in logs)
    sender_name = event_data.get('senderName', 'Unknown')
    sender_phone = event_data.get('from', 'Unknown')
    business_name = event_data.get('businessName', 'WECARE.DIGITAL')
    business_phone = event_data.get('businessPhone', '')
    message_type = event_data.get('messageType', 'text')
    text_body = event_data.get('text', event_data.get('caption', ''))
    media_s3_key = event_data.get('mediaS3Key', '')
    media_type = event_data.get('mediaType', '')
    waba_id = event_data.get('wabaId', '')
    phone_number_id = event_data.get('phoneNumberId', '')
    
    # Generate media link
    media_link = generate_presigned_url(media_s3_key) if media_s3_key else None
    
    # Build HTML
    html = build_inbound_html(
        sender_name=sender_name,
        sender_phone=sender_phone,
        business_name=business_name,
        business_phone=business_phone,
        message_type=message_type,
        text_body=text_body,
        media_link=media_link,
        media_type=media_type,
        message_id=message_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id
    )
    
    # Send email
    recipients = os.environ.get('INBOUND_NOTIFY_TO', 'ops@wecare.digital').split(',')
    sender = os.environ.get('SES_SENDER_EMAIL', 'noreply@wecare.digital')
    subject = f"📥 WhatsApp from {sender_name} ({sender_phone[-4:] if len(sender_phone) > 4 else '****'})"
    
    send_html_email(sender, recipients, subject, html)
    mark_email_sent(event_id, 'inbound')
    logger.info(f"Inbound notification sent for message {message_id}")


def send_outbound_notification(event_data: Dict[str, Any]):
    """Send HTML email for outbound message."""
    message_id = event_data.get('messageId', 'unknown')
    event_id = f"outbound-{message_id}"
    
    # Idempotency check
    if check_idempotency(event_id):
        logger.info(f"Email already sent for {event_id}")
        return
    
    # Extract data
    recipient_phone = event_data.get('to', 'Unknown')
    business_name = event_data.get('businessName', 'WECARE.DIGITAL')
    business_phone = event_data.get('businessPhone', '')
    message_type = event_data.get('messageType', 'text')
    text_body = event_data.get('text', event_data.get('caption', ''))
    template_name = event_data.get('templateName', '')
    waba_id = event_data.get('wabaId', '')
    phone_number_id = event_data.get('phoneNumberId', '')
    
    # Build HTML
    html = build_outbound_html(
        recipient_phone=recipient_phone,
        business_name=business_name,
        business_phone=business_phone,
        message_type=message_type,
        text_body=text_body,
        template_name=template_name,
        message_id=message_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id
    )
    
    # Send email
    recipients = os.environ.get('OUTBOUND_NOTIFY_TO', 'ops@wecare.digital').split(',')
    sender = os.environ.get('SES_SENDER_EMAIL', 'noreply@wecare.digital')
    subject = f"📤 WhatsApp sent to {recipient_phone[-4:] if len(recipient_phone) > 4 else '****'}"
    
    send_html_email(sender, recipients, subject, html)
    mark_email_sent(event_id, 'outbound')
    logger.info(f"Outbound notification sent for message {message_id}")


def build_inbound_html(**kwargs) -> str:
    """Build HTML for inbound notification."""
    media_section = ""
    if kwargs.get('media_link'):
        media_section = f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Media</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                {kwargs['media_type']} - <a href="{kwargs['media_link']}" style="color: #25D366;">Download</a>
            </td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #25D366; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">📥 Inbound WhatsApp Message</h2>
        </div>
        <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; width: 120px;"><strong>From</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['sender_name']} ({kwargs['sender_phone']})</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>To Business</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['business_name']} ({kwargs['business_phone']})</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Type</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['message_type']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Message</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['text_body'] or '(no text)'}</td>
                </tr>
                {media_section}
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Message ID</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; font-size: 11px; color: #666;">{kwargs['message_id']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>WABA / Phone</strong></td>
                    <td style="padding: 8px; font-size: 11px; color: #666;">{kwargs['waba_id']} / {kwargs['phone_number_id']}</td>
                </tr>
            </table>
        </div>
        <p style="font-size: 11px; color: #999; text-align: center; margin-top: 15px;">
            WECARE.DIGITAL WhatsApp Notifications
        </p>
    </body>
    </html>
    """


def build_outbound_html(**kwargs) -> str:
    """Build HTML for outbound notification."""
    template_section = ""
    if kwargs.get('template_name'):
        template_section = f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Template</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['template_name']}</td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #128C7E; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">📤 Outbound WhatsApp Message</h2>
        </div>
        <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; width: 120px;"><strong>To</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['recipient_phone']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>From Business</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['business_name']} ({kwargs['business_phone']})</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Type</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['message_type']}</td>
                </tr>
                {template_section}
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Message</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{kwargs['text_body'] or '(no text)'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Message ID</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; font-size: 11px; color: #666;">{kwargs['message_id']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>WABA / Phone</strong></td>
                    <td style="padding: 8px; font-size: 11px; color: #666;">{kwargs['waba_id']} / {kwargs['phone_number_id']}</td>
                </tr>
            </table>
        </div>
        <p style="font-size: 11px; color: #999; text-align: center; margin-top: 15px;">
            WECARE.DIGITAL WhatsApp Notifications
        </p>
    </body>
    </html>
    """


def send_html_email(sender: str, recipients: list, subject: str, html: str):
    """Send HTML email via SES with proper FROM name and REPLY-TO."""
    # Format sender with display name: "WECARE.DIGITAL" <one@wecare.digital>
    sender_email = os.environ.get('SES_SENDER_EMAIL', 'one@wecare.digital')
    sender_name = os.environ.get('SES_SENDER_NAME', 'WECARE.DIGITAL')
    formatted_sender = f'"{sender_name}" <{sender_email}>'
    
    # Reply-to address
    reply_to = os.environ.get('SES_REPLY_TO', 'selfcare@wecare.digital')
    
    try:
        get_ses_client().send_email(
            Source=formatted_sender,
            Destination={'ToAddresses': [r.strip() for r in recipients]},
            ReplyToAddresses=[reply_to],
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html, 'Charset': 'UTF-8'}
                }
            }
        )
    except ClientError as e:
        logger.exception(f"Failed to send email: {e}")
        raise
