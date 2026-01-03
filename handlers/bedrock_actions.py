# =============================================================================
# BEDROCK AGENT ACTION GROUP HANDLERS - OMNI-CHANNEL MESSAGING
# =============================================================================
# Handles requests from Bedrock Agent action groups.
# Supports: WhatsApp, SMS, Voice, Email, Payment Links
# 
# Configuration:
# - WhatsApp: AWS End User Messaging Social, UK test +447447840003
# - SMS: AWS EUM SMS (pinpoint-sms-voice-v2), NO sender ID unless explicitly provided
# - Voice: Polly TTS + SMS fallback (no voice origination in ap-south-1)
# - Email: SES from "WECARE.DIGITAL" <one@wecare.digital>
# =============================================================================

import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFIG = {
    "region": "ap-south-1",
    "whatsapp": {
        "waba_id": "1347766229904230",
        "test_number": "+447447840003",
    },
    "sms": {
        "test_number": "+919903300044",
        # India DLT Registration - use when template_id is provided
        "india_sender_id": "WDBEEP",
        "india_entity_id": "1201161991108627443",
        # template_id must be provided by agent for DLT compliance
    },
    "email": {
        "from_address": '"WECARE.DIGITAL" <one@wecare.digital>',
        "from_simple": "one@wecare.digital",
        "reply_to": "one@wecare.digital",
        "default_recipient": "manish@wecare.digital",
    },
    "voice": {
        "polly_voice": "Aditi",
        "polly_engine": "standard",
        "s3_bucket": "dev.wecare.digital",
    },
}


def format_agent_response(action_group: str, function: str, response_body: Dict, api_path: str = "/") -> Dict:
    """Format response for Bedrock Agent (OpenAPI format)."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": "POST",
            "httpStatusCode": response_body.get("statusCode", 200),
            "responseBody": {
                "application/json": {
                    "body": json.dumps(response_body, default=str)
                }
            }
        }
    }


def extract_params(event: Dict) -> Dict:
    """Extract parameters from Bedrock Agent event."""
    request_body = event.get("requestBody", {})
    content = request_body.get("content", {})
    app_json = content.get("application/json", {})
    properties = app_json.get("properties", [])
    
    params = {}
    for prop in properties:
        params[prop.get("name", "")] = prop.get("value", "")
    
    if not params:
        parameters = event.get("parameters", [])
        params = {p["name"]: p["value"] for p in parameters} if parameters else {}
    
    return params


# =============================================================================
# PAYMENTS API HANDLER
# =============================================================================
def handle_payments_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Bedrock Agent requests for Payments API (Razorpay)."""
    logger.info(f"Bedrock Agent Payments Request: {json.dumps(event, default=str)[:500]}")
    
    action_group = event.get("actionGroup", "PaymentsAPI")
    function = event.get("function", "")
    params = extract_params(event)
    
    if function == "createPaymentLink" or not function:
        from handlers.razorpay_api import create_payment
        
        amount = float(params.get("amount", 0))
        description = params.get("description", "Payment")
        
        result = create_payment({"amount": amount, "description": description})
        
        if result.get("error"):
            response_body = {"statusCode": 400, "error": result["error"]}
        else:
            response_body = {
                "statusCode": 200,
                "success": True,
                "paymentId": result.get("paymentId"),
                "paymentUrl": result.get("paymentUrl"),
                "amount": result.get("amount"),
                "message": f"Payment link created for Rs. {amount}: {result.get('paymentUrl')}"
            }
        
        return format_agent_response(action_group, function, response_body)
    
    return format_agent_response(action_group, function, {"statusCode": 400, "error": f"Unknown function: {function}"})


