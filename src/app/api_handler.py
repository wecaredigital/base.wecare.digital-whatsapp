# =============================================================================
# API Gateway Handler
# =============================================================================
# Entry point for API Gateway HTTP API requests.
# Parses request, dispatches to handler, formats response.
# =============================================================================

import json
import logging
from typing import Any, Dict
from src.runtime.envelope import Envelope
from src.runtime.parse_event import parse_event, EventSource
from src.runtime.dispatch import dispatch
from src.runtime.deps import create_deps

logger = logging.getLogger(__name__)


def api_response(data: Dict[str, Any], status_code: int = None) -> Dict[str, Any]:
    """Format response for API Gateway HTTP API."""
    code = status_code or data.get("statusCode", 200)
    
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(data, ensure_ascii=False, default=str),
    }


def api_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway entry point.
    
    Handles:
    - HTTP API (v2) requests
    - REST API (v1) requests
    - SNS subscription confirmations via HTTPS
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response format
    """
    logger.info(f"API_HANDLER event keys: {list(event.keys())}")
    
    # Parse event into envelope(s)
    envelopes, source = parse_event(event)
    
    if not envelopes:
        return api_response({
            "statusCode": 400,
            "error": "Could not parse request",
        }, 400)
    
    # API Gateway should produce single envelope
    envelope = envelopes[0]
    
    # Handle SNS subscription confirmation
    if envelope.action == "_sns_subscription_confirmation":
        return _handle_sns_subscription(envelope)
    
    # Create deps and dispatch
    deps = create_deps()
    result = dispatch(envelope, deps)
    
    return api_response(result)


def _handle_sns_subscription(envelope: Envelope) -> Dict[str, Any]:
    """Handle SNS subscription confirmation."""
    subscribe_url = envelope.payload.get("SubscribeURL")
    
    if not subscribe_url:
        return api_response({
            "statusCode": 400,
            "error": "Missing SubscribeURL",
        }, 400)
    
    logger.info(f"Confirming SNS subscription: {subscribe_url}")
    
    try:
        import urllib.request
        urllib.request.urlopen(subscribe_url, timeout=10)
        return api_response({
            "statusCode": 200,
            "message": "Subscription confirmed",
        })
    except Exception as e:
        logger.exception(f"Failed to confirm SNS subscription: {e}")
        return api_response({
            "statusCode": 500,
            "error": str(e),
        }, 500)
