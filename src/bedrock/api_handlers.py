# =============================================================================
# Bedrock Agent Core - API Handlers for Amplify/Frontend
# =============================================================================
# Lambda handlers for frontend API integration.
# Designed for API Gateway HTTP API with CORS support.
# Supports:
# - Chat with AI (direct model or Bedrock Agent)
# - Knowledge Base queries
# - Session management
# - S3 file operations
# =============================================================================

import json
import logging
import os
import base64
from typing import Any, Dict

from src.bedrock.agent_core import get_agent_core, AgentCoreResponse, KBQueryResult

logger = logging.getLogger(__name__)

# =============================================================================
# CORS CONFIGURATION
# =============================================================================

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "*"
).split(",")

def get_cors_headers(origin: str = None) -> Dict[str, str]:
    """Get CORS headers for response."""
    # Allow all origins with *
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Tenant-Id,X-User-Id",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Max-Age": "86400",
    }


def api_response(
    data: Dict[str, Any],
    status_code: int = 200,
    origin: str = None,
) -> Dict[str, Any]:
    """Format API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(origin),
        "body": json.dumps(data, ensure_ascii=False, default=str),
    }


def parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse request body from API Gateway event."""
    body = event.get("body", "{}")
    
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    
    return body or {}


def get_origin(event: Dict[str, Any]) -> str:
    """Get origin from request headers."""
    headers = event.get("headers", {})
    return headers.get("origin") or headers.get("Origin", "")


# =============================================================================
# API HANDLERS
# =============================================================================

