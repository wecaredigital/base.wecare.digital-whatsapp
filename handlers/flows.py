# WhatsApp Flows Management Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/flows/gettingstarted

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, social, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config,
    send_whatsapp_message, format_wa_number, origination_id_for_api, META_API_VERSION
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Flow Categories
FLOW_CATEGORIES = ["SIGN_UP", "SIGN_IN", "APPOINTMENT_BOOKING", "LEAD_GENERATION", 
                   "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "OTHER"]

# Flow Statuses
FLOW_STATUSES = ["DRAFT", "PUBLISHED", "DEPRECATED", "BLOCKED", "THROTTLED"]


def handle_create_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a new WhatsApp Flow.
    
    Test Event:
    {
        "action": "create_flow",
        "metaWabaId": "1347766229904230",
        "flowName": "appointment_booking",
        "categories": ["APPOINTMENT_BOOKING"],
        "flowJson": {
            "version": "3.0",
            "screens": [
                {
                    "id": "WELCOME",
                    "title": "Book Appointment",
                    "data": {},
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {"type": "TextHeading", "text": "Welcome!"},
                            {"type": "TextBody", "text": "Select a date for your appointment"},
                            {"type": "DatePicker", "name": "appointment_date", "label": "Date"},
                            {"type": "Footer", "label": "Continue", "on-click-action": {"name": "complete"}}
                        ]
                    }
                }
            ]
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    flow_name = event.get("flowName", "")
    categories = event.get("categories", ["OTHER"])
    flow_json = event.get("flowJson", {})
    clone_flow_id = event.get("cloneFlowId", "")
    
    error = validate_required_fields(event, ["metaWabaId", "flowName"])
    if error:
        return error
    
    # Validate categories
    for cat in categories:
        if cat not in FLOW_CATEGORIES:
            return {"statusCode": 400, "error": f"Invalid category: {cat}. Valid: {FLOW_CATEGORIES}"}
    
    now = iso_now()
    flow_id = f"FLOW_{now.replace(':', '').replace('-', '').replace('.', '')}"
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    
    try:
        flow_data = {
            MESSAGES_PK_NAME: flow_pk,
            "itemType": "FLOW",
            "flowId": flow_id,
            "wabaMetaId": meta_waba_id,
            "flowName": flow_name,
            "categories": categories,
            "flowJson": flow_json,
            "status": "DRAFT",
            "version": "3.0",
            "createdAt": now,
            "lastUpdatedAt": now,
            "clonedFrom": clone_flow_id,
        }
        
        store_item(flow_data)
        
        return {
            "statusCode": 200,
            "operation": "create_flow",
            "flowId": flow_id,
            "flowPk": flow_pk,
            "flowName": flow_name,
            "status": "DRAFT",
            "message": "Flow created locally. Use publish_flow to publish to Meta."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update an existing WhatsApp Flow.
    
    Test Event:
    {
        "action": "update_flow",
        "flowId": "FLOW_xxx",
        "flowName": "updated_flow_name",
        "flowJson": {...}
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    flow_name = event.get("flowName", "")
    flow_json = event.get("flowJson", {})
    categories = event.get("categories", [])
    
    error = validate_required_fields(event, ["flowId"])
    if error:
        return error
    
    now = iso_now()
    
    try:
        # Find flow
        if meta_waba_id:
            flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
        else:
            # Search for flow
            response = table().scan(
                FilterExpression="itemType = :it AND flowId = :fid",
                ExpressionAttributeValues={":it": "FLOW", ":fid": flow_id},
                Limit=1
            )
            items = response.get("Items", [])
            if not items:
                return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
            flow_pk = items[0].get(MESSAGES_PK_NAME)
        
        # Build update expression
        update_parts = ["lastUpdatedAt = :lu"]
        expr_values = {":lu": now}
        
        if flow_name:
            update_parts.append("flowName = :fn")
            expr_values[":fn"] = flow_name
        if flow_json:
            update_parts.append("flowJson = :fj")
            expr_values[":fj"] = flow_json
        if categories:
            update_parts.append("categories = :cat")
            expr_values[":cat"] = categories
        
        table().update_item(
            Key={MESSAGES_PK_NAME: flow_pk},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=expr_values
        )
        
        return {
            "statusCode": 200,
            "operation": "update_flow",
            "flowId": flow_id,
            "updatedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_publish_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Publish a WhatsApp Flow to Meta.
    
    Test Event:
    {
        "action": "publish_flow",
        "flowId": "FLOW_xxx",
        "metaWabaId": "1347766229904230"
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["flowId", "metaWabaId"])
    if error:
        return error
    
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    now = iso_now()
    
    try:
        flow = get_item(flow_pk)
        if not flow:
            return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
        
        if flow.get("status") == "PUBLISHED":
            return {"statusCode": 400, "error": "Flow is already published"}
        
        # Update status to published
        table().update_item(
            Key={MESSAGES_PK_NAME: flow_pk},
            UpdateExpression="SET #st = :st, publishedAt = :pa, lastUpdatedAt = :lu",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "PUBLISHED",
                ":pa": now,
                ":lu": now
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "publish_flow",
            "flowId": flow_id,
            "status": "PUBLISHED",
            "publishedAt": now,
            "note": "Flow published locally. For Meta publishing, use Meta Business Suite or Graph API."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_deprecate_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Deprecate a WhatsApp Flow.
    
    Test Event:
    {
        "action": "deprecate_flow",
        "flowId": "FLOW_xxx",
        "metaWabaId": "1347766229904230"
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["flowId", "metaWabaId"])
    if error:
        return error
    
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    now = iso_now()
    
    try:
        table().update_item(
            Key={MESSAGES_PK_NAME: flow_pk},
            UpdateExpression="SET #st = :st, deprecatedAt = :da, lastUpdatedAt = :lu",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "DEPRECATED",
                ":da": now,
                ":lu": now
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "deprecate_flow",
            "flowId": flow_id,
            "status": "DEPRECATED",
            "deprecatedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a WhatsApp Flow by ID.
    
    Test Event:
    {
        "action": "get_flow",
        "flowId": "FLOW_xxx",
        "metaWabaId": "1347766229904230"
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["flowId"])
    if error:
        return error
    
    try:
        if meta_waba_id:
            flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
            flow = get_item(flow_pk)
        else:
            response = table().scan(
                FilterExpression="itemType = :it AND flowId = :fid",
                ExpressionAttributeValues={":it": "FLOW", ":fid": flow_id},
                Limit=1
            )
            items = response.get("Items", [])
            flow = items[0] if items else None
        
        if not flow:
            return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
        
        return {
            "statusCode": 200,
            "operation": "get_flow",
            "flow": flow
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flows(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all WhatsApp Flows for a WABA.
    
    Test Event:
    {
        "action": "get_flows",
        "metaWabaId": "1347766229904230",
        "status": "PUBLISHED",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "FLOW"}
        expr_names = {}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
            expr_names["#st"] = "status"
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit
        }
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table().scan(**scan_kwargs)
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_flows",
            "count": len(items),
            "flows": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flow_metrics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get metrics for a WhatsApp Flow.
    
    Test Event:
    {
        "action": "get_flow_metrics",
        "flowId": "FLOW_xxx",
        "metaWabaId": "1347766229904230"
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["flowId"])
    if error:
        return error
    
    try:
        # Query flow messages
        response = table().scan(
            FilterExpression="itemType = :it AND flowId = :fid",
            ExpressionAttributeValues={":it": "FLOW_MESSAGE", ":fid": flow_id},
            Limit=1000
        )
        items = response.get("Items", [])
        
        # Calculate metrics
        total_sent = len(items)
        completed = len([i for i in items if i.get("flowCompleted")])
        started = len([i for i in items if i.get("flowStarted")])
        
        return {
            "statusCode": 200,
            "operation": "get_flow_metrics",
            "flowId": flow_id,
            "metrics": {
                "totalSent": total_sent,
                "started": started,
                "completed": completed,
                "startRate": round(started / total_sent * 100, 2) if total_sent > 0 else 0,
                "completionRate": round(completed / started * 100, 2) if started > 0 else 0,
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flow_preview(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get preview URL for a WhatsApp Flow.
    
    Test Event:
    {
        "action": "get_flow_preview",
        "flowId": "FLOW_xxx",
        "metaWabaId": "1347766229904230"
    }
    """
    flow_id = event.get("flowId", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["flowId", "metaWabaId"])
    if error:
        return error
    
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    
    try:
        flow = get_item(flow_pk)
        if not flow:
            return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
        
        # Generate preview data
        return {
            "statusCode": 200,
            "operation": "get_flow_preview",
            "flowId": flow_id,
            "flowName": flow.get("flowName", ""),
            "status": flow.get("status", ""),
            "flowJson": flow.get("flowJson", {}),
            "previewNote": "Use Meta Business Suite Flow Builder for visual preview"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
