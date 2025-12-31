# =============================================================================
# WhatsApp Business API - Unified Handler Package
# =============================================================================
# Production-grade handler system with unified dispatcher.
#
# ARCHITECTURE:
#   handlers/
#   ├── __init__.py          # This file - package exports
#   ├── dispatcher.py        # UNIFIED DISPATCHER (main entry point)
#   ├── base.py              # Shared utilities, clients, helpers
#   ├── extended.py          # Extended handler registry
#   ├── registry.py          # Legacy registry (for compatibility)
#   └── <feature>.py         # Individual feature handlers
#
# USAGE IN app.py:
#   from handlers import unified_dispatch, list_all_actions
#   
#   # In lambda_handler:
#   result = unified_dispatch(action, event, context)
#   if result is not None:
#       return maybe_wrap(result)
#
# TO ADD A NEW HANDLER:
#   Option 1 - Using decorator (recommended):
#       from handlers.dispatcher import register
#       
#       @register("my_action", category="my_category", requires=["param1"])
#       def handle_my_action(event, context):
#           return {"statusCode": 200}
#   
#   Option 2 - Manual registration:
#       from handlers.dispatcher import register_handler
#       register_handler("my_action", my_handler_func, "category", "description")
#   
#   Option 3 - Add to extended.py (for feature modules):
#       1. Create handler in handlers/<feature>.py
#       2. Import in handlers/extended.py
#       3. Add to EXTENDED_HANDLERS dict
# =============================================================================

# -----------------------------------------------------------------------------
# UNIFIED DISPATCHER - Primary interface
# -----------------------------------------------------------------------------
from handlers.dispatcher import (
    # Main dispatch function
    unified_dispatch,
    dispatch_with_validation,
    # Registration
    register,
    register_handler,
    register_bulk,
    # Query functions
    get_handler,
    handler_exists,
    get_handler_metadata,
    list_all_actions,
    list_actions_by_category,
    get_category_actions,
    get_handler_count,
    get_deprecated_actions,
    # Documentation
    generate_help,
    generate_action_docs,
    # Constants
    CATEGORIES,
)

# -----------------------------------------------------------------------------
# EXTENDED HANDLERS - Lazy import to avoid circular imports
# -----------------------------------------------------------------------------
def _get_extended_module():
    """Lazy import of extended handlers to avoid circular imports."""
    from handlers import extended
    return extended

def dispatch_extended_handler(action, event, context):
    """Dispatch to extended handler if action is registered."""
    return _get_extended_module().dispatch_extended_handler(action, event, context)

def list_extended_actions():
    """List all extended actions with their descriptions."""
    return _get_extended_module().list_extended_actions()

def get_extended_actions_by_category():
    """Get extended actions grouped by category."""
    return _get_extended_module().get_extended_actions_by_category()

def get_extended_handler_count():
    """Get total count of extended handlers."""
    return _get_extended_module().get_extended_handler_count()

def is_extended_action(action):
    """Check if an action is an extended handler."""
    return _get_extended_module().is_extended_action(action)

def get_extended_handlers():
    """Get the extended handlers dict."""
    return _get_extended_module().EXTENDED_HANDLERS

# Alias for backward compatibility - use get_extended_handlers() function instead
# Note: Direct access to EXTENDED_HANDLERS dict is deprecated, use get_extended_handlers()
def _lazy_extended_handlers():
    """Lazy accessor for EXTENDED_HANDLERS dict."""
    return get_extended_handlers()

# -----------------------------------------------------------------------------
# BASE UTILITIES - Shared across all handlers
# -----------------------------------------------------------------------------
from handlers.base import (
    # AWS Clients (lazy-loaded)
    get_ddb, get_s3, get_social, get_sns, get_ec2, get_iam, get_table,
    table, social, s3, sns, ec2, iam,
    
    # Environment Configuration
    MESSAGES_TABLE_NAME, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    META_API_VERSION, WABA_PHONE_MAP,
    
    # Utility Functions
    iso_now, jdump, safe, format_wa_number, origination_id_for_api, arn_suffix,
    
    # WABA Configuration
    get_waba_config, get_phone_arn, get_business_name,
    
    # Validation Helpers
    validate_required_fields, validate_enum,
    
    # DynamoDB Operations
    store_item, update_item, get_item, query_items, delete_item,
    
    # WhatsApp Messaging
    send_whatsapp_message,
    
    # S3 Operations
    generate_s3_presigned_url,
    
    # Response Helpers
    success_response, error_response, not_found_response,
    
    # Media Types
    SUPPORTED_MEDIA_TYPES, get_supported_mime_types, is_supported_media, mime_to_ext,
)

# -----------------------------------------------------------------------------
# LEGACY REGISTRY - For backward compatibility
# -----------------------------------------------------------------------------
HANDLER_CATEGORIES = {
    "messaging": "Send WhatsApp messages",
    "media": "Media file operations",
    "templates": "Template management",
    "payments": "Payment processing",
    "webhooks": "Webhook handling",
    "analytics": "Analytics & reporting",
}

# -----------------------------------------------------------------------------
# PUBLIC API
# -----------------------------------------------------------------------------
__all__ = [
    # === UNIFIED DISPATCHER (PRIMARY) ===
    'unified_dispatch',
    'dispatch_with_validation',
    'register',
    'register_handler',
    'register_bulk',
    'get_handler',
    'handler_exists',
    'get_handler_metadata',
    'list_all_actions',
    'list_actions_by_category',
    'get_category_actions',
    'get_handler_count',
    'get_deprecated_actions',
    'generate_help',
    'generate_action_docs',
    'CATEGORIES',
    
    # === EXTENDED HANDLERS (BACKWARD COMPAT) ===
    'dispatch_extended_handler',
    'list_extended_actions',
    'get_extended_actions_by_category',
    'get_extended_handler_count',
    'is_extended_action',
    'get_extended_handlers',
    
    # === AWS CLIENTS ===
    'get_ddb', 'get_s3', 'get_social', 'get_sns', 'get_ec2', 'get_iam', 'get_table',
    'table', 'social', 's3', 'sns', 'ec2', 'iam',
    
    # === ENVIRONMENT ===
    'MESSAGES_TABLE_NAME', 'MESSAGES_PK_NAME', 'MEDIA_BUCKET', 'MEDIA_PREFIX',
    'META_API_VERSION', 'WABA_PHONE_MAP',
    
    # === UTILITIES ===
    'iso_now', 'jdump', 'safe', 'format_wa_number', 'origination_id_for_api', 'arn_suffix',
    'get_waba_config', 'get_phone_arn', 'get_business_name',
    'validate_required_fields', 'validate_enum',
    
    # === DYNAMODB ===
    'store_item', 'update_item', 'get_item', 'query_items', 'delete_item',
    
    # === MESSAGING ===
    'send_whatsapp_message',
    
    # === S3 ===
    'generate_s3_presigned_url',
    
    # === RESPONSES ===
    'success_response', 'error_response', 'not_found_response',
    
    # === MEDIA ===
    'SUPPORTED_MEDIA_TYPES', 'get_supported_mime_types', 'is_supported_media', 'mime_to_ext',
    
    # === LEGACY ===
    'HANDLER_CATEGORIES',
]

# -----------------------------------------------------------------------------
# VERSION INFO
# -----------------------------------------------------------------------------
__version__ = "2.0.0"
__author__ = "WhatsApp Business API Team"
