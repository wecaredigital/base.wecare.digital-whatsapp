# =============================================================================
# Message Retry Logic
# =============================================================================
# Production-grade retry system for failed WhatsApp messages.
# Implements exponential backoff, dead letter queue, and retry tracking.
#
# Features:
# - Automatic retry with exponential backoff
# - Configurable max retries and delays
# - Dead letter queue for permanently failed messages
# - Retry status tracking in DynamoDB
# - Manual retry trigger support
# =============================================================================

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, social, MESSAGES_PK_NAME, WABA_PHONE_MAP, META_API_VERSION,
    iso_now, store_item, get_item, update_item, query_items,
    validate_required_fields, success_response, error_response,
    origination_id_for_api, format_wa_number,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_SECONDS = 10
DEFAULT_MAX_DELAY_SECONDS = 300  # 5 minutes
RETRY_BACKOFF_MULTIPLIER = 2

# Retryable error codes from AWS Social Messaging
RETRYABLE_ERRORS = [
    "ThrottlingException",
    "ServiceUnavailableException", 
    "InternalServerException",
    "RequestTimeout",
    "TooManyRequestsException",
]

# Non-retryable errors (permanent failures)
NON_RETRYABLE_ERRORS = [
    "ValidationException",
    "InvalidParameterException",
    "ResourceNotFoundException",
    "AccessDeniedException",
    "InvalidRecipient",
    "MessageUndeliverable",
]


# =============================================================================
# RETRY STATUS CONSTANTS
# =============================================================================
class RetryStatus:
    PENDING = "PENDING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    DEAD_LETTER = "DEAD_LETTER"


# =============================================================================
# CORE RETRY FUNCTIONS
# =============================================================================

def calculate_retry_delay(retry_count: int, base_delay: int = DEFAULT_BASE_DELAY_SECONDS,
                          max_delay: int = DEFAULT_MAX_DELAY_SECONDS) -> int:
    """Calculate exponential backoff delay for retry.
    
    Formula: min(max_delay, base_delay * (2 ^ retry_count))
    
    Example delays with base=10s:
    - Retry 1: 10s
    - Retry 2: 20s
    - Retry 3: 40s
    - Retry 4: 80s
    - Retry 5: 160s
    """
    delay = base_delay * (RETRY_BACKOFF_MULTIPLIER ** retry_count)
    return min(delay, max_delay)


def is_retryable_error(error_code: str, error_message: str = "") -> bool:
    """Determine if an error is retryable."""
    # Check explicit retryable codes
    if error_code in RETRYABLE_ERRORS:
        return True
    
    # Check explicit non-retryable codes
    if error_code in NON_RETRYABLE_ERRORS:
        return False
    
    # Check error message patterns
    error_lower = error_message.lower()
    if any(term in error_lower for term in ["throttl", "rate limit", "too many", "timeout", "temporary"]):
        return True
    if any(term in error_lower for term in ["invalid", "not found", "denied", "forbidden"]):
        return False
    
    # Default to retryable for unknown errors
    return True


def create_retry_record(
    original_message_id: str,
    meta_waba_id: str,
    to_number: str,
    message_type: str,
    payload: Dict[str, Any],
    error_code: str,
    error_message: str,
) -> Dict[str, Any]:
    """Create a retry record in DynamoDB."""
    now = iso_now()
    retry_pk = f"RETRY#{original_message_id}"
    
    is_retryable = is_retryable_error(error_code, error_message)
    initial_status = RetryStatus.FAILED_RETRYABLE if is_retryable else RetryStatus.FAILED_PERMANENT
    
    retry_record = {
        MESSAGES_PK_NAME: retry_pk,
        "itemType": "MESSAGE_RETRY",
        "originalMessageId": original_message_id,
        "wabaMetaId": meta_waba_id,
        "to": to_number,
        "messageType": message_type,
        "payload": json.dumps(payload),
        "retryCount": 0,
        "maxRetries": DEFAULT_MAX_RETRIES,
        "status": initial_status,
        "isRetryable": is_retryable,
        "lastErrorCode": error_code,
        "lastErrorMessage": error_message,
        "createdAt": now,
        "lastAttemptAt": now,
        "nextRetryAt": "" if not is_retryable else (
            datetime.now(timezone.utc) + timedelta(seconds=calculate_retry_delay(0))
        ).isoformat(),
    }
    
    store_item(retry_record)
    logger.info(f"Created retry record: {retry_pk}, status={initial_status}, retryable={is_retryable}")
    
    return retry_record


