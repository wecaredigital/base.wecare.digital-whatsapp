# =============================================================================
# Event Parser - Detect and Parse Lambda Events
# =============================================================================
# Detects event source and normalizes into Envelope format.
# Supports: API Gateway, SNS, SQS, Direct Invoke, CLI
# =============================================================================

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from src.runtime.envelope import Envelope, EnvelopeKind

logger = logging.getLogger(__name__)


class EventSource:
    """Event source identifiers."""
    API_GATEWAY = "api_gateway"
    SNS = "sns"
    SQS = "sqs"
    DIRECT = "direct"
    CLI = "cli"
    STEP_FUNCTIONS = "step_functions"
    EVENTBRIDGE = "eventbridge"
    UNKNOWN = "unknown"


def detect_event_source(event: Dict[str, Any]) -> str:
    """
    Detect the source of a Lambda event.
    
    Returns one of: api_gateway, sns, sqs, direct, step_functions, eventbridge, unknown
    """
    if not event:
        return EventSource.UNKNOWN
    
    # API Gateway HTTP API (v2) or REST API (v1)
    if "requestContext" in event:
        if "http" in event.get("requestContext", {}):
            return EventSource.API_GATEWAY  # HTTP API v2
        if "httpMethod" in event.get("requestContext", {}):
            return EventSource.API_GATEWAY  # REST API v1
    
    # Check for body (API Gateway sends body as string)
    if "body" in event and event.get("body"):
        return EventSource.API_GATEWAY
    
    # SQS Records
    if "Records" in event:
        records = event.get("Records", [])
        if records and isinstance(records[0], dict):
            if "eventSource" in records[0]:
                source = records[0].get("eventSource", "")
                if source == "aws:sqs":
                    return EventSource.SQS
                if source == "aws:sns":
                    return EventSource.SNS
            # SNS wrapped in SQS
            if "Sns" in records[0]:
                return EventSource.SNS
    
    # EventBridge
    if "detail-type" in event and "source" in event:
        return EventSource.EVENTBRIDGE
    
    # Step Functions (has specific structure)
    if "taskToken" in event or event.get("source") == "step_functions":
        return EventSource.STEP_FUNCTIONS
    
    # Direct invoke with action
    if "action" in event:
        return EventSource.DIRECT
    
    # CLI (explicit marker)
    if event.get("_source") == "cli":
        return EventSource.CLI
    
    return EventSource.UNKNOWN


def _parse_api_gateway_event(event: Dict[str, Any]) -> Envelope:
    """Parse API Gateway HTTP API or REST API event."""
    request_context = event.get("requestContext", {})
    
    # Extract request ID
    request_id = (
        request_context.get("requestId") or
        event.get("headers", {}).get("x-amzn-trace-id") or
        str(uuid.uuid4())
    )
    
    # Parse body
    body = event.get("body", "")
    payload = {}
    
    if body:
        if isinstance(body, str):
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"rawBody": body}
        elif isinstance(body, dict):
            payload = body
    
    # Handle SNS messages via API Gateway (subscription confirmation, notifications)
    sns_type = payload.get("Type")
    if sns_type == "SubscriptionConfirmation":
        return Envelope(
            kind=EnvelopeKind.WEBHOOK_EVENT,
            request_id=request_id,
            tenant_id="",
            source=EventSource.API_GATEWAY,
            payload={"action": "_sns_subscription_confirmation", **payload},
            raw_event=event,
            metadata={
                "headers": event.get("headers", {}),
                "queryStringParameters": event.get("queryStringParameters", {}),
                "snsType": sns_type,
            },
        )
    elif sns_type == "Notification":
        # Extract actual message from SNS notification
        sns_message = payload.get("Message", "")
        if isinstance(sns_message, str):
            try:
                payload = json.loads(sns_message)
            except json.JSONDecodeError:
                payload = {"rawMessage": sns_message}
    
    # Merge query parameters into payload
    query_params = event.get("queryStringParameters") or {}
    for key, value in query_params.items():
        if key not in payload:
            payload[key] = value
    
    # Extract tenant ID
    tenant_id = (
        payload.get("metaWabaId") or
        payload.get("tenantId") or
        query_params.get("tenantId") or
        ""
    )
    
    return Envelope(
        kind=EnvelopeKind.ACTION_REQUEST,
        request_id=request_id,
        tenant_id=tenant_id,
        source=EventSource.API_GATEWAY,
        payload=payload,
        raw_event=event,
        metadata={
            "headers": event.get("headers", {}),
            "queryStringParameters": query_params,
            "pathParameters": event.get("pathParameters", {}),
            "httpMethod": request_context.get("http", {}).get("method") or request_context.get("httpMethod"),
            "path": request_context.get("http", {}).get("path") or event.get("path"),
        },
    )


