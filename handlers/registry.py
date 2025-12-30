# Handler Registry - Unified registration and dispatch system
# This module provides a centralized registry for all action handlers
# 
# PATTERN: All handlers should use the @register_handler decorator from base.py
# This ensures automatic registration and consistent metadata tracking.
#
# Usage:
#     from handlers.base import register_handler
#     
#     @register_handler("my_action", category="messaging", description="Do something")
#     def handle_my_action(event, context):
#         return {"statusCode": 200}

from typing import Any, Dict, List, Optional

# Re-export from base for backward compatibility
from handlers.base import (
    register_handler,
    get_handler,
    list_handlers,
    get_handlers_by_category,
    dispatch_handler,
    HandlerFunc,
)

# =============================================================================
# HANDLER CATEGORIES
# =============================================================================
HANDLER_CATEGORIES = {
    "messaging": "Send and manage WhatsApp messages",
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
}


def get_category_description(category: str) -> str:
    """Get description for a handler category."""
    return HANDLER_CATEGORIES.get(category, "General handlers")


def get_all_categories() -> Dict[str, str]:
    """Get all handler categories with descriptions."""
    return HANDLER_CATEGORIES.copy()


# =============================================================================
# HANDLER DISCOVERY
# =============================================================================
def discover_handlers() -> Dict[str, Dict[str, Any]]:
    """
    Discover all registered handlers with full metadata.
    
    Returns dict with structure:
    {
        "action_name": {
            "category": "category_name",
            "description": "Handler description",
            "module": "handlers.module_name"
        }
    }
    """
    from handlers.base import _HANDLER_METADATA
    return _HANDLER_METADATA.copy()


def get_handlers_for_category(category: str) -> List[str]:
    """Get list of handler actions for a specific category."""
    by_category = get_handlers_by_category()
    return by_category.get(category, [])


def handler_exists(action: str) -> bool:
    """Check if a handler exists for the given action."""
    return get_handler(action) is not None


# =============================================================================
# HANDLER DOCUMENTATION
# =============================================================================
def get_handler_docs(action: str) -> Optional[str]:
    """Get full docstring for a handler."""
    handler = get_handler(action)
    if handler:
        return handler.__doc__
    return None


def generate_handler_help() -> Dict[str, Any]:
    """Generate help documentation for all handlers."""
    by_category = get_handlers_by_category()
    handlers = list_handlers()
    
    help_doc = {
        "categories": {},
        "total_handlers": len(handlers),
    }
    
    for category, actions in by_category.items():
        help_doc["categories"][category] = {
            "description": get_category_description(category),
            "actions": {action: handlers.get(action, "") for action in actions}
        }
    
    return help_doc
