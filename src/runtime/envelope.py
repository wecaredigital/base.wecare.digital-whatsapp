# =============================================================================
# Envelope - Normalized Event Container
# =============================================================================
# All inputs (API Gateway, SNS/SQS, direct invoke, CLI) are normalized into
# a common Envelope structure for unified processing.
# =============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from datetime import datetime, timezone


class EnvelopeKind(str, Enum):
    """Types of events that can be processed."""
    ACTION_REQUEST = "action_request"      # API Gateway / direct invoke / CLI
    INBOUND_EVENT = "inbound_event"        # SQS message from SNS event destination
    INTERNAL_JOB = "internal_job"          # Step Functions / scheduled tasks
    WEBHOOK_EVENT = "webhook_event"        # Webhook callbacks
    UNKNOWN = "unknown"


@dataclass
class Envelope:
    """
    Normalized event container for all trigger sources.
    
    Attributes:
        kind: Type of event (action_request, inbound_event, internal_job)
        request_id: Unique identifier for this request
        tenant_id: Tenant/WABA identifier
        source: Origin of the event (api_gateway, sns, sqs, direct, cli)
        payload: The actual event data (action + parameters)
        raw_event: Original unmodified event for debugging
        timestamp: When the envelope was created
        trace_id: Distributed tracing ID
        metadata: Additional context (headers, attributes, etc.)
    """
    kind: EnvelopeKind
    request_id: str
    tenant_id: str
    source: str
    payload: Dict[str, Any]
    raw_event: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def action(self) -> str:
        """Get the action name from payload."""
        return self.payload.get("action", "")
    
    @property
    def is_action_request(self) -> bool:
        """Check if this is an action request (API/CLI/direct)."""
        return self.kind == EnvelopeKind.ACTION_REQUEST
    
    @property
    def is_inbound_event(self) -> bool:
        """Check if this is an inbound WhatsApp event."""
        return self.kind == EnvelopeKind.INBOUND_EVENT
    
    @property
    def is_internal_job(self) -> bool:
        """Check if this is an internal job (Step Functions, etc.)."""
        return self.kind == EnvelopeKind.INTERNAL_JOB
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from payload."""
        return self.payload.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary."""
        return {
            "kind": self.kind.value,
            "requestId": self.request_id,
            "tenantId": self.tenant_id,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "traceId": self.trace_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_action_request(
        cls,
        payload: Dict[str, Any],
        source: str = "direct",
        tenant_id: str = "",
        request_id: str = None,
        raw_event: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create envelope from action request."""
        return cls(
            kind=EnvelopeKind.ACTION_REQUEST,
            request_id=request_id or str(uuid.uuid4()),
            tenant_id=tenant_id or payload.get("metaWabaId", "") or payload.get("tenantId", ""),
            source=source,
            payload=payload,
            raw_event=raw_event or payload,
            metadata=metadata or {},
        )
    
    @classmethod
    def from_inbound_event(
        cls,
        payload: Dict[str, Any],
        source: str = "sqs",
        tenant_id: str = "",
        request_id: str = None,
        raw_event: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create envelope from inbound WhatsApp event."""
        return cls(
            kind=EnvelopeKind.INBOUND_EVENT,
            request_id=request_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            source=source,
            payload=payload,
            raw_event=raw_event or payload,
            metadata=metadata or {},
        )
    
    @classmethod
    def from_internal_job(
        cls,
        payload: Dict[str, Any],
        source: str = "step_functions",
        tenant_id: str = "",
        request_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> "Envelope":
        """Create envelope from internal job."""
        return cls(
            kind=EnvelopeKind.INTERNAL_JOB,
            request_id=request_id or str(uuid.uuid4()),
            tenant_id=tenant_id or payload.get("tenantId", ""),
            source=source,
            payload=payload,
            raw_event=payload,
            metadata=metadata or {},
        )
