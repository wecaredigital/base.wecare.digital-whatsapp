# =============================================================================
# Bedrock Agent Core Client - Shareable SDK for Other Repos
# =============================================================================
# Use this client to connect to the Bedrock Agent Core API from any repo.
#
# Installation:
#   pip install requests
#
# Usage:
#   from bedrock_client import AgentCoreClient
#   
#   client = AgentCoreClient(
#       api_endpoint="https://xxx.execute-api.ap-south-1.amazonaws.com",
#       tenant_id="1347766229904230"
#   )
#   
#   response = client.chat("What services do you offer?")
#   print(response["response"])
# =============================================================================

import json
import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AgentCoreConfig:
    """Configuration for Agent Core Client."""
    api_endpoint: str
    tenant_id: str
    user_id: str = "anonymous"
    timeout: int = 60


class AgentCoreClient:
    """
    Client for Bedrock Agent Core API.
    
    Use this to connect to the Agent Core from any application:
    - Amplify/React apps
    - Python backends
    - Other Lambda functions
    - CLI tools
    """
    
    def __init__(
        self,
        api_endpoint: str,
        tenant_id: str,
        user_id: str = "anonymous",
        timeout: int = 60,
    ):
        """
        Initialize Agent Core Client.
        
        Args:
            api_endpoint: Base URL of the Agent Core API
            tenant_id: Your tenant/WABA ID
            user_id: User identifier (email, phone, etc.)
            timeout: Request timeout in seconds
        """
        self.config = AgentCoreConfig(
            api_endpoint=api_endpoint.rstrip("/"),
            tenant_id=tenant_id,
            user_id=user_id,
            timeout=timeout,
        )
        self._session_id: Optional[str] = None

    
    @property
    def session_id(self) -> Optional[str]:
        """Current session ID."""
        return self._session_id
    
    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Content-Type": "application/json",
            "X-Tenant-Id": self.config.tenant_id,
            "X-User-Id": self.config.user_id,
        }
    
    def _request(
        self,
        method: str,
        path: str,
        data: Dict[str, Any] = None,
        params: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = f"{self.config.api_endpoint}{path}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=data,
                params=params,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # CHAT API
    # =========================================================================
    
    def chat(
        self,
        message: str,
        session_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat message and get AI response.
        
        Args:
            message: User message
            session_id: Existing session ID (uses current if None)
            metadata: Additional context
            
        Returns:
            Response dict with: success, sessionId, response, intent, suggestedActions
        """
        data = {
            "message": message,
            "tenantId": self.config.tenant_id,
            "userId": self.config.user_id,
            "sessionId": session_id or self._session_id,
            "metadata": metadata or {},
        }
        
        result = self._request("POST", "/api/chat", data)
        
        # Store session ID for continuity
        if result.get("success") and result.get("sessionId"):
            self._session_id = result["sessionId"]
        
        return result
    
    def invoke_agent(
        self,
        input_text: str,
        session_id: str = None,
        enable_trace: bool = False,
    ) -> Dict[str, Any]:
        """
        Directly invoke Bedrock Agent.
        
        Args:
            input_text: User input
            session_id: Session ID for conversation continuity
            enable_trace: Enable agent trace for debugging
            
        Returns:
            Response dict with: success, sessionId, response, citations
        """
        data = {
            "inputText": input_text,
            "sessionId": session_id or self._session_id or f"sess-{id(self)}",
            "tenantId": self.config.tenant_id,
            "enableTrace": enable_trace,
        }
        
        result = self._request("POST", "/api/invoke-agent", data)
        
        if result.get("success") and result.get("sessionId"):
            self._session_id = result["sessionId"]
        
        return result
    
    def query_kb(
        self,
        query: str,
        max_results: int = 5,
        generate_response: bool = True,
    ) -> Dict[str, Any]:
        """
        Query the Knowledge Base.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            generate_response: If True, generate a response using retrieved context
            
        Returns:
            Response dict with: success, query, generatedResponse, citations, results
        """
        data = {
            "query": query,
            "maxResults": max_results,
            "generateResponse": generate_response,
        }
        
        return self._request("POST", "/api/query-kb", data)

    
    # =========================================================================
    # SESSION API
    # =========================================================================
    
    def get_session(self, session_id: str = None) -> Dict[str, Any]:
        """
        Get session details and history.
        
        Args:
            session_id: Session ID (uses current if None)
            
        Returns:
            Response dict with: success, session, history
        """
        sid = session_id or self._session_id
        if not sid:
            return {"success": False, "error": "No session ID"}
        
        return self._request("GET", f"/api/sessions/{sid}")
    
    def get_history(
        self,
        session_id: str = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get chat history for a session.
        
        Args:
            session_id: Session ID (uses current if None)
            limit: Max messages to return
            
        Returns:
            Response dict with: success, sessionId, history
        """
        sid = session_id or self._session_id
        if not sid:
            return {"success": False, "error": "No session ID"}
        
        return self._request("GET", f"/api/sessions/{sid}/history", params={"limit": str(limit)})
    
    def delete_session(self, session_id: str = None) -> Dict[str, Any]:
        """
        Delete/clear a session.
        
        Args:
            session_id: Session ID (uses current if None)
            
        Returns:
            Response dict with: success, message
        """
        sid = session_id or self._session_id
        if not sid:
            return {"success": False, "error": "No session ID"}
        
        result = self._request("DELETE", f"/api/sessions/{sid}")
        
        if result.get("success") and sid == self._session_id:
            self._session_id = None
        
        return result
    
    def list_sessions(self, limit: int = 10) -> Dict[str, Any]:
        """
        List sessions for the current tenant/user.
        
        Args:
            limit: Max sessions to return
            
        Returns:
            Response dict with: success, sessions
        """
        return self._request("GET", "/api/sessions", params={
            "tenantId": self.config.tenant_id,
            "userId": self.config.user_id,
            "limit": str(limit),
        })
    
    def new_session(self) -> None:
        """Start a new session (clears current session ID)."""
        self._session_id = None
    
    # =========================================================================
    # UTILITY API
    # =========================================================================
    
    def health(self) -> Dict[str, Any]:
        """
        Check API health.
        
        Returns:
            Response dict with: success, status, service, region
        """
        return self._request("GET", "/api/health")
    
    def upload_file(
        self,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Upload a file to S3.
        
        Args:
            content: File content as bytes
            filename: Original filename
            content_type: MIME type
            
        Returns:
            Response dict with: success, s3Key, presignedUrl
        """
        import base64
        
        data = {
            "filename": filename,
            "content": base64.b64encode(content).decode("utf-8"),
            "contentType": content_type,
            "tenantId": self.config.tenant_id,
        }
        
        return self._request("POST", "/api/upload", data)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_client(
    api_endpoint: str,
    tenant_id: str,
    user_id: str = "anonymous",
) -> AgentCoreClient:
    """
    Create an Agent Core client.
    
    Example:
        client = create_client(
            api_endpoint="https://xxx.execute-api.ap-south-1.amazonaws.com",
            tenant_id="1347766229904230"
        )
        response = client.chat("Hello!")
    """
    return AgentCoreClient(
        api_endpoint=api_endpoint,
        tenant_id=tenant_id,
        user_id=user_id,
    )


# =============================================================================
# CLI USAGE
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python client.py <api_endpoint> <tenant_id> [message]")
        print("Example: python client.py https://xxx.execute-api.ap-south-1.amazonaws.com 1347766229904230 'Hello!'")
        sys.exit(1)
    
    api_endpoint = sys.argv[1]
    tenant_id = sys.argv[2]
    message = sys.argv[3] if len(sys.argv) > 3 else "Hello!"
    
    client = create_client(api_endpoint, tenant_id)
    
    # Health check
    health = client.health()
    print(f"Health: {health}")
    
    # Chat
    response = client.chat(message)
    print(f"\nChat Response:")
    print(f"  Session: {response.get('sessionId')}")
    print(f"  Intent: {response.get('intent')}")
    print(f"  Response: {response.get('response')}")
    print(f"  Suggested: {response.get('suggestedActions')}")
