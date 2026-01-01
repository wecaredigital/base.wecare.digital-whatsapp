# =============================================================================
# Bedrock Agent Client
# =============================================================================
# Client for Amazon Bedrock Agent "base-wecare-digital-WhatsApp".
# Supports text, image, document, audio, and video processing.
# =============================================================================

import json
import logging
import os
import base64
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from Bedrock Agent."""
    session_id: str
    completion: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    trace: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None


class BedrockAgent:
    """
    Client for Bedrock Agent "base-wecare-digital-WhatsApp".
    
    Features:
    - Text conversations with knowledge base
    - Image understanding (Claude 3.7 Sonnet)
    - Document processing via Data Automation
    - Audio/video transcript extraction
    
    Usage:
        agent = BedrockAgent()
        response = agent.invoke("What services does WECARE.DIGITAL offer?")
        print(response.completion)
    """
    
    def __init__(
        self,
        agent_id: str = None,
        agent_alias_id: str = None,
        region: str = None,
    ):
        self.region = region or os.environ.get("BEDROCK_REGION", "ap-south-1")
        self.agent_id = agent_id or os.environ.get("BEDROCK_AGENT_ID", "")
        self.agent_alias_id = agent_alias_id or os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID")
        
        self._client = None
        self._runtime_client = None
    
    @property
    def client(self):
        """Bedrock Agent Runtime client."""
        if self._client is None:
            self._client = boto3.client("bedrock-agent-runtime", region_name=self.region)
        return self._client
    
    @property
    def runtime_client(self):
        """Bedrock Runtime client (for direct model invocation)."""
        if self._runtime_client is None:
            self._runtime_client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._runtime_client
    
    def invoke(
        self,
        input_text: str,
        session_id: str = None,
        enable_trace: bool = False,
        session_attributes: Dict[str, str] = None,
    ) -> AgentResponse:
        """
        Invoke Bedrock with text input.
        Uses Agent if configured, otherwise falls back to direct Claude invocation.
        
        Args:
            input_text: User message/question
            session_id: Session ID for conversation continuity
            enable_trace: Enable trace for debugging
            session_attributes: Additional session context
            
        Returns:
            AgentResponse with completion and citations
        """
        session_id = session_id or self._generate_session_id()
        
        # If Agent is configured, use it
        if self.agent_id:
            return self._invoke_agent(input_text, session_id, enable_trace, session_attributes)
        
        # Otherwise, use direct Claude invocation
        return self._invoke_claude_direct(input_text, session_id)
    
    def _invoke_agent(
        self,
        input_text: str,
        session_id: str,
        enable_trace: bool,
        session_attributes: Dict[str, str] = None,
    ) -> AgentResponse:
        """Invoke Bedrock Agent."""
        try:
            kwargs = {
                "agentId": self.agent_id,
                "agentAliasId": self.agent_alias_id,
                "sessionId": session_id,
                "inputText": input_text,
                "enableTrace": enable_trace,
            }
            
            if session_attributes:
                kwargs["sessionState"] = {
                    "sessionAttributes": session_attributes,
                }
            
            response = self.client.invoke_agent(**kwargs)
            
            # Process streaming response
            completion = ""
            citations = []
            trace = None
            
            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        completion += chunk["bytes"].decode("utf-8")
                    if "attribution" in chunk:
                        citations.extend(chunk["attribution"].get("citations", []))
                
                if "trace" in event and enable_trace:
                    trace = event["trace"]
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
                citations=citations,
                trace=trace,
                raw_response=response,
            )
            
        except ClientError as e:
            logger.exception(f"Bedrock Agent invoke failed: {e}")
            # Fallback to direct Claude
            return self._invoke_claude_direct(input_text, session_id)
    
    def _invoke_claude_direct(
        self,
        input_text: str,
        session_id: str,
    ) -> AgentResponse:
        """
        Invoke model directly without Agent.
        Uses Amazon Nova 2 Lite for text processing.
        """
        # Use Amazon Nova 2 Lite (AWS first-party, no subscription needed)
        model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-2-lite-v1:0")
        
        try:
            # Amazon Nova uses Converse API format
            messages = [
                {
                    "role": "user",
                    "content": [{"text": input_text}],
                }
            ]
            
            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "messages": messages,
                    "system": [{"text": self._get_system_prompt()}],
                    "inferenceConfig": {"maxTokens": 4096, "temperature": 0.7},
                }),
            )
            
            result = json.loads(response["body"].read())
            # Nova response format
            completion = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
                raw_response=result,
            )
            
        except ClientError as e:
            logger.exception(f"Bedrock Claude invoke failed: {e}")
            return AgentResponse(
                session_id=session_id,
                completion=f"I'm sorry, I couldn't process your request. Please try again later.",
            )
    
    def invoke_with_image(
        self,
        input_text: str,
        image_bytes: bytes,
        media_type: str = "image/jpeg",
        session_id: str = None,
    ) -> AgentResponse:
        """
        Invoke with image input (uses Amazon Nova 2 Lite).
        
        Args:
            input_text: User message/question about the image
            image_bytes: Raw image bytes
            media_type: MIME type (image/jpeg, image/png, etc.)
            session_id: Session ID
            
        Returns:
            AgentResponse with image analysis
        """
        session_id = session_id or self._generate_session_id()
        
        # Use Amazon Nova 2 Lite for image understanding (supports multimodal)
        model_id = "amazon.nova-2-lite-v1:0"
        
        try:
            # Encode image
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            
            # Build message with image (Nova format)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": media_type.split("/")[1],  # jpeg, png, etc.
                                "source": {"bytes": image_base64},
                            },
                        },
                        {"text": input_text},
                    ],
                }
            ]
            
            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "messages": messages,
                    "system": [{"text": self._get_system_prompt()}],
                    "inferenceConfig": {"maxTokens": 4096, "temperature": 0.7},
                }),
            )
            
            result = json.loads(response["body"].read())
            # Nova response format
            completion = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
                raw_response=result,
            )
            
        except ClientError as e:
            logger.exception(f"Bedrock image invoke failed: {e}")
            return AgentResponse(
                session_id=session_id,
                completion=f"Error processing image: {str(e)}",
            )
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return f"session-{uuid.uuid4().hex[:16]}"
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the agent."""
        return """You are the WhatsApp assistant for WECARE.DIGITAL.

When users ask about WECARE.DIGITAL services, use only the knowledge base content derived from https://wecare.digital.

If a question is outside that content, say you don't have that info and ask a clarifying question.

Be helpful, concise, and professional. Format responses for WhatsApp (use emojis sparingly, keep messages readable on mobile).

WECARE.DIGITAL brands include:
- BNB CLUB (Travel)
- NO FAULT (ODR - Online Dispute Resolution)
- EXPO WEEK (Digital events)
- RITUAL GURU (Culture)
- LEGAL CHAMP (Documentation)
- SWDHYA (Samvad)

Self-service options:
- Submit Request
- Request Amendment
- Request Tracking
- RX Slot
- Drop Docs
- Enterprise Assist
- Leave Review
- FAQ"""