# =============================================================================
# SHORTLINKS API HANDLER
# =============================================================================
def handle_shortlinks_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Bedrock Agent requests for Shortlinks API."""
    logger.info(f"Bedrock Agent Shortlinks Request: {json.dumps(event, default=str)[:500]}")
    
    action_group = event.get("actionGroup", "ShortlinksAPI")
    function = event.get("function", "")
    params = extract_params(event)
    
    if function == "createShortLink" or "targetUrl" in params:
        from handlers.shortlinks import create
        
        target_url = params.get("targetUrl", "")
        title = params.get("title", "")
        custom_code = params.get("customCode")
        
        result = create(target_url, custom_code, title)
        
        if result.get("error"):
            response_body = {"statusCode": 400, "error": result["error"]}
        else:
            response_body = {
                "statusCode": 200,
                "success": True,
                "code": result.get("code"),
                "shortUrl": result.get("shortUrl"),
                "target": result.get("target"),
                "message": f"Short link created: {result.get('shortUrl')}"
            }
        
        return format_agent_response(action_group, function, response_body)
    
    elif function == "getShortLinkStats":
        from handlers.shortlinks import stats
        code = params.get("code", "")
        result = stats(code)
        return format_agent_response(action_group, function, result)
    
    return format_agent_response(action_group, function, {"statusCode": 400, "error": f"Unknown function: {function}"})


# =============================================================================
# WHATSAPP API HANDLER (AWS End User Messaging Social)
# =============================================================================
def handle_whatsapp_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Bedrock Agent requests for WhatsApp API via AWS EUM Social."""
    logger.info(f"Bedrock Agent WhatsApp Request: {json.dumps(event, default=str)[:500]}")
    
    action_group = event.get("actionGroup", "WhatsAppAPI")
    api_path = event.get("apiPath", "/")
    params = extract_params(event)
    
    action = params.get("action", "send_text")
    waba_id = params.get("waba_id", "") or CONFIG["whatsapp"]["waba_id"]
    
    wa_event = {
        "action": action,
        "metaWabaId": waba_id,
        "to": params.get("to", ""),
        "text": params.get("text", ""),
        "template_name": params.get("template_name", ""),
        "template_language": params.get("template_language", "en"),
        "template_params": params.get("template_params", []),
        "media_url": params.get("media_url", ""),
        "caption": params.get("caption", ""),
    }
    
    try:
        if action == "send_text":
            from app import handle_send_text
            result = handle_send_text(wa_event, context)
        elif action == "send_template":
            from app import handle_send_template
            result = handle_send_template(wa_event, context)
        elif action == "send_image":
            from app import handle_send_image
            result = handle_send_image(wa_event, context)
        elif action == "send_document":
            from app import handle_send_document
            result = handle_send_document(wa_event, context)
        else:
            from handlers import unified_dispatch
            result = unified_dispatch(action, wa_event, context)
        
        if result:
            response_body = {
                "statusCode": result.get("statusCode", 200),
                "messageId": result.get("messageId", ""),
                "provider": "AWS_WHATSAPP",
                "destination": wa_event["to"],
                "status": "sent" if result.get("statusCode") == 200 else "failed",
                "message": f"WhatsApp {action} sent to {wa_event['to']}"
            }
        else:
            response_body = {"statusCode": 400, "error": f"Unknown WhatsApp action: {action}"}
    except Exception as e:
        logger.exception(f"Error executing WhatsApp action: {e}")
        response_body = {"statusCode": 500, "error": str(e)}
    
    return format_agent_response(action_group, "", response_body, api_path)


