# =============================================================================
# Bedrock Agent Core - API Lambda Entry Point
# =============================================================================
# Lambda handler for API Gateway HTTP API.
# Routes requests to appropriate handlers.
# =============================================================================

import json
import logging
import os
from typing import Any, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import handlers
from src.bedrock.api_handlers import (
    handle_chat,
    handle_get_session,
    handle_get_history,
    handle_delete_session,
    handle_list_sessions,
    handle_options,
    handle_health,
    handle_invoke_agent,
    handle_query_kb,
    handle_upload_file,
    api_response,
    get_origin,
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway HTTP API Lambda handler.
    
    Routes:
    - POST   /api/chat                    -> handle_chat
    - POST   /api/invoke-agent            -> handle_invoke_agent
    - POST   /api/query-kb                -> handle_query_kb
    - POST   /api/upload                  -> handle_upload_file
    - GET    /api/sessions                -> handle_list_sessions
    - GET    /api/sessions/{sessionId}    -> handle_get_session
    - GET    /api/sessions/{sessionId}/history -> handle_get_history
    - DELETE /api/sessions/{sessionId}    -> handle_delete_session
    - GET    /api/health                  -> handle_health
    - OPTIONS /*                          -> handle_options (CORS)
    """
    logger.info(f"Event: {json.dumps(event, default=str)[:500]}")
    
    origin = get_origin(event)
    
    # Get HTTP method and path
    request_context = event.get("requestContext", {})
    http = request_context.get("http", {})
    method = http.get("method", event.get("httpMethod", "GET")).upper()
    path = http.get("path", event.get("path", "/"))
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return handle_options(event, context)
    
    # Route based on path and method
    try:
        # Health check
        if path == "/api/health" and method == "GET":
            return handle_health(event, context)
        
        # Chat endpoint
        if path == "/api/chat" and method == "POST":
            return handle_chat(event, context)
        
        # Invoke Agent endpoint
        if path == "/api/invoke-agent" and method == "POST":
            return handle_invoke_agent(event, context)
        
        # Query KB endpoint
        if path == "/api/query-kb" and method == "POST":
            return handle_query_kb(event, context)
        
        # Upload file endpoint
        if path == "/api/upload" and method == "POST":
            return handle_upload_file(event, context)
        
        # Sessions list
        if path == "/api/sessions" and method == "GET":
            return handle_list_sessions(event, context)
        
        # Session operations
        if path.startswith("/api/sessions/"):
            parts = path.split("/")
            
            # /api/sessions/{sessionId}
            if len(parts) == 4:
                session_id = parts[3]
                event["pathParameters"] = {"sessionId": session_id}
                
                if method == "GET":
                    return handle_get_session(event, context)
                elif method == "DELETE":
                    return handle_delete_session(event, context)
            
            # /api/sessions/{sessionId}/history
            if len(parts) == 5 and parts[4] == "history":
                session_id = parts[3]
                event["pathParameters"] = {"sessionId": session_id}
                
                if method == "GET":
                    return handle_get_history(event, context)
        
        # Not found
        return api_response({
            "success": False,
            "error": f"Not found: {method} {path}",
        }, 404, origin)
        
    except Exception as e:
        logger.exception(f"Handler error: {e}")
        return api_response({
            "success": False,
            "error": str(e),
        }, 500, origin)


# =============================================================================
# DIRECT INVOCATION SUPPORT
# =============================================================================

def invoke_direct(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Direct invocation for internal use (e.g., from other Lambdas).
    
    Actions:
    - chat: Send message
    - get_session: Get session details
    - get_history: Get chat history
    - delete_session: Delete session
    - list_sessions: List sessions
    """
    from src.bedrock.api_handlers import AGENT_CORE_API_HANDLERS
    
    handler = AGENT_CORE_API_HANDLERS.get(f"agent_{action}")
    
    if not handler:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
        }
    
    # Create mock event
    event = {
        "body": json.dumps(payload),
        "headers": {},
        "pathParameters": payload.get("pathParameters", {}),
        "queryStringParameters": payload.get("queryStringParameters", {}),
    }
    
    result = handler(event, None)
    
    # Parse response body
    body = result.get("body", "{}")
    if isinstance(body, str):
        return json.loads(body)
    return body
