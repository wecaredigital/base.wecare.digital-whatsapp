# =============================================================================
# UNIFIED DISPATCHER - Single entry point for all handlers
# =============================================================================
# Routes requests to appropriate handlers based on:
# - Action name (for action_request events)
# - Event type (for inbound_event events)
# - Job type (for internal_job events)
# =============================================================================

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps

from src.runtime.envelope import Envelope, EnvelopeKind
from src.runtime.deps import Deps, get_deps

logger = logging.getLogger(__name__)

# Type definitions
HandlerFunc = Callable[[Dict[str, Any], Deps], Dict[str, Any]]

# =============================================================================
# HANDLER REGISTRY
# =============================================================================
_ACTION_HANDLERS: Dict[str, HandlerFunc] = {}
_ACTION_METADATA: Dict[str, Dict[str, Any]] = {}
_INBOUND_HANDLERS: List[Callable[[Envelope, Deps], Optional[Dict[str, Any]]]] = []

# Handler categories
CATEGORIES = {
    "messaging": "Send WhatsApp messages (text, media, templates)",
    "media": "Upload, download, and manage media files",
    "templates": "Message template management (AWS EUM)",
    "templates_eum": "AWS EUM template APIs",
    "business_profile": "Business profile management",
    "conversations": "Manage conversation threads",
    "marketing": "Marketing campaigns and templates",
    "webhooks": "Webhook configuration and processing",
    "event_destinations": "AWS EUM event destinations",
    "calling": "WhatsApp calling features",
    "groups": "WhatsApp group management",
    "analytics": "Analytics and reporting",
    "catalogs": "Product catalog management",
    "payments": "Payment processing",
    "media_eum": "AWS EUM media handling",
    "config": "Configuration and settings",
    "utility": "Utility and helper actions",
    "query": "Query and search data",
}


# =============================================================================
# REGISTRATION DECORATORS
# =============================================================================
def register(
    action: str,
    category: str = "general",
    description: str = None,
    requires: List[str] = None,
    deprecated: bool = False,
):
    """
    Decorator to register an action handler.
    
    Args:
        action: Unique action name
        category: Handler category for grouping
        description: Short description (defaults to docstring)
        requires: List of required payload fields
        deprecated: Mark handler as deprecated
    
    Usage:
        @register("send_text", category="messaging", requires=["to", "text"])
        def handle_send_text(payload: Dict, deps: Deps) -> Dict:
            '''Send a text message.'''
            return {"statusCode": 200}
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        desc = description
        if not desc and func.__doc__:
            desc = func.__doc__.split("\n")[0].strip()
        if not desc:
            desc = f"Handle {action} action"
        
        _ACTION_HANDLERS[action] = func
        _ACTION_METADATA[action] = {
            "category": category,
            "description": desc,
            "requires": requires or [],
            "deprecated": deprecated,
            "module": func.__module__,
            "function": func.__name__,
        }
        
        @wraps(func)
        def wrapper(payload: Dict[str, Any], deps: Deps) -> Dict[str, Any]:
            if deprecated:
                logger.warning(f"Action '{action}' is deprecated")
            
            # Validate required fields
            if requires:
                missing = [f for f in requires if not payload.get(f)]
                if missing:
                    return {
                        "statusCode": 400,
                        "error": f"Missing required fields: {', '.join(missing)}"
                    }
            
            return func(payload, deps)
        
        return wrapper
    return decorator


def register_handler(
    action: str,
    handler: HandlerFunc,
    category: str = "general",
    description: str = None,
    requires: List[str] = None,
):
    """Manually register a handler function."""
    desc = description
    if not desc and handler.__doc__:
        desc = handler.__doc__.split("\n")[0].strip()
    if not desc:
        desc = f"Handle {action} action"
    
    _ACTION_HANDLERS[action] = handler
    _ACTION_METADATA[action] = {
        "category": category,
        "description": desc,
        "requires": requires or [],
        "deprecated": False,
        "module": handler.__module__,
        "function": handler.__name__,
    }


def register_inbound_handler(handler: Callable[[Envelope, Deps], Optional[Dict[str, Any]]]):
    """Register a handler for inbound events (SNS from AWS EUM)."""
    _INBOUND_HANDLERS.append(handler)


# =============================================================================
# DISPATCH FUNCTIONS
# =============================================================================
def dispatch(envelope: Envelope, deps: Deps = None) -> Dict[str, Any]:
    """
    Main dispatch function - routes envelope to appropriate handler.
    
    Args:
        envelope: Normalized event envelope
        deps: Dependency injection container (defaults to global)
        
    Returns:
        Handler response dict
    """
    if deps is None:
        deps = get_deps()
    
    logger.info(f"dispatch: kind={envelope.kind.value}, action={envelope.action}, source={envelope.source}")
    
    if envelope.is_action_request():
        return _dispatch_action(envelope, deps)
    elif envelope.is_inbound_event():
        return _dispatch_inbound(envelope, deps)
    elif envelope.is_internal_job():
        return _dispatch_job(envelope, deps)
    else:
        return {
            "statusCode": 400,
            "error": f"Unknown envelope kind: {envelope.kind.value}"
        }


def dispatch_with_deps(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Dispatch with explicit deps (for testing)."""
    return dispatch(envelope, deps)


