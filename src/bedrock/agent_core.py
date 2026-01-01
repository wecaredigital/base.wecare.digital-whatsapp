# =============================================================================
# Bedrock Agent Core - Frontend API for Amplify
# =============================================================================
# Production-ready API for connecting Bedrock Agent to frontend apps.
# Features:
# - Session management with DynamoDB
# - S3 integration for media/documents
# - Bedrock Agent + Knowledge Base integration
# - Streaming responses via WebSocket or polling
# - Multi-tenant support
# - Rate limiting
# - CORS-enabled for Amplify
# =============================================================================

import json
import logging
import os
import uuid
import base64
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Generator
from dataclasses import dataclass, field, asdict
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

REGION = os.environ.get("BEDROCK_REGION", "ap-south-1")
TABLE_NAME = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
PK_NAME = os.environ.get("MESSAGES_PK_NAME", "pk")
S3_BUCKET = os.environ.get("MEDIA_BUCKET", "dev.wecare.digital")
S3_PREFIX = os.environ.get("BEDROCK_S3_PREFIX", "Bedrock/agent-core/")

# Bedrock Agent config
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")
KB_ID = os.environ.get("BEDROCK_KB_ID", "")

# Session config
SESSION_TTL_HOURS = 24
MAX_HISTORY_MESSAGES = 20

# Rate limiting
RATE_LIMIT_REQUESTS = 60  # per minute
RATE_LIMIT_WINDOW = 60    # seconds

