# =============================================================================
# EVENT PARSER - Detect and normalize all Lambda event types
# =============================================================================
# Detects:
# - API Gateway HTTP API events
# - SNS Records[] (AWS EUM event destination)
# - Direct Lambda invoke events
# - CLI invocations
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from src.runtime.envelope import Envelope, EnvelopeKind

logger = logging.getLogger(__name__)


def parse_event(event: Dict[str, Any], context: Any = None) -> Envelope:
    """
    Parse a Lambda event and return a normalized Envelope.
    
    Detects the event source and normalizes it into a common format
    that handlers can process uniformly.
    
    Args:
        event: The raw Lambda event
        context: The Lambda context (optional)
        
    Returns:
        Envelope with normalized payload
    """
    # Extract request ID from context if available
    request_id = getattr(context, 'aws_request_id', None) if context else None
    
    # Check for API Gateway HTTP API event
    if _is_api_gateway_event(event):
        return _parse_api_gateway_event(event, request_id)
    
    # Check for SNS Records (AWS EUM event destination)
    if _is_sns_event(event):
        return _parse_sns_event(event, request_id)
    
    # Check for direct invoke with action
    if "action" in event:
        return _parse_direct_invoke(event, request_id)
    
    # Check for internal job (Step Functions, scheduled)
    if "jobType" in event or "detail-type" in event:
        return _parse_internal_job(event, request_id)
    
    # Unknown event type - treat as direct invoke
    logger.warning(f"Unknown event type, treating as direct invoke")
    return Envelope(
        kind=EnvelopeKind.UNKNOWN,
        request_id=request_id or "",
        source="unknown",
        payload=event,
        raw_event=event,
    )


def _is_api_gateway_event(event: Dict[str, Any]) -> bool:
    """Check if event is from API Gateway."""
    return "requestContext" in event or ("body" in event and "httpMethod" in event)


def _is_sns_event(event: Dict[str, Any]) -> bool:
    """Check if event contains SNS Records."""
    records = event.get("Records", [])
    if not records:
        return False
    return any(r.get("EventSource") == "aws:sns" or "Sns" in r for r in records)


def _parse_api_gateway_event(event: Dict[str, Any], request_id: str = None) -> Envelope:
    """Parse API Gateway HTTP API event."""
    # Extract body
    body = {}
    body_str = event.get("body", "")
    
    if body_str:
        if isinstance(body_str, str):
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                body = {"raw_body": body_str}
        elif isinstance(body_str, dict):
            body = body_str
    
    # Handle SNS messages sent via HTTPS endpoint
    sns_type = body.get("Type")
    if sns_type == "SubscriptionConfirmation":
        return Envelope.action_request(
            action="_sns_subscription_confirmation",
            payload=body,
            source="api_gateway_sns",
            request_id=request_id,
            raw_event=event,
            metadata={"subscribe_url": body.get("SubscribeURL")},
        )
    elif sns_type == "Notification":
        # Extract the actual message from SNS notification
        sns_message = body.get("Message", "")
        if isinstance(sns_message, str):
            try:
                inner_payload = json.loads(sns_message)
                return _parse_sns_notification_payload(inner_payload, request_id, event)
            except json.JSONDecodeError:
                pass
    
    # Regular API Gateway action request
    action = body.get("action", "")
    
    # Merge query params and path params into payload
    query_params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    
    payload = {**body, **query_params, **path_params}
    
    # Extract metadata
    metadata = {
        "http_method": event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method"),
        "path": event.get("path") or event.get("requestContext", {}).get("http", {}).get("path"),
        "headers": event.get("headers", {}),
        "request_context": event.get("requestContext", {}),
    }
    
    return Envelope.action_request(
        action=action,
        payload=payload,
        source="api_gateway",
        request_id=request_id or event.get("requestContext", {}).get("requestId"),
        raw_event=event,
        metadata=metadata,
    )


