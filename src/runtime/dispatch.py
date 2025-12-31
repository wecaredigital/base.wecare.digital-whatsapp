# =============================================================================
# Unified Dispatcher
# =============================================================================
# Single entry point for all handler dispatch.
# Works with API Gateway, SNS/SQS, direct invoke, and CLI.
# =============================================================================

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.runtime.envelope import Envelope, EnvelopeKind
from src.runtime.deps import Deps, get_deps

logger = logging.getLogger(__name__)

# Type definitions
HandlerFunc = Callable[[Dict[str, Any], Deps], Dict[str, Any]]

# =============================================================================
# HANDLER REGISTRY
# =============================================================================
_HANDLERS: Dict[str, HandlerFunc] = {}
_HANDLER_METADATA: Dict[str, Dict[str, Any]] = {}


def register(action: str, category: str = "general", description: str = None, requires: List[str] = None):
    """
    Decorator to register a handler.
    
    Usage:
        @register("my_action", category="messaging", requires=["to", "text"])
        def handle_my_action(req: Dict, deps: Deps) -> Dict:
            return {"statusCode": 200}
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        desc = description
        if not desc and func.__doc__:
            desc = func.__doc__.split("\n")[0].strip()
        if not desc:
            desc = f"Handle {action} action"
        
        _HANDLERS[action] = func
        _HANDLER_METADATA[action] = {
            "category": category,
            "description": desc,
            "requires": requires or [],
            "module": func.__module__,
            "function": func.__name__,
        }
        return func
    return decorator


def register_handler(action: str, handler: HandlerFunc, category: str = "general", 
                     description: str = None, requires: List[str] = None):
    """Manually register a handler function."""
    desc = description
    if not desc and handler.__doc__:
        desc = handler.__doc__.split("\n")[0].strip()
    if not desc:
        desc = f"Handle {action} action"
    
    _HANDLERS[action] = handler
    _HANDLER_METADATA[action] = {
        "category": category,
        "description": desc,
        "requires": requires or [],
        "module": handler.__module__,
        "function": handler.__name__,
    }


def get_handler(action: str) -> Optional[HandlerFunc]:
    """Get handler for an action."""
    return _HANDLERS.get(action)


def handler_exists(action: str) -> bool:
    """Check if handler exists."""
    return action in _HANDLERS


def list_handlers() -> Dict[str, str]:
    """List all handlers with descriptions."""
    return {action: meta["description"] for action, meta in _HANDLER_METADATA.items()}


def get_handlers_by_category() -> Dict[str, List[str]]:
    """Get handlers grouped by category."""
    categories: Dict[str, List[str]] = {}
    for action, meta in _HANDLER_METADATA.items():
        cat = meta.get("category", "general")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(action)
    return categories


# =============================================================================
# DISPATCH FUNCTIONS
# =============================================================================

def dispatch(envelope: Envelope, deps: Deps = None) -> Dict[str, Any]:
    """
    Dispatch envelope to appropriate handler.
    
    This is the main entry point for all handler dispatch.
    
    Args:
        envelope: Normalized event envelope
        deps: Dependency injection container (optional, uses global if not provided)
        
    Returns:
        Handler response dict
    """
    if deps is None:
        deps = get_deps()
    
    action = envelope.action
    
    if not action:
        logger.warning(f"No action in envelope: {envelope.kind}")
        return {
            "statusCode": 400,
            "error": "No action specified",
            "hint": "Include 'action' field in request payload",
        }
    
    # Ensure handlers are loaded
    _ensure_handlers_loaded()
    
    logger.info(f"Dispatching action={action} kind={envelope.kind} source={envelope.source}")
    
    handler = _HANDLERS.get(action)
    if not handler:
        logger.warning(f"Unknown action: {action}")
        return {
            "statusCode": 400,
            "error": f"Unknown action: {action}",
            "availableActions": list(_HANDLERS.keys())[:20],
            "hint": "Use action='list_actions' to see all available actions",
        }
    
    # Validate required fields
    meta = _HANDLER_METADATA.get(action, {})
    requires = meta.get("requires", [])
    if requires:
        missing = [f for f in requires if not envelope.get(f)]
        if missing:
            return {
                "statusCode": 400,
                "error": f"Missing required fields: {', '.join(missing)}",
                "action": action,
            }
    
    try:
        # Call handler with payload and deps
        result = handler(envelope.payload, deps)
        
        # Add request metadata to response
        if isinstance(result, dict):
            result["_requestId"] = envelope.request_id
            result["_action"] = action
        
        return result
        
    except Exception as e:
        logger.exception(f"Handler error for action '{action}': {e}")
        return {
            "statusCode": 500,
            "error": f"Internal error: {str(e)}",
            "action": action,
            "_requestId": envelope.request_id,
        }


def dispatch_with_deps(action: str, payload: Dict[str, Any], deps: Deps = None) -> Dict[str, Any]:
    """
    Convenience function to dispatch action directly.
    
    Creates an envelope internally and dispatches.
    
    Args:
        action: Action name
        payload: Request payload (should include action)
        deps: Dependency injection container
        
    Returns:
        Handler response dict
    """
    from src.runtime.envelope import Envelope
    
    if "action" not in payload:
        payload = {"action": action, **payload}
    
    envelope = Envelope.from_action_request(payload)
    return dispatch(envelope, deps)


# =============================================================================
# HANDLER LOADING
# =============================================================================

_handlers_loaded = False


def _ensure_handlers_loaded():
    """Ensure all handlers are loaded into registry."""
    global _handlers_loaded
    if _handlers_loaded:
        return
    _handlers_loaded = True
    
    try:
        logger.info("Loading handlers into unified registry...")
        
        # Import extended handlers from existing system
        from handlers.extended import EXTENDED_HANDLERS, get_extended_actions_by_category
        
        # Get category mapping
        categories = get_extended_actions_by_category()
        action_to_category = {}
        for cat, actions in categories.items():
            cat_key = cat.lower().replace(" & ", "_").replace(" ", "_")
            for action in actions:
                action_to_category[action] = cat_key
        
        # Register all extended handlers
        for action, handler in EXTENDED_HANDLERS.items():
            if action not in _HANDLERS:
                category = action_to_category.get(action, "extended")
                desc = None
                if handler.__doc__:
                    desc = handler.__doc__.split("\n")[0].strip()
                
                # Wrap handler to accept (payload, deps) signature
                wrapped = _wrap_legacy_handler(handler)
                register_handler(action, wrapped, category, desc)
        
        logger.info(f"Loaded {len(_HANDLERS)} handlers into unified registry")
        
    except ImportError as e:
        logger.warning(f"Could not import handlers: {e}")
    except Exception as e:
        logger.exception(f"Error loading handlers: {e}")


def _wrap_legacy_handler(handler: Callable) -> HandlerFunc:
    """Wrap legacy handler (event, context) to new signature (payload, deps)."""
    def wrapped(payload: Dict[str, Any], deps: Deps) -> Dict[str, Any]:
        # Legacy handlers expect (event, context) - pass payload as event, None as context
        return handler(payload, None)
    
    # Preserve docstring
    wrapped.__doc__ = handler.__doc__
    wrapped.__name__ = handler.__name__
    wrapped.__module__ = handler.__module__
    
    return wrapped


# =============================================================================
# BUILT-IN HANDLERS
# =============================================================================

@register("help", category="utility", description="Get help documentation")
def handle_help(payload: Dict[str, Any], deps: Deps) -> Dict[str, Any]:
    """Get comprehensive help documentation."""
    _ensure_handlers_loaded()
    
    by_category = get_handlers_by_category()
    
    return {
        "statusCode": 200,
        "totalActions": len(_HANDLERS),
        "categories": {
            cat: {
                "count": len(actions),
                "actions": sorted(actions),
            }
            for cat, actions in sorted(by_category.items())
        },
    }


@register("list_actions", category="utility", description="List all available actions")
def handle_list_actions(payload: Dict[str, Any], deps: Deps) -> Dict[str, Any]:
    """List all available actions with descriptions."""
    _ensure_handlers_loaded()
    
    category_filter = payload.get("category")
    
    if category_filter:
        by_category = get_handlers_by_category()
        actions = by_category.get(category_filter, [])
        return {
            "statusCode": 200,
            "category": category_filter,
            "count": len(actions),
            "actions": {
                action: _HANDLER_METADATA.get(action, {}).get("description", "")
                for action in sorted(actions)
            },
        }
    
    return {
        "statusCode": 200,
        "count": len(_HANDLERS),
        "actions": {
            action: meta["description"]
            for action, meta in sorted(_HANDLER_METADATA.items())
        },
    }


@register("ping", category="utility", description="Health check")
def handle_ping(payload: Dict[str, Any], deps: Deps) -> Dict[str, Any]:
    """Health check endpoint."""
    from datetime import datetime, timezone
    
    return {
        "statusCode": 200,
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "handlerCount": len(_HANDLERS),
    }
