# =============================================================================
# DASHBOARD HANDLERS - WhatsApp Analytics & Management
# =============================================================================
# Separate dashboards for:
#   - Inbound messages
#   - Outbound messages
#   - Templates
#   - Flow messages
#   - Payments
#
# DynamoDB Tables:
#   - wecare-digital-inbound: Inbound messages
#   - wecare-digital-outbound: Outbound messages
#   - wecare-digital-flows: Flow data
#   - wecare-digital-payments: Payment data
#   - wecare-digital-orders: Order payments
# =============================================================================

import json
import logging
import os
from typing import Any, Dict, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# TABLE CONFIGURATION
# =============================================================================
TABLES = {
    "main": os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp"),
    "inbound": os.environ.get("INBOUND_TABLE", "wecare-digital-inbound"),
    "outbound": os.environ.get("OUTBOUND_TABLE", "wecare-digital-outbound"),
    "flows": os.environ.get("FLOWS_TABLE", "wecare-digital-flows"),
    "payments": os.environ.get("PAYMENTS_TABLE", "wecare-digital-payments"),
    "orders": os.environ.get("ORDERS_TABLE", "wecare-digital-orders"),
    "shortlinks": os.environ.get("SHORTLINKS_TABLE", "wecare-digital-shortlinks"),
}

_tables = {}

def get_table(name: str):
    if name not in _tables:
        table_name = TABLES.get(name, name)
        _tables[name] = boto3.resource("dynamodb").Table(table_name)
    return _tables[name]

def now(): return datetime.now(timezone.utc).isoformat()

# =============================================================================
# DECIMAL ENCODER
# =============================================================================
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o) if o % 1 else int(o)
        return super().default(o)

def to_json(obj):
    return json.dumps(obj, cls=DecimalEncoder, default=str)