def _parse_sns_event(event: Dict[str, Any], request_id: str = None) -> Envelope:
    """Parse SNS Records event (AWS EUM event destination)."""
    records = event.get("Records", [])
    
    # Collect all inbound events from SNS records
    inbound_events = []
    tenant_id = ""
    
    for record in records:
        sns_data = record.get("Sns", {})
        message_str = sns_data.get("Message", "")
        
        # Parse the SNS message
        try:
            message = json.loads(message_str) if isinstance(message_str, str) else message_str
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse SNS message: {message_str[:100]}")
            continue
        
        # Extract WhatsApp webhook entry (AWS EUM format)
        webhook_entry = message.get("whatsAppWebhookEntry", {})
        if isinstance(webhook_entry, str):
            try:
                webhook_entry = json.loads(webhook_entry)
            except json.JSONDecodeError:
                webhook_entry = {}
        
        # Extract tenant ID (WABA Meta ID)
        entry_waba_id = str(webhook_entry.get("id", ""))
        if entry_waba_id and not tenant_id:
            tenant_id = entry_waba_id
        
        inbound_events.append({
            "sns_message_id": sns_data.get("MessageId"),
            "sns_timestamp": sns_data.get("Timestamp"),
            "sns_topic_arn": sns_data.get("TopicArn"),
            "message": message,
            "webhook_entry": webhook_entry,
            "waba_meta_id": entry_waba_id,
        })
    
    # Build metadata
    metadata = {
        "record_count": len(records),
        "event_count": len(inbound_events),
    }
    
    return Envelope.inbound_event(
        payload={"events": inbound_events, "records": records},
        tenant_id=tenant_id,
        request_id=request_id,
        raw_event=event,
        metadata=metadata,
    )


def _parse_sns_notification_payload(
    payload: Dict[str, Any], 
    request_id: str = None,
    raw_event: Dict[str, Any] = None
) -> Envelope:
    """Parse SNS notification payload received via HTTPS."""
    # Extract WhatsApp webhook entry
    webhook_entry = payload.get("whatsAppWebhookEntry", {})
    if isinstance(webhook_entry, str):
        try:
            webhook_entry = json.loads(webhook_entry)
        except json.JSONDecodeError:
            webhook_entry = {}
    
    tenant_id = str(webhook_entry.get("id", ""))
    
    return Envelope.inbound_event(
        payload={
            "events": [{
                "message": payload,
                "webhook_entry": webhook_entry,
                "waba_meta_id": tenant_id,
            }],
        },
        tenant_id=tenant_id,
        request_id=request_id,
        raw_event=raw_event or {},
    )


def _parse_direct_invoke(event: Dict[str, Any], request_id: str = None) -> Envelope:
    """Parse direct Lambda invoke event."""
    action = event.get("action", "")
    tenant_id = event.get("metaWabaId", "")
    
    return Envelope.action_request(
        action=action,
        payload=event,
        source="direct",
        tenant_id=tenant_id,
        request_id=request_id,
        raw_event=event,
    )


def _parse_internal_job(event: Dict[str, Any], request_id: str = None) -> Envelope:
    """Parse internal job event (Step Functions, EventBridge)."""
    # Step Functions task
    if "jobType" in event:
        return Envelope.internal_job(
            job_type=event.get("jobType"),
            payload=event,
            request_id=request_id,
            metadata={"source": "step_functions"},
        )
    
    # EventBridge scheduled event
    if "detail-type" in event:
        return Envelope.internal_job(
            job_type=event.get("detail-type"),
            payload=event.get("detail", {}),
            request_id=request_id,
            metadata={
                "source": "eventbridge",
                "detail_type": event.get("detail-type"),
                "resources": event.get("resources", []),
            },
        )
    
    return Envelope.internal_job(
        job_type="unknown",
        payload=event,
        request_id=request_id,
    )


def parse_cli_args(args: List[str]) -> Envelope:
    """
    Parse CLI arguments into an Envelope.
    
    Usage:
        python -m tools.cli send_text --metaWabaId=123 --to=+1234567890 --text="Hello"
        
    Or with JSON:
        python -m tools.cli '{"action": "send_text", "metaWabaId": "123", ...}'
    """
    if not args:
        return Envelope.action_request(
            action="help",
            payload={},
            source="cli",
        )
    
    # Check if first arg is JSON
    first_arg = args[0]
    if first_arg.startswith("{"):
        try:
            payload = json.loads(first_arg)
            return Envelope.action_request(
                action=payload.get("action", ""),
                payload=payload,
                source="cli",
            )
        except json.JSONDecodeError:
            pass
    
    # Parse as action + flags
    action = first_arg
    payload = {"action": action}
    
    for arg in args[1:]:
        if arg.startswith("--"):
            key_value = arg[2:]
            if "=" in key_value:
                key, value = key_value.split("=", 1)
                # Try to parse as JSON for complex values
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                payload[key] = value
            else:
                payload[key_value] = True
    
    return Envelope.action_request(
        action=action,
        payload=payload,
        source="cli",
    )
