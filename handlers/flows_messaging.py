# WhatsApp Flows Messaging Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/flows/gettingstarted/sendingaflow
# 
# This module handles sending Flow messages and Flow data exchange
# =============================================================================

import json
import logging
import hashlib
import hmac
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, social, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config,
    send_whatsapp_message, format_wa_number, origination_id_for_api, META_API_VERSION
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Flow Action Types
FLOW_ACTION_TYPES = ["navigate", "data_exchange"]

# Flow Modes
FLOW_MODES = ["draft", "published"]


def handle_create_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Store a WhatsApp Flow definition in DynamoDB.
    
    Use this to store Flow IDs created in Meta Business Suite for later use.
    
    Test Event:
    {
        "action": "create_flow",
        "metaWabaId": "1347766229904230",
        "flowId": "1234567890",
        "flowName": "Appointment Booking",
        "flowDescription": "Book appointments with customers",
        "flowStatus": "PUBLISHED",
        "flowJson": {}
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    flow_id = event.get("flowId", "")
    flow_name = event.get("flowName", "")
    flow_description = event.get("flowDescription", "")
    flow_status = event.get("flowStatus", "DRAFT")
    flow_json = event.get("flowJson", {})
    
    error = validate_required_fields(event, ["metaWabaId", "flowId", "flowName"])
    if error:
        return error
    
    now = iso_now()
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: flow_pk,
            "itemType": "FLOW",
            "wabaMetaId": meta_waba_id,
            "flowId": flow_id,
            "flowName": flow_name,
            "flowDescription": flow_description,
            "status": flow_status,
            "flowJson": flow_json,
            "createdAt": now,
            "lastUpdatedAt": now,
            "messagesSent": 0,
            "completions": 0,
        })
        
        return {
            "statusCode": 200,
            "operation": "create_flow",
            "flowPk": flow_pk,
            "flowId": flow_id,
            "flowName": flow_name,
            "status": flow_status,
            "message": "Flow stored successfully. Use send_flow_message to trigger."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flows(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all stored Flows for a WABA.
    
    Test Event:
    {
        "action": "get_flows",
        "metaWabaId": "1347766229904230",
        "status": "PUBLISHED"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "FLOW", ":waba": meta_waba_id}
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
        
        scan_params = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit
        }
        
        if status:
            scan_params["ExpressionAttributeNames"] = {"#st": "status"}
        
        response = table().scan(**scan_params)
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_flows",
            "wabaMetaId": meta_waba_id,
            "count": len(items),
            "flows": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update a stored Flow definition.
    
    Test Event:
    {
        "action": "update_flow",
        "metaWabaId": "1347766229904230",
        "flowId": "1234567890",
        "flowStatus": "PUBLISHED",
        "flowName": "Updated Flow Name"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    flow_id = event.get("flowId", "")
    flow_name = event.get("flowName", "")
    flow_description = event.get("flowDescription", "")
    flow_status = event.get("flowStatus", "")
    flow_json = event.get("flowJson")
    
    error = validate_required_fields(event, ["metaWabaId", "flowId"])
    if error:
        return error
    
    flow_pk = f"FLOW#{meta_waba_id}#{flow_id}"
    now = iso_now()
    
    try:
        # Check if flow exists
        flow = get_item(flow_pk)
        if not flow:
            return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
        
        # Build update expression
        update_parts = ["lastUpdatedAt = :lu"]
        expr_values = {":lu": now}
        expr_names = {}
        
        if flow_name:
            update_parts.append("flowName = :fn")
            expr_values[":fn"] = flow_name
        
        if flow_description:
            update_parts.append("flowDescription = :fd")
            expr_values[":fd"] = flow_description
        
        if flow_status:
            update_parts.append("#st = :st")
            expr_values[":st"] = flow_status
            expr_names["#st"] = "status"
        
        if flow_json is not None:
            update_parts.append("flowJson = :fj")
            expr_values[":fj"] = flow_json
        
        update_params = {
            "Key": {MESSAGES_PK_NAME: flow_pk},
            "UpdateExpression": "SET " + ", ".join(update_parts),
            "ExpressionAttributeValues": expr_values
        }
        
        if expr_names:
            update_params["ExpressionAttributeNames"] = expr_names
        
        table().update_item(**update_params)
        
        return {
            "statusCode": 200,
            "operation": "update_flow",
            "flowPk": flow_pk,
            "flowId": flow_id,
            "updated": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_flow_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a WhatsApp Flow as an interactive message.
    
    This triggers a Flow that the user can interact with directly in WhatsApp.
    The Flow must be published (or in draft mode for testing).
    
    Test Event:
    {
        "action": "send_flow_message",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "flowId": "1234567890",
        "flowToken": "unique_flow_token_123",
        "flowCta": "Book Appointment",
        "flowAction": "navigate",
        "flowActionPayload": {
            "screen": "APPOINTMENT_SCREEN",
            "data": {
                "preselected_date": "2024-12-30"
            }
        },
        "header": "Schedule Your Visit",
        "body": "Click below to book your appointment with us.",
        "footer": "Powered by WECARE.DIGITAL",
        "mode": "published"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    flow_id = event.get("flowId", "")
    flow_token = event.get("flowToken", "")
    flow_cta = event.get("flowCta", "Open")
    flow_action = event.get("flowAction", "navigate")
    flow_action_payload = event.get("flowActionPayload", {})
    header = event.get("header", "")
    body = event.get("body", "")
    footer = event.get("footer", "")
    mode = event.get("mode", "published")
    
    # Validation
    error = validate_required_fields(event, ["metaWabaId", "to", "flowId", "flowToken", "body"])
    if error:
        return error
    
    if flow_action not in FLOW_ACTION_TYPES:
        return {"statusCode": 400, "error": f"Invalid flowAction. Valid: {FLOW_ACTION_TYPES}"}
    
    if mode not in FLOW_MODES:
        return {"statusCode": 400, "error": f"Invalid mode. Valid: {FLOW_MODES}"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build the interactive flow message
        interactive = {
            "type": "flow",
            "body": {"text": body},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": flow_token,
                    "flow_id": flow_id,
                    "flow_cta": flow_cta,
                    "flow_action": flow_action,
                }
            }
        }
        
        # Add optional header
        if header:
            interactive["header"] = {"type": "text", "text": header}
        
        # Add optional footer
        if footer:
            interactive["footer"] = {"text": footer}
        
        # Add flow action payload for navigate action
        if flow_action == "navigate" and flow_action_payload:
            interactive["action"]["parameters"]["flow_action_payload"] = flow_action_payload
        
        # Add mode for draft testing
        if mode == "draft":
            interactive["action"]["parameters"]["mode"] = "draft"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        now = iso_now()
        
        if result.get("success"):
            # Store flow message record
            flow_msg_pk = f"FLOW_MESSAGE#{meta_waba_id}#{result['messageId']}"
            store_item({
                MESSAGES_PK_NAME: flow_msg_pk,
                "itemType": "FLOW_MESSAGE",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "flowId": flow_id,
                "flowToken": flow_token,
                "flowAction": flow_action,
                "messageId": result["messageId"],
                "sentAt": now,
                "flowStarted": False,
                "flowCompleted": False,
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_flow_message",
            "flowId": flow_id,
            "flowToken": flow_token,
            **result
        }
    except ClientError as e:
        logger.exception(f"Failed to send flow message: {e}")
        return {"statusCode": 500, "error": str(e)}


def handle_send_flow_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a Flow as a template message (for outside 24-hour window).
    
    Test Event:
    {
        "action": "send_flow_template",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "templateName": "appointment_booking_flow",
        "languageCode": "en_US",
        "flowId": "1234567890",
        "flowToken": "unique_flow_token_123",
        "flowAction": "navigate",
        "flowActionPayload": {
            "screen": "WELCOME"
        },
        "bodyParams": ["John", "December 30"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    flow_id = event.get("flowId", "")
    flow_token = event.get("flowToken", "")
    flow_action = event.get("flowAction", "navigate")
    flow_action_payload = event.get("flowActionPayload", {})
    body_params = event.get("bodyParams", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "flowId", "flowToken"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build template components
        components = []
        
        # Body parameters
        if body_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in body_params]
            })
        
        # Flow button component
        flow_button = {
            "type": "button",
            "sub_type": "flow",
            "index": "0",
            "parameters": [{
                "type": "action",
                "action": {
                    "flow_token": flow_token,
                    "flow_action_data": flow_action_payload if flow_action == "navigate" else {}
                }
            }]
        }
        components.append(flow_button)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        now = iso_now()
        
        if result.get("success"):
            store_item({
                MESSAGES_PK_NAME: f"FLOW_TEMPLATE#{meta_waba_id}#{result['messageId']}",
                "itemType": "FLOW_TEMPLATE_MESSAGE",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "templateName": template_name,
                "flowId": flow_id,
                "flowToken": flow_token,
                "messageId": result["messageId"],
                "sentAt": now,
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_flow_template",
            "templateName": template_name,
            "flowId": flow_id,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_flow_data_exchange(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Flow data exchange webhook.
    
    This endpoint receives data from WhatsApp Flows when:
    1. User completes a screen (data_exchange action)
    2. Flow needs to fetch dynamic data
    3. Flow is completed
    
    Test Event:
    {
        "action": "flow_data_exchange",
        "flowToken": "unique_flow_token_123",
        "flowId": "1234567890",
        "screen": "APPOINTMENT_SCREEN",
        "data": {
            "selected_date": "2024-12-30",
            "selected_time": "10:00 AM",
            "customer_name": "John Doe"
        },
        "version": "3.0",
        "action_type": "data_exchange"
    }
    """
    flow_token = event.get("flowToken", "")
    flow_id = event.get("flowId", "")
    screen = event.get("screen", "")
    data = event.get("data", {})
    version = event.get("version", "3.0")
    action_type = event.get("action_type", "data_exchange")
    
    error = validate_required_fields(event, ["flowToken"])
    if error:
        return error
    
    now = iso_now()
    
    try:
        # Store flow data exchange record
        data_pk = f"FLOW_DATA#{flow_id}#{flow_token}#{now}"
        store_item({
            MESSAGES_PK_NAME: data_pk,
            "itemType": "FLOW_DATA_EXCHANGE",
            "flowId": flow_id,
            "flowToken": flow_token,
            "screen": screen,
            "data": data,
            "version": version,
            "actionType": action_type,
            "receivedAt": now,
        })
        
        # Update flow message status
        # Find the original flow message by token
        response = table().scan(
            FilterExpression="itemType = :it AND flowToken = :ft",
            ExpressionAttributeValues={":it": "FLOW_MESSAGE", ":ft": flow_token},
            Limit=1
        )
        items = response.get("Items", [])
        
        if items:
            flow_msg_pk = items[0].get(MESSAGES_PK_NAME)
            table().update_item(
                Key={MESSAGES_PK_NAME: flow_msg_pk},
                UpdateExpression="SET flowStarted = :fs, lastScreen = :ls, lastDataAt = :lda",
                ExpressionAttributeValues={
                    ":fs": True,
                    ":ls": screen,
                    ":lda": now
                }
            )
        
        # Return response based on action type
        # In production, this would return dynamic data for the next screen
        response_data = {
            "version": version,
            "screen": screen,
            "data": {}  # Populate with dynamic data as needed
        }
        
        return {
            "statusCode": 200,
            "operation": "flow_data_exchange",
            "flowToken": flow_token,
            "screen": screen,
            "processed": True,
            "response": response_data
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_flow_completion(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Flow completion webhook.
    
    Called when a user completes a Flow.
    
    Test Event:
    {
        "action": "flow_completion",
        "flowToken": "unique_flow_token_123",
        "flowId": "1234567890",
        "responseJson": {
            "appointment_date": "2024-12-30",
            "appointment_time": "10:00 AM",
            "customer_name": "John Doe",
            "customer_phone": "+919903300044"
        }
    }
    """
    flow_token = event.get("flowToken", "")
    flow_id = event.get("flowId", "")
    response_json = event.get("responseJson", {})
    
    error = validate_required_fields(event, ["flowToken"])
    if error:
        return error
    
    now = iso_now()
    
    try:
        # Store completion record
        completion_pk = f"FLOW_COMPLETION#{flow_id}#{flow_token}"
        store_item({
            MESSAGES_PK_NAME: completion_pk,
            "itemType": "FLOW_COMPLETION",
            "flowId": flow_id,
            "flowToken": flow_token,
            "responseJson": response_json,
            "completedAt": now,
        })
        
        # Update flow message status
        response = table().scan(
            FilterExpression="itemType = :it AND flowToken = :ft",
            ExpressionAttributeValues={":it": "FLOW_MESSAGE", ":ft": flow_token},
            Limit=1
        )
        items = response.get("Items", [])
        
        if items:
            flow_msg_pk = items[0].get(MESSAGES_PK_NAME)
            table().update_item(
                Key={MESSAGES_PK_NAME: flow_msg_pk},
                UpdateExpression="SET flowCompleted = :fc, completedAt = :ca, responseJson = :rj",
                ExpressionAttributeValues={
                    ":fc": True,
                    ":ca": now,
                    ":rj": response_json
                }
            )
        
        return {
            "statusCode": 200,
            "operation": "flow_completion",
            "flowToken": flow_token,
            "flowId": flow_id,
            "completed": True,
            "responseJson": response_json
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_flow_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate Flow JSON structure.
    
    Test Event:
    {
        "action": "flow_health_check",
        "flowJson": {
            "version": "3.0",
            "screens": [...]
        }
    }
    """
    flow_json = event.get("flowJson", {})
    
    error = validate_required_fields(event, ["flowJson"])
    if error:
        return error
    
    issues = []
    warnings = []
    
    # Validate version
    version = flow_json.get("version", "")
    if not version:
        issues.append("Missing 'version' field")
    elif version not in ["2.1", "3.0", "4.0"]:
        warnings.append(f"Version '{version}' may not be supported")
    
    # Validate screens
    screens = flow_json.get("screens", [])
    if not screens:
        issues.append("No screens defined")
    else:
        screen_ids = set()
        for idx, screen in enumerate(screens):
            screen_id = screen.get("id", "")
            if not screen_id:
                issues.append(f"Screen {idx} missing 'id'")
            elif screen_id in screen_ids:
                issues.append(f"Duplicate screen ID: {screen_id}")
            else:
                screen_ids.add(screen_id)
            
            if not screen.get("layout"):
                issues.append(f"Screen '{screen_id}' missing 'layout'")
            
            if not screen.get("title"):
                warnings.append(f"Screen '{screen_id}' missing 'title'")
    
    # Validate data sources if present
    data_sources = flow_json.get("data_api_version")
    if data_sources:
        warnings.append("Flow uses data API - ensure endpoint is configured")
    
    is_valid = len(issues) == 0
    
    return {
        "statusCode": 200,
        "operation": "flow_health_check",
        "valid": is_valid,
        "issues": issues,
        "warnings": warnings,
        "screenCount": len(screens),
        "version": version
    }


def handle_delete_flow(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete a Flow from local storage.
    
    Test Event:
    {
        "action": "delete_flow",
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
        # Check if flow exists
        flow = get_item(flow_pk)
        if not flow:
            return {"statusCode": 404, "error": f"Flow not found: {flow_id}"}
        
        # Soft delete - mark as deleted
        table().update_item(
            Key={MESSAGES_PK_NAME: flow_pk},
            UpdateExpression="SET #st = :st, deletedAt = :da",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "DELETED",
                ":da": now
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "delete_flow",
            "flowId": flow_id,
            "status": "DELETED",
            "deletedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_flow_responses(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all responses/completions for a Flow.
    
    Test Event:
    {
        "action": "get_flow_responses",
        "flowId": "1234567890",
        "limit": 50
    }
    """
    flow_id = event.get("flowId", "")
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["flowId"])
    if error:
        return error
    
    try:
        response = table().scan(
            FilterExpression="itemType = :it AND flowId = :fid",
            ExpressionAttributeValues={":it": "FLOW_COMPLETION", ":fid": flow_id},
            Limit=limit
        )
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_flow_responses",
            "flowId": flow_id,
            "count": len(items),
            "responses": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
