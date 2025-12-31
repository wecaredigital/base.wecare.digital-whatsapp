# =============================================================================
# Application Entry Points
# =============================================================================
# Thin transport adapters that parse events and call the unified dispatcher.
# =============================================================================

from src.app.api_handler import api_handler
from src.app.inbound_handler import inbound_handler
from src.app.direct_handler import direct_handler

__all__ = [
    "api_handler",
    "inbound_handler", 
    "direct_handler",
]
