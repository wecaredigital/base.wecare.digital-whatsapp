# =============================================================================
# Bedrock AgentCore with Strands Agents SDK
# =============================================================================
# Uses Strands Agents for WECARE.DIGITAL WhatsApp assistant.
# Supports text, image processing with Claude models via Bedrock.
# =============================================================================

import json
import logging
import os
import base64
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Check if strands is available
try:
    from strands import Agent
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    logger.warning("strands-agents not installed. Install with: pip install strands-agents")


SYSTEM_PROMPT = """You are the WhatsApp assistant for WECARE.DIGITAL.

CAPABILITIES:
- Answer questions about WECARE.DIGITAL services
- Help users navigate to the right service or brand
- Process user requests and route to appropriate actions

WECARE.DIGITAL BRANDS:
- BNB CLUB: Travel services
- NO FAULT: Online Dispute Resolution (ODR)
- EXPO WEEK: Digital events
- RITUAL GURU: Cultural services
- LEGAL CHAMP: Documentation services
- SWDHYA: Samvad (communication)

SELF-SERVICE OPTIONS:
- Submit Request: Start a new service request
- Request Amendment: Modify existing request
- Request Tracking: Check status of request
- RX Slot: Book appointment slot
- Drop Docs: Upload documents
- Enterprise Assist: Business support
- Leave Review: Submit feedback
- FAQ: Frequently asked questions
- Gift Card: Purchase gift cards
- Download App: Get mobile app

RULES:
1. Be helpful, concise, and professional
2. Format responses for WhatsApp (mobile-friendly)
3. Use emojis sparingly but appropriately
4. If unsure, ask clarifying questions
5. For actions outside your scope, explain what you can help with
6. Keep responses under 500 characters when possible
"""


@dataclass
class AgentResponse:
    """Response from Strands Agent."""
    session_id: str
    completion: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None


class StrandsBedrockAgent:
    """
    WECARE.DIGITAL WhatsApp Agent using Strands SDK with Bedrock.
    
    Features:
    - Text conversations with Claude 3 Sonnet
    - Image understanding with Claude 3 vision
    - Tool integration for WhatsApp actions
    
    Usage:
        agent = StrandsBedrockAgent()
        response = agent.invoke("What services does WECARE.DIGITAL offer?")
        print(response.completion)
    """
    
    def __init__(
        self,
        region: str = None,
        model_id: str = None,
    ):
        self.region = region or os.environ.get("BEDROCK_REGION", "ap-south-1")
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", 
            "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        
        self._agent = None
        self._sessions: Dict[str, List[Dict]] = {}  # Simple session memory
    
    @property
    def agent(self):
        """Get or create Strands Agent."""
        if self._agent is None and STRANDS_AVAILABLE:
            try:
                # Create Bedrock model
                model = BedrockModel(
                    model_id=self.model_id,
                    region_name=self.region,
                )
                
                # Create agent with system prompt
                self._agent = Agent(
                    model=model,
                    system_prompt=SYSTEM_PROMPT,
                )
                logger.info(f"Strands Agent initialized with model: {self.model_id}")
            except Exception as e:
                logger.exception(f"Failed to create Strands Agent: {e}")
                self._agent = None
        
        return self._agent
    
    def invoke(
        self,
        input_text: str,
        session_id: str = None,
    ) -> AgentResponse:
        """
        Invoke the agent with text input.
        
        Args:
            input_text: User message/question
            session_id: Session ID for conversation continuity
            
        Returns:
            AgentResponse with completion
        """
        session_id = session_id or self._generate_session_id()
        
        if not STRANDS_AVAILABLE:
            return self._fallback_invoke(input_text, session_id)
        
        if self.agent is None:
            return self._fallback_invoke(input_text, session_id)
        
        try:
            # Get conversation history for session
            history = self._sessions.get(session_id, [])
            
            # Add user message to history
            history.append({"role": "user", "content": input_text})
            
            # Invoke agent
            response = self.agent(input_text)
            
            # Extract completion
            completion = str(response) if response else ""
            
            # Add assistant response to history
            history.append({"role": "assistant", "content": completion})
            
            # Keep last 10 messages
            self._sessions[session_id] = history[-10:]
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
            )
            
        except Exception as e:
            logger.exception(f"Strands Agent invoke failed: {e}")
            return self._fallback_invoke(input_text, session_id)
    
    def invoke_with_image(
        self,
        input_text: str,
        image_bytes: bytes,
        media_type: str = "image/jpeg",
        session_id: str = None,
    ) -> AgentResponse:
        """
        Invoke with image input.
        
        Args:
            input_text: User message/question about the image
            image_bytes: Raw image bytes
            media_type: MIME type (image/jpeg, image/png, etc.)
            session_id: Session ID
            
        Returns:
            AgentResponse with image analysis
        """
        session_id = session_id or self._generate_session_id()
        
        # For image processing, use direct Bedrock call
        return self._invoke_with_image_direct(input_text, image_bytes, media_type, session_id)
    
    def _fallback_invoke(
        self,
        input_text: str,
        session_id: str,
    ) -> AgentResponse:
        """Fallback to direct Bedrock API when Strands not available."""
        import boto3
        from botocore.exceptions import ClientError
        
        try:
            client = boto3.client("bedrock-runtime", region_name=self.region)
            
            messages = [{"role": "user", "content": input_text}]
            
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": messages,
                    "system": SYSTEM_PROMPT,
                }),
            )
            
            result = json.loads(response["body"].read())
            completion = result.get("content", [{}])[0].get("text", "")
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
                raw_response=result,
            )
            
        except ClientError as e:
            logger.exception(f"Bedrock fallback invoke failed: {e}")
            return AgentResponse(
                session_id=session_id,
                completion="I'm sorry, I couldn't process your request. Please try again later.",
            )
    
    def _invoke_with_image_direct(
        self,
        input_text: str,
        image_bytes: bytes,
        media_type: str,
        session_id: str,
    ) -> AgentResponse:
        """Direct Bedrock call for image processing."""
        import boto3
        from botocore.exceptions import ClientError
        
        # Use Claude 3.5 Sonnet via APAC inference profile for vision
        vision_model = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
        
        try:
            client = boto3.client("bedrock-runtime", region_name=self.region)
            
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": input_text,
                        },
                    ],
                }
            ]
            
            response = client.invoke_model(
                modelId=vision_model,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": messages,
                    "system": SYSTEM_PROMPT,
                }),
            )
            
            result = json.loads(response["body"].read())
            completion = result.get("content", [{}])[0].get("text", "")
            
            return AgentResponse(
                session_id=session_id,
                completion=completion,
                raw_response=result,
            )
            
        except ClientError as e:
            logger.exception(f"Bedrock image invoke failed: {e}")
            return AgentResponse(
                session_id=session_id,
                completion="I couldn't process the image. Please try again.",
            )
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return f"session-{uuid.uuid4().hex[:16]}"


