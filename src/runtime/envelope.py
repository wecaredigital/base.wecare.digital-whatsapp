# =============================================================================
# ENVELOPE - Normalized event wrapper for all trigger types
# =============================================================================
# Provides a unified interface for events from:
# - API Gateway (HTTP)
# - SNS (AWS EUM event destination)
# - Lambda direct invoke (internal workflows)
# - CLI (developer/admin tooling)
# =============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid


class EnvelopeKind(Enum):
    """Types of events that can be processed."""
    ACTION_REQUEST = "action_request"      # API Gateway / direct invoke / CLI
    INBOUND_EVENT = "inbound_event"        # SNS from AWS EUM
    INTERNAL_JOB = "internal_job"          # Step Functions / scheduled tasks
    UNKNOWN = "unknown"


@dataclass
class Envelope:
    """
    Normalized event envelope for all trigger types.
    
    This provides a single interface for handlers regardless of how
    the Lambda was invoked (API Gateway, SNS, direct invoke, CLI).
    
    Attributes:
        kind: Type of event (action_request, inbound_event, internal_job)
        request_id: Unique identifier for this request
        tenant_id: Tenant/WABA identifier (metaWabaId)
        source: Source of the event (api_gateway, sns, direct, cli)
        action: Action name for action_request events
        payload: The actual event payload (normalized)
        raw_event: Original Lambda event (for debugging)
        timestamp: When the event was received
        metadata: Additional context (headers, SNS attributes, etc.)
    """
    kind: EnvelopeKind
    request_id: str
    source: str
    payload: Dict[str, Any]
    raw_event: Dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    action: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def action_request(
        cls,
        action: str,
        payload: Dict[str, Any],
        source: str = "direct",
        tenant_id: str = "",
        request_id: str = None,
        raw_event: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create an action request envelope."""
        return cls(
            kind=EnvelopeKind.ACTION_REQUEST,
            request_id=request_id or str(uuid.uuid4()),
            source=source,
            action=action,
            payload=payload,
            tenant_id=tenant_id or payload.get("metaWabaId", ""),
            raw_event=raw_event or {},
            metadata=metadata or {},
        )
    
    @classmethod
    def inbound_event(
        cls,
        payload: Dict[str, Any],
        tenant_id: str = "",
        request_id: str = None,
        raw_event: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create an inbound event envelope (from SNS/AWS EUM)."""
        return cls(
            kind=EnvelopeKind.INBOUND_EVENT,
            request_id=request_id or str(uuid.uuid4()),
            source="sns",
            action="",  # Inbound events don't have actions
            payload=payload,
            tenant_id=tenant_id,
            raw_event=raw_event or {},
            metadata=metadata or {},
        )
    
    @classmethod
    def internal_job(
        cls,
        job_type: str,
        payload: Dict[str, Any],
        request_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create an internal job envelope (Step Functions, scheduled)."""
        return cls(
            kind=EnvelopeKind.INTERNAL_JOB,
            request_id=request_id or str(uuid.uuid4()),
            source="internal",
            action=job_type,
            payload=payload,
            raw_event={},
            metadata=metadata or {},
        )
    
    def is_action_request(self) -> bool:
        """Check if this is an action request."""
        return self.kind == EnvelopeKind.ACTION_REQUEST
    
    def is_inbound_event(self) -> bool:
        """Check if this is an inbound event from SNS."""
        return self.kind == EnvelopeKind.INBOUND_EVENT
    
    def is_internal_job(self) -> bool:
        """Check if this is an internal job."""
        return self.kind == EnvelopeKind.INTERNAL_JOB
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the payload."""
        return self.payload.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary."""
        return {
            "kind": self.kind.value,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "action": self.action,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