def execute_retry(retry_pk: str) -> Dict[str, Any]:
    """Execute a single retry attempt for a message."""
    retry_record = get_item(retry_pk)
    
    if not retry_record:
        return error_response(f"Retry record not found: {retry_pk}", 404)
    
    # Check if already succeeded or permanently failed
    status = retry_record.get("status", "")
    if status == RetryStatus.SUCCESS:
        return success_response("retry_skipped", reason="Already succeeded", pk=retry_pk)
    if status in (RetryStatus.FAILED_PERMANENT, RetryStatus.DEAD_LETTER):
        return success_response("retry_skipped", reason="Permanently failed", pk=retry_pk)
    
    # Check retry count
    retry_count = retry_record.get("retryCount", 0)
    max_retries = retry_record.get("maxRetries", DEFAULT_MAX_RETRIES)
    
    if retry_count >= max_retries:
        # Move to dead letter
        update_item(retry_pk, {
            "status": RetryStatus.DEAD_LETTER,
            "movedToDeadLetterAt": iso_now(),
        })
        logger.warning(f"Retry exhausted, moved to dead letter: {retry_pk}")
        return success_response("retry_exhausted", pk=retry_pk, 
                               message="Max retries exceeded, moved to dead letter queue")
    
    # Get WABA config
    meta_waba_id = retry_record.get("wabaMetaId", "")
    config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
    if not config or not config.get("phoneArn"):
        update_item(retry_pk, {
            "status": RetryStatus.FAILED_PERMANENT,
            "lastErrorMessage": f"WABA config not found: {meta_waba_id}",
        })
        return error_response(f"WABA config not found: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    
    # Parse payload
    try:
        payload = json.loads(retry_record.get("payload", "{}"))
    except json.JSONDecodeError:
        update_item(retry_pk, {
            "status": RetryStatus.FAILED_PERMANENT,
            "lastErrorMessage": "Invalid payload JSON",
        })
        return error_response("Invalid payload JSON", 400)
    
    # Update status to retrying
    now = iso_now()
    update_item(retry_pk, {
        "status": RetryStatus.RETRYING,
        "retryCount": retry_count + 1,
        "lastAttemptAt": now,
    })
    
    # Attempt to send
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        
        new_message_id = response.get("messageId", "")
        
        # Success!
        update_item(retry_pk, {
            "status": RetryStatus.SUCCESS,
            "succeededAt": iso_now(),
            "newMessageId": new_message_id,
        })
        
        logger.info(f"Retry succeeded: {retry_pk}, new messageId={new_message_id}")
        
        return success_response("retry_success", 
                               pk=retry_pk,
                               originalMessageId=retry_record.get("originalMessageId"),
                               newMessageId=new_message_id,
                               retryCount=retry_count + 1)
    
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = str(e)
        
        is_retryable = is_retryable_error(error_code, error_message)
        next_retry_count = retry_count + 1
        
        if not is_retryable or next_retry_count >= max_retries:
            # Permanent failure or exhausted
            final_status = RetryStatus.DEAD_LETTER if next_retry_count >= max_retries else RetryStatus.FAILED_PERMANENT
            update_item(retry_pk, {
                "status": final_status,
                "lastErrorCode": error_code,
                "lastErrorMessage": error_message,
                "failedPermanentlyAt": iso_now(),
            })
            logger.error(f"Retry failed permanently: {retry_pk}, error={error_code}")
        else:
            # Schedule next retry
            next_delay = calculate_retry_delay(next_retry_count)
            next_retry_at = (datetime.now(timezone.utc) + timedelta(seconds=next_delay)).isoformat()
            
            update_item(retry_pk, {
                "status": RetryStatus.FAILED_RETRYABLE,
                "lastErrorCode": error_code,
                "lastErrorMessage": error_message,
                "nextRetryAt": next_retry_at,
            })
            logger.warning(f"Retry failed, will retry in {next_delay}s: {retry_pk}")
        
        return error_response(f"Retry failed: {error_message}", 500)


# =============================================================================
# HANDLER FUNCTIONS
# =============================================================================

def handle_retry_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Manually trigger retry for a failed message.
    
    Required: messageId (original message ID or retry PK)
    Optional: force (retry even if not retryable)
    
    Test Event:
    {
        "action": "retry_message",
        "messageId": "abc123-def456"
    }
    """
    message_id = event.get("messageId", "")
    force = event.get("force", False)
    
    error = validate_required_fields(event, ["messageId"])
    if error:
        return error
    
    # Try to find retry record
    retry_pk = message_id if message_id.startswith("RETRY#") else f"RETRY#{message_id}"
    retry_record = get_item(retry_pk)
    
    if not retry_record:
        return error_response(f"No retry record found for message: {message_id}", 404)
    
    # Check if force retry is needed
    if not retry_record.get("isRetryable") and not force:
        return error_response(
            "Message is not retryable. Use force=true to retry anyway.",
            400
        )
    
    return execute_retry(retry_pk)


def handle_get_retry_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get retry status for a message.
    
    Required: messageId
    
    Test Event:
    {
        "action": "get_retry_status",
        "messageId": "abc123-def456"
    }
    """
    message_id = event.get("messageId", "")
    
    error = validate_required_fields(event, ["messageId"])
    if error:
        return error
    
    retry_pk = message_id if message_id.startswith("RETRY#") else f"RETRY#{message_id}"
    retry_record = get_item(retry_pk)
    
    if not retry_record:
        return error_response(f"No retry record found for message: {message_id}", 404)
    
    return success_response("get_retry_status",
        pk=retry_pk,
        status=retry_record.get("status"),
        retryCount=retry_record.get("retryCount", 0),
        maxRetries=retry_record.get("maxRetries", DEFAULT_MAX_RETRIES),
        isRetryable=retry_record.get("isRetryable", False),
        lastErrorCode=retry_record.get("lastErrorCode", ""),
        lastErrorMessage=retry_record.get("lastErrorMessage", ""),
        nextRetryAt=retry_record.get("nextRetryAt", ""),
        createdAt=retry_record.get("createdAt", ""),
        lastAttemptAt=retry_record.get("lastAttemptAt", ""),
    )


def handle_get_pending_retries(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all pending retry messages.
    
    Optional: metaWabaId, limit, status
    
    Test Event:
    {
        "action": "get_pending_retries",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    limit = min(event.get("limit", 50), 100)
    status_filter = event.get("status", RetryStatus.FAILED_RETRYABLE)
    
    try:
        # Scan for retry records
        filter_expr = "itemType = :it AND #status = :st"
        expr_values = {
            ":it": "MESSAGE_RETRY",
            ":st": status_filter,
        }
        expr_names = {"#status": "status"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        items = query_items(
            filter_expr=filter_expr,
            expr_values=expr_values,
            expr_names=expr_names,
            limit=limit,
        )
        
        # Format response
        retries = []
        for item in items:
            retries.append({
                "pk": item.get(MESSAGES_PK_NAME),
                "originalMessageId": item.get("originalMessageId"),
                "to": item.get("to"),
                "messageType": item.get("messageType"),
                "status": item.get("status"),
                "retryCount": item.get("retryCount", 0),
                "nextRetryAt": item.get("nextRetryAt", ""),
                "lastErrorCode": item.get("lastErrorCode", ""),
            })
        
        return success_response("get_pending_retries",
            count=len(retries),
            retries=retries,
            statusFilter=status_filter,
        )
    
    except ClientError as e:
        return error_response(str(e), 500)


def handle_process_retry_queue(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process all due retries (called by scheduled Lambda or manually).
    
    Optional: limit, dryRun
    
    Test Event:
    {
        "action": "process_retry_queue",
        "limit": 10
    }
    """
    limit = min(event.get("limit", 10), 50)
    dry_run = event.get("dryRun", False)
    
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    try:
        # Find retries that are due
        items = query_items(
            filter_expr="itemType = :it AND #status = :st",
            expr_values={
                ":it": "MESSAGE_RETRY",
                ":st": RetryStatus.FAILED_RETRYABLE,
            },
            expr_names={"#status": "status"},
            limit=limit * 2,  # Get more to filter by nextRetryAt
        )
        
        # Filter by nextRetryAt
        due_retries = []
        for item in items:
            next_retry = item.get("nextRetryAt", "")
            if next_retry and next_retry <= now_iso:
                due_retries.append(item)
            if len(due_retries) >= limit:
                break
        
        if dry_run:
            return success_response("process_retry_queue",
                dryRun=True,
                dueCount=len(due_retries),
                retries=[{
                    "pk": r.get(MESSAGES_PK_NAME),
                    "nextRetryAt": r.get("nextRetryAt"),
                    "retryCount": r.get("retryCount", 0),
                } for r in due_retries],
            )
        
        # Process each retry
        results = {"success": 0, "failed": 0, "skipped": 0}
        processed = []
        
        for item in due_retries:
            retry_pk = item.get(MESSAGES_PK_NAME)
            result = execute_retry(retry_pk)
            
            if result.get("statusCode") == 200:
                if "success" in result.get("operation", ""):
                    results["success"] += 1
                else:
                    results["skipped"] += 1
            else:
                results["failed"] += 1
            
            processed.append({
                "pk": retry_pk,
                "result": result.get("operation", "error"),
                "statusCode": result.get("statusCode"),
            })
        
        return success_response("process_retry_queue",
            processed=len(processed),
            results=results,
            details=processed,
        )
    
    except ClientError as e:
        return error_response(str(e), 500)


def handle_get_dead_letter_queue(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get messages in dead letter queue (permanently failed).
    
    Optional: metaWabaId, limit
    
    Test Event:
    {
        "action": "get_dead_letter_queue",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    limit = min(event.get("limit", 50), 100)
    
    try:
        filter_expr = "itemType = :it AND #status = :st"
        expr_values = {
            ":it": "MESSAGE_RETRY",
            ":st": RetryStatus.DEAD_LETTER,
        }
        expr_names = {"#status": "status"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        items = query_items(
            filter_expr=filter_expr,
            expr_values=expr_values,
            expr_names=expr_names,
            limit=limit,
        )
        
        dead_letters = []
        for item in items:
            dead_letters.append({
                "pk": item.get(MESSAGES_PK_NAME),
                "originalMessageId": item.get("originalMessageId"),
                "to": item.get("to"),
                "messageType": item.get("messageType"),
                "retryCount": item.get("retryCount", 0),
                "lastErrorCode": item.get("lastErrorCode", ""),
                "lastErrorMessage": item.get("lastErrorMessage", ""),
                "createdAt": item.get("createdAt", ""),
                "movedToDeadLetterAt": item.get("movedToDeadLetterAt", ""),
            })
        
        return success_response("get_dead_letter_queue",
            count=len(dead_letters),
            messages=dead_letters,
        )
    
    except ClientError as e:
        return error_response(str(e), 500)


def handle_clear_dead_letter(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Remove a message from dead letter queue (acknowledge failure).
    
    Required: messageId
    
    Test Event:
    {
        "action": "clear_dead_letter",
        "messageId": "abc123-def456"
    }
    """
    message_id = event.get("messageId", "")
    
    error = validate_required_fields(event, ["messageId"])
    if error:
        return error
    
    retry_pk = message_id if message_id.startswith("RETRY#") else f"RETRY#{message_id}"
    
    try:
        # Update status to acknowledged
        update_item(retry_pk, {
            "status": "ACKNOWLEDGED",
            "acknowledgedAt": iso_now(),
        })
        
        return success_response("clear_dead_letter",
            pk=retry_pk,
            message="Removed from dead letter queue",
        )
    
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# HANDLER MAPPING
# =============================================================================

RETRY_HANDLERS = {
    "retry_message": handle_retry_message,
    "get_retry_status": handle_get_retry_status,
    "get_pending_retries": handle_get_pending_retries,
    "process_retry_queue": handle_process_retry_queue,
    "get_dead_letter_queue": handle_get_dead_letter_queue,
    "clear_dead_letter": handle_clear_dead_letter,
}
