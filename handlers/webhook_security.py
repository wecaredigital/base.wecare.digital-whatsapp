# Webhook Security & Verification Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
#
# This module handles webhook verification and signature validation
# for secure webhook processing.
# =============================================================================

import json
import logging
import hashlib
import hmac
import os
from typing import Any, Dict, Optional
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Environment variables for webhook security
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "")
WEBHOOK_APP_SECRET = os.environ.get("WEBHOOK_APP_SECRET", "")


def handle_verify_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle webhook verification (GET request from Meta).
    
    When you configure a webhook URL in Meta Business Suite, Meta sends a GET
    request with a challenge to verify you control the endpoint.
    
    Query Parameters from Meta:
    - hub.mode: Should be "subscribe"
    - hub.verify_token: The token you set in Meta Business Suite
    - hub.challenge: Random string to echo back
    
    Test Event:
    {
        "action": "verify_webhook",
        "hub.mode": "subscribe",
        "hub.verify_token": "your_verify_token",
        "hub.challenge": "1234567890"
    }
    
    Or from API Gateway query parameters:
    {
        "action": "verify_webhook",
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "your_verify_token",
            "hub.challenge": "1234567890"
        }
    }
    """
    # Extract parameters (support both direct and queryStringParameters)
    query_params = event.get("queryStringParameters", {}) or {}
    
    hub_mode = event.get("hub.mode") or query_params.get("hub.mode", "")
    hub_verify_token = event.get("hub.verify_token") or query_params.get("hub.verify_token", "")
    hub_challenge = event.get("hub.challenge") or query_params.get("hub.challenge", "")
    
    # Get verify token from environment or event
    expected_token = event.get("expectedToken") or WEBHOOK_VERIFY_TOKEN
    
    if not expected_token:
        logger.error("WEBHOOK_VERIFY_TOKEN not configured")
        return {
            "statusCode": 500,
            "error": "Webhook verify token not configured"
        }
    
    # Validate the verification request
    if hub_mode != "subscribe":
        logger.warning(f"Invalid hub.mode: {hub_mode}")
        return {
            "statusCode": 400,
            "error": f"Invalid hub.mode. Expected 'subscribe', got '{hub_mode}'"
        }
    
    if hub_verify_token != expected_token:
        logger.warning("Webhook verification token mismatch")
        return {
            "statusCode": 403,
            "error": "Verification token mismatch"
        }
    
    if not hub_challenge:
        return {
            "statusCode": 400,
            "error": "Missing hub.challenge"
        }
    
    # Log successful verification
    now = iso_now()
    try:
        store_item({
            MESSAGES_PK_NAME: f"WEBHOOK_VERIFICATION#{now}",
            "itemType": "WEBHOOK_VERIFICATION",
            "verifiedAt": now,
            "challenge": hub_challenge,
            "success": True,
        })
    except Exception as e:
        logger.warning(f"Failed to log webhook verification: {e}")
    
    logger.info(f"Webhook verified successfully. Challenge: {hub_challenge}")
    
    # Return the challenge as plain text (required by Meta)
    # Note: The Lambda response format depends on your API Gateway configuration
    return {
        "statusCode": 200,
        "body": hub_challenge,
        "headers": {
            "Content-Type": "text/plain"
        },
        "isBase64Encoded": False,
        # Also include for direct invocation
        "challenge": hub_challenge,
        "verified": True
    }


def handle_validate_webhook_signature(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate webhook payload signature (X-Hub-Signature-256).
    
    Meta signs all webhook payloads with your app secret. This handler
    validates the signature to ensure the payload is authentic.
    
    Test Event:
    {
        "action": "validate_webhook_signature",
        "signature": "sha256=abc123...",
        "payload": "{\"object\":\"whatsapp_business_account\",...}",
        "appSecret": "your_app_secret"
    }
    
    Or from API Gateway:
    {
        "action": "validate_webhook_signature",
        "headers": {
            "X-Hub-Signature-256": "sha256=abc123..."
        },
        "body": "{\"object\":\"whatsapp_business_account\",...}"
    }
    """
    # Extract signature and payload
    headers = event.get("headers", {}) or {}
    
    # Handle case-insensitive headers
    signature = event.get("signature") or headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256", "")
    payload = event.get("payload") or event.get("body", "")
    app_secret = event.get("appSecret") or WEBHOOK_APP_SECRET
    
    if not signature:
        return {
            "statusCode": 400,
            "error": "Missing X-Hub-Signature-256 header",
            "valid": False
        }
    
    if not payload:
        return {
            "statusCode": 400,
            "error": "Missing payload/body",
            "valid": False
        }
    
    if not app_secret:
        logger.error("WEBHOOK_APP_SECRET not configured")
        return {
            "statusCode": 500,
            "error": "App secret not configured",
            "valid": False
        }
    
    # Parse signature
    if not signature.startswith("sha256="):
        return {
            "statusCode": 400,
            "error": "Invalid signature format. Expected 'sha256=...'",
            "valid": False
        }
    
    expected_signature = signature[7:]  # Remove "sha256=" prefix
    
    # Calculate expected signature
    # Ensure payload is bytes
    if isinstance(payload, str):
        payload_bytes = payload.encode('utf-8')
    else:
        payload_bytes = payload
    
    calculated_signature = hmac.new(
        app_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (timing-safe comparison)
    is_valid = hmac.compare_digest(expected_signature.lower(), calculated_signature.lower())
    
    if not is_valid:
        logger.warning("Webhook signature validation failed")
        return {
            "statusCode": 403,
            "error": "Invalid signature",
            "valid": False
        }
    
    logger.info("Webhook signature validated successfully")
    
    return {
        "statusCode": 200,
        "operation": "validate_webhook_signature",
        "valid": True,
        "message": "Signature is valid"
    }


def handle_process_secure_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process webhook with automatic signature validation.
    
    This is a convenience handler that validates the signature and then
    processes the webhook payload.
    
    Test Event:
    {
        "action": "process_secure_webhook",
        "headers": {
            "X-Hub-Signature-256": "sha256=abc123..."
        },
        "body": "{\"object\":\"whatsapp_business_account\",\"entry\":[...]}"
    }
    """
    headers = event.get("headers", {}) or {}
    body = event.get("body", "")
    
    # First validate signature
    validation_result = handle_validate_webhook_signature({
        "headers": headers,
        "body": body
    }, context)
    
    if not validation_result.get("valid"):
        return validation_result
    
    # Parse the webhook body
    try:
        if isinstance(body, str):
            webhook_data = json.loads(body)
        else:
            webhook_data = body
    except json.JSONDecodeError as e:
        return {
            "statusCode": 400,
            "error": f"Invalid JSON payload: {str(e)}"
        }
    
    # Process the webhook
    now = iso_now()
    processed_events = []
    
    try:
        object_type = webhook_data.get("object", "")
        entries = webhook_data.get("entry", [])
        
        for entry in entries:
            entry_id = entry.get("id", "")
            changes = entry.get("changes", [])
            
            for change in changes:
                field = change.get("field", "")
                value = change.get("value", {})
                
                event_pk = f"SECURE_WEBHOOK#{entry_id}#{now}#{field}"
                
                store_item({
                    MESSAGES_PK_NAME: event_pk,
                    "itemType": "SECURE_WEBHOOK_EVENT",
                    "objectType": object_type,
                    "entryId": entry_id,
                    "field": field,
                    "value": value,
                    "receivedAt": now,
                    "signatureValid": True,
                })
                
                processed_events.append({
                    "pk": event_pk,
                    "field": field,
                    "entryId": entry_id
                })
        
        return {
            "statusCode": 200,
            "operation": "process_secure_webhook",
            "signatureValid": True,
            "processedCount": len(processed_events),
            "events": processed_events
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_webhook_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Store webhook configuration for a WABA.
    
    Test Event:
    {
        "action": "set_webhook_config",
        "metaWabaId": "1347766229904230",
        "verifyToken": "my_secure_token",
        "appSecret": "app_secret_from_meta",
        "webhookUrl": "https://api.example.com/webhook",
        "subscribedFields": ["messages", "message_template_status_update"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    verify_token = event.get("verifyToken", "")
    app_secret = event.get("appSecret", "")
    webhook_url = event.get("webhookUrl", "")
    subscribed_fields = event.get("subscribedFields", [
        "messages",
        "message_template_status_update",
        "phone_number_quality_update",
        "account_update"
    ])
    
    error = validate_required_fields(event, ["metaWabaId", "verifyToken"])
    if error:
        return error
    
    now = iso_now()
    config_pk = f"WEBHOOK_CONFIG#{meta_waba_id}"
    
    try:
        # Note: In production, encrypt appSecret before storing
        store_item({
            MESSAGES_PK_NAME: config_pk,
            "itemType": "WEBHOOK_CONFIG",
            "wabaMetaId": meta_waba_id,
            "verifyToken": verify_token,
            "appSecretHash": hashlib.sha256(app_secret.encode()).hexdigest() if app_secret else "",
            "webhookUrl": webhook_url,
            "subscribedFields": subscribed_fields,
            "status": "ACTIVE",
            "configuredAt": now,
            "lastUpdatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_webhook_config",
            "wabaMetaId": meta_waba_id,
            "webhookUrl": webhook_url,
            "subscribedFields": subscribed_fields,
            "status": "ACTIVE"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_webhook_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get webhook configuration for a WABA.
    
    Test Event:
    {
        "action": "get_webhook_config",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    config_pk = f"WEBHOOK_CONFIG#{meta_waba_id}"
    
    try:
        config = get_item(config_pk)
        
        if not config:
            return {
                "statusCode": 404,
                "error": f"Webhook config not found for WABA: {meta_waba_id}"
            }
        
        # Don't return sensitive data
        safe_config = {
            "wabaMetaId": config.get("wabaMetaId"),
            "webhookUrl": config.get("webhookUrl"),
            "subscribedFields": config.get("subscribedFields"),
            "status": config.get("status"),
            "configuredAt": config.get("configuredAt"),
            "hasAppSecret": bool(config.get("appSecretHash")),
        }
        
        return {
            "statusCode": 200,
            "operation": "get_webhook_config",
            "config": safe_config
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_test_webhook_signature(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Generate a test signature for webhook testing.
    
    This is useful for testing your webhook endpoint locally.
    
    Test Event:
    {
        "action": "test_webhook_signature",
        "payload": "{\"object\":\"whatsapp_business_account\",\"entry\":[]}",
        "appSecret": "your_app_secret"
    }
    """
    payload = event.get("payload", "")
    app_secret = event.get("appSecret") or WEBHOOK_APP_SECRET
    
    error = validate_required_fields(event, ["payload"])
    if error:
        return error
    
    if not app_secret:
        return {
            "statusCode": 400,
            "error": "appSecret is required (or set WEBHOOK_APP_SECRET env var)"
        }
    
    # Generate signature
    if isinstance(payload, str):
        payload_bytes = payload.encode('utf-8')
    else:
        payload_bytes = json.dumps(payload).encode('utf-8')
    
    signature = hmac.new(
        app_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    return {
        "statusCode": 200,
        "operation": "test_webhook_signature",
        "signature": f"sha256={signature}",
        "header": "X-Hub-Signature-256",
        "usage": "Add this header to your test webhook request"
    }


def handle_webhook_retry(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle webhook retry logic for failed deliveries.
    
    Meta retries webhook deliveries if they fail. This handler tracks
    retry attempts and can be used to implement custom retry logic.
    
    Test Event:
    {
        "action": "webhook_retry",
        "webhookEventId": "WEBHOOK_EVENT#xxx",
        "retryCount": 1,
        "lastError": "Connection timeout"
    }
    """
    webhook_event_id = event.get("webhookEventId", "")
    retry_count = event.get("retryCount", 0)
    last_error = event.get("lastError", "")
    max_retries = event.get("maxRetries", 5)
    
    error = validate_required_fields(event, ["webhookEventId"])
    if error:
        return error
    
    now = iso_now()
    
    try:
        # Get the original webhook event
        original_event = get_item(webhook_event_id)
        
        if not original_event:
            return {"statusCode": 404, "error": f"Webhook event not found: {webhook_event_id}"}
        
        # Check if max retries exceeded
        if retry_count >= max_retries:
            # Mark as failed permanently
            table().update_item(
                Key={MESSAGES_PK_NAME: webhook_event_id},
                UpdateExpression="SET retryStatus = :rs, lastRetryAt = :lra, retryCount = :rc, lastError = :le",
                ExpressionAttributeValues={
                    ":rs": "FAILED_PERMANENTLY",
                    ":lra": now,
                    ":rc": retry_count,
                    ":le": last_error
                }
            )
            
            return {
                "statusCode": 200,
                "operation": "webhook_retry",
                "webhookEventId": webhook_event_id,
                "status": "FAILED_PERMANENTLY",
                "retryCount": retry_count,
                "message": f"Max retries ({max_retries}) exceeded"
            }
        
        # Update retry status
        table().update_item(
            Key={MESSAGES_PK_NAME: webhook_event_id},
            UpdateExpression="SET retryStatus = :rs, lastRetryAt = :lra, retryCount = :rc, lastError = :le",
            ExpressionAttributeValues={
                ":rs": "PENDING_RETRY",
                ":lra": now,
                ":rc": retry_count,
                ":le": last_error
            }
        )
        
        # Calculate next retry delay (exponential backoff)
        next_retry_delay = min(300, 2 ** retry_count * 10)  # Max 5 minutes
        
        return {
            "statusCode": 200,
            "operation": "webhook_retry",
            "webhookEventId": webhook_event_id,
            "status": "PENDING_RETRY",
            "retryCount": retry_count,
            "nextRetryDelaySeconds": next_retry_delay,
            "remainingRetries": max_retries - retry_count
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