# =============================================================================
# INBOUND MESSAGES DASHBOARD
# =============================================================================
def get_inbound_stats(event: Dict, context: Any) -> Dict:
    """Get inbound message statistics.
    
    Test Event:
    {"action": "get_inbound_stats", "days": 7}
    """
    days = event.get("days", 7)
    waba_id = event.get("metaWabaId", "")
    
    try:
        table = get_table("main")
        
        # Scan for inbound messages
        filter_expr = "itemType = :it AND direction = :dir"
        expr_values = {":it": "MESSAGE", ":dir": "INBOUND"}
        
        if waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = waba_id
        
        response = table.scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        
        items = response.get("Items", [])
        
        # Calculate stats
        total = len(items)
        by_type = {}
        by_sender = {}
        
        for item in items:
            msg_type = item.get("type", "unknown")
            sender = item.get("from", "unknown")
            
            by_type[msg_type] = by_type.get(msg_type, 0) + 1
            by_sender[sender] = by_sender.get(sender, 0) + 1
        
        # Top senders
        top_senders = sorted(by_sender.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "statusCode": 200,
            "operation": "get_inbound_stats",
            "total": total,
            "byType": by_type,
            "topSenders": [{"phone": s[0], "count": s[1]} for s in top_senders],
            "days": days,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

def get_inbound_messages(event: Dict, context: Any) -> Dict:
    """Get recent inbound messages.
    
    Test Event:
    {"action": "get_inbound_messages", "limit": 50, "from": "+919876543210"}
    """
    limit = event.get("limit", 50)
    from_phone = event.get("from", "")
    waba_id = event.get("metaWabaId", "")
    
    try:
        table = get_table("main")
        
        filter_expr = "itemType = :it AND direction = :dir"
        expr_values = {":it": "MESSAGE", ":dir": "INBOUND"}
        
        if from_phone:
            filter_expr += " AND #f = :from"
            expr_values[":from"] = from_phone
        
        if waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = waba_id
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit,
        }
        
        if from_phone:
            scan_kwargs["ExpressionAttributeNames"] = {"#f": "from"}
        
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        
        # Sort by receivedAt descending
        items.sort(key=lambda x: x.get("receivedAt", ""), reverse=True)
        
        return {
            "statusCode": 200,
            "operation": "get_inbound_messages",
            "count": len(items),
            "messages": items[:limit],
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# OUTBOUND MESSAGES DASHBOARD
# =============================================================================
def get_outbound_stats(event: Dict, context: Any) -> Dict:
    """Get outbound message statistics.
    
    Test Event:
    {"action": "get_outbound_stats", "days": 7}
    """
    days = event.get("days", 7)
    waba_id = event.get("metaWabaId", "")
    
    try:
        table = get_table("main")
        
        filter_expr = "itemType = :it AND direction = :dir"
        expr_values = {":it": "MESSAGE", ":dir": "OUTBOUND"}
        
        if waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = waba_id
        
        response = table.scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        
        items = response.get("Items", [])
        
        # Calculate stats
        total = len(items)
        by_type = {}
        by_status = {}
        by_recipient = {}
        
        for item in items:
            msg_type = item.get("type", "unknown")
            status = item.get("deliveryStatus", "unknown")
            recipient = item.get("to", "unknown")
            
            by_type[msg_type] = by_type.get(msg_type, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
            by_recipient[recipient] = by_recipient.get(recipient, 0) + 1
        
        # Top recipients
        top_recipients = sorted(by_recipient.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "statusCode": 200,
            "operation": "get_outbound_stats",
            "total": total,
            "byType": by_type,
            "byStatus": by_status,
            "topRecipients": [{"phone": r[0], "count": r[1]} for r in top_recipients],
            "days": days,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

def get_outbound_messages(event: Dict, context: Any) -> Dict:
    """Get recent outbound messages.
    
    Test Event:
    {"action": "get_outbound_messages", "limit": 50, "to": "+919876543210"}
    """
    limit = event.get("limit", 50)
    to_phone = event.get("to", "")
    waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    
    try:
        table = get_table("main")
        
        filter_expr = "itemType = :it AND direction = :dir"
        expr_values = {":it": "MESSAGE", ":dir": "OUTBOUND"}
        expr_names = {}
        
        if to_phone:
            filter_expr += " AND #to = :to"
            expr_values[":to"] = to_phone
            expr_names["#to"] = "to"
        
        if waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = waba_id
        
        if status:
            filter_expr += " AND deliveryStatus = :st"
            expr_values[":st"] = status
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit,
        }
        
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        
        # Sort by sentAt descending
        items.sort(key=lambda x: x.get("sentAt", x.get("createdAt", "")), reverse=True)
        
        return {
            "statusCode": 200,
            "operation": "get_outbound_messages",
            "count": len(items),
            "messages": items[:limit],
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# TEMPLATES DASHBOARD
# =============================================================================
def get_template_stats(event: Dict, context: Any) -> Dict:
    """Get template usage statistics.
    
    Test Event:
    {"action": "get_template_stats"}
    """
    waba_id = event.get("metaWabaId", "")
    
    try:
        table = get_table("main")
        
        # Get templates
        filter_expr = "itemType = :it"
        expr_values = {":it": "TEMPLATE"}
        
        if waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = waba_id
        
        response = table.scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=500
        )
        
        templates = response.get("Items", [])
        
        # Calculate stats
        by_status = {}
        by_category = {}
        by_language = {}
        
        for t in templates:
            status = t.get("status", "unknown")
            category = t.get("category", "unknown")
            language = t.get("language", "unknown")
            
            by_status[status] = by_status.get(status, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
            by_language[language] = by_language.get(language, 0) + 1
        
        return {
            "statusCode": 200,
            "operation": "get_template_stats",
            "total": len(templates),
            "byStatus": by_status,
            "byCategory": by_category,
            "byLanguage": by_language,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# FLOWS DASHBOARD
# =============================================================================
def get_flow_stats(event: Dict, context: Any) -> Dict:
    """Get flow message statistics.
    
    Test Event:
    {"action": "get_flow_stats"}
    """
    try:
        table = get_table("main")
        
        # Get flow-related items
        response = table.scan(
            FilterExpression="begins_with(pk, :prefix)",
            ExpressionAttributeValues={":prefix": "FLOW#"},
            Limit=500
        )
        
        items = response.get("Items", [])
        
        by_status = {}
        by_flow_id = {}
        
        for item in items:
            status = item.get("status", "unknown")
            flow_id = item.get("flowId", "unknown")
            
            by_status[status] = by_status.get(status, 0) + 1
            by_flow_id[flow_id] = by_flow_id.get(flow_id, 0) + 1
        
        return {
            "statusCode": 200,
            "operation": "get_flow_stats",
            "total": len(items),
            "byStatus": by_status,
            "byFlowId": by_flow_id,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# PAYMENTS DASHBOARD
# =============================================================================
def get_payment_stats(event: Dict, context: Any) -> Dict:
    """Get payment statistics.
    
    Test Event:
    {"action": "get_payment_stats"}
    """
    try:
        table = get_table("payments")
        
        # Get all payments
        response = table.scan(
            FilterExpression="#t = :t",
            ExpressionAttributeNames={"#t": "type"},
            ExpressionAttributeValues={":t": "PAYMENT"},
            Limit=500
        )
        
        items = response.get("Items", [])
        
        by_status = {}
        total_amount = 0
        captured_amount = 0
        
        for item in items:
            status = item.get("status", "unknown")
            amount = float(item.get("amount", 0))
            
            by_status[status] = by_status.get(status, 0) + 1
            total_amount += amount
            
            if status == "captured":
                captured_amount += amount
        
        return {
            "statusCode": 200,
            "operation": "get_payment_stats",
            "total": len(items),
            "byStatus": by_status,
            "totalAmount": total_amount,
            "capturedAmount": captured_amount,
            "currency": "INR",
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

def get_payments(event: Dict, context: Any) -> Dict:
    """Get recent payments.
    
    Test Event:
    {"action": "get_payments", "limit": 50, "status": "captured"}
    """
    limit = event.get("limit", 50)
    status = event.get("status", "")
    
    try:
        table = get_table("payments")
        
        filter_expr = "#t = :t"
        expr_values = {":t": "PAYMENT"}
        expr_names = {"#t": "type"}
        
        if status:
            filter_expr += " AND #s = :s"
            expr_values[":s"] = status
            expr_names["#s"] = "status"
        
        response = table.scan(
            FilterExpression=filter_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        
        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("capturedAt", x.get("createdAt", "")), reverse=True)
        
        return {
            "statusCode": 200,
            "operation": "get_payments",
            "count": len(items),
            "payments": items[:limit],
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# SHORT LINKS DASHBOARD
# =============================================================================
def get_shortlink_stats(event: Dict, context: Any) -> Dict:
    """Get short link statistics.
    
    Test Event:
    {"action": "get_shortlink_stats"}
    """
    try:
        table = get_table("shortlinks")
        
        # Get all links
        response = table.scan(
            FilterExpression="#t = :t",
            ExpressionAttributeNames={"#t": "type"},
            ExpressionAttributeValues={":t": "LINK"},
            Limit=500
        )
        
        items = response.get("Items", [])
        
        total_clicks = 0
        active_count = 0
        
        for item in items:
            clicks = int(item.get("clicks", 0))
            active = item.get("active", True)
            
            total_clicks += clicks
            if active:
                active_count += 1
        
        return {
            "statusCode": 200,
            "operation": "get_shortlink_stats",
            "totalLinks": len(items),
            "activeLinks": active_count,
            "totalClicks": total_clicks,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

def get_shortlinks(event: Dict, context: Any) -> Dict:
    """Get short links.
    
    Test Event:
    {"action": "get_shortlinks", "limit": 50}
    """
    limit = event.get("limit", 50)
    
    try:
        table = get_table("shortlinks")
        
        response = table.scan(
            FilterExpression="#t = :t",
            ExpressionAttributeNames={"#t": "type"},
            ExpressionAttributeValues={":t": "LINK"},
            Limit=limit
        )
        
        items = response.get("Items", [])
        items.sort(key=lambda x: int(x.get("clicks", 0)), reverse=True)
        
        return {
            "statusCode": 200,
            "operation": "get_shortlinks",
            "count": len(items),
            "links": items[:limit],
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}

# =============================================================================
# COMBINED DASHBOARD
# =============================================================================
def get_dashboard_summary(event: Dict, context: Any) -> Dict:
    """Get combined dashboard summary.
    
    Test Event:
    {"action": "get_dashboard_summary"}
    """
    summary = {
        "statusCode": 200,
        "operation": "get_dashboard_summary",
        "timestamp": now(),
    }
    
    # Get inbound stats
    try:
        inbound = get_inbound_stats(event, context)
        summary["inbound"] = {"total": inbound.get("total", 0), "byType": inbound.get("byType", {})}
    except:
        summary["inbound"] = {"error": "Failed to fetch"}
    
    # Get outbound stats
    try:
        outbound = get_outbound_stats(event, context)
        summary["outbound"] = {"total": outbound.get("total", 0), "byStatus": outbound.get("byStatus", {})}
    except:
        summary["outbound"] = {"error": "Failed to fetch"}
    
    # Get template stats
    try:
        templates = get_template_stats(event, context)
        summary["templates"] = {"total": templates.get("total", 0), "byStatus": templates.get("byStatus", {})}
    except:
        summary["templates"] = {"error": "Failed to fetch"}
    
    # Get payment stats
    try:
        payments = get_payment_stats(event, context)
        summary["payments"] = {
            "total": payments.get("total", 0),
            "capturedAmount": payments.get("capturedAmount", 0),
            "byStatus": payments.get("byStatus", {})
        }
    except:
        summary["payments"] = {"error": "Failed to fetch"}
    
    # Get shortlink stats
    try:
        shortlinks = get_shortlink_stats(event, context)
        summary["shortlinks"] = {
            "totalLinks": shortlinks.get("totalLinks", 0),
            "totalClicks": shortlinks.get("totalClicks", 0)
        }
    except:
        summary["shortlinks"] = {"error": "Failed to fetch"}
    
    return summary

# =============================================================================
# HANDLER EXPORTS
# =============================================================================
DASHBOARD_HANDLERS = {
    # Inbound
    "get_inbound_stats": get_inbound_stats,
    "get_inbound_messages": get_inbound_messages,
    # Outbound
    "get_outbound_stats": get_outbound_stats,
    "get_outbound_messages": get_outbound_messages,
    # Templates
    "get_template_stats": get_template_stats,
    # Flows
    "get_flow_stats": get_flow_stats,
    # Payments
    "get_payment_stats": get_payment_stats,
    "get_payments": get_payments,
    # Short links
    "get_shortlink_stats": get_shortlink_stats,
    "get_shortlinks": get_shortlinks,
    # Combined
    "get_dashboard_summary": get_dashboard_summary,
}