# Model config
DEFAULT_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "amazon.nova-2-lite-v1:0"
)
MAX_TOKENS = 4096


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChatMessage:
    """Single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = ""
    message_id: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.message_id:
            self.message_id = f"msg-{uuid.uuid4().hex[:12]}"


@dataclass
class ChatSession:
    """Chat session with history."""
    session_id: str
    tenant_id: str
    user_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class AgentCoreResponse:
    """Response from Agent Core."""
    success: bool
    session_id: str
    message_id: str = ""
    response: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    intent: str = ""
    suggested_actions: List[str] = field(default_factory=list)
    s3_attachments: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KBQueryResult:
    """Knowledge Base query result."""
    success: bool
    query: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    generated_response: str = ""
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# AGENT CORE CLASS
# =============================================================================

class BedrockAgentCore:
    """
    Bedrock Agent Core for frontend integration.
    
    Features:
    - Session-based conversations with history
    - S3 integration for media/documents
    - Bedrock Agent invocation
    - Knowledge Base queries
    - Multi-tenant support
    - Rate limiting
    - Intent detection
    - Suggested actions
    
    Usage (from Amplify/frontend):
        POST /api/chat
        {
            "sessionId": "optional-existing-session",
            "tenantId": "1347766229904230",
            "userId": "user@example.com",
            "message": "What services do you offer?"
        }
    """
    
    def __init__(self, region: str = None):
        self.region = region or REGION
        self._bedrock = None
        self._bedrock_agent = None
        self._bedrock_agent_runtime = None
        self._table = None
        self._s3 = None
    
    @property
    def bedrock(self):
        """Bedrock Runtime client."""
        if self._bedrock is None:
            self._bedrock = boto3.client("bedrock-runtime", region_name=self.region)
        return self._bedrock
    
    @property
    def bedrock_agent(self):
        """Bedrock Agent client."""
        if self._bedrock_agent is None:
            self._bedrock_agent = boto3.client("bedrock-agent", region_name=self.region)
        return self._bedrock_agent
    
    @property
    def bedrock_agent_runtime(self):
        """Bedrock Agent Runtime client."""
        if self._bedrock_agent_runtime is None:
            self._bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=self.region)
        return self._bedrock_agent_runtime
    
    @property
    def table(self):
        """DynamoDB table."""
        if self._table is None:
            dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._table = dynamodb.Table(TABLE_NAME)
        return self._table
    
    @property
    def s3(self):
        """S3 client."""
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3

    
    # =========================================================================
    # PUBLIC API - CHAT
    # =========================================================================
    
    def chat(
        self,
        message: str,
        tenant_id: str,
        user_id: str,
        session_id: str = None,
        metadata: Dict[str, Any] = None,
        use_agent: bool = False,
    ) -> AgentCoreResponse:
        """
        Send a chat message and get response.
        
        Args:
            message: User message
            tenant_id: Tenant/WABA ID
            user_id: User identifier (email, phone, etc.)
            session_id: Existing session ID (creates new if None)
            metadata: Additional context
            use_agent: If True, use Bedrock Agent; else use direct model
            
        Returns:
            AgentCoreResponse with AI response
        """
        # Rate limit check
        if not self._check_rate_limit(tenant_id, user_id):
            return AgentCoreResponse(
                success=False,
                session_id=session_id or "",
                error="Rate limit exceeded. Please wait a moment.",
            )
        
        # Get or create session
        session = self._get_or_create_session(session_id, tenant_id, user_id, metadata)
        
        # Add user message to history
        user_msg = ChatMessage(role="user", content=message)
        session.messages.append(user_msg)
        
        # Choose invocation method
        if use_agent and AGENT_ID and AGENT_ALIAS_ID:
            result = self._invoke_agent(message, session)
        else:
            result = self._invoke_model(message, session, tenant_id)
        
        if not result.get("success"):
            return AgentCoreResponse(
                success=False,
                session_id=session.session_id,
                message_id=user_msg.message_id,
                error=result.get("error", "Unknown error"),
            )
        
        completion = result.get("response", "")
        citations = result.get("citations", [])
        
        # Add assistant response to history
        assistant_msg = ChatMessage(role="assistant", content=completion)
        session.messages.append(assistant_msg)
        
        # Trim history if too long
        if len(session.messages) > MAX_HISTORY_MESSAGES * 2:
            session.messages = session.messages[-MAX_HISTORY_MESSAGES * 2:]
        
        # Save session
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_session(session)
        
        # Detect intent and suggest actions
        intent = self._detect_intent(message)
        suggested_actions = self._get_suggested_actions(intent)
        
        return AgentCoreResponse(
            success=True,
            session_id=session.session_id,
            message_id=assistant_msg.message_id,
            response=completion,
            citations=citations,
            intent=intent,
            suggested_actions=suggested_actions,
        )

    
    # =========================================================================
    # PUBLIC API - BEDROCK AGENT INVOCATION
    # =========================================================================
    
    def invoke_agent(
        self,
        input_text: str,
        session_id: str,
        tenant_id: str = "",
        enable_trace: bool = False,
    ) -> AgentCoreResponse:
        """
        Directly invoke Bedrock Agent.
        
        Args:
            input_text: User input
            session_id: Session ID for conversation continuity
            tenant_id: Tenant ID for context
            enable_trace: Enable agent trace for debugging
            
        Returns:
            AgentCoreResponse with agent response
        """
        if not AGENT_ID or not AGENT_ALIAS_ID:
            return AgentCoreResponse(
                success=False,
                session_id=session_id,
                error="Bedrock Agent not configured (AGENT_ID or AGENT_ALIAS_ID missing)",
            )
        
        try:
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=AGENT_ID,
                agentAliasId=AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=input_text,
                enableTrace=enable_trace,
            )
            
            # Process streaming response
            completion = ""
            citations = []
            
            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_data = event["chunk"]
                    if "bytes" in chunk_data:
                        completion += chunk_data["bytes"].decode("utf-8")
                
                if "trace" in event and enable_trace:
                    logger.info(f"Agent trace: {event['trace']}")
                
                if "attribution" in event:
                    citations.extend(event["attribution"].get("citations", []))
            
            return AgentCoreResponse(
                success=True,
                session_id=session_id,
                response=completion,
                citations=citations,
            )
            
        except ClientError as e:
            logger.exception(f"Agent invocation failed: {e}")
            return AgentCoreResponse(
                success=False,
                session_id=session_id,
                error=f"Agent error: {str(e)}",
            )

    
    # =========================================================================
    # PUBLIC API - KNOWLEDGE BASE QUERY
    # =========================================================================
    
    def query_knowledge_base(
        self,
        query: str,
        max_results: int = 5,
        generate_response: bool = True,
    ) -> KBQueryResult:
        """
        Query the Bedrock Knowledge Base.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            generate_response: If True, generate a response using retrieved context
            
        Returns:
            KBQueryResult with search results and optional generated response
        """
        if not KB_ID:
            return KBQueryResult(
                success=False,
                query=query,
                error="Knowledge Base not configured (KB_ID missing)",
            )
        
        try:
            if generate_response:
                # Retrieve and Generate
                response = self.bedrock_agent_runtime.retrieve_and_generate(
                    input={"text": query},
                    retrieveAndGenerateConfiguration={
                        "type": "KNOWLEDGE_BASE",
                        "knowledgeBaseConfiguration": {
                            "knowledgeBaseId": KB_ID,
                            "modelArn": f"arn:aws:bedrock:{self.region}::foundation-model/{DEFAULT_MODEL_ID}",
                            "retrievalConfiguration": {
                                "vectorSearchConfiguration": {
                                    "numberOfResults": max_results,
                                }
                            }
                        }
                    }
                )
                
                output = response.get("output", {})
                citations = response.get("citations", [])
                
                return KBQueryResult(
                    success=True,
                    query=query,
                    generated_response=output.get("text", ""),
                    citations=[
                        {
                            "text": c.get("generatedResponsePart", {}).get("textResponsePart", {}).get("text", ""),
                            "references": c.get("retrievedReferences", []),
                        }
                        for c in citations
                    ],
                )
            else:
                # Retrieve only
                response = self.bedrock_agent_runtime.retrieve(
                    knowledgeBaseId=KB_ID,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": max_results,
                        }
                    }
                )
                
                results = []
                for result in response.get("retrievalResults", []):
                    results.append({
                        "content": result.get("content", {}).get("text", ""),
                        "score": result.get("score", 0),
                        "location": result.get("location", {}),
                        "metadata": result.get("metadata", {}),
                    })
                
                return KBQueryResult(
                    success=True,
                    query=query,
                    results=results,
                )
                
        except ClientError as e:
            logger.exception(f"KB query failed: {e}")
            return KBQueryResult(
                success=False,
                query=query,
                error=f"KB error: {str(e)}",
            )

    
    # =========================================================================
    # PUBLIC API - S3 OPERATIONS
    # =========================================================================
    
    def upload_to_s3(
        self,
        content: bytes,
        filename: str,
        tenant_id: str,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Upload content to S3.
        
        Args:
            content: File content as bytes
            filename: Original filename
            tenant_id: Tenant ID for path organization
            content_type: MIME type
            
        Returns:
            Dict with s3_key, s3_uri, presigned_url
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"{S3_PREFIX}{tenant_id}/{timestamp}_{filename}"
        
        try:
            self.s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
            )
            
            # Generate presigned URL (24 hour expiry)
            presigned_url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": s3_key},
                ExpiresIn=86400,
            )
            
            return {
                "success": True,
                "s3_bucket": S3_BUCKET,
                "s3_key": s3_key,
                "s3_uri": f"s3://{S3_BUCKET}/{s3_key}",
                "presigned_url": presigned_url,
                "content_type": content_type,
            }
            
        except ClientError as e:
            logger.exception(f"S3 upload failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def get_s3_presigned_url(
        self,
        s3_key: str,
        expiry: int = 86400,
    ) -> Optional[str]:
        """Generate presigned URL for S3 object."""
        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": s3_key},
                ExpiresIn=expiry,
            )
        except ClientError as e:
            logger.warning(f"Failed to generate presigned URL: {e}")
            return None
    
    def download_from_s3(self, s3_key: str) -> Optional[bytes]:
        """Download content from S3."""
        try:
            response = self.s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
            return response["Body"].read()
        except ClientError as e:
            logger.warning(f"S3 download failed: {e}")
            return None

    
    # =========================================================================
    # PUBLIC API - SESSION MANAGEMENT
    # =========================================================================
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get existing session by ID."""
        pk = f"AGENT_SESSION#{session_id}"
        
        try:
            response = self.table.get_item(Key={PK_NAME: pk})
            item = response.get("Item")
            
            if not item:
                return None
            
            messages = [
                ChatMessage(**msg) for msg in item.get("messages", [])
            ]
            
            return ChatSession(
                session_id=item.get("sessionId", session_id),
                tenant_id=item.get("tenantId", ""),
                user_id=item.get("userId", ""),
                messages=messages,
                created_at=item.get("createdAt", ""),
                updated_at=item.get("updatedAt", ""),
                metadata=item.get("metadata", {}),
            )
        except ClientError as e:
            logger.warning(f"Failed to get session: {e}")
            return None
    
    def get_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get chat history for a session."""
        session = self.get_session(session_id)
        if not session:
            return []
        messages = session.messages[-limit:]
        return [asdict(msg) for msg in messages]
    
    def clear_session(self, session_id: str) -> bool:
        """Clear/delete a session."""
        pk = f"AGENT_SESSION#{session_id}"
        try:
            self.table.delete_item(Key={PK_NAME: pk})
            return True
        except ClientError as e:
            logger.warning(f"Failed to clear session: {e}")
            return False
    
    def list_sessions(
        self,
        tenant_id: str,
        user_id: str = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """List sessions for a tenant/user."""
        try:
            filter_expr = "tenantId = :tid AND itemType = :it"
            expr_values = {":tid": tenant_id, ":it": "AGENT_SESSION"}
            
            if user_id:
                filter_expr += " AND userId = :uid"
                expr_values[":uid"] = user_id
            
            response = self.table.scan(
                FilterExpression=filter_expr,
                ExpressionAttributeValues=expr_values,
                Limit=limit,
            )
            
            sessions = []
            for item in response.get("Items", []):
                sessions.append({
                    "sessionId": item.get("sessionId"),
                    "userId": item.get("userId"),
                    "createdAt": item.get("createdAt"),
                    "updatedAt": item.get("updatedAt"),
                    "messageCount": len(item.get("messages", [])),
                })
            
            return sorted(sessions, key=lambda x: x.get("updatedAt", ""), reverse=True)
            
        except ClientError as e:
            logger.warning(f"Failed to list sessions: {e}")
            return []

    
    # =========================================================================
    # STREAMING API (for real-time responses)
    # =========================================================================
    
    def chat_stream(
        self,
        message: str,
        tenant_id: str,
        user_id: str,
        session_id: str = None,
    ) -> Generator[str, None, None]:
        """
        Stream chat response (for WebSocket/SSE).
        Yields chunks of the response as they're generated.
        Note: Amazon Nova streaming uses different format than Claude.
        """
        session = self._get_or_create_session(session_id, tenant_id, user_id)
        user_msg = ChatMessage(role="user", content=message)
        session.messages.append(user_msg)
        messages = self._build_messages_nova(session)
        
        try:
            response = self.bedrock.invoke_model_with_response_stream(
                modelId=DEFAULT_MODEL_ID,
                body=json.dumps({
                    "messages": messages,
                    "system": [{"text": self._get_system_prompt(tenant_id)}],
                    "inferenceConfig": {"maxTokens": MAX_TOKENS, "temperature": 0.7},
                }),
            )
            
            full_response = ""
            for event in response.get("body", []):
                chunk = event.get("chunk")
                if chunk:
                    chunk_data = json.loads(chunk.get("bytes", b"{}").decode())
                    # Nova streaming format
                    if "contentBlockDelta" in chunk_data:
                        delta = chunk_data.get("contentBlockDelta", {}).get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            full_response += text
                            yield text
            
            # Save complete response
            assistant_msg = ChatMessage(role="assistant", content=full_response)
            session.messages.append(assistant_msg)
            session.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_session(session)
            
        except ClientError as e:
            logger.exception(f"Streaming failed: {e}")
            yield f"[Error: {str(e)}]"

    
    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================
    
    def _invoke_model(
        self,
        message: str,
        session: ChatSession,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Invoke Bedrock model directly (Amazon Nova 2 Lite)."""
        messages = self._build_messages_nova(session)
        
        try:
            response = self.bedrock.invoke_model(
                modelId=DEFAULT_MODEL_ID,
                body=json.dumps({
                    "messages": messages,
                    "system": [{"text": self._get_system_prompt(tenant_id)}],
                    "inferenceConfig": {"maxTokens": MAX_TOKENS, "temperature": 0.7},
                }),
            )
            
            result = json.loads(response["body"].read())
            # Nova response format
            completion = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            
            return {"success": True, "response": completion}
            
        except ClientError as e:
            logger.exception(f"Model invoke failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _invoke_agent(
        self,
        message: str,
        session: ChatSession,
    ) -> Dict[str, Any]:
        """Invoke Bedrock Agent."""
        try:
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=AGENT_ID,
                agentAliasId=AGENT_ALIAS_ID,
                sessionId=session.session_id,
                inputText=message,
            )
            
            completion = ""
            citations = []
            
            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_data = event["chunk"]
                    if "bytes" in chunk_data:
                        completion += chunk_data["bytes"].decode("utf-8")
                if "attribution" in event:
                    citations.extend(event["attribution"].get("citations", []))
            
            return {"success": True, "response": completion, "citations": citations}
            
        except ClientError as e:
            logger.exception(f"Agent invoke failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_or_create_session(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        metadata: Dict[str, Any] = None,
    ) -> ChatSession:
        """Get existing session or create new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        new_session_id = f"sess-{uuid.uuid4().hex[:16]}"
        return ChatSession(
            session_id=new_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata or {},
        )
    
    def _save_session(self, session: ChatSession) -> None:
        """Save session to DynamoDB."""
        pk = f"AGENT_SESSION#{session.session_id}"
        ttl = int((datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).timestamp())
        
        item = {
            PK_NAME: pk,
            "itemType": "AGENT_SESSION",
            "sessionId": session.session_id,
            "tenantId": session.tenant_id,
            "userId": session.user_id,
            "messages": [asdict(msg) for msg in session.messages],
            "createdAt": session.created_at,
            "updatedAt": session.updated_at,
            "metadata": session.metadata,
            "ttl": ttl,
        }
        
        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            logger.warning(f"Failed to save session: {e}")
    
    def _build_messages(self, session: ChatSession) -> List[Dict[str, Any]]:
        """Build messages array for Claude (legacy)."""
        messages = []
        for msg in session.messages[-MAX_HISTORY_MESSAGES * 2:]:
            messages.append({"role": msg.role, "content": msg.content})
        return messages
    
    def _build_messages_nova(self, session: ChatSession) -> List[Dict[str, Any]]:
        """Build messages array for Amazon Nova format."""
        messages = []
        for msg in session.messages[-MAX_HISTORY_MESSAGES * 2:]:
            messages.append({
                "role": msg.role,
                "content": [{"text": msg.content}]
            })
        return messages

    
    def _check_rate_limit(self, tenant_id: str, user_id: str) -> bool:
        """Check if request is within rate limits."""
        key = f"RATE#{tenant_id}#{user_id}"
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(seconds=RATE_LIMIT_WINDOW)).isoformat()
        
        try:
            response = self.table.query(
                KeyConditionExpression=f"{PK_NAME} = :pk",
                FilterExpression="requestedAt > :window",
                ExpressionAttributeValues={":pk": key, ":window": window_start},
            )
            
            count = len(response.get("Items", []))
            if count >= RATE_LIMIT_REQUESTS:
                return False
            
            self.table.put_item(Item={
                PK_NAME: f"{key}#{now.isoformat()}",
                "itemType": "RATE_LIMIT",
                "requestedAt": now.isoformat(),
                "ttl": int((now + timedelta(minutes=5)).timestamp()),
            })
            return True
        except ClientError:
            return True
    
    def _get_system_prompt(self, tenant_id: str) -> str:
        """Get system prompt for the agent."""
        return f"""You are the AI assistant for WECARE.DIGITAL.

