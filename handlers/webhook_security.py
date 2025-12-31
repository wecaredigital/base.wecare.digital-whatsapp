# =============================================================================
# Webhook Security & Verification Handlers
# =============================================================================
# Production-grade webhook security for WhatsApp Business API.
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
#
# Features:
# - Webhook verification (GET challenge-response)
# - HMAC-SHA256 signature validation
# - Replay attack prevention with timestamp validation
# - Rate limiting for webhook endpoints
# - Secure configuration storage
# =============================================================================

import json
import logging
import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item, update_item,
    validate_required_fields, success_response, error_response,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "")
WEBHOOK_APP_SECRET = os.environ.get("WEBHOOK_APP_SECRET", "")

# Timestamp validation window (seconds) - reject webhooks older than this
TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 100


# =============================================================================
# SECURITY HELPER FUNCTIONS
# =============================================================================

def compute_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload."""
    return hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()


def validate_signature(payload: bytes, signature: str, secret: str) -> Tuple[bool, str]:
    """Validate webhook signature with timing-safe comparison.
    
    Returns: (is_valid, error_message)
    """
    if not signature:
        return False, "Missing signature"
    
    if not secret:
        return False, "App secret not configured"
    
    # Parse signature format
    if not signature.startswith("sha256="):
        return False, "Invalid signature format. Expected 'sha256=...'"
    
    provided_sig = signature[7:].lower()
    computed_sig = compute_signature(payload, secret).lower()
    
    # Timing-safe comparison to prevent timing attacks
    if not hmac.compare_digest(provided_sig, computed_sig):
        return False, "Signature mismatch"
    
    return True, ""


def validate_timestamp(timestamp: int) -> Tuple[bool, str]:
    """Validate webhook timestamp to prevent replay attacks.
    
    Returns: (is_valid, error_message)
    """
    if not timestamp:
        return True, ""  # Timestamp validation is optional
    
    current_time = int(time.time())
    time_diff = abs(current_time - timestamp)
    
    if time_diff > TIMESTAMP_TOLERANCE_SECONDS:
        return False, f"Timestamp too old. Difference: {time_diff}s, max allowed: {TIMESTAMP_TOLERANCE_SECONDS}s"
    
    return True, ""


def check_rate_limit(source_ip: str, waba_id: str = "") -> Tuple[bool, str]:
    """Check if request is within rate limits.
    
    Returns: (is_allowed, error_message)
    """
    # Create rate limit key
    rate_key = f"RATE_LIMIT#{source_ip}#{waba_id}" if waba_id else f"RATE_LIMIT#{source_ip}"
    
    try:
        now = int(time.time())
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        
        # Get current rate limit record
        record = get_item(rate_key)
        
        if record:
            # Check if within window
            last_reset = record.get("windowStart", 0)
            request_count = record.get("requestCount", 0)
            
            if last_reset >= window_start:
                # Still in same window
                if request_count >= RATE_LIMIT_MAX_REQUESTS:
                    return False, f"Rate limit exceeded. Max {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW_SECONDS}s"
                
                # Increment counter
                update_item(rate_key, {"requestCount": request_count + 1})
            else:
                # New window, reset counter
                update_item(rate_key, {
                    "windowStart": now,
                    "requestCount": 1,
                })
        else:
            # First request, create record
            store_item({
                MESSAGES_PK_NAME: rate_key,
                "itemType": "RATE_LIMIT",
                "windowStart": now,
                "requestCount": 1,
                "ttl": now + RATE_LIMIT_WINDOW_SECONDS * 2,  # Auto-expire
            })
        
        return True, ""
    
    except ClientError as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True, ""  # Allow on error to prevent blocking legitimate requests


def log_security_event(event_type: str, details: Dict[str, Any], success: bool) -> None:
    """Log security-related events for audit trail."""
    try:
        now = iso_now()
        event_pk = f"SECURITY_EVENT#{event_type}#{now}"
        
        store_item({
            MESSAGES_PK_NAME: event_pk,
            "itemType": "SECURITY_EVENT",
            "eventType": event_type,
            "success": success,
            "details": details,
            "timestamp": now,
            "ttl": int(time.time()) + 86400 * 30,  # Keep for 30 days
        })
    except Exception as e:
        logger.warning(f"Failed to log security event: {e}")


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
    
    Security Features:
    - HMAC-SHA256 signature validation
    - Timing-safe comparison (prevents timing attacks)
    - Timestamp validation (prevents replay attacks)
    - Rate limiting (prevents abuse)
    
    Test Event:
    {
        "action": "validate_webhook_signature",
        "signature": "sha256=abc123...",
        "payload": "{\"object\":\"whatsapp_business_account\",...}",
        "appSecret": "your_app_secret",
        "timestamp": 1704067200
    }
    
    Or from API Gateway:
    {
        "action": "validate_webhook_signature",
        "headers": {
            "X-Hub-Signature-256": "sha256=abc123...",
            "X-Hub-Timestamp": "1704067200"
        },
        "body": "{\"object\":\"whatsapp_business_account\",...}",
        "requestContext": {
            "identity": {"sourceIp": "1.2.3.4"}
        }
    }
    """
    # Extract parameters
    headers = event.get("headers", {}) or {}
    request_context = event.get("requestContext", {}) or {}
    identity = request_context.get("identity", {}) or {}
    
    # Handle case-insensitive headers
    signature = (event.get("signature") or 
                 headers.get("X-Hub-Signature-256") or 
                 headers.get("x-hub-signature-256", ""))
    
    payload = event.get("payload") or event.get("body", "")
    app_secret = event.get("appSecret") or WEBHOOK_APP_SECRET
    
    # Get timestamp for replay protection
    timestamp_str = (event.get("timestamp") or 
                     headers.get("X-Hub-Timestamp") or 
                     headers.get("x-hub-timestamp", ""))
    timestamp = int(timestamp_str) if timestamp_str else 0
    
    # Get source IP for rate limiting
    source_ip = identity.get("sourceIp", "unknown")
    
    # Log the validation attempt
    log_details = {
        "sourceIp": source_ip,
        "hasSignature": bool(signature),
        "payloadSize": len(payload) if payload else 0,
        "hasTimestamp": bool(timestamp),
    }
    
    # Rate limit check
    rate_ok, rate_error = check_rate_limit(source_ip)
    if not rate_ok:
        log_security_event("WEBHOOK_RATE_LIMITED", log_details, False)
        return {
            "statusCode": 429,
            "error": rate_error,
            "valid": False
        }
    
    # Validate required fields
    if not signature:
        log_security_event("WEBHOOK_MISSING_SIGNATURE", log_details, False)
        return {
            "statusCode": 400,
            "error": "Missing X-Hub-Signature-256 header",
            "valid": False
        }
    
    if not payload:
        log_security_event("WEBHOOK_MISSING_PAYLOAD", log_details, False)
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
    
    # Convert payload to bytes
    payload_bytes = payload.encode('utf-8') if isinstance(payload, str) else payload
    
    # Validate signature
    sig_valid, sig_error = validate_signature(payload_bytes, signature, app_secret)
    if not sig_valid:
        log_security_event("WEBHOOK_INVALID_SIGNATURE", {**log_details, "error": sig_error}, False)
        logger.warning(f"Webhook signature validation failed: {sig_error}")
        return {
            "statusCode": 403,
            "error": sig_error,
            "valid": False
        }
    
    # Validate timestamp (replay protection)
    if timestamp:
        ts_valid, ts_error = validate_timestamp(timestamp)
        if not ts_valid:
            log_security_event("WEBHOOK_REPLAY_ATTACK", {**log_details, "error": ts_error}, False)
            logger.warning(f"Webhook timestamp validation failed: {ts_error}")
            return {
                "statusCode": 403,
                "error": ts_error,
                "valid": False
            }
    
    # Success
    log_security_event("WEBHOOK_VALIDATED", log_details, True)
    logger.info("Webhook signature validated successfully")
    
    return {
        "statusCode": 200,
        "operation": "validate_webhook_signature",
        "valid": True,
        "message": "Signature is valid",
        "timestampValidated": bool(timestamp),
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
