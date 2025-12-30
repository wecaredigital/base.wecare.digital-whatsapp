# WhatsApp Calling Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/phone-numbers/calling

import json
import logging
from typing import Any, Dict
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Call Types
CALL_TYPES = {
    "business_initiated": "Business initiates call to customer",
    "user_initiated": "Customer initiates call to business",
    "sip": "SIP-based calling"
}

# Call Status
CALL_STATUSES = ["initiated", "ringing", "connected", "ended", "failed", "missed"]


def handle_initiate_call(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initiate a WhatsApp call (business-initiated).
    
    Test Event:
    {
        "action": "initiate_call",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "callType": "business_initiated",
        "agentId": "agent_001",
        "callReason": "Order follow-up"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    call_type = event.get("callType", "business_initiated")
    agent_id = event.get("agentId", "")
    call_reason = event.get("callReason", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to"])
    if error:
        return error
    
    if call_type not in CALL_TYPES:
        return {"statusCode": 400, "error": f"Invalid callType. Valid: {list(CALL_TYPES.keys())}"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    now = iso_now()
    call_id = f"CALL_{now.replace(':', '').replace('-', '').replace('.', '')}"
    call_pk = f"CALL#{call_id}"
    
    try:
        # Store call record
        call_data = {
            MESSAGES_PK_NAME: call_pk,
            "itemType": "CALL",
            "callId": call_id,
            "wabaMetaId": meta_waba_id,
            "phoneArn": phone_arn,
            "toNumber": to_number,
            "callType": call_type,
            "agentId": agent_id,
            "callReason": call_reason,
            "status": "initiated",
            "initiatedAt": now,
            "statusHistory": [{"status": "initiated", "timestamp": now}],
        }
        
        store_item(call_data)
        
        # Note: Actual call initiation requires WhatsApp Business API call endpoint
        # This stores the call intent and tracking data
        
        return {
            "statusCode": 200,
            "operation": "initiate_call",
            "callId": call_id,
            "callPk": call_pk,
            "to": to_number,
            "callType": call_type,
            "status": "initiated",
            "message": "Call initiated. Actual call requires WhatsApp Business API calling endpoint."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_call_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update call status (from webhook or manual).
    
    Test Event:
    {
        "action": "update_call_status",
        "callId": "CALL_20241230120000",
        "status": "connected",
        "duration": 120
    }
    """
    call_id = event.get("callId", "")
    status = event.get("status", "")
    duration = event.get("duration", 0)
    end_reason = event.get("endReason", "")
    
    error = validate_required_fields(event, ["callId", "status"])
    if error:
        return error
    
    if status not in CALL_STATUSES:
        return {"statusCode": 400, "error": f"Invalid status. Valid: {CALL_STATUSES}"}
    
    call_pk = f"CALL#{call_id}"
    now = iso_now()
    
    try:
        # Get existing call
        existing = get_item(call_pk)
        if not existing:
            return {"statusCode": 404, "error": f"Call not found: {call_id}"}
        
        # Update status history
        status_history = existing.get("statusHistory", [])
        status_history.append({"status": status, "timestamp": now})
        
        update_data = {
            "status": status,
            "lastUpdatedAt": now,
            "statusHistory": status_history,
        }
        
        if duration:
            update_data["duration"] = duration
        if end_reason:
            update_data["endReason"] = end_reason
        if status == "ended":
            update_data["endedAt"] = now
        
        # Update in DynamoDB
        update_expr_parts = []
        expr_values = {}
        for key, value in update_data.items():
            update_expr_parts.append(f"{key} = :{key}")
            expr_values[f":{key}"] = value
        
        table().update_item(
            Key={MESSAGES_PK_NAME: call_pk},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeValues=expr_values,
        )
        
        return {
            "statusCode": 200,
            "operation": "update_call_status",
            "callId": call_id,
            "status": status,
            "duration": duration
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_call_logs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get call logs.
    
    Test Event:
    {
        "action": "get_call_logs",
        "metaWabaId": "1347766229904230",
        "agentId": "agent_001",
        "status": "ended",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    agent_id = event.get("agentId", "")
    status = event.get("status", "")
    to_number = event.get("toNumber", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "CALL"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        if agent_id:
            filter_expr += " AND agentId = :aid"
            expr_values[":aid"] = agent_id
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
        
        if to_number:
            filter_expr += " AND toNumber = :tn"
            expr_values[":tn"] = to_number
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit
        }
        
        if status:
            scan_kwargs["ExpressionAttributeNames"] = {"#st": "status"}
        
        response = table().scan(**scan_kwargs)
        items = response.get("Items", [])
        
        # Calculate stats
        total_calls = len(items)
        total_duration = sum(i.get("duration", 0) for i in items)
        connected_calls = len([i for i in items if i.get("status") == "ended" and i.get("duration", 0) > 0])
        
        return {
            "statusCode": 200,
            "operation": "get_call_logs",
            "count": total_calls,
            "stats": {
                "totalCalls": total_calls,
                "connectedCalls": connected_calls,
                "totalDurationSeconds": total_duration,
                "avgDurationSeconds": round(total_duration / connected_calls, 2) if connected_calls > 0 else 0
            },
            "calls": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_call_settings(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update call settings for a WABA.
    
    Test Event:
    {
        "action": "update_call_settings",
        "metaWabaId": "1347766229904230",
        "settings": {
            "callingEnabled": true,
            "businessInitiatedEnabled": true,
            "userInitiatedEnabled": true,
            "sipEnabled": false,
            "maxConcurrentCalls": 10,
            "callRecordingEnabled": true,
            "autoAnswerEnabled": false
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    settings = event.get("settings", {})
    
    error = validate_required_fields(event, ["metaWabaId", "settings"])
    if error:
        return error
    
    now = iso_now()
    settings_pk = f"CALL_SETTINGS#{meta_waba_id}"
    
    try:
        settings_data = {
            MESSAGES_PK_NAME: settings_pk,
            "itemType": "CALL_SETTINGS",
            "wabaMetaId": meta_waba_id,
            "callingEnabled": settings.get("callingEnabled", True),
            "businessInitiatedEnabled": settings.get("businessInitiatedEnabled", True),
            "userInitiatedEnabled": settings.get("userInitiatedEnabled", True),
            "sipEnabled": settings.get("sipEnabled", False),
            "maxConcurrentCalls": settings.get("maxConcurrentCalls", 10),
            "callRecordingEnabled": settings.get("callRecordingEnabled", False),
            "autoAnswerEnabled": settings.get("autoAnswerEnabled", False),
            "lastUpdatedAt": now,
        }
        
        store_item(settings_data)
        
        return {
            "statusCode": 200,
            "operation": "update_call_settings",
            "settingsPk": settings_pk,
            "settings": settings_data
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_call_settings(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get call settings for a WABA.
    
    Test Event:
    {
        "action": "get_call_settings",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    settings_pk = f"CALL_SETTINGS#{meta_waba_id}"
    
    try:
        settings = get_item(settings_pk)
        
        if not settings:
            # Return defaults
            settings = {
                "callingEnabled": True,
                "businessInitiatedEnabled": True,
                "userInitiatedEnabled": True,
                "sipEnabled": False,
                "maxConcurrentCalls": 10,
                "callRecordingEnabled": False,
                "autoAnswerEnabled": False,
            }
        
        return {
            "statusCode": 200,
            "operation": "get_call_settings",
            "wabaMetaId": meta_waba_id,
            "settings": settings
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_create_call_deeplink(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a deep link for WhatsApp call button.
    
    Test Event:
    {
        "action": "create_call_deeplink",
        "phoneNumber": "+919903300044",
        "callType": "voice"
    }
    """
    phone_number = event.get("phoneNumber", "")
    call_type = event.get("callType", "voice")  # voice or video
    
    error = validate_required_fields(event, ["phoneNumber"])
    if error:
        return error
    
    # Clean phone number
    clean_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    # WhatsApp deep links
    deeplinks = {
        "voice": f"https://wa.me/{clean_number}?call=voice",
        "video": f"https://wa.me/{clean_number}?call=video",
        "universal": f"whatsapp://call?phone={clean_number}",
    }
    
    return {
        "statusCode": 200,
        "operation": "create_call_deeplink",
        "phoneNumber": phone_number,
        "callType": call_type,
        "deeplinks": deeplinks,
        "note": "Use these links in buttons or CTA messages to initiate calls"
    }