TENANT CONTEXT: {tenant_id}

ABOUT WECARE.DIGITAL:
WECARE.DIGITAL is a microservice company ecosystem offering various services through specialized brands.

BRANDS:
- BNB CLUB: Travel agency + tourism support
- NO FAULT: Online Dispute Resolution (ODR) platform
- EXPO WEEK: Digital events + expo experiences
- RITUAL GURU: Puja kits + step-by-step guides
- LEGAL CHAMP: Business documentation services
- SWDHYA: Self-inquiry conversations for clarity

SELF-SERVICE OPTIONS:
- Submit Request: Start a new service request
- Request Amendment: Update an existing request
- Request Tracking: Check request status
- RX Slot: Book or manage appointments
- Drop Docs: Upload documents securely
- Enterprise Assist: Enterprise-level support
- Leave Review: Share feedback

GUIDELINES:
1. Be helpful, concise, and professional
2. If you don't know something, say so and offer to help find the answer
3. Suggest relevant self-service options when appropriate
4. Keep responses mobile-friendly (short paragraphs, clear formatting)
5. Use emojis sparingly for friendliness
6. Always prioritize user privacy and security

WEBSITE: https://www.wecare.digital"""
    
    def _detect_intent(self, message: str) -> str:
        """Detect user intent from message."""
        text = message.lower()
        
        intents = {
            "greeting": ["hi", "hello", "hey", "good morning", "good evening"],
            "service_inquiry": ["service", "offer", "provide", "what do you do"],
            "pricing": ["price", "cost", "how much", "fee", "charge"],
            "booking": ["book", "schedule", "appointment", "slot", "rx"],
            "tracking": ["track", "status", "where", "update", "progress"],
            "support": ["help", "support", "assist", "problem", "issue"],
            "document": ["document", "upload", "drop", "file", "pdf"],
            "cancellation": ["cancel", "refund", "stop", "end"],
            "feedback": ["feedback", "review", "rating", "complaint"],
            "menu": ["menu", "options", "start", "begin"],
        }
        
        for intent, keywords in intents.items():
            if any(kw in text for kw in keywords):
                return intent
        return "general_inquiry"
    
    def _get_suggested_actions(self, intent: str) -> List[str]:
        """Get suggested actions based on intent."""
        action_map = {
            "greeting": ["View Services", "Submit Request", "Track Request"],
            "service_inquiry": ["BNB CLUB", "NO FAULT", "LEGAL CHAMP", "View All Services"],
            "pricing": ["Contact Sales", "View Pricing", "Request Quote"],
            "booking": ["Book RX Slot", "View Calendar", "Contact Support"],
            "tracking": ["Track Request", "View Status", "Contact Support"],
            "support": ["FAQ", "Contact Us", "Submit Ticket"],
            "document": ["Drop Docs", "View Uploads", "Submit Request"],
            "cancellation": ["Cancel Request", "Request Refund", "Contact Support"],
            "feedback": ["Leave Review", "Submit Feedback", "Contact Us"],
            "menu": ["Services", "Self Service", "Support"],
            "general_inquiry": ["View Services", "FAQ", "Contact Us"],
        }
        return action_map.get(intent, ["View Services", "Contact Us"])


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_agent_core_instance = None

def get_agent_core() -> BedrockAgentCore:
    """Get singleton AgentCore instance."""
    global _agent_core_instance
    if _agent_core_instance is None:
        _agent_core_instance = BedrockAgentCore()
    return _agent_core_instance