# =============================================================================
# WhatsApp Tools for Strands Agent
# =============================================================================

def create_whatsapp_tools():
    """Create WhatsApp action tools for Strands Agent."""
    if not STRANDS_AVAILABLE:
        return []
    
    from strands import tool
    
    @tool
    def get_main_menu() -> str:
        """Get the main menu options for WECARE.DIGITAL services."""
        return """
🏠 *WECARE.DIGITAL Main Menu*

*Our Brands:*
1️⃣ BNB CLUB - Travel Services
2️⃣ NO FAULT - Dispute Resolution
3️⃣ EXPO WEEK - Digital Events
4️⃣ RITUAL GURU - Cultural Services
5️⃣ LEGAL CHAMP - Documentation
6️⃣ SWDHYA - Communication

*Self-Service:*
📝 Submit Request
🔄 Request Amendment
📍 Request Tracking
📅 RX Slot
📎 Drop Docs
🏢 Enterprise Assist
⭐ Leave Review
❓ FAQ

Reply with a number or option name!
"""
    
    @tool
    def get_brand_info(brand_name: str) -> str:
        """Get information about a specific WECARE.DIGITAL brand.
        
        Args:
            brand_name: Name of the brand (e.g., "BNB CLUB", "NO FAULT")
        """
        brands = {
            "bnb club": "🏨 *BNB CLUB* - Your travel companion! We offer hotel bookings, travel packages, and vacation planning services.",
            "no fault": "⚖️ *NO FAULT* - Online Dispute Resolution (ODR) platform for quick and fair conflict resolution.",
            "expo week": "🎪 *EXPO WEEK* - Digital events and virtual exhibitions platform.",
            "ritual guru": "🕉️ *RITUAL GURU* - Cultural and spiritual services for ceremonies and traditions.",
            "legal champ": "📜 *LEGAL CHAMP* - Documentation and legal assistance services.",
            "swdhya": "💬 *SWDHYA* - Samvad communication platform for meaningful conversations.",
        }
        
        key = brand_name.lower().strip()
        return brands.get(key, f"Brand '{brand_name}' not found. Please check the main menu for available brands.")
    
    @tool
    def submit_request(request_type: str, details: str) -> str:
        """Submit a new service request.
        
        Args:
            request_type: Type of request (e.g., "booking", "support", "inquiry")
            details: Details of the request
        """
        import uuid
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        return f"✅ Request submitted!\n\n*Request ID:* {request_id}\n*Type:* {request_type}\n*Details:* {details}\n\nWe'll get back to you within 24 hours."
    
    @tool
    def track_request(request_id: str) -> str:
        """Track the status of an existing request.
        
        Args:
            request_id: The request ID to track
        """
        # In production, this would query DynamoDB
        return f"📍 *Request Status*\n\n*ID:* {request_id}\n*Status:* In Progress\n*Last Updated:* Today\n\nOur team is working on your request."
    
    return [get_main_menu, get_brand_info, submit_request, track_request]
