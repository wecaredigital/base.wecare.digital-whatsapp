# =============================================================================
# Direct Invoke Handler
# =============================================================================
# Entry point for direct Lambda invocations and internal workflows.
# =============================================================================

import logging
from typing import Any, Dict
from src.runtime.envelope import Envelope
from src.runtime.parse_event import parse_event
from src.runtime.dispatch import dispatch
from src.runtime.deps import create_deps

logger = logging.getLogger(__name__)


def direct_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Direct invoke entry point.
    
    Handles:
    - Direct Lambda invocations
    - Step Functions tasks
    - Internal workflow calls
    
    Args:
        event: Direct invoke event (should contain 'action')
        context: Lambda context
        
    Returns:
        Handler response
    """
    logger.info(f"DIRECT_HANDLER event keys: {list(event.keys())}")
    
    # Parse event into envelope
    envelopes, source = parse_event(event)
    
    if not envelopes:
        return {
            "statusCode": 400,
            "error": "Could not parse request",
        }
    
    envelope = envelopes[0]
    
    # Create deps and dispatch
    deps = create_deps()
    result = dispatch(envelope, deps)
    
    return result
