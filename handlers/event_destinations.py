# AWS Event Destinations Handlers
# Ref: https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations.html
#
# This module handles SNS/EventBridge event destination configuration
# =============================================================================

import json
import logging
from typing import Any, Dict
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_sns
)
from botocore.exceptions import ClientError

logger = logging.getLogger()


def handle_create_event_destination(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create SNS event destination for WhatsApp webhooks.
    
    Test Event:
    {
        "action": "create_event_destination",
        "metaWabaId": "1347766229904230",
        "destinationType": "SNS",
        "snsTopicArn": "arn:aws:sns:ap-south-1:123456789:whatsapp-events",
        "eventTypes": ["message", "status", "error"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    destination_type = event.get("destinationType", "SNS")
    sns_topic_arn = event.get("snsTopicArn", "")
    event_types = event.get("eventTypes", ["message", "status"])
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if destination_type == "SNS" and not sns_topic_arn:
        return {"statusCode": 400, "error": "snsTopicArn required for SNS destination"}
    
    dest_pk = f"EVENT_DEST#{meta_waba_id}#{destination_type}"
    now = iso_now()
    
    try:
        store_item({
            MESSAGES_PK_NAME: dest_pk,
            "itemType": "EVENT_DESTINATION",
            "wabaMetaId": meta_waba_id,
            "destinationType": destination_type,
            "snsTopicArn": sns_topic_arn,
            "eventTypes": event_types,
            "status": "active",
            "createdAt": now
        })
        
        return {
            "statusCode": 200,
            "operation": "create_event_destination",
            "wabaMetaId": meta_waba_id,
            "destinationType": destination_type,
            "eventTypes": event_types,
            "status": "active"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_event_destinations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get configured event destinations.
    
    Test Event:
    {
        "action": "get_event_destinations",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        response = table().scan(
            FilterExpression="itemType = :it AND wabaMetaId = :waba",
            ExpressionAttributeValues={":it": "EVENT_DESTINATION", ":waba": meta_waba_id}
        )
        
        return {
            "statusCode": 200,
            "operation": "get_event_destinations",
            "count": len(response.get("Items", [])),
            "destinations": response.get("Items", [])
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_event_destination(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update event destination configuration.
    
    Test Event:
    {
        "action": "update_event_destination",
        "metaWabaId": "1347766229904230",
        "destinationType": "SNS",
        "eventTypes": ["message", "status", "error", "quality"],
        "status": "active"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    destination_type = event.get("destinationType", "SNS")
    event_types = event.get("eventTypes", [])
    status = event.get("status", "")
    
    error = validate_required_fields(event, ["metaWabaId", "destinationType"])
    if error:
        return error
    
    dest_pk = f"EVENT_DEST#{meta_waba_id}#{destination_type}"
    now = iso_now()
    
    try:
        update_expr = "SET lastUpdatedAt = :lu"
        expr_values = {":lu": now}
        
        if event_types:
            update_expr += ", eventTypes = :et"
            expr_values[":et"] = event_types
        if status:
            update_expr += ", #st = :st"
            expr_values[":st"] = status
        
        update_kwargs = {
            "Key": {MESSAGES_PK_NAME: dest_pk},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values
        }
        if status:
            update_kwargs["ExpressionAttributeNames"] = {"#st": "status"}
        
        table().update_item(**update_kwargs)
        
        return {
            "statusCode": 200,
            "operation": "update_event_destination",
            "wabaMetaId": meta_waba_id,
            "destinationType": destination_type,
            "updated": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_delete_event_destination(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete event destination.
    
    Test Event:
    {
        "action": "delete_event_destination",
        "metaWabaId": "1347766229904230",
        "destinationType": "SNS"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    destination_type = event.get("destinationType", "SNS")
    
    error = validate_required_fields(event, ["metaWabaId", "destinationType"])
    if error:
        return error
    
    dest_pk = f"EVENT_DEST#{meta_waba_id}#{destination_type}"
    
    try:
        table().delete_item(Key={MESSAGES_PK_NAME: dest_pk})
        
        return {
            "statusCode": 200,
            "operation": "delete_event_destination",
            "wabaMetaId": meta_waba_id,
            "destinationType": destination_type,
            "deleted": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_test_event_destination(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Test event destination by sending a test message.
    
    Test Event:
    {
        "action": "test_event_destination",
        "metaWabaId": "1347766229904230",
        "destinationType": "SNS"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    destination_type = event.get("destinationType", "SNS")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    dest_pk = f"EVENT_DEST#{meta_waba_id}#{destination_type}"
    
    try:
        dest = get_item(dest_pk)
        if not dest:
            return {"statusCode": 404, "error": "Event destination not found"}
        
        if destination_type == "SNS" and dest.get("snsTopicArn"):
            test_message = {
                "type": "test",
                "wabaMetaId": meta_waba_id,
                "timestamp": iso_now(),
                "message": "Test event from WhatsApp Business API"
            }
            
            get_sns().publish(
                TopicArn=dest.get("snsTopicArn"),
                Message=json.dumps(test_message),
                Subject="WhatsApp Event Destination Test"
            )
            
            return {
                "statusCode": 200,
                "operation": "test_event_destination",
                "wabaMetaId": meta_waba_id,
                "destinationType": destination_type,
                "testSent": True,
                "snsTopicArn": dest.get("snsTopicArn")
            }
        
        return {"statusCode": 400, "error": "Unsupported destination type or missing config"}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
