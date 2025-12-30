# =============================================================================
# UNIFIED HANDLER DISPATCHER
# =============================================================================
# Production-grade unified dispatcher for all WhatsApp Business API handlers.
# 
# FEATURES:
# - Single entry point for ALL handlers (core + extended)
# - Auto-registration via decorator
# - Category-based organization
# - Built-in documentation generation
# - Easy to extend for future upgrades
#
# USAGE:
#     from handlers.dispatcher import unified_dispatch, register, list_all_actions
#     
#     # Register a handler
#     @register("my_action", category="my_category")
#     def handle_my_action(event, context):
#         return {"statusCode": 200}
#     
#     # Dispatch in lambda_handler
#     result = unified_dispatch(action, event, context)
# =============================================================================

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps

logger = logging.getLogger()

# Type definitions
HandlerFunc = Callable[[Dict[str, Any], Any], Dict[str, Any]]

# =============================================================================
# GLOBAL REGISTRY
# =============================================================================
_REGISTRY: Dict[str, HandlerFunc] = {}
_METADATA: Dict[str, Dict[str, Any]] = {}

# Handler categories with descriptions
CATEGORIES = {
    "messaging": "Send WhatsApp messages (text, media, templates)",
    "media": "Upload, download, and manage media files",
    "conversations": "Manage conversation threads",
    "templates": "Message template management",
    "business_profile": "Business profile management",
    "marketing": "Marketing campaigns and templates",
    "webhooks": "Webhook configuration and processing",
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
# REGISTRATION DECORATOR
# =============================================================================
def register(action: str, category: str = "general", description: str = None, 
             requires: List[str] = None, deprecated: bool = False):
    """
    Decorator to register a handler in the unified registry.
    
    Args:
        action: Unique action name (e.g., "send_text", "get_analytics")
        category: Handler category for grouping
        description: Short description (defaults to first line of docstring)
        requires: List of required event fields
        deprecated: Mark handler as deprecated
    
    Usage:
        @register("send_text", category="messaging", requires=["to", "text"])
        def handle_send_text(event, context):
            '''Send a text message to a WhatsApp number.'''
            return {"statusCode": 200}
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        # Extract description from docstring if not provided
        desc = description
        if not desc and func.__doc__:
            desc = func.__doc__.split("\n")[0].strip()
        if not desc:
            desc = f"Handle {action} action"
        
        # Register handler
        _REGISTRY[action] = func
        _METADATA[action] = {
            "category": category,
            "description": desc,
            "requires": requires or [],
            "deprecated": deprecated,
            "module": func.__module__,
            "function": func.__name__,
        }
        
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Log deprecated warning
            if deprecated:
                logger.warning(f"Action '{action}' is deprecated")
            
            # Validate required fields if specified
            if requires:
                missing = [f for f in requires if not event.get(f)]
                if missing:
                    return {
                        "statusCode": 400,
                        "error": f"Missing required fields: {', '.join(missing)}"
                    }
            
            return func(event, context)
        
        return wrapper
    return decorator


# =============================================================================
# MANUAL REGISTRATION (for handlers defined elsewhere)
# =============================================================================
def register_handler(action: str, handler: HandlerFunc, category: str = "general",
                     description: str = None, requires: List[str] = None):
    """
    Manually register a handler function.
    
    Use this for handlers defined in other modules that can't use the decorator.
    
    Args:
        action: Unique action name
        handler: Handler function
        category: Handler category
        description: Short description
        requires: List of required event fields
    """
    desc = description
    if not desc and handler.__doc__:
        desc = handler.__doc__.split("\n")[0].strip()
    if not desc:
        desc = f"Handle {action} action"
    
    _REGISTRY[action] = handler
    _METADATA[action] = {
        "category": category,
        "description": desc,
        "requires": requires or [],
        "deprecated": False,
        "module": handler.__module__,
        "function": handler.__name__,
    }


def register_bulk(handlers: Dict[str, Tuple[HandlerFunc, str, str]]):
    """
    Register multiple handlers at once.
    
    Args:
        handlers: Dict of {action: (handler_func, category, description)}
    """
    for action, (handler, category, description) in handlers.items():
        register_handler(action, handler, category, description)


# =============================================================================
# UNIFIED DISPATCH
# =============================================================================
def unified_dispatch(action: str, event: Dict[str, Any], context: Any) -> Optional[Dict[str, Any]]:
    """
    Unified dispatcher for all registered handlers.
    
    This is the main entry point called from lambda_handler.
    Returns None if action is not registered, allowing fallback processing.
    
    Args:
        action: The action name from the event
        event: The full Lambda event
        context: The Lambda context
        
    Returns:
        Handler response dict, or None if action not found
    """
    # Ensure extended handlers are loaded
    _init_extended_handlers()
    
    logger.info(f"unified_dispatch: action={action}, registry_size={len(_REGISTRY)}")
    
    handler = _REGISTRY.get(action)
    if handler:
        logger.info(f"Found handler for action: {action}")
        try:
            return handler(event, context)
        except Exception as e:
            logger.exception(f"Handler error for action '{action}': {e}")
            return {"statusCode": 500, "error": f"Internal error: {str(e)}"}
    
    logger.info(f"No handler found for action: {action}")
    return None


def dispatch_with_validation(action: str, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Dispatch with automatic validation and error handling.
    
    Unlike unified_dispatch, this returns an error response for unknown actions.
    """
    # Ensure extended handlers are loaded
    _init_extended_handlers()
    
    if action not in _REGISTRY:
        return {
            "statusCode": 400,
            "error": f"Unknown action: {action}",
            "availableActions": list(_REGISTRY.keys())[:20],
            "hint": "Use action='help' to see all available actions"
        }
    return unified_dispatch(action, event, context)


# =============================================================================
# QUERY FUNCTIONS
# =============================================================================
def get_handler(action: str) -> Optional[HandlerFunc]:
    """Get handler function for an action."""
    return _REGISTRY.get(action)


def handler_exists(action: str) -> bool:
    """Check if a handler exists for the given action."""
    return action in _REGISTRY


def get_handler_metadata(action: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a handler."""
    return _METADATA.get(action)


def list_all_actions() -> Dict[str, str]:
    """List all registered actions with descriptions."""
    return {
        action: meta["description"]
        for action, meta in _METADATA.items()
        if not meta.get("deprecated")
    }


def list_actions_by_category() -> Dict[str, List[str]]:
    """Get actions grouped by category."""
    categories: Dict[str, List[str]] = {}
    for action, meta in _METADATA.items():
        if meta.get("deprecated"):
            continue
        cat = meta.get("category", "general")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(action)
    return categories


def get_category_actions(category: str) -> List[str]:
    """Get all actions for a specific category."""
    return [
        action for action, meta in _METADATA.items()
        if meta.get("category") == category and not meta.get("deprecated")
    ]


def get_handler_count() -> int:
    """Get total count of registered handlers."""
    return len(_REGISTRY)


def get_deprecated_actions() -> List[str]:
    """Get list of deprecated actions."""
    return [
        action for action, meta in _METADATA.items()
        if meta.get("deprecated")
    ]


# =============================================================================
# DOCUMENTATION GENERATION
# =============================================================================
def generate_help() -> Dict[str, Any]:
    """Generate comprehensive help documentation."""
    by_category = list_actions_by_category()
    
    help_doc = {
        "totalActions": get_handler_count(),
        "categories": {},
        "deprecatedCount": len(get_deprecated_actions()),
    }
    
    for category, actions in sorted(by_category.items()):
        cat_desc = CATEGORIES.get(category, "General handlers")
        help_doc["categories"][category] = {
            "description": cat_desc,
            "actionCount": len(actions),
            "actions": {
                action: _METADATA[action]["description"]
                for action in sorted(actions)
            }
        }
    
    return help_doc


def generate_action_docs(action: str) -> Optional[Dict[str, Any]]:
    """Generate detailed documentation for a specific action."""
    meta = _METADATA.get(action)
    if not meta:
        return None
    
    handler = _REGISTRY.get(action)
    
    return {
        "action": action,
        "category": meta["category"],
        "description": meta["description"],
        "requiredFields": meta["requires"],
        "deprecated": meta["deprecated"],
        "module": meta["module"],
        "docstring": handler.__doc__ if handler else None,
    }


# =============================================================================
# INITIALIZATION - Import and register all handlers
# =============================================================================
_extended_initialized = False

def _init_extended_handlers():
    """Initialize extended handlers from handlers/extended.py."""
    global _extended_initialized
    if _extended_initialized:
        return
    _extended_initialized = True
    
    try:
        logger.info("Initializing extended handlers...")
        from handlers.extended import EXTENDED_HANDLERS, get_extended_actions_by_category
        
        logger.info(f"Found {len(EXTENDED_HANDLERS)} extended handlers to register")
        
        # Get category mapping
        categories = get_extended_actions_by_category()
        action_to_category = {}
        for cat, actions in categories.items():
            # Normalize category name
            cat_key = cat.lower().replace(" & ", "_").replace(" ", "_")
            for action in actions:
                action_to_category[action] = cat_key
        
        # Register all extended handlers
        for action, handler in EXTENDED_HANDLERS.items():
            category = action_to_category.get(action, "extended")
            desc = None
            if handler.__doc__:
                desc = handler.__doc__.split("\n")[0].strip()
            register_handler(action, handler, category, desc)
        
        logger.info(f"Registered {len(EXTENDED_HANDLERS)} extended handlers successfully")
    except ImportError as e:
        logger.warning(f"Could not import extended handlers: {e}")
    except Exception as e:
        logger.exception(f"Error initializing extended handlers: {e}")


def ensure_handlers_initialized():
    """Ensure extended handlers are initialized. Call before dispatch."""
    _init_extended_handlers()


# Don't auto-initialize on module load - do it lazily
# _init_extended_handlers()