def _dispatch_action(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Dispatch an action request to registered handler."""
    action = envelope.action
    
    if not action:
        return {
            "statusCode": 400,
            "error": "No action specified",
            "hint": "Use action='help' to see available actions"
        }
    
    # Special actions
    if action == "help":
        return _generate_help()
    elif action == "list_actions":
        return _list_actions()
    elif action == "_sns_subscription_confirmation":
        return _handle_sns_subscription(envelope, deps)
    
    # Look up handler
    handler = _ACTION_HANDLERS.get(action)
    if handler:
        try:
            return handler(envelope.payload, deps)
        except Exception as e:
            logger.exception(f"Handler error for action '{action}': {e}")
            return {"statusCode": 500, "error": f"Internal error: {str(e)}"}
    
    # Action not found
    return {
        "statusCode": 400,
        "error": f"Unknown action: {action}",
        "availableActions": list(_ACTION_HANDLERS.keys())[:20],
        "hint": "Use action='help' to see all available actions"
    }


def _dispatch_inbound(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Dispatch inbound events to registered handlers."""
    results = []
    
    for handler in _INBOUND_HANDLERS:
        try:
            result = handler(envelope, deps)
            if result:
                results.append(result)
        except Exception as e:
            logger.exception(f"Inbound handler error: {e}")
            results.append({"error": str(e)})
    
    return {
        "statusCode": 200,
        "processed": len(results),
        "results": results,
    }


def _dispatch_job(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Dispatch internal job to handler."""
    job_type = envelope.action
    
    # Look up job handler (same registry as actions)
    handler = _ACTION_HANDLERS.get(f"job_{job_type}") or _ACTION_HANDLERS.get(job_type)
    if handler:
        try:
            return handler(envelope.payload, deps)
        except Exception as e:
            logger.exception(f"Job handler error for '{job_type}': {e}")
            return {"statusCode": 500, "error": f"Job error: {str(e)}"}
    
    return {
        "statusCode": 400,
        "error": f"Unknown job type: {job_type}"
    }


def _handle_sns_subscription(envelope: Envelope, deps: Deps) -> Dict[str, Any]:
    """Handle SNS subscription confirmation."""
    subscribe_url = envelope.metadata.get("subscribe_url")
    if subscribe_url:
        try:
            import urllib.request
            urllib.request.urlopen(subscribe_url, timeout=10)
            return {"statusCode": 200, "message": "Subscription confirmed"}
        except Exception as e:
            logger.exception(f"Failed to confirm SNS subscription: {e}")
            return {"statusCode": 500, "error": str(e)}
    return {"statusCode": 400, "error": "No subscribe URL"}


# =============================================================================
# QUERY FUNCTIONS
# =============================================================================
def get_handler(action: str) -> Optional[HandlerFunc]:
    """Get handler function for an action."""
    return _ACTION_HANDLERS.get(action)


def handler_exists(action: str) -> bool:
    """Check if a handler exists."""
    return action in _ACTION_HANDLERS


def get_handler_metadata(action: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a handler."""
    return _ACTION_METADATA.get(action)


def list_all_actions() -> Dict[str, str]:
    """List all registered actions with descriptions."""
    return {
        action: meta["description"]
        for action, meta in _ACTION_METADATA.items()
        if not meta.get("deprecated")
    }


def list_actions_by_category() -> Dict[str, List[str]]:
    """Get actions grouped by category."""
    categories: Dict[str, List[str]] = {}
    for action, meta in _ACTION_METADATA.items():
        if meta.get("deprecated"):
            continue
        cat = meta.get("category", "general")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(action)
    return categories


def get_handler_count() -> int:
    """Get total count of registered handlers."""
    return len(_ACTION_HANDLERS)


# =============================================================================
# HELP GENERATION
# =============================================================================
def _generate_help() -> Dict[str, Any]:
    """Generate comprehensive help documentation."""
    by_category = list_actions_by_category()
    
    return {
        "statusCode": 200,
        "totalActions": get_handler_count(),
        "categories": {
            cat: {
                "description": CATEGORIES.get(cat, "General handlers"),
                "actions": sorted(actions)
            }
            for cat, actions in sorted(by_category.items())
        },
    }


def _list_actions() -> Dict[str, Any]:
    """List all available actions."""
    return {
        "statusCode": 200,
        "actions": list_all_actions(),
        "count": get_handler_count(),
    }
