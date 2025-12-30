# Webhook Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/webhooks

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, sns, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Webhook Event Types
WEBHOOK_EVENT_TYPES = {
    # Account Events
    "account_update": "Account status changes",
    "account_review_update": "Account review status",
    "phone_number_name_update": "Display name changes",
    "phone_number_quality_update": "Quality rating changes",
    "template_category_update": "Template category changes",
    # Message Events
    "messages": "Incoming messages",
    "message_template_status_update": "Template approval status",
    # Status Events
    "statuses": "Message delivery status"
}


def handle_register_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Register webhook endpoint configuration.
    
    Test Event:
    {
        "action": "register_webhook",
        "metaWabaId": "1347766229904230",
        "webhookUrl": "https://api.example.com/webhook",
        "verifyToken": "my_verify_token",
        "subscribedEvents": ["messages", "statuses", "account_update"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    webhook_url = event.get("webhookUrl", "")
    verify_token = event.get("verifyToken", "")
    subscribed_events = event.get("subscribedEvents", list(WEBHOOK_EVENT_TYPES.keys()))
    
    error = validate_required_fields(event, ["metaWabaId", "webhookUrl", "verifyToken"])
    if error:
        return error
    
    now = iso_now()
    webhook_pk = f"WEBHOOK#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: webhook_pk,
            "itemType": "WEBHOOK_CONFIG",
            "wabaMetaId": meta_waba_id,
            "webhookUrl": webhook_url,
            "verifyToken": verify_token,
            "subscribedEvents": subscribed_events,
            "status": "ACTIVE",
            "createdAt": now,
            "lastUpdatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "register_webhook",
            "webhookPk": webhook_pk,
            "subscribedEvents": subscribed_events,
            "status": "ACTIVE"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_process_wix_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Wix e-commerce webhook for order notifications.
    
    Test Event:
    {
        "action": "process_wix_webhook",
        "metaWabaId": "1347766229904230",
        "wixEvent": {
            "eventType": "order_created",
            "orderId": "WIX-ORD-12345",
            "customerPhone": "+919876543210",
            "customerName": "John Doe",
            "orderTotal": "₹2,500",
            "items": [
                {"name": "Product A", "quantity": 2, "price": "₹1,000"},
                {"name": "Product B", "quantity": 1, "price": "₹500"}
            ],
            "shippingAddress": "123 Main St, Mumbai"
        },
        "templateName": "order_confirmation"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    wix_event = event.get("wixEvent", {})
    template_name = event.get("templateName", "order_confirmation")
    
    error = validate_required_fields(event, ["metaWabaId", "wixEvent"])
    if error:
        return error
    
    event_type = wix_event.get("eventType", "")
    order_id = wix_event.get("orderId", "")
    customer_phone = wix_event.get("customerPhone", "")
    customer_name = wix_event.get("customerName", "")
    order_total = wix_event.get("orderTotal", "")
    
    if not customer_phone:
        return {"statusCode": 400, "error": "Customer phone is required in wixEvent"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    now = iso_now()
    
    try:
        # Store Wix order
        order_pk = f"WIX_ORDER#{order_id}"
        store_item({
            MESSAGES_PK_NAME: order_pk,
            "itemType": "WIX_ORDER",
            "wabaMetaId": meta_waba_id,
            "orderId": order_id,
            "eventType": event_type,
            "customerPhone": customer_phone,
            "customerName": customer_name,
            "orderTotal": order_total,
            "orderData": wix_event,
            "receivedAt": now,
            "notificationSent": False,
        })
        
        # Send WhatsApp notification based on event type
        template_map = {
            "order_created": "order_confirmation",
            "order_paid": "payment_received",
            "order_shipped": "shipping_notification",
            "order_delivered": "delivery_confirmation",
            "order_cancelled": "order_cancelled"
        }
        
        actual_template = template_map.get(event_type, template_name)
        
        # Build template message
        body_params = [customer_name, order_id, order_total]
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(customer_phone),
            "type": "template",
            "template": {
                "name": actual_template,
                "language": {"code": "en_US"},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in body_params]
                }]
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        # Update order with notification status
        if result.get("success"):
            table().update_item(
                Key={MESSAGES_PK_NAME: order_pk},
                UpdateExpression="SET notificationSent = :ns, notificationMessageId = :mid, notificationSentAt = :sat",
                ExpressionAttributeValues={
                    ":ns": True,
                    ":mid": result.get("messageId", ""),
                    ":sat": now
                }
            )
        
        return {
            "statusCode": 200,
            "operation": "process_wix_webhook",
            "orderId": order_id,
            "eventType": event_type,
            "notificationSent": result.get("success", False),
            "messageId": result.get("messageId", ""),
            "templateUsed": actual_template
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_webhook_events(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get webhook events history.
    
    Test Event:
    {
        "action": "get_webhook_events",
        "metaWabaId": "1347766229904230",
        "eventType": "messages",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    event_type = event.get("eventType", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "begins_with(pk, :prefix)"
        expr_values = {":prefix": "WEBHOOK_EVENT#"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        if event_type:
            filter_expr += " AND eventType = :et"
            expr_values[":et"] = event_type
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_webhook_events",
            "count": len(items),
            "events": items,
            "availableEventTypes": list(WEBHOOK_EVENT_TYPES.keys())
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_process_webhook_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process incoming webhook event from Meta.
    
    This handler processes all webhook event types:
    - Account events (account_update, phone_number_quality_update, etc.)
    - Template events (message_template_status_update)
    - Message events (messages - text, image, audio, video, document, etc.)
    - Status events (statuses - sent, delivered, read, failed)
    """
    webhook_body = event.get("webhookBody", {})
    
    if not webhook_body:
        return {"statusCode": 400, "error": "webhookBody is required"}
    
    now = iso_now()
    processed_events = []
    
    try:
        entries = webhook_body.get("entry", [])
        
        for entry in entries:
            waba_id = entry.get("id", "")
            changes = entry.get("changes", [])
            
            for change in changes:
                field = change.get("field", "")
                value = change.get("value", {})
                
                event_pk = f"WEBHOOK_EVENT#{waba_id}#{now}#{field}"
                
                # Store the event
                event_data = {
                    MESSAGES_PK_NAME: event_pk,
                    "itemType": "WEBHOOK_EVENT",
                    "wabaMetaId": waba_id,
                    "eventType": field,
                    "eventData": value,
                    "receivedAt": now,
                    "processed": False,
                }
                
                # Process specific event types
                if field == "messages":
                    messages = value.get("messages", [])
                    for msg in messages:
                        event_data["messageType"] = msg.get("type", "")
                        event_data["fromNumber"] = msg.get("from", "")
                        event_data["messageId"] = msg.get("id", "")
                
                elif field == "statuses":
                    statuses = value.get("statuses", [])
                    for status in statuses:
                        event_data["statusType"] = status.get("status", "")
                        event_data["recipientId"] = status.get("recipient_id", "")
                        event_data["statusMessageId"] = status.get("id", "")
                
                elif field == "message_template_status_update":
                    event_data["templateName"] = value.get("message_template_name", "")
                    event_data["templateStatus"] = value.get("event", "")
                    event_data["reason"] = value.get("reason", "")
                
                elif field == "phone_number_quality_update":
                    event_data["qualityRating"] = value.get("current_limit", "")
                    event_data["displayPhoneNumber"] = value.get("display_phone_number", "")
                
                elif field == "account_update":
                    event_data["accountEvent"] = value.get("event", "")
                    event_data["banInfo"] = value.get("ban_info", {})
                
                store_item(event_data)
                event_data["processed"] = True
                processed_events.append({"pk": event_pk, "type": field})
        
        return {
            "statusCode": 200,
            "operation": "process_webhook_event",
            "processedCount": len(processed_events),
            "events": processed_events
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_wix_orders(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get Wix orders linked to WhatsApp contacts.
    
    Test Event:
    {
        "action": "get_wix_orders",
        "customerPhone": "+919876543210",
        "limit": 20
    }
    """
    customer_phone = event.get("customerPhone", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "WIX_ORDER"}
        
        if customer_phone:
            filter_expr += " AND customerPhone = :cp"
            expr_values[":cp"] = customer_phone
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_wix_orders",
            "count": len(items),
            "orders": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