def handle_chat(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /api/chat
    
    Send a message and get AI response.
    
    Request Body:
    {
        "message": "What services do you offer?",
        "sessionId": "optional-existing-session-id",
        "tenantId": "1347766229904230",
        "userId": "user@example.com",
        "metadata": {}
    }
    
    Response:
    {
        "success": true,
        "sessionId": "sess-abc123",
        "messageId": "msg-xyz789",
        "response": "WECARE.DIGITAL offers...",
        "intent": "service_inquiry",
        "suggestedActions": ["View Services", "Contact Us"]
    }
    """
    origin = get_origin(event)
    body = parse_body(event)
    
    # Validate required fields
    message = body.get("message", "").strip()
    if not message:
        return api_response({
            "success": False,
            "error": "message is required",
        }, 400, origin)
    
    tenant_id = body.get("tenantId") or event.get("headers", {}).get("x-tenant-id", "")
    user_id = body.get("userId") or event.get("headers", {}).get("x-user-id", "anonymous")
    session_id = body.get("sessionId")
    metadata = body.get("metadata", {})
    
    if not tenant_id:
        return api_response({
            "success": False,
            "error": "tenantId is required (body or X-Tenant-Id header)",
        }, 400, origin)
    
    # Get agent core and process
    agent = get_agent_core()
    result = agent.chat(
        message=message,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
    )
    
    status = 200 if result.success else 500
    return api_response(result.to_dict(), status, origin)


def handle_get_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /api/sessions/{sessionId}
    
    Get session details and history.
    
    Response:
    {
        "success": true,
        "session": {
            "sessionId": "sess-abc123",
            "tenantId": "...",
            "userId": "...",
            "createdAt": "...",
            "updatedAt": "...",
            "messageCount": 10
        },
        "history": [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "..."}
        ]
    }
    """
    origin = get_origin(event)
    
    # Get session ID from path
    path_params = event.get("pathParameters", {}) or {}
    session_id = path_params.get("sessionId", "")
    
    if not session_id:
        return api_response({
            "success": False,
            "error": "sessionId is required",
        }, 400, origin)
    
    agent = get_agent_core()
    session = agent.get_session(session_id)
    
    if not session:
        return api_response({
            "success": False,
            "error": f"Session not found: {session_id}",
        }, 404, origin)
    
    history = agent.get_history(session_id, limit=50)
    
    return api_response({
        "success": True,
        "session": {
            "sessionId": session.session_id,
            "tenantId": session.tenant_id,
            "userId": session.user_id,
            "createdAt": session.created_at,
            "updatedAt": session.updated_at,
            "messageCount": len(session.messages),
        },
        "history": history,
    }, 200, origin)


def handle_get_history(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /api/sessions/{sessionId}/history
    
    Get chat history for a session.
    
    Query Parameters:
    - limit: Max messages to return (default 20)
    
    Response:
    {
        "success": true,
        "sessionId": "sess-abc123",
        "history": [...]
    }
    """
    origin = get_origin(event)
    
    path_params = event.get("pathParameters", {}) or {}
    session_id = path_params.get("sessionId", "")
    
    query_params = event.get("queryStringParameters", {}) or {}
    limit = int(query_params.get("limit", "20"))
    
    if not session_id:
        return api_response({
            "success": False,
            "error": "sessionId is required",
        }, 400, origin)
    
    agent = get_agent_core()
    history = agent.get_history(session_id, limit=limit)
    
    return api_response({
        "success": True,
        "sessionId": session_id,
        "history": history,
    }, 200, origin)


def handle_delete_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    DELETE /api/sessions/{sessionId}
    
    Delete/clear a session.
    
    Response:
    {
        "success": true,
        "message": "Session deleted"
    }
    """
    origin = get_origin(event)
    
    path_params = event.get("pathParameters", {}) or {}
    session_id = path_params.get("sessionId", "")
    
    if not session_id:
        return api_response({
            "success": False,
            "error": "sessionId is required",
        }, 400, origin)
    
    agent = get_agent_core()
    success = agent.clear_session(session_id)
    
    if success:
        return api_response({
            "success": True,
            "message": "Session deleted",
        }, 200, origin)
    
    return api_response({
        "success": False,
        "error": "Failed to delete session",
    }, 500, origin)


def handle_list_sessions(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /api/sessions
    
    List sessions for a tenant/user.
    
    Query Parameters:
    - tenantId: Required
    - userId: Optional (filter by user)
    - limit: Max sessions (default 10)
    
    Response:
    {
        "success": true,
        "sessions": [
            {"sessionId": "...", "userId": "...", "createdAt": "...", "messageCount": 5}
        ]
    }
    """
    origin = get_origin(event)
    
    query_params = event.get("queryStringParameters", {}) or {}
    headers = event.get("headers", {}) or {}
    
    tenant_id = query_params.get("tenantId") or headers.get("x-tenant-id", "")
    user_id = query_params.get("userId") or headers.get("x-user-id")
    limit = int(query_params.get("limit", "10"))
    
    if not tenant_id:
        return api_response({
            "success": False,
            "error": "tenantId is required",
        }, 400, origin)
    
    agent = get_agent_core()
    sessions = agent.list_sessions(tenant_id, user_id, limit)
    
    return api_response({
        "success": True,
        "sessions": sessions,
    }, 200, origin)


def handle_options(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    OPTIONS /api/*
    
    Handle CORS preflight requests.
    """
    origin = get_origin(event)
    return api_response({}, 200, origin)


def handle_health(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /api/health
    
    Health check endpoint.
    """
    origin = get_origin(event)
    
    return api_response({
        "success": True,
        "status": "healthy",
        "service": "bedrock-agent-core",
        "region": os.environ.get("BEDROCK_REGION", "ap-south-1"),
        "agent_id": os.environ.get("BEDROCK_AGENT_ID", ""),
        "kb_id": os.environ.get("BEDROCK_KB_ID", ""),
    }, 200, origin)


def handle_invoke_agent(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /api/invoke-agent
    
    Directly invoke Bedrock Agent.
    
    Request Body:
    {
        "inputText": "What services do you offer?",
        "sessionId": "sess-abc123",
        "tenantId": "1347766229904230",
        "enableTrace": false
    }
    
    Response:
    {
        "success": true,
        "sessionId": "sess-abc123",
        "response": "WECARE.DIGITAL offers...",
        "citations": [...]
    }
    """
    origin = get_origin(event)
    body = parse_body(event)
    
    input_text = body.get("inputText", "").strip()
    if not input_text:
        return api_response({
            "success": False,
            "error": "inputText is required",
        }, 400, origin)
    
    session_id = body.get("sessionId", f"sess-{os.urandom(8).hex()}")
    tenant_id = body.get("tenantId") or event.get("headers", {}).get("x-tenant-id", "")
    enable_trace = body.get("enableTrace", False)
    
    agent = get_agent_core()
    result = agent.invoke_agent(
        input_text=input_text,
        session_id=session_id,
        tenant_id=tenant_id,
        enable_trace=enable_trace,
    )
    
    status = 200 if result.success else 500
    return api_response(result.to_dict(), status, origin)


def handle_query_kb(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /api/query-kb
    
    Query the Bedrock Knowledge Base.
    
    Request Body:
    {
        "query": "What is BNB CLUB?",
        "maxResults": 5,
        "generateResponse": true
    }
    
    Response:
    {
        "success": true,
        "query": "What is BNB CLUB?",
        "generatedResponse": "BNB CLUB is...",
        "citations": [...],
        "results": [...]
    }
    """
    origin = get_origin(event)
    body = parse_body(event)
    
    query = body.get("query", "").strip()
    if not query:
        return api_response({
            "success": False,
            "error": "query is required",
        }, 400, origin)
    
    max_results = int(body.get("maxResults", 5))
    generate_response = body.get("generateResponse", True)
    
    agent = get_agent_core()
    result = agent.query_knowledge_base(
        query=query,
        max_results=max_results,
        generate_response=generate_response,
    )
    
    status = 200 if result.success else 500
    return api_response(result.to_dict(), status, origin)


def handle_upload_file(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /api/upload
    
    Upload a file to S3.
    
    Request Body:
    {
        "filename": "document.pdf",
        "content": "base64-encoded-content",
        "contentType": "application/pdf",
        "tenantId": "1347766229904230"
    }
    
    Response:
    {
        "success": true,
        "s3Key": "agent-core/tenant/...",
        "presignedUrl": "https://..."
    }
    """
    origin = get_origin(event)
    body = parse_body(event)
    
    filename = body.get("filename", "")
    content_b64 = body.get("content", "")
    content_type = body.get("contentType", "application/octet-stream")
    tenant_id = body.get("tenantId") or event.get("headers", {}).get("x-tenant-id", "default")
    
    if not filename or not content_b64:
        return api_response({
            "success": False,
            "error": "filename and content are required",
        }, 400, origin)
    
    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        return api_response({
            "success": False,
            "error": f"Invalid base64 content: {str(e)}",
        }, 400, origin)
    
    agent = get_agent_core()
    result = agent.upload_to_s3(
        content=content,
        filename=filename,
        tenant_id=tenant_id,
        content_type=content_type,
    )
    
    status = 200 if result.get("success") else 500
    return api_response(result, status, origin)


# =============================================================================
# HANDLER MAPPING
# =============================================================================

AGENT_CORE_API_HANDLERS = {
    "agent_chat": handle_chat,
    "agent_get_session": handle_get_session,
    "agent_get_history": handle_get_history,
    "agent_delete_session": handle_delete_session,
    "agent_list_sessions": handle_list_sessions,
    "agent_options": handle_options,
    "agent_health": handle_health,
    "agent_invoke_agent": handle_invoke_agent,
    "agent_query_kb": handle_query_kb,
    "agent_upload_file": handle_upload_file,
}
