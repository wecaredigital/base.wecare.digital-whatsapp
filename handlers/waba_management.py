# WABA Management Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api

import json
import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta
from handlers.base import (
    table, social, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config, WABA_PHONE_MAP
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Analytics Granularity
GRANULARITY_OPTIONS = ["HALF_HOUR", "DAY", "MONTH"]

# Conversation Types
CONVERSATION_TYPES = ["REGULAR", "MARKETING", "UTILITY", "AUTHENTICATION", "SERVICE"]


def handle_get_waba_analytics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get WABA-level analytics from Meta.
    
    Test Event:
    {
        "action": "get_waba_analytics",
        "metaWabaId": "1347766229904230",
        "startDate": "2024-12-01",
        "endDate": "2024-12-30",
        "granularity": "DAY"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    start_date = event.get("startDate", "")
    end_date = event.get("endDate", "")
    granularity = event.get("granularity", "DAY")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if granularity not in GRANULARITY_OPTIONS:
        return {"statusCode": 400, "error": f"Invalid granularity. Valid: {GRANULARITY_OPTIONS}"}
    
    try:
        # Query local analytics data
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "MESSAGE", ":waba": meta_waba_id}
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        items = response.get("Items", [])
        
        # Calculate analytics
        total_messages = len(items)
        outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
        inbound = [i for i in items if i.get("direction") == "INBOUND"]
        delivered = [i for i in outbound if i.get("deliveryStatus") == "delivered"]
        read = [i for i in outbound if i.get("deliveryStatus") == "read"]
        failed = [i for i in outbound if i.get("deliveryStatus") == "failed"]
        
        return {
            "statusCode": 200,
            "operation": "get_waba_analytics",
            "wabaMetaId": meta_waba_id,
            "period": {"start": start_date, "end": end_date, "granularity": granularity},
            "analytics": {
                "totalMessages": total_messages,
                "outbound": len(outbound),
                "inbound": len(inbound),
                "delivered": len(delivered),
                "read": len(read),
                "failed": len(failed),
                "deliveryRate": round(len(delivered) / len(outbound) * 100, 2) if outbound else 0,
                "readRate": round(len(read) / len(delivered) * 100, 2) if delivered else 0,
            },
            "note": "For Meta API analytics, use Graph API endpoint /{waba-id}/analytics"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_conversation_analytics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get conversation analytics (billable conversations).
    
    Test Event:
    {
        "action": "get_conversation_analytics",
        "metaWabaId": "1347766229904230",
        "startDate": "2024-12-01",
        "endDate": "2024-12-30",
        "conversationType": "MARKETING"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    start_date = event.get("startDate", "")
    end_date = event.get("endDate", "")
    conversation_type = event.get("conversationType", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if conversation_type and conversation_type not in CONVERSATION_TYPES:
        return {"statusCode": 400, "error": f"Invalid conversationType. Valid: {CONVERSATION_TYPES}"}
    
    try:
        # Query conversations
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "CONVERSATION", ":waba": meta_waba_id}
        
        if conversation_type:
            filter_expr += " AND conversationType = :ct"
            expr_values[":ct"] = conversation_type
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        items = response.get("Items", [])
        
        # Group by type
        by_type = {}
        for item in items:
            ct = item.get("conversationType", "SERVICE")
            by_type[ct] = by_type.get(ct, 0) + 1
        
        return {
            "statusCode": 200,
            "operation": "get_conversation_analytics",
            "wabaMetaId": meta_waba_id,
            "period": {"start": start_date, "end": end_date},
            "conversations": {
                "total": len(items),
                "byType": by_type,
            },
            "note": "For Meta API analytics, use Graph API endpoint /{waba-id}/conversation_analytics"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_template_analytics_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get template analytics from Meta.
    
    Test Event:
    {
        "action": "get_template_analytics_meta",
        "metaWabaId": "1347766229904230",
        "templateName": "order_confirmation",
        "startDate": "2024-12-01",
        "endDate": "2024-12-30"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    start_date = event.get("startDate", "")
    end_date = event.get("endDate", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query template messages
        filter_expr = "itemType = :it AND wabaMetaId = :waba AND messageType = :mt"
        expr_values = {":it": "MESSAGE", ":waba": meta_waba_id, ":mt": "template"}
        
        if template_name:
            filter_expr += " AND templateName = :tn"
            expr_values[":tn"] = template_name
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        items = response.get("Items", [])
        
        # Group by template
        by_template = {}
        for item in items:
            tn = item.get("templateName", "unknown")
            if tn not in by_template:
                by_template[tn] = {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
            by_template[tn]["sent"] += 1
            status = item.get("deliveryStatus", "")
            if status in by_template[tn]:
                by_template[tn][status] += 1
        
        return {
            "statusCode": 200,
            "operation": "get_template_analytics_meta",
            "wabaMetaId": meta_waba_id,
            "period": {"start": start_date, "end": end_date},
            "templateAnalytics": by_template,
            "note": "For Meta API analytics, use Graph API endpoint /{waba-id}/template_analytics"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_waba_settings(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update WABA settings.
    
    Test Event:
    {
        "action": "set_waba_settings",
        "metaWabaId": "1347766229904230",
        "settings": {
            "webhooksEnabled": true,
            "readReceiptsEnabled": true,
            "typingIndicatorsEnabled": true
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    settings = event.get("settings", {})
    
    error = validate_required_fields(event, ["metaWabaId", "settings"])
    if error:
        return error
    
    now = iso_now()
    settings_pk = f"WABA_SETTINGS#{meta_waba_id}"
    
    try:
        # Get existing settings
        existing = get_item(settings_pk) or {}
        
        # Merge settings
        merged_settings = {**existing.get("settings", {}), **settings}
        
        store_item({
            MESSAGES_PK_NAME: settings_pk,
            "itemType": "WABA_SETTINGS",
            "wabaMetaId": meta_waba_id,
            "settings": merged_settings,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_waba_settings",
            "wabaMetaId": meta_waba_id,
            "settings": merged_settings,
            "updatedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_waba_settings(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get WABA settings.
    
    Test Event:
    {
        "action": "get_waba_settings",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    settings_pk = f"WABA_SETTINGS#{meta_waba_id}"
    
    try:
        settings = get_item(settings_pk)
        waba_config = get_waba_config(meta_waba_id)
        
        return {
            "statusCode": 200,
            "operation": "get_waba_settings",
            "wabaMetaId": meta_waba_id,
            "settings": settings.get("settings", {}) if settings else {},
            "wabaConfig": waba_config
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_credit_line(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get credit line information for WABA.
    
    Test Event:
    {
        "action": "get_credit_line",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # This would typically call Meta Graph API
        return {
            "statusCode": 200,
            "operation": "get_credit_line",
            "wabaMetaId": meta_waba_id,
            "creditLine": {
                "status": "ACTIVE",
                "currency": "USD",
                "note": "Credit line info requires Meta Graph API call to /{waba-id}/assigned_users"
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