def _parse_sns_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a single SNS record."""
    sns_data = record.get("Sns", {})
    message = sns_data.get("Message", "")
    
    # Parse message JSON
    if isinstance(message, str):
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return {"rawMessage": message}
    return message if isinstance(message, dict) else {}


def _parse_sqs_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a single SQS record."""
    body = record.get("body", "")
    
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
            # Check if this is an SNS message wrapped in SQS
            if parsed.get("Type") == "Notification":
                message = parsed.get("Message", "")
                if isinstance(message, str):
                    try:
                        return json.loads(message)
                    except json.JSONDecodeError:
                        return {"rawMessage": message}
                return message if isinstance(message, dict) else {}
            return parsed
        except json.JSONDecodeError:
            return {"rawBody": body}
    return body if isinstance(body, dict) else {}


def _parse_sns_event(event: Dict[str, Any]) -> List[Envelope]:
    """Parse SNS event with multiple records."""
    envelopes = []
    records = event.get("Records", [])
    
    for i, record in enumerate(records):
        sns_data = record.get("Sns", {})
        message_id = sns_data.get("MessageId", str(uuid.uuid4()))
        timestamp = sns_data.get("Timestamp", "")
        topic_arn = sns_data.get("TopicArn", "")
        
        payload = _parse_sns_record(record)
        
        # Extract WhatsApp webhook entry for tenant ID
        webhook_entry = payload.get("whatsAppWebhookEntry", {})
        if isinstance(webhook_entry, str):
            try:
                webhook_entry = json.loads(webhook_entry)
            except json.JSONDecodeError:
                webhook_entry = {}
        
        tenant_id = str(webhook_entry.get("id", "")) or payload.get("metaWabaId", "")
        
        envelope = Envelope(
            kind=EnvelopeKind.INBOUND_EVENT,
            request_id=message_id,
            tenant_id=tenant_id,
            source=EventSource.SNS,
            payload=payload,
            raw_event=record,
            metadata={
                "snsMessageId": message_id,
                "snsTimestamp": timestamp,
                "snsTopicArn": topic_arn,
                "recordIndex": i,
            },
        )
        envelopes.append(envelope)
    
    return envelopes


def _parse_sqs_event(event: Dict[str, Any]) -> List[Envelope]:
    """Parse SQS event with multiple records."""
    envelopes = []
    records = event.get("Records", [])
    
    for i, record in enumerate(records):
        message_id = record.get("messageId", str(uuid.uuid4()))
        receipt_handle = record.get("receiptHandle", "")
        event_source_arn = record.get("eventSourceARN", "")
        
        payload = _parse_sqs_record(record)
        
        # Extract WhatsApp webhook entry for tenant ID
        webhook_entry = payload.get("whatsAppWebhookEntry", {})
        if isinstance(webhook_entry, str):
            try:
                webhook_entry = json.loads(webhook_entry)
            except json.JSONDecodeError:
                webhook_entry = {}
        
        tenant_id = str(webhook_entry.get("id", "")) or payload.get("metaWabaId", "")
        
        envelope = Envelope(
            kind=EnvelopeKind.INBOUND_EVENT,
            request_id=message_id,
            tenant_id=tenant_id,
            source=EventSource.SQS,
            payload=payload,
            raw_event=record,
            metadata={
                "sqsMessageId": message_id,
                "sqsReceiptHandle": receipt_handle,
                "sqsEventSourceArn": event_source_arn,
                "recordIndex": i,
            },
        )
        envelopes.append(envelope)
    
    return envelopes


