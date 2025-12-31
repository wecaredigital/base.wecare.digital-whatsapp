# =============================================================================
# Dependency Injection Container
# =============================================================================
# Provides lazy-loaded AWS clients and shared services to handlers.
# Handlers receive Deps instead of creating their own clients.
# =============================================================================

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import boto3
from functools import cached_property

logger = logging.getLogger(__name__)


@dataclass
class Deps:
    """
    Dependency injection container for handlers.
    
    All AWS clients are lazy-loaded on first access.
    Handlers should use this instead of creating their own clients.
    
    Usage:
        def handle_my_action(req: Dict, deps: Deps) -> Dict:
            # Use deps.social for socialmessaging client
            deps.social.send_whatsapp_message(...)
            
            # Use deps.table for DynamoDB table
            deps.table.put_item(...)
    """
    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "ap-south-1"))
    _clients: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    # ==========================================================================
    # AWS Clients (lazy-loaded)
    # ==========================================================================
    
    @cached_property
    def dynamodb(self):
        """DynamoDB resource."""
        return boto3.resource("dynamodb", region_name=self.region)
    
    @cached_property
    def table(self):
        """DynamoDB table for messages."""
        table_name = os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp")
        return self.dynamodb.Table(table_name)
    
    @cached_property
    def s3(self):
        """S3 client."""
        return boto3.client("s3", region_name=self.region)
    
    @cached_property
    def social(self):
        """AWS Social Messaging client (socialmessaging)."""
        return boto3.client("socialmessaging", region_name=self.region)
    
    @cached_property
    def sns(self):
        """SNS client."""
        return boto3.client("sns", region_name=self.region)
    
    @cached_property
    def sqs(self):
        """SQS client."""
        return boto3.client("sqs", region_name=self.region)
    
    @cached_property
    def ses(self):
        """SES client."""
        ses_region = os.environ.get("SES_REGION", self.region)
        return boto3.client("ses", region_name=ses_region)
    
    @cached_property
    def eventbridge(self):
        """EventBridge client."""
        return boto3.client("events", region_name=self.region)
    
    @cached_property
    def stepfunctions(self):
        """Step Functions client."""
        return boto3.client("stepfunctions", region_name=self.region)
    
    @cached_property
    def bedrock_runtime(self):
        """Bedrock Runtime client (for agent invocation)."""
        bedrock_region = os.environ.get("BEDROCK_REGION", "ap-south-1")
        return boto3.client("bedrock-runtime", region_name=bedrock_region)
    
    @cached_property
    def bedrock_agent_runtime(self):
        """Bedrock Agent Runtime client."""
        bedrock_region = os.environ.get("BEDROCK_REGION", "ap-south-1")
        return boto3.client("bedrock-agent-runtime", region_name=bedrock_region)
    
    @cached_property
    def ec2(self):
        """EC2 client (for VPC endpoint checks)."""
        return boto3.client("ec2", region_name=self.region)
    
    @cached_property
    def iam(self):
        """IAM client (for service-linked role checks)."""
        return boto3.client("iam", region_name=self.region)
    
    # ==========================================================================
    # Configuration
    # ==========================================================================
    
    @cached_property
    def config(self) -> Dict[str, Any]:
        """Environment configuration."""
        return {
            "MESSAGES_TABLE_NAME": os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp"),
            "MESSAGES_PK_NAME": os.environ.get("MESSAGES_PK_NAME", "pk"),
            "MEDIA_BUCKET": os.environ.get("MEDIA_BUCKET", "dev.wecare.digital"),
            "MEDIA_PREFIX": os.environ.get("MEDIA_PREFIX", "WhatsApp/"),
            "META_API_VERSION": os.environ.get("META_API_VERSION", "v20.0"),
            "AUTO_REPLY_ENABLED": os.environ.get("AUTO_REPLY_ENABLED", "false").lower() == "true",
            "AUTO_REPLY_TEXT": os.environ.get("AUTO_REPLY_TEXT", "Thanks! We received your message."),
            "ECHO_MEDIA_BACK": os.environ.get("ECHO_MEDIA_BACK", "true").lower() == "true",
            "MARK_AS_READ_ENABLED": os.environ.get("MARK_AS_READ_ENABLED", "true").lower() == "true",
            "REACT_EMOJI_ENABLED": os.environ.get("REACT_EMOJI_ENABLED", "true").lower() == "true",
            "EMAIL_NOTIFICATION_ENABLED": os.environ.get("EMAIL_NOTIFICATION_ENABLED", "true").lower() == "true",
            "EMAIL_SNS_TOPIC_ARN": os.environ.get("EMAIL_SNS_TOPIC_ARN", ""),
            "SES_SENDER_EMAIL": os.environ.get("SES_SENDER_EMAIL", "noreply@wecare.digital"),
            "INBOUND_NOTIFY_TO": os.environ.get("INBOUND_NOTIFY_TO", "ops@wecare.digital"),
            "OUTBOUND_NOTIFY_TO": os.environ.get("OUTBOUND_NOTIFY_TO", "ops@wecare.digital"),
            "AUTO_WELCOME_ENABLED": os.environ.get("AUTO_WELCOME_ENABLED", "false").lower() == "true",
            "AUTO_MENU_ON_KEYWORDS": os.environ.get("AUTO_MENU_ON_KEYWORDS", "true").lower() == "true",
            "WELCOME_COOLDOWN_HOURS": int(os.environ.get("WELCOME_COOLDOWN_HOURS", "72")),
            "AUTO_REPLY_BEDROCK_ENABLED": os.environ.get("AUTO_REPLY_BEDROCK_ENABLED", "false").lower() == "true",
            "BEDROCK_AGENT_ID": os.environ.get("BEDROCK_AGENT_ID", ""),
            "BEDROCK_AGENT_ALIAS_ID": os.environ.get("BEDROCK_AGENT_ALIAS_ID", ""),
            "BEDROCK_KB_ID": os.environ.get("BEDROCK_KB_ID", ""),
        }
    
    @cached_property
    def waba_phone_map(self) -> Dict[str, Any]:
        """WABA to phone number mapping."""
        raw = os.environ.get("WABA_PHONE_MAP_JSON", "{}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse WABA_PHONE_MAP_JSON")
            return {}
    
    def get_waba_config(self, meta_waba_id: str) -> Dict[str, Any]:
        """Get WABA configuration by Meta WABA ID."""
        return self.waba_phone_map.get(str(meta_waba_id), {})
    
    def get_phone_arn(self, meta_waba_id: str) -> str:
        """Get phone ARN for a WABA."""
        return self.get_waba_config(meta_waba_id).get("phoneArn", "")
    
    # ==========================================================================
    # Helper Methods
    # ==========================================================================
    
    def origination_id_for_api(self, phone_arn: str) -> str:
        """Convert phone ARN to API format."""
        if not phone_arn:
            return ""
        if "phone-number-id/" in phone_arn:
            suffix = phone_arn.split("phone-number-id/")[-1]
            return f"phone-number-id-{suffix}"
        return phone_arn
    
    def format_wa_number(self, wa_id: str) -> str:
        """Format WhatsApp number with + prefix."""
        if not wa_id:
            return ""
        wa_id = wa_id.strip()
        if not wa_id.startswith("+"):
            return f"+{wa_id}"
        return wa_id
    
    def generate_presigned_url(self, bucket: str, key: str, expiry: int = 86400) -> str:
        """Generate S3 presigned URL."""
        if not bucket or not key:
            return ""
        try:
            return self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiry
            )
        except Exception:
            return f"s3://{bucket}/{key}"


def create_deps(region: str = None) -> Deps:
    """Create a new Deps instance."""
    return Deps(region=region or os.environ.get("AWS_REGION", "ap-south-1"))


# Global deps instance (for backward compatibility)
_global_deps: Optional[Deps] = None


def get_deps() -> Deps:
    """Get or create global Deps instance."""
    global _global_deps
    if _global_deps is None:
        _global_deps = create_deps()
    return _global_deps
