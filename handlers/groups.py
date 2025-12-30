# WhatsApp Groups Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/groups

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, social, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message,
    format_wa_number, origination_id_for_api, META_API_VERSION
)
from botocore.exceptions import ClientError

logger = logging.getLogger()


def handle_create_group(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a WhatsApp group.
    
    Test Event:
    {
        "action": "create_group",
        "metaWabaId": "1347766229904230",
        "groupName": "Customer Support",
        "groupDescription": "Support group for customers",
        "participants": ["+919876543210", "+919876543211"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    group_name = event.get("groupName", "")
    group_description = event.get("groupDescription", "")
    participants = event.get("participants", [])
    
    error = validate_required_fields(event, ["metaWabaId", "groupName"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    now = iso_now()
    group_id = f"GROUP_{now.replace(':', '').replace('-', '').replace('.', '')}"
    group_pk = f"GROUP#{group_id}"
    
    try:
        # Store group
        group_data = {
            MESSAGES_PK_NAME: group_pk,
            "itemType": "GROUP",
            "groupId": group_id,
            "wabaMetaId": meta_waba_id,
            "phoneArn": phone_arn,
            "groupName": group_name,
            "groupDescription": group_description,
            "participants": [format_wa_number(p) for p in participants],
            "participantCount": len(participants),
            "createdAt": now,
            "lastUpdatedAt": now,
            "status": "active",
            "messageCount": 0,
        }
        
        store_item(group_data)
        
        return {
            "statusCode": 200,
            "operation": "create_group",
            "groupId": group_id,
            "groupPk": group_pk,
            "groupName": group_name,
            "participantCount": len(participants),
            "message": "Group created. Note: WhatsApp Business API group creation requires specific API access."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_add_group_participant(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add participant to a group.
    
    Test Event:
    {
        "action": "add_group_participant",
        "groupId": "GROUP_20241230120000",
        "participant": "+919876543212"
    }
    """
    group_id = event.get("groupId", "")
    participant = event.get("participant", "")
    
    error = validate_required_fields(event, ["groupId", "participant"])
    if error:
        return error
    
    group_pk = f"GROUP#{group_id}"
    now = iso_now()
    
    try:
        # Get existing group
        group = get_item(group_pk)
        if not group:
            return {"statusCode": 404, "error": f"Group not found: {group_id}"}
        
        participants = group.get("participants", [])
        formatted_participant = format_wa_number(participant)
        
        if formatted_participant in participants:
            return {"statusCode": 400, "error": "Participant already in group"}
        
        participants.append(formatted_participant)
        
        # Update group
        table().update_item(
            Key={MESSAGES_PK_NAME: group_pk},
            UpdateExpression="SET participants = :p, participantCount = :pc, lastUpdatedAt = :lu",
            ExpressionAttributeValues={
                ":p": participants,
                ":pc": len(participants),
                ":lu": now
            }
        )
        
        # Store participant history
        store_item({
            MESSAGES_PK_NAME: f"GROUP_PARTICIPANT#{group_id}#{formatted_participant}",
            "itemType": "GROUP_PARTICIPANT",
            "groupId": group_id,
            "participant": formatted_participant,
            "action": "added",
            "addedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "add_group_participant",
            "groupId": group_id,
            "participant": formatted_participant,
            "participantCount": len(participants)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_remove_group_participant(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Remove participant from a group.
    
    Test Event:
    {
        "action": "remove_group_participant",
        "groupId": "GROUP_20241230120000",
        "participant": "+919876543212"
    }
    """
    group_id = event.get("groupId", "")
    participant = event.get("participant", "")
    
    error = validate_required_fields(event, ["groupId", "participant"])
    if error:
        return error
    
    group_pk = f"GROUP#{group_id}"
    now = iso_now()
    
    try:
        group = get_item(group_pk)
        if not group:
            return {"statusCode": 404, "error": f"Group not found: {group_id}"}
        
        participants = group.get("participants", [])
        formatted_participant = format_wa_number(participant)
        
        if formatted_participant not in participants:
            return {"statusCode": 400, "error": "Participant not in group"}
        
        participants.remove(formatted_participant)
        
        table().update_item(
            Key={MESSAGES_PK_NAME: group_pk},
            UpdateExpression="SET participants = :p, participantCount = :pc, lastUpdatedAt = :lu",
            ExpressionAttributeValues={
                ":p": participants,
                ":pc": len(participants),
                ":lu": now
            }
        )
        
        # Update participant history
        table().update_item(
            Key={MESSAGES_PK_NAME: f"GROUP_PARTICIPANT#{group_id}#{formatted_participant}"},
            UpdateExpression="SET #act = :a, removedAt = :ra",
            ExpressionAttributeNames={"#act": "action"},
            ExpressionAttributeValues={":a": "removed", ":ra": now}
        )
        
        return {
            "statusCode": 200,
            "operation": "remove_group_participant",
            "groupId": group_id,
            "participant": formatted_participant,
            "participantCount": len(participants)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_group_info(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get group information.
    
    Test Event:
    {
        "action": "get_group_info",
        "groupId": "GROUP_20241230120000"
    }
    """
    group_id = event.get("groupId", "")
    
    error = validate_required_fields(event, ["groupId"])
    if error:
        return error
    
    group_pk = f"GROUP#{group_id}"
    
    try:
        group = get_item(group_pk)
        if not group:
            return {"statusCode": 404, "error": f"Group not found: {group_id}"}
        
        return {
            "statusCode": 200,
            "operation": "get_group_info",
            "group": group
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_groups(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all groups for a WABA.
    
    Test Event:
    {
        "action": "get_groups",
        "metaWabaId": "1347766229904230",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "GROUP"}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_groups",
            "count": len(items),
            "groups": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_group_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send message to a group.
    
    Test Event:
    {
        "action": "send_group_message",
        "groupId": "GROUP_20241230120000",
        "messageType": "text",
        "text": "Hello group!"
    }
    
    Or with media:
    {
        "action": "send_group_message",
        "groupId": "GROUP_20241230120000",
        "messageType": "image",
        "mediaId": "123456789",
        "caption": "Check this out!"
    }
    """
    group_id = event.get("groupId", "")
    message_type = event.get("messageType", "text")
    text = event.get("text", "")
    media_id = event.get("mediaId", "")
    caption = event.get("caption", "")
    
    error = validate_required_fields(event, ["groupId"])
    if error:
        return error
    
    group_pk = f"GROUP#{group_id}"
    
    try:
        group = get_item(group_pk)
        if not group:
            return {"statusCode": 404, "error": f"Group not found: {group_id}"}
        
        phone_arn = group.get("phoneArn", "")
        participants = group.get("participants", [])
        
        if not participants:
            return {"statusCode": 400, "error": "Group has no participants"}
        
        now = iso_now()
        results = []
        success_count = 0
        
        # Send to each participant
        for participant in participants:
            if message_type == "text":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": participant,
                    "type": "text",
                    "text": {"body": text}
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": participant,
                    "type": message_type,
                    message_type: {"id": media_id}
                }
                if caption:
                    payload[message_type]["caption"] = caption
            
            result = send_whatsapp_message(phone_arn, payload)
            results.append({"participant": participant, **result})
            if result.get("success"):
                success_count += 1
        
        # Update group message count
        table().update_item(
            Key={MESSAGES_PK_NAME: group_pk},
            UpdateExpression="SET messageCount = messageCount + :one, lastMessageAt = :lm",
            ExpressionAttributeValues={":one": 1, ":lm": now}
        )
        
        # Store group message
        msg_pk = f"GROUP_MSG#{group_id}#{now}"
        store_item({
            MESSAGES_PK_NAME: msg_pk,
            "itemType": "GROUP_MESSAGE",
            "groupId": group_id,
            "messageType": message_type,
            "text": text,
            "mediaId": media_id,
            "caption": caption,
            "sentAt": now,
            "recipientCount": len(participants),
            "successCount": success_count,
        })
        
        return {
            "statusCode": 200,
            "operation": "send_group_message",
            "groupId": group_id,
            "recipientCount": len(participants),
            "successCount": success_count,
            "results": results
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_group_messages(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get messages sent to a group.
    
    Test Event:
    {
        "action": "get_group_messages",
        "groupId": "GROUP_20241230120000",
        "limit": 50
    }
    """
    group_id = event.get("groupId", "")
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["groupId"])
    if error:
        return error
    
    try:
        response = table().scan(
            FilterExpression="itemType = :it AND groupId = :gid",
            ExpressionAttributeValues={":it": "GROUP_MESSAGE", ":gid": group_id},
            Limit=limit
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_group_messages",
            "groupId": group_id,
            "count": len(items),
            "messages": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