def _parse_eventbridge_event(event: Dict[str, Any]) -> Envelope:
    """Parse EventBridge event."""
    detail_type = event.get("detail-type", "")
    source = event.get("source", "")
    detail = event.get("detail", {})
    event_id = event.get("id", str(uuid.uuid4()))
    
    # Map detail-type to action
    action = detail.get("action", "")
    if not action:
        # Convert detail-type to action (e.g., "whatsapp.inbound.received" -> "process_inbound")
        if "inbound" in detail_type:
            action = "process_inbound_event"
        elif "outbound" in detail_type:
            action = "process_outbound_event"
        else:
            action = detail_type.replace(".", "_")
    
    payload = {"action": action, **detail}
    
    return Envelope(
        kind=EnvelopeKind.INTERNAL_JOB,
        request_id=event_id,
        tenant_id=detail.get("tenantId", ""),
        source=EventSource.EVENTBRIDGE,
        payload=payload,
        raw_event=event,
        metadata={
            "detailType": detail_type,
            "eventBridgeSource": source,
            "account": event.get("account", ""),
            "region": event.get("region", ""),
            "time": event.get("time", ""),
        },
    )


def _parse_step_functions_event(event: Dict[str, Any]) -> Envelope:
    """Parse Step Functions event."""
    task_token = event.get("taskToken", "")
    input_data = event.get("input", event)
    
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError:
            input_data = {"rawInput": input_data}
    
    return Envelope(
        kind=EnvelopeKind.INTERNAL_JOB,
        request_id=str(uuid.uuid4()),
        tenant_id=input_data.get("tenantId", ""),
        source=EventSource.STEP_FUNCTIONS,
        payload=input_data,
        raw_event=event,
        metadata={
            "taskToken": task_token,
        },
    )


def _parse_direct_event(event: Dict[str, Any]) -> Envelope:
    """Parse direct Lambda invoke event."""
    request_id = event.get("requestId", str(uuid.uuid4()))
    
    return Envelope(
        kind=EnvelopeKind.ACTION_REQUEST,
        request_id=request_id,
        tenant_id=event.get("metaWabaId", "") or event.get("tenantId", ""),
        source=EventSource.DIRECT,
        payload=event,
        raw_event=event,
    )


def parse_event(event: Dict[str, Any]) -> Tuple[List[Envelope], str]:
    """
    Parse Lambda event and return list of Envelopes.
    
    Returns:
        Tuple of (list of Envelopes, detected source)
        
    Note: Most sources return a single envelope, but SNS/SQS can have multiple records.
    """
    source = detect_event_source(event)
    logger.info(f"Detected event source: {source}")
    
    if source == EventSource.API_GATEWAY:
        return [_parse_api_gateway_event(event)], source
    
    elif source == EventSource.SNS:
        return _parse_sns_event(event), source
    
    elif source == EventSource.SQS:
        return _parse_sqs_event(event), source
    
    elif source == EventSource.EVENTBRIDGE:
        return [_parse_eventbridge_event(event)], source
    
    elif source == EventSource.STEP_FUNCTIONS:
        return [_parse_step_functions_event(event)], source
    
    elif source in (EventSource.DIRECT, EventSource.CLI):
        return [_parse_direct_event(event)], source
    
    else:
        # Unknown source - try to parse as direct invoke
        logger.warning(f"Unknown event source, treating as direct invoke")
        return [_parse_direct_event(event)], EventSource.UNKNOWN
