# Refund Processing Handlers
import logging
from typing import Any, Dict
from handlers.base import table, MESSAGES_PK_NAME, iso_now, store_item, get_item, validate_required_fields
from botocore.exceptions import ClientError

logger = logging.getLogger()
REFUND_STATUSES = ["pending", "processing", "completed", "failed", "cancelled"]
REFUND_REASONS = ["customer_request", "duplicate_payment", "order_cancelled", "other"]

def handle_create_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a refund request for a payment."""
    payment_id = event.get("paymentId", "")
    amount = event.get("amount")
    reason = event.get("reason", "customer_request")
    
    error = validate_required_fields(event, ["paymentId"])
    if error:
        return error
    
    payment_pk = f"PAYMENT#{payment_id}"
    payment = get_item(payment_pk)
    if not payment:
        payment_pk = f"PAYMENT_ORDER#{payment_id}"
        payment = get_item(payment_pk)
    if not payment:
        return {"statusCode": 404, "error": f"Payment not found: {payment_id}"}
    
    original_amount = payment.get("amount") or payment.get("totalAmount", 0)
    refund_amount = amount if amount else original_amount
    now = iso_now()
    refund_id = f"REFUND_{now.replace(':', '').replace('-', '').replace('.', '')}"
    
    store_item({
        MESSAGES_PK_NAME: f"REFUND#{refund_id}",
        "itemType": "REFUND",
        "refundId": refund_id,
        "paymentId": payment_id,
        "refundAmount": refund_amount,
        "status": "pending",
        "createdAt": now
    })
    
    return {"statusCode": 200, "operation": "create_refund", "refundId": refund_id, "status": "pending"}

def handle_process_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process a pending refund."""
    refund_id = event.get("refundId", "")
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund = get_item(f"REFUND#{refund_id}")
    if not refund:
        return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
    
    table().update_item(
        Key={MESSAGES_PK_NAME: f"REFUND#{refund_id}"},
        UpdateExpression="SET #st = :st",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "processing"}
    )
    return {"statusCode": 200, "operation": "process_refund", "refundId": refund_id, "status": "processing"}

def handle_complete_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Mark refund as completed."""
    refund_id = event.get("refundId", "")
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    table().update_item(
        Key={MESSAGES_PK_NAME: f"REFUND#{refund_id}"},
        UpdateExpression="SET #st = :st, completedAt = :ca",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "completed", ":ca": iso_now()}
    )
    return {"statusCode": 200, "operation": "complete_refund", "refundId": refund_id, "status": "completed"}

def handle_fail_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Mark refund as failed."""
    refund_id = event.get("refundId", "")
    failure_reason = event.get("failureReason", "Unknown")
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    table().update_item(
        Key={MESSAGES_PK_NAME: f"REFUND#{refund_id}"},
        UpdateExpression="SET #st = :st, failureReason = :fr",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "failed", ":fr": failure_reason}
    )
    return {"statusCode": 200, "operation": "fail_refund", "refundId": refund_id, "status": "failed"}

def handle_cancel_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Cancel a pending refund."""
    refund_id = event.get("refundId", "")
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    table().update_item(
        Key={MESSAGES_PK_NAME: f"REFUND#{refund_id}"},
        UpdateExpression="SET #st = :st",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "cancelled"}
    )
    return {"statusCode": 200, "operation": "cancel_refund", "refundId": refund_id, "status": "cancelled"}

def handle_get_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get refund details."""
    refund_id = event.get("refundId", "")
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund = get_item(f"REFUND#{refund_id}")
    if not refund:
        return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
    return {"statusCode": 200, "operation": "get_refund", "refund": refund}

def handle_get_refunds(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get refunds list."""
    limit = event.get("limit", 50)
    response = table().scan(FilterExpression="itemType = :it", ExpressionAttributeValues={":it": "REFUND"}, Limit=limit)
    return {"statusCode": 200, "operation": "get_refunds", "refunds": response.get("Items", [])}

def handle_process_refund_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process refund webhook."""
    refund_id = event.get("refundId", "")
    status = event.get("status", "")
    error = validate_required_fields(event, ["refundId", "status"])
    if error:
        return error
    
    if status.lower() in ["processed", "completed", "success"]:
        return handle_complete_refund({"refundId": refund_id}, context)
    elif status.lower() == "failed":
        return handle_fail_refund({"refundId": refund_id, "failureReason": status}, context)
    return handle_process_refund({"refundId": refund_id}, context)
