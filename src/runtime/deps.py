# =============================================================================
# DEPENDENCY INJECTION - Lazy-loaded AWS clients and shared resources
# =============================================================================
# Provides a single Deps object that handlers receive, containing:
# - Lazy-loaded AWS clients (DynamoDB, S3, SNS, SQS, socialmessaging)
# - Environment configuration
# - Shared utilities
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
class EnvConfig:
    """Environment configuration loaded lazily."""
    messages_table_name: str = ""
    messages_pk_name: str = "pk"
    media_bucket: str = ""
    media_prefix: str = "WhatsApp/"
    meta_api_version: str = "v20.0"
    waba_phone_map: Dict[str, Any] = field(default_factory=dict)
    
    # Feature flags
    auto_reply_enabled: bool = False
    auto_reply_text: str = "Thanks! We received your message."
    mark_as_read_enabled: bool = True
    react_emoji_enabled: bool = True
    email_notification_enabled: bool = False
    email_sns_topic_arn: str = ""
    
    @classmethod
    def from_env(cls) -> "EnvConfig":
        """Load configuration from environment variables."""
        waba_map = {}
        waba_json = os.environ.get("WABA_PHONE_MAP_JSON", "")
        if waba_json:
            try:
                waba_map = json.loads(waba_json)
            except json.JSONDecodeError:
                logger.warning("Failed to parse WABA_PHONE_MAP_JSON")
        
        return cls(
            messages_table_name=os.environ.get("MESSAGES_TABLE_NAME", "base-wecare-digital-whatsapp"),
            messages_pk_name=os.environ.get("MESSAGES_PK_NAME", "pk"),
            media_bucket=os.environ.get("MEDIA_BUCKET", ""),
            media_prefix=os.environ.get("MEDIA_PREFIX", "WhatsApp/"),
            meta_api_version=os.environ.get("META_API_VERSION", "v20.0"),
            waba_phone_map=waba_map,
            auto_reply_enabled=os.environ.get("AUTO_REPLY_ENABLED", "false").lower() == "true",
            auto_reply_text=os.environ.get("AUTO_REPLY_TEXT", "Thanks! We received your message."),
            mark_as_read_enabled=os.environ.get("MARK_AS_READ_ENABLED", "true").lower() == "true",
            react_emoji_enabled=os.environ.get("REACT_EMOJI_ENABLED", "true").lower() == "true",
            email_notification_enabled=os.environ.get("EMAIL_NOTIFICATION_ENABLED", "false").lower() == "true",
            email_sns_topic_arn=os.environ.get("EMAIL_SNS_TOPIC_ARN", ""),
        )


class Deps:
    """
    Dependency injection container with lazy-loaded AWS clients.
    
    Usage in handlers:
        def handle_my_action(req: RequestModel, deps: Deps) -> ResponseModel:
            # Access clients lazily
            table = deps.table
            social = deps.social
            
            # Access config
            bucket = deps.config.media_bucket
    """
    
    def __init__(self, config: EnvConfig = None):
        """Initialize with optional config (defaults to env vars)."""
        self._config = config
        self._clients: Dict[str, Any] = {}
        self._table = None
    
    @cached_property
    def config(self) -> EnvConfig:
        """Get environment configuration."""
        if self._config is None:
            self._config = EnvConfig.from_env()
        return self._config
    
    def _get_client(self, name: str, service: str = None) -> Any:
        """Get or create a boto3 client."""
        if name not in self._clients:
            self._clients[name] = boto3.client(service or name)
        return self._clients[name]
    
    def _get_resource(self, name: str, service: str = None) -> Any:
        """Get or create a boto3 resource."""
        key = f"resource_{name}"
        if key not in self._clients:
            self._clients[key] = boto3.resource(service or name)
        return self._clients[key]
    
    # AWS Clients (lazy-loaded)
    @cached_property
    def ddb(self):
        """DynamoDB resource."""
        return self._get_resource("dynamodb")
    
    @cached_property
    def table(self):
        """DynamoDB table for messages."""
        return self.ddb.Table(self.config.messages_table_name)
    
    @cached_property
    def s3(self):
        """S3 client."""
        return self._get_client("s3")
    
    @cached_property
    def social(self):
        """AWS End User Messaging Social client (socialmessaging)."""
        return self._get_client("socialmessaging")
    
    @cached_property
    def sns(self):
        """SNS client."""
        return self._get_client("sns")
    
    @cached_property
    def sqs(self):
        """SQS client."""
        return self._get_client("sqs")
    
    @cached_property
    def stepfunctions(self):
        """Step Functions client."""
        return self._get_client("stepfunctions")
    
    @cached_property
    def ec2(self):
        """EC2 client."""
        return self._get_client("ec2")
    
    @cached_property
    def iam(self):
        """IAM client."""
        return self._get_client("iam")
    
    # Helper methods
    def get_waba_config(self, meta_waba_id: str) -> Dict[str, Any]:
        """Get WABA configuration by Meta WABA ID."""
        return self.config.waba_phone_map.get(str(meta_waba_id), {})
    
    def get_phone_arn(self, meta_waba_id: str) -> str:
        """Get phone ARN for a WABA."""
        return self.get_waba_config(meta_waba_id).get("phoneArn", "")
    
    def get_business_name(self, meta_waba_id: str) -> str:
        """Get business name for a WABA."""
        return self.get_waba_config(meta_waba_id).get("businessAccountName", "")


# Global deps instance (created lazily)
_deps: Optional[Deps] = None


def get_deps() -> Deps:
    """Get the global Deps instance."""
    global _deps
    if _deps is None:
        _deps = Deps()
    return _deps


def reset_deps():
    """Reset the global Deps instance (for testing)."""
    global _deps
    _deps = None
