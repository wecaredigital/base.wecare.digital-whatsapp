# Refund Processing Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api
#
# This module handles payment refund processing for WhatsApp Payments
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Refund Statuses
REFUND_STATUSES = ["pending", "processing", "completed", "failed", "cancelled"]

# Refund Reasons
REFUND_REASONS = [
    "customer_request",
    "duplicate_payment", 
    "order_cancelled",
    "product_unavailable",
    "quality_issue",
    "wrong_item",
    "delivery_failed",
    "other"
]


def handle_create_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a refund request for a payment."""
    payment_id = event.get("paymentId", "")
    amount = event.get("amount")
    reason = event.get("reason", "customer_request")
    notes = event.get("notes", "")
    
    error = validate_required_fields(event, ["paymentId"])
    if error:
        return error
    
    if reason not in REFUND_REASONS:
        return {"statusCode": 400, "error": f"Invalid reason. Valid: {REFUND_REASONS}"}
    
    payment_pk = f"PAYMENT#{payment_id}"
    
    try:
        payment = get_item(payment_pk)
        if not payment:
            payment_pk = f"PAYMENT_ORDER#{payment_id}"
            payment = get_item(payment_pk)
        
        if not payment:
            return {"statusCode": 404, "error": f"Payment not found: {payment_id}"}

        payment_status = payment.get("status") or payment.get("paymentStatus", "")
        if payment_status not in ["completed", "captured"]:
            return {"statusCode": 400, "error": f"Payment cannot be refunded. Status: {payment_status}"}
        
        original_amount = payment.get("amount") or payment.get("totalAmount", 0)
        refund_amount = amount if amount is not None else original_amount
        
        if refund_amount > original_amount:
            return {"statusCode": 400, "error": f"Refund amount exceeds payment amount"}
        
        now = iso_now()
        refund_id = f"REFUND_{now.replace(':', '').replace('-', '').replace('.', '')}"
        refund_pk = f"REFUND#{refund_id}"
        
        refund_data = {
            MESSAGES_PK_NAME: refund_pk,
            "itemType": "REFUND",
            "refundId": refund_id,
            "paymentId": payment_id,
            "paymentPk": payment_pk,
            "wabaMetaId": payment.get("wabaMetaId", ""),
            "customerPhone": payment.get("customerPhone", ""),
            "originalAmount": original_amount,
            "refundAmount": refund_amount,
            "currency": payment.get("currency", "INR"),
            "reason": reason,
            "notes": notes,
            "status": "pending",
            "isFullRefund": amount is None or amount == original_amount,
            "createdAt": now,
        }
        
        store_item(refund_data)
        
        return {
            "statusCode": 200,
            "operation": "create_refund",
            "refundId": refund_id,
            "paymentId": payment_id,
            "refundAmount": refund_amount,
            "status": "pending"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_process_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process a pending refund."""
    refund_id = event.get("refundId", "")
    
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund_pk = f"REFUND#{refund_id}"
    now = iso_now()
    
    try:
        refund = get_item(refund_pk)
        if not refund:
            return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
        
        if refund.get("status") != "pending":
            return {"statusCode": 400, "error": f"Refund cannot be processed. Status: {refund.get('status')}"}
        
        table().update_item(
            Key={MESSAGES_PK_NAME: refund_pk},
            UpdateExpression="SET #st = :st, processingStartedAt = :psa",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "processing", ":psa": now}
        )
        
        return {"statusCode": 200, "operation": "process_refund", "refundId": refund_id, "status": "processing"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_complete_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Mark refund as completed."""
    refund_id = event.get("refundId", "")
    send_notification = event.get("sendNotification", True)
    
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund_pk = f"REFUND#{refund_id}"
    now = iso_now()
    
    try:
        refund = get_item(refund_pk)
        if not refund:
            return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
        
        table().update_item(
            Key={MESSAGES_PK_NAME: refund_pk},
            UpdateExpression="SET #st = :st, completedAt = :ca",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "completed", ":ca": now}
        )
        
        return {"statusCode": 200, "operation": "complete_refund", "refundId": refund_id, "status": "completed"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_fail_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Mark refund as failed."""
    refund_id = event.get("refundId", "")
    failure_reason = event.get("failureReason", "Unknown error")
    
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund_pk = f"REFUND#{refund_id}"
    now = iso_now()
    
    try:
        refund = get_item(refund_pk)
        if not refund:
            return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
        
        table().update_item(
            Key={MESSAGES_PK_NAME: refund_pk},
            UpdateExpression="SET #st = :st, failedAt = :fa, failureReason = :fr",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "failed", ":fa": now, ":fr": failure_reason}
        )
        
        return {"statusCode": 200, "operation": "fail_refund", "refundId": refund_id, "status": "failed"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_cancel_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Cancel a pending refund."""
    refund_id = event.get("refundId", "")
    
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund_pk = f"REFUND#{refund_id}"
    now = iso_now()
    
    try:
        refund = get_item(refund_pk)
        if not refund:
            return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
        
        if refund.get("status") not in ["pending", "processing"]:
            return {"statusCode": 400, "error": f"Cannot cancel refund with status: {refund.get('status')}"}
        
        table().update_item(
            Key={MESSAGES_PK_NAME: refund_pk},
            UpdateExpression="SET #st = :st, cancelledAt = :ca",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "cancelled", ":ca": now}
        )
        
        return {"statusCode": 200, "operation": "cancel_refund", "refundId": refund_id, "status": "cancelled"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_refund(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get refund details."""
    refund_id = event.get("refundId", "")
    
    error = validate_required_fields(event, ["refundId"])
    if error:
        return error
    
    refund_pk = f"REFUND#{refund_id}"
    
    try:
        refund = get_item(refund_pk)
        if not refund:
            return {"statusCode": 404, "error": f"Refund not found: {refund_id}"}
        
        return {"statusCode": 200, "operation": "get_refund", "refund": refund}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_refunds(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get refunds list with filters."""
    payment_id = event.get("paymentId", "")
    status = event.get("status", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "REFUND"}
        expr_names = {}
        
        if payment_id:
            filter_expr += " AND paymentId = :pid"
            expr_values[":pid"] = payment_id
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
            expr_names["#st"] = "status"
        
        scan_kwargs = {"FilterExpression": filter_expr, "ExpressionAttributeValues": expr_values, "Limit": limit}
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table().scan(**scan_kwargs)
        items = response.get("Items", [])
        
        return {"statusCode": 200, "operation": "get_refunds", "count": len(items), "refunds": items}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_process_refund_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process refund webhook from payment gateway."""
    refund_id = event.get("refundId", "")
    status = event.get("status", "")
    
    error = validate_required_fields(event, ["refundId", "status"])
    if error:
        return error
    
    status_map = {"processed": "completed", "completed": "completed", "success": "completed", "failed": "failed"}
    mapped_status = status_map.get(status.lower(), "processing")
    
    if mapped_status == "completed":
        return handle_complete_refund({"refundId": refund_id}, context)
    elif mapped_status == "failed":
        return handle_fail_refund({"refundId": refund_id, "failureReason": f"Provider status: {status}"}, context)
    else:
        return handle_process_refund({"refundId": refund_id}, context)
