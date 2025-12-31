# =============================================================================
# Bedrock Handlers
# =============================================================================
# Action handlers for Bedrock integration.
# =============================================================================

import json
import logging
import os
from typing import Any, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def handle_bedrock_process_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process a WhatsApp message with Bedrock.
    
    Required: messageId
    Optional: tenantId, conversationId, generateReply
    
    Test Event:
    {
        "action": "bedrock_process_message",
        "messageId": "wamid.xxx",
        "tenantId": "1347766229904230"
    }
    """
    from src.bedrock.processor import BedrockProcessor
    
    message_id = event.get("messageId", "")
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    conversation_id = event.get("conversationId", "")
    generate_reply = event.get("generateReply", True)
    
    if not message_id:
        return {"statusCode": 400, "error": "messageId is required"}
    
    processor = BedrockProcessor()
    result = processor.process_message(
        message_id=message_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        generate_reply=generate_reply,
    )
    
    return {
        "statusCode": 200 if result.success else 500,
        "operation": "bedrock_process_message",
        "messageId": result.message_id,
        "contentType": result.content_type,
        "summary": result.summary,
        "intent": result.intent,
        "entities": result.entities,
        "replyDraft": result.reply_draft,
        "error": result.error if not result.success else None,
    }


def handle_bedrock_invoke_agent(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Invoke Bedrock Agent directly with text.
    
    Required: inputText
    Optional: sessionId, enableTrace
    
    Test Event:
    {
        "action": "bedrock_invoke_agent",
        "inputText": "What services does WECARE.DIGITAL offer?"
    }
    """
    from src.bedrock.agent import BedrockAgent
    
    input_text = event.get("inputText", "")
    session_id = event.get("sessionId")
    enable_trace = event.get("enableTrace", False)
    
    if not input_text:
        return {"statusCode": 400, "error": "inputText is required"}
    
    agent = BedrockAgent()
    response = agent.invoke(
        input_text=input_text,
        session_id=session_id,
        enable_trace=enable_trace,
    )
    
    return {
        "statusCode": 200,
        "operation": "bedrock_invoke_agent",
        "sessionId": response.session_id,
        "completion": response.completion,
        "citations": response.citations,
        "trace": response.trace if enable_trace else None,
    }


def handle_bedrock_get_reply_draft(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get stored reply draft for a message.
    
    Required: messageId
    Optional: tenantId, conversationId
    
    Test Event:
    {
        "action": "bedrock_get_reply_draft",
        "messageId": "wamid.xxx"
    }
    """
    import boto3
    from botocore.exceptions import ClientError
    
    message_id = event.get("messageId", "")
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    conversation_id = event.get("conversationId", "")
    
    if not message_id:
        return {"statusCode": 400, "error": "messageId is required"}
    
    pk_name = os.environ.get("MESSAGES_PK_NAME", "pk")
    table_name = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
    
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    
    pk = f"BEDROCK#{conversation_id or tenant_id}#{message_id}"
    
    try:
        response = table.get_item(Key={pk_name: pk})
        item = response.get("Item")
        
        if not item:
            return {
                "statusCode": 404,
                "error": f"No Bedrock result found for message: {message_id}",
            }
        
        return {
            "statusCode": 200,
            "operation": "bedrock_get_reply_draft",
            "messageId": message_id,
            "replyDraft": item.get("replyDraft", ""),
            "summary": item.get("summary", ""),
            "intent": item.get("intent", ""),
            "processedAt": item.get("processedAt", ""),
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_bedrock_send_reply(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Send the Bedrock-generated reply to the user.
    
    Required: messageId, metaWabaId, to
    Optional: customReply (override stored draft)
    
    Test Event:
    {
        "action": "bedrock_send_reply",
        "messageId": "wamid.xxx",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003"
    }
    """
    import boto3
    from botocore.exceptions import ClientError
    
    message_id = event.get("messageId", "")
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    custom_reply = event.get("customReply", "")
    
    if not message_id or not meta_waba_id or not to_number:
        return {"statusCode": 400, "error": "messageId, metaWabaId, and to are required"}
    
    # Get WABA config
    waba_map_json = os.environ.get("WABA_PHONE_MAP_JSON", "{}")
    try:
        waba_map = json.loads(waba_map_json)
    except json.JSONDecodeError:
        waba_map = {}
    
    config = waba_map.get(str(meta_waba_id), {})
    phone_arn = config.get("phoneArn", "")
    
    if not phone_arn:
        return {"statusCode": 404, "error": f"WABA not found: {meta_waba_id}"}
    
    # Get reply text
    reply_text = custom_reply
    if not reply_text:
        # Get from stored draft
        result = handle_bedrock_get_reply_draft({
            "messageId": message_id,
            "tenantId": meta_waba_id,
        }, context)
        
        if result.get("statusCode") != 200:
            return result
        
        reply_text = result.get("replyDraft", "")
    
    if not reply_text:
        return {"statusCode": 400, "error": "No reply text available"}
    
    # Format number
    to_formatted = to_number.strip()
    if not to_formatted.startswith("+"):
        to_formatted = f"+{to_formatted}"
    
    # Send message
    social = boto3.client("socialmessaging")
    meta_api_version = os.environ.get("META_API_VERSION", "v20.0")
    
    # Convert phone ARN to API format
    origination_id = phone_arn
    if "phone-number-id/" in phone_arn:
        suffix = phone_arn.split("phone-number-id/")[-1]
        origination_id = f"phone-number-id-{suffix}"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "text",
        "text": {"body": reply_text},
    }
    
    try:
        response = social.send_whatsapp_message(
            originationPhoneNumberId=origination_id,
            metaApiVersion=meta_api_version,
            message=json.dumps(payload).encode("utf-8"),
        )
        
        return {
            "statusCode": 200,
            "operation": "bedrock_send_reply",
            "messageId": response.get("messageId", ""),
            "to": to_formatted,
            "replyText": reply_text[:200] + "..." if len(reply_text) > 200 else reply_text,
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_bedrock_get_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get Bedrock configuration status.
    
    Test Event:
    {
        "action": "bedrock_get_config"
    }
    """
    return {
        "statusCode": 200,
        "operation": "bedrock_get_config",
        "config": {
            "region": os.environ.get("BEDROCK_REGION", "ap-south-1"),
            "agentId": os.environ.get("BEDROCK_AGENT_ID", ""),
            "agentAliasId": os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID"),
            "knowledgeBaseId": os.environ.get("BEDROCK_KB_ID", ""),
            "autoReplyEnabled": os.environ.get("AUTO_REPLY_BEDROCK_ENABLED", "false").lower() == "true",
        },
        "capabilities": {
            "textProcessing": True,
            "imageProcessing": True,
            "documentProcessing": True,  # Via Data Automation
            "audioProcessing": True,     # Via Data Automation
            "videoProcessing": True,     # Via Data Automation
        },
    }


# =============================================================================
# HANDLER MAPPING
# =============================================================================

BEDROCK_HANDLERS = {
    "bedrock_process_message": handle_bedrock_process_message,
    "bedrock_invoke_agent": handle_bedrock_invoke_agent,
    "bedrock_get_reply_draft": handle_bedrock_get_reply_draft,
    "bedrock_send_reply": handle_bedrock_send_reply,
    "bedrock_get_config": handle_bedrock_get_config,
}
