# =============================================================================
# Runtime Package - Unified Dispatch System
# =============================================================================
# Provides a single core dispatch layer invokable via:
# - API Gateway (HTTP)
# - SNS → SQS (AWS EUM event destination)
# - Lambda direct invoke (internal workflows)
# - CLI (developer/admin tooling)
# =============================================================================

from src.runtime.envelope import Envelope, EnvelopeKind
from src.runtime.parse_event import parse_event, detect_event_source
from src.runtime.dispatch import dispatch, dispatch_with_deps
from src.runtime.deps import Deps, create_deps

__all__ = [
    "Envelope",
    "EnvelopeKind",
    "parse_event",
    "detect_event_source",
    "dispatch",
    "dispatch_with_deps",
    "Deps",
    "create_deps",
]