# =============================================================================
# NOTIFICATIONS API HANDLER (SMS & Email)
# =============================================================================
def handle_notifications_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle SMS and Email notifications.
    
    SMS: AWS End User Messaging SMS (pinpoint-sms-voice-v2)
    - DO NOT use sender_id unless explicitly provided with DLT IDs
    Email: Amazon SES
    - From: "WECARE.DIGITAL" <one@wecare.digital>
    """
    logger.info(f"Bedrock Agent Notifications Request: {json.dumps(event, default=str)[:500]}")
    
    import boto3
    
    action_group = event.get("actionGroup", "NotificationsAPI")
    api_path = event.get("apiPath", "/")
    params = extract_params(event)
    
    try:
        # SMS via AWS End User Messaging SMS
        if api_path == "/sms" or event.get("function") == "sendSMS":
            to_number = params.get("to", "")
            message = params.get("message", "")
            # Only use sender_id if explicitly provided in request
            sender_id = params.get("sender_id", "")
            dlt_entity_id = params.get("dlt_entity_id", "")
            dlt_template_id = params.get("dlt_template_id", "")
            
            if not to_number or not message:
                return format_agent_response(action_group, "sendSMS", 
                    {"statusCode": 400, "error": "to and message are required"}, api_path)
            
            if not to_number.startswith("+"):
                to_number = f"+{to_number}"
            
            sms_voice = boto3.client("pinpoint-sms-voice-v2", region_name=CONFIG["region"])
            
            # Build SMS params - keep under 160 chars to avoid extra charges
            sms_params = {
                "DestinationPhoneNumber": to_number,
                "MessageBody": message[:160],
                "MessageType": "TRANSACTIONAL"
            }
            
            # For India (+91) with template_id provided - use DLT with WDBEEP sender
            if to_number.startswith("+91") and dlt_template_id:
                sms_params["OriginationIdentity"] = CONFIG["sms"]["india_sender_id"]
                sms_params["DestinationCountryParameters"] = {
                    "IN_ENTITY_ID": CONFIG["sms"]["india_entity_id"],
                    "IN_TEMPLATE_ID": dlt_template_id
                }
                logger.info(f"India SMS with DLT: sender=WDBEEP, template={dlt_template_id}")
            elif sender_id:
                sms_params["OriginationIdentity"] = sender_id
                logger.info(f"Using sender_id: {sender_id}")
            else:
                # No sender ID - AWS will route automatically
                logger.info("No sender_id/template_id - AWS auto-routing")
            
            logger.info(f"SMS params: {json.dumps(sms_params)}")
            
            response = sms_voice.send_text_message(**sms_params)
            
            # Build response message
            if to_number.startswith("+91") and dlt_template_id:
                msg = f"SMS sent to {to_number} via WDBEEP (DLT template: {dlt_template_id})"
            elif sender_id:
                msg = f"SMS sent to {to_number} via Sender ID {sender_id}"
            else:
                msg = f"SMS sent to {to_number} via AWS automatic routing"
            
            response_body = {
                "statusCode": 200,
                "messageId": response.get("MessageId", ""),
                "provider": "AWS_SMS",
                "destination": to_number,
                "status": "sent",
                "message": msg
            }
            if sender_id:
                response_body["originationIdentity"] = sender_id
            return format_agent_response(action_group, "sendSMS", response_body, api_path)
        
        # Email via Amazon SES
        elif api_path == "/email" or event.get("function") == "sendEmail":
            to_email = params.get("to", CONFIG["email"]["default_recipient"])
            subject = params.get("subject", "")
            body = params.get("body", "")
            html_body = params.get("html_body", "")
            
            if not subject or not body:
                return format_agent_response(action_group, "sendEmail",
                    {"statusCode": 400, "error": "subject and body are required"}, api_path)
            
            ses = boto3.client("ses", region_name=CONFIG["region"])
            
            email_body = {"Text": {"Data": body, "Charset": "UTF-8"}}
            if html_body:
                email_body["Html"] = {"Data": html_body, "Charset": "UTF-8"}
            
            response = ses.send_email(
                Source=CONFIG["email"]["from_simple"],
                Destination={"ToAddresses": [to_email]},
                ReplyToAddresses=[CONFIG["email"]["reply_to"]],
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": email_body
                }
            )
            
            response_body = {
                "statusCode": 200,
                "messageId": response.get("MessageId", ""),
                "provider": "AWS_SES",
                "destination": to_email,
                "from": CONFIG["email"]["from_address"],
                "status": "sent",
                "message": f"Email sent to {to_email}"
            }
            return format_agent_response(action_group, "sendEmail", response_body, api_path)
        
        # Voice - delegate to VoiceAPI
        elif api_path == "/voice" or event.get("function") == "sendVoice":
            return handle_voice_action(event, context)
        
        else:
            return format_agent_response(action_group, "", 
                {"statusCode": 400, "error": f"Unknown action: {api_path}"}, api_path)
    
    except Exception as e:
        logger.exception(f"Error sending notification: {e}")
        return format_agent_response(action_group, "", {"statusCode": 500, "error": str(e)}, api_path)


# =============================================================================
# VOICE API HANDLER (Polly TTS + SMS fallback)
# =============================================================================
def handle_voice_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Voice API requests using Polly TTS.
    
    Since no voice-capable origination identity exists in ap-south-1,
    generates audio via Polly and sends SMS with audio link.
    DO NOT use sender_id unless explicitly provided.
    """
    logger.info(f"Bedrock Agent Voice Request: {json.dumps(event, default=str)[:500]}")
    
    import boto3
    import uuid
    
    action_group = event.get("actionGroup", "VoiceAPI")
    api_path = event.get("apiPath", "/call")
    params = extract_params(event)
    
    try:
        to_number = params.get("to", "")
        message = params.get("message", "")
        voice_id = params.get("voice_id", CONFIG["voice"]["polly_voice"])
        # Only use sender_id if explicitly provided
        sender_id = params.get("sender_id", "")
        
        if not to_number or not message:
            return format_agent_response(action_group, "makeVoiceCall",
                {"statusCode": 400, "error": "to and message are required"}, api_path)
        
        if not to_number.startswith("+"):
            to_number = f"+{to_number}"
        
        polly = boto3.client("polly", region_name=CONFIG["region"])
        s3 = boto3.client("s3", region_name=CONFIG["region"])
        
        # Generate TTS audio with Polly
        polly_response = polly.synthesize_speech(
            Text=message,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine=CONFIG["voice"]["polly_engine"]
        )
        
        # Save to S3
        audio_key = f"voice/{uuid.uuid4()}.mp3"
        s3.put_object(
            Bucket=CONFIG["voice"]["s3_bucket"],
            Key=audio_key,
            Body=polly_response["AudioStream"].read(),
            ContentType="audio/mpeg"
        )
        
        audio_url = f"https://{CONFIG['voice']['s3_bucket']}/{audio_key}"
        
        # For India numbers, send SMS with audio link
        if to_number.startswith("+91"):
            sms_voice = boto3.client("pinpoint-sms-voice-v2", region_name=CONFIG["region"])
            
            sms_text = f"WECARE.DIGITAL: {message[:140]}"  # Keep under 160 chars
            
            # Build SMS params - AWS auto-routing (no DLT for voice fallback)
            sms_params = {
                "DestinationPhoneNumber": to_number,
                "MessageBody": sms_text,
                "MessageType": "TRANSACTIONAL"
            }
            logger.info(f"Voice SMS to {to_number} via AWS auto-routing")
            
            sms_response = sms_voice.send_text_message(**sms_params)
            
            response_body = {
                "statusCode": 200,
                "messageId": sms_response.get("MessageId", ""),
                "audioUrl": audio_url,
                "provider": "AWS_POLLY_SMS",
                "destination": to_number,
                "status": "sent_as_sms",
                "message": f"Voice message generated and SMS sent to {to_number}"
            }
        else:
            response_body = {
                "statusCode": 200,
                "audioUrl": audio_url,
                "provider": "AWS_POLLY",
                "destination": to_number,
                "status": "audio_generated",
                "message": f"Voice audio generated: {audio_url}"
            }
        
        return format_agent_response(action_group, "makeVoiceCall", response_body, api_path)
    
    except Exception as e:
        logger.exception(f"Error making voice call: {e}")
        return format_agent_response(action_group, "makeVoiceCall", 
            {"statusCode": 500, "error": str(e)}, api_path)


