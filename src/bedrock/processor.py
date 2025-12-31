# =============================================================================
# Bedrock Multimedia Processor
# =============================================================================
# Processes WhatsApp multimedia content using Bedrock.
# Supports: text, images, documents, audio, video.
# =============================================================================

import json
import logging
import os
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from src.bedrock.agent import BedrockAgent, AgentResponse

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of multimedia processing."""
    success: bool
    message_id: str
    content_type: str
    summary: str = ""
    extracted_text: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    intent: str = ""
    action_suggestions: list = field(default_factory=list)
    reply_draft: str = ""
    agent_response: Optional[AgentResponse] = None
    error: str = ""


class BedrockProcessor:
    """
    Processes WhatsApp multimedia content using Bedrock.
    
    Pipeline:
    1. Load message + media from DynamoDB/S3
    2. Process based on content type:
       - Text: Direct agent invocation
       - Image: Claude 3.7 Sonnet vision
       - Document/Audio/Video: Data Automation extraction → agent
    3. Store results in DynamoDB
    4. Optionally generate reply draft
    
    Usage:
        processor = BedrockProcessor(deps)
        result = processor.process_message(message_id, tenant_id)
    """
    
    def __init__(self, deps=None, region: str = None):
        self.region = region or os.environ.get("BEDROCK_REGION", "ap-south-1")
        self.deps = deps
        self.agent = BedrockAgent(region=self.region)
        
        self._s3 = None
        self._table = None
    
    @property
    def s3(self):
        if self._s3 is None:
            if self.deps:
                self._s3 = self.deps.s3
            else:
                self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3
    
    @property
    def table(self):
        if self._table is None:
            if self.deps:
                self._table = self.deps.table
            else:
                dynamodb = boto3.resource("dynamodb", region_name=self.region)
                table_name = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
                self._table = dynamodb.Table(table_name)
        return self._table
    
    def process_message(
        self,
        message_id: str,
        tenant_id: str,
        conversation_id: str = None,
        generate_reply: bool = True,
    ) -> ProcessingResult:
        """
        Process a WhatsApp message with Bedrock.
        
        Args:
            message_id: WhatsApp message ID
            tenant_id: Tenant/WABA ID
            conversation_id: Conversation ID for session continuity
            generate_reply: Whether to generate reply draft
            
        Returns:
            ProcessingResult with analysis and optional reply
        """
        # Load message from DynamoDB
        pk_name = os.environ.get("MESSAGES_PK_NAME", "pk")
        msg_pk = f"MSG#{message_id}"
        
        try:
            response = self.table.get_item(Key={pk_name: msg_pk})
            message = response.get("Item")
            
            if not message:
                return ProcessingResult(
                    success=False,
                    message_id=message_id,
                    content_type="unknown",
                    error=f"Message not found: {message_id}",
                )
        except ClientError as e:
            return ProcessingResult(
                success=False,
                message_id=message_id,
                content_type="unknown",
                error=str(e),
            )
        
        # Determine content type and process
        content_type = message.get("type", "text")
        
        if content_type == "text":
            return self._process_text(message, tenant_id, conversation_id, generate_reply)
        elif content_type in ("image", "sticker"):
            return self._process_image(message, tenant_id, conversation_id, generate_reply)
        elif content_type == "document":
            return self._process_document(message, tenant_id, conversation_id, generate_reply)
        elif content_type in ("audio", "video"):
            return self._process_media(message, tenant_id, conversation_id, generate_reply)
        else:
            return self._process_text(message, tenant_id, conversation_id, generate_reply)
    
    def _process_text(
        self,
        message: Dict[str, Any],
        tenant_id: str,
        conversation_id: str,
        generate_reply: bool,
    ) -> ProcessingResult:
        """Process text message."""
        message_id = message.get("pk", "").replace("MSG#", "")
        text_body = message.get("textBody", "") or message.get("caption", "")
        sender_name = message.get("senderName", "User")
        
        if not text_body:
            return ProcessingResult(
                success=True,
                message_id=message_id,
                content_type="text",
                summary="Empty message",
            )
        
        # Build session ID from conversation
        session_id = f"conv-{conversation_id}" if conversation_id else None
        
        # Invoke agent
        prompt = f"User {sender_name} says: {text_body}"
        agent_response = self.agent.invoke(prompt, session_id=session_id)
        
        # Extract intent and entities (simple heuristics)
        intent = self._detect_intent(text_body)
        entities = self._extract_entities(text_body)
        
        # Generate reply draft
        reply_draft = ""
        if generate_reply and agent_response.completion:
            reply_draft = agent_response.completion
        
        result = ProcessingResult(
            success=True,
            message_id=message_id,
            content_type="text",
            summary=text_body[:200],
            extracted_text=text_body,
            entities=entities,
            intent=intent,
            reply_draft=reply_draft,
            agent_response=agent_response,
        )
        
        # Store result
        self._store_result(message_id, tenant_id, conversation_id, result)
        
        return result
    
    def _process_image(
        self,
        message: Dict[str, Any],
        tenant_id: str,
        conversation_id: str,
        generate_reply: bool,
    ) -> ProcessingResult:
        """Process image message."""
        message_id = message.get("pk", "").replace("MSG#", "")
        s3_bucket = message.get("s3Bucket", "")
        s3_key = message.get("s3Key", "")
        caption = message.get("caption", "")
        mime_type = message.get("mimeType", "image/jpeg")
        
        if not s3_bucket or not s3_key:
            return ProcessingResult(
                success=False,
                message_id=message_id,
                content_type="image",
                error="No S3 location for image",
            )
        
        try:
            # Download image from S3
            response = self.s3.get_object(Bucket=s3_bucket, Key=s3_key)
            image_bytes = response["Body"].read()
            
            # Build prompt
            prompt = caption if caption else "Describe this image and identify any relevant information."
            
            # Invoke with image
            session_id = f"conv-{conversation_id}" if conversation_id else None
            agent_response = self.agent.invoke_with_image(
                prompt, image_bytes, mime_type, session_id
            )
            
            result = ProcessingResult(
                success=True,
                message_id=message_id,
                content_type="image",
                summary=agent_response.completion[:200] if agent_response.completion else "Image processed",
                extracted_text=agent_response.completion,
                reply_draft=agent_response.completion if generate_reply else "",
                agent_response=agent_response,
            )
            
            self._store_result(message_id, tenant_id, conversation_id, result)
            return result
            
        except ClientError as e:
            return ProcessingResult(
                success=False,
                message_id=message_id,
                content_type="image",
                error=str(e),
            )
    
    def _process_document(
        self,
        message: Dict[str, Any],
        tenant_id: str,
        conversation_id: str,
        generate_reply: bool,
    ) -> ProcessingResult:
        """Process document message."""
        message_id = message.get("pk", "").replace("MSG#", "")
        s3_bucket = message.get("s3Bucket", "")
        s3_key = message.get("s3Key", "")
        filename = message.get("filename", "document")
        caption = message.get("caption", "")
        
        # For now, acknowledge document and suggest manual review
        # Full Data Automation integration would extract text here
        
        summary = f"Document received: {filename}"
        if caption:
            summary += f" - {caption}"
        
        reply_draft = ""
        if generate_reply:
            reply_draft = f"Thank you for sending the document '{filename}'. Our team will review it shortly."
        
        result = ProcessingResult(
            success=True,
            message_id=message_id,
            content_type="document",
            summary=summary,
            reply_draft=reply_draft,
        )
        
        self._store_result(message_id, tenant_id, conversation_id, result)
        return result
    
    def _process_media(
        self,
        message: Dict[str, Any],
        tenant_id: str,
        conversation_id: str,
        generate_reply: bool,
    ) -> ProcessingResult:
        """Process audio/video message."""
        message_id = message.get("pk", "").replace("MSG#", "")
        content_type = message.get("type", "media")
        caption = message.get("caption", "")
        
        # For now, acknowledge media
        # Full Data Automation would transcribe audio/video
        
        summary = f"{content_type.capitalize()} message received"
        if caption:
            summary += f": {caption}"
        
        reply_draft = ""
        if generate_reply:
            reply_draft = f"Thank you for the {content_type} message. We'll process it shortly."
        
        result = ProcessingResult(
            success=True,
            message_id=message_id,
            content_type=content_type,
            summary=summary,
            reply_draft=reply_draft,
        )
        
        self._store_result(message_id, tenant_id, conversation_id, result)
        return result
    
    def _detect_intent(self, text: str) -> str:
        """Simple intent detection."""
        text_lower = text.lower()
        
        if any(w in text_lower for w in ["help", "support", "assist"]):
            return "support_request"
        if any(w in text_lower for w in ["price", "cost", "how much"]):
            return "pricing_inquiry"
        if any(w in text_lower for w in ["book", "schedule", "appointment"]):
            return "booking_request"
        if any(w in text_lower for w in ["track", "status", "where"]):
            return "tracking_inquiry"
        if any(w in text_lower for w in ["cancel", "refund"]):
            return "cancellation_request"
        if any(w in text_lower for w in ["menu", "options", "start"]):
            return "menu_request"
        if any(w in text_lower for w in ["hi", "hello", "hey"]):
            return "greeting"
        
        return "general_inquiry"
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Simple entity extraction."""
        import re
        
        entities = {}
        
        # Phone numbers
        phones = re.findall(r'\+?\d{10,15}', text)
        if phones:
            entities["phone_numbers"] = phones
        
        # Email addresses
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if emails:
            entities["emails"] = emails
        
        # Order/reference numbers
        refs = re.findall(r'(?:order|ref|booking|ticket)[#:\s]*([A-Z0-9-]+)', text, re.IGNORECASE)
        if refs:
            entities["reference_numbers"] = refs
        
        return entities
    
    def _store_result(
        self,
        message_id: str,
        tenant_id: str,
        conversation_id: str,
        result: ProcessingResult,
    ) -> None:
        """Store processing result in DynamoDB."""
        pk_name = os.environ.get("MESSAGES_PK_NAME", "pk")
        now = datetime.now(timezone.utc).isoformat()
        
        pk = f"BEDROCK#{conversation_id or tenant_id}#{message_id}"
        
        item = {
            pk_name: pk,
            "itemType": "BEDROCK_RESULT",
            "messageId": message_id,
            "tenantId": tenant_id,
            "conversationId": conversation_id or "",
            "contentType": result.content_type,
            "summary": result.summary,
            "extractedText": result.extracted_text[:5000] if result.extracted_text else "",
            "entities": result.entities,
            "intent": result.intent,
            "replyDraft": result.reply_draft[:2000] if result.reply_draft else "",
            "processedAt": now,
        }
        
        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            logger.warning(f"Failed to store Bedrock result: {e}")