# =============================================================================
# LAMBDA HANDLER - MAIN ENTRY POINT
# =============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for Bedrock Agent action group invocations.
    
    Routes to appropriate handler based on actionGroup:
    - PaymentsAPI: Razorpay payment links
    - ShortlinksAPI: Short URL creation
    - WhatsAppAPI: AWS End User Messaging Social
    - NotificationsAPI: SMS (EUM) + Email (SES)
    - VoiceAPI: Polly TTS + SMS fallback
    """
    logger.info(f"Bedrock Agent Event: {json.dumps(event, default=str)[:1000]}")
    
    action_group = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    
    # Normalize OpenAPI-based events
    if api_path:
        request_body = event.get("requestBody", {})
        content = request_body.get("content", {})
        app_json = content.get("application/json", {})
        properties = app_json.get("properties", [])
        
        params = []
        for prop in properties:
            params.append({"name": prop.get("name", ""), "value": prop.get("value", "")})
        
        event["parameters"] = params
        event["function"] = api_path.replace("/", "") or "default"
    
    # Route to appropriate handler
    if action_group == "PaymentsAPI":
        return handle_payments_action(event, context)
    elif action_group == "ShortlinksAPI":
        return handle_shortlinks_action(event, context)
    elif action_group == "WhatsAppAPI":
        return handle_whatsapp_action(event, context)
    elif action_group == "NotificationsAPI":
        return handle_notifications_action(event, context)
    elif action_group == "VoiceAPI":
        return handle_voice_action(event, context)
    else:
        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": action_group,
                "apiPath": api_path or "/",
                "httpMethod": "POST",
                "httpStatusCode": 400,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps({"error": f"Unknown action group: {action_group}"})
                    }
                }
            }
        }
