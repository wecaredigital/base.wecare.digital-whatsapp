# Extended Handlers Integration
# =============================================================================
# This module provides unified dispatch for all extended handlers.
# It integrates with the base registry system for consistent handler management.
#
# ARCHITECTURE:
# - All handlers are imported from their respective modules
# - Handlers are registered in EXTENDED_HANDLERS dict for dispatch
# - dispatch_extended_handler() is called from lambda_handler in app.py
# - This provides a single entry point for all extended functionality
#
# TO ADD A NEW HANDLER:
# 1. Create handler function in appropriate module (e.g., handlers/my_feature.py)
# 2. Import it here
# 3. Add to EXTENDED_HANDLERS dict with action name as key
# 4. Add to get_extended_actions_by_category() for documentation
# =============================================================================

from typing import Any, Dict, List, Optional

# =============================================================================
# IMPORT ALL HANDLERS
# =============================================================================

# Core Messaging Handlers
from handlers.messaging import (
    handle_send_text,
    handle_send_media,
    handle_send_image,
    handle_send_video,
    handle_send_audio,
    handle_send_document,
    handle_send_sticker,
    handle_send_location,
    handle_send_contact,
    handle_send_reaction,
    handle_remove_reaction,
    handle_send_interactive,
    handle_send_cta_url,
    handle_send_template,
    handle_send_reply,
    handle_mark_read,
    MESSAGING_HANDLERS,
)

# Query Handlers
from handlers.queries import (
    handle_get_messages,
    handle_get_conversations,
    handle_get_message,
    handle_get_message_by_wa_id,
    handle_get_conversation,
    handle_get_conversation_messages,
    handle_get_unread_count,
    handle_search_messages,
    handle_get_archived_conversations,
    handle_get_failed_messages,
    handle_get_delivery_status,
    QUERY_HANDLERS,
)

# Config & Utility Handlers
from handlers.config import (
    handle_ping,
    handle_get_config,
    handle_get_quality,
    handle_get_stats,
    handle_get_wabas,
    handle_get_phone_info,
    handle_get_infra,
    handle_get_media_types,
    handle_get_supported_formats,
    handle_list_actions,
    handle_get_best_practices,
    CONFIG_HANDLERS,
)

# Business Profile Handlers
from handlers.business_profile import (
    handle_get_business_profile,
    handle_update_business_profile,
    handle_upload_profile_picture,
    handle_get_business_profile_apply_instructions,
)

# Marketing & Templates Handlers
from handlers.marketing import (
    handle_create_marketing_template,
    handle_send_marketing_message,
    handle_send_utility_template,
    handle_send_auth_template,
    handle_send_catalog_template,
    handle_send_coupon_template,
    handle_send_limited_offer_template,
    handle_send_carousel_template,
    handle_send_mpm_template,
    handle_get_template_analytics,
    handle_get_template_pacing,
    handle_set_template_ttl,
)

# Webhook Handlers
from handlers.webhooks import (
    handle_register_webhook,
    handle_process_wix_webhook,
    handle_get_webhook_events,
    handle_process_webhook_event,
    handle_get_wix_orders,
)

# Calling Handlers
from handlers.calling import (
    handle_initiate_call,
    handle_update_call_status,
    handle_get_call_logs,
    handle_update_call_settings,
    handle_get_call_settings,
    handle_create_call_deeplink,
)

# Groups Handlers
from handlers.groups import (
    handle_create_group,
    handle_add_group_participant,
    handle_remove_group_participant,
    handle_get_group_info,
    handle_get_groups,
    handle_send_group_message,
    handle_get_group_messages,
)

# Analytics Handlers
from handlers.analytics import (
    handle_get_analytics,
    handle_get_ctwa_metrics,
    handle_get_funnel_insights,
    handle_track_ctwa_click,
    handle_setup_welcome_sequence,
)

# Catalogs Handlers
from handlers.catalogs import (
    handle_upload_catalog,
    handle_get_catalog_products,
    handle_send_catalog_message,
)

# Payments Handlers
from handlers.payments import (
    handle_payment_onboarding,
    handle_create_payment_request,
    handle_get_payment_status,
    handle_update_payment_status,
    handle_send_payment_confirmation,
    handle_get_payments,
    handle_send_payment_order,
    handle_send_order_status,
    handle_process_payment_webhook,
    handle_send_checkout_template,
    handle_meta_payment_onboarding,
    handle_get_payment_configurations,
    handle_verify_payment_configuration,
)

# Payment Configuration Handlers (Tenant-based)
from handlers.payment_config import (
    handle_seed_payment_configs,
    handle_list_payment_configurations,
    handle_get_payment_configuration,
    handle_set_default_payment_configuration,
    handle_validate_payment_configuration,
    handle_send_order_details_with_payment,
)

# AWS EUM Media Handlers
from handlers.media_eum import (
    handle_eum_download_media,
    handle_eum_upload_media,
    handle_eum_validate_media,
    handle_eum_get_supported_formats,
    handle_eum_setup_s3_lifecycle,
    handle_eum_get_media_stats,
)

# Refunds Handlers
from handlers.refunds import (
    handle_create_refund,
    handle_process_refund,
    handle_complete_refund,
    handle_fail_refund,
    handle_cancel_refund,
    handle_get_refund,
    handle_get_refunds,
    handle_process_refund_webhook,
)

# Templates Meta API Handlers
from handlers.templates_meta import (
    handle_get_templates_meta,
    handle_cache_template_meta,
    handle_create_template_meta,
    handle_edit_template_meta,
    handle_delete_template_meta,
    handle_get_template_quality,
    handle_sync_templates_meta,
)

# Webhook Security Handlers
from handlers.webhook_security import (
    handle_verify_webhook,
    handle_validate_webhook_signature,
    handle_process_secure_webhook,
    handle_set_webhook_config,
    handle_get_webhook_config,
    handle_test_webhook_signature,
    handle_webhook_retry,
)

# Address Messages Handlers
from handlers.address_messages import (
    handle_send_address_message,
    handle_process_address_response,
    handle_get_customer_addresses,
    handle_validate_address,
    handle_save_address,
    handle_get_saved_addresses,
    handle_delete_saved_address,
)

# Flows Messaging Handlers
from handlers.flows_messaging import (
    handle_send_flow_message,
    handle_send_flow_template,
    handle_flow_data_exchange,
    handle_flow_completion,
    handle_flow_health_check,
    handle_delete_flow,
    handle_get_flow_responses,
)

# Carousel Message Handlers
from handlers.carousels import (
    handle_send_media_carousel,
    handle_send_product_carousel,
    handle_send_single_product,
)

# Throughput Management Handlers
from handlers.throughput import (
    handle_get_throughput_limits,
    handle_set_throughput_tier,
    handle_get_throughput_stats,
    handle_check_rate_limit,
)

# Template Library Handlers
from handlers.template_library import (
    handle_get_template_library,
    handle_use_library_template,
    handle_get_local_templates,
    handle_customize_template,
)

# AWS Event Destinations Handlers
from handlers.event_destinations import (
    handle_create_event_destination,
    handle_get_event_destinations,
    handle_update_event_destination,
    handle_delete_event_destination,
    handle_test_event_destination,
)

# AWS EUM Template Handlers
from handlers.templates_eum import EUM_TEMPLATE_HANDLERS

# =============================================================================
# HANDLER REGISTRY - Maps action names to handler functions
# =============================================================================
EXTENDED_HANDLERS: Dict[str, Any] = {
    # -------------------------------------------------------------------------
    # Core Messaging (from handlers/messaging.py)
    # -------------------------------------------------------------------------
    **MESSAGING_HANDLERS,
    
    # -------------------------------------------------------------------------
    # Query Handlers (from handlers/queries.py)
    # -------------------------------------------------------------------------
    **QUERY_HANDLERS,
    
    # -------------------------------------------------------------------------
    # Config & Utility Handlers (from handlers/config.py)
    # -------------------------------------------------------------------------
    **CONFIG_HANDLERS,
    
    # -------------------------------------------------------------------------
    # Business Profile
    # -------------------------------------------------------------------------
    "get_business_profile": handle_get_business_profile,
    "update_business_profile": handle_update_business_profile,
    "upload_profile_picture": handle_upload_profile_picture,
    "get_business_profile_apply_instructions": handle_get_business_profile_apply_instructions,
    
    # -------------------------------------------------------------------------
    # Marketing & Templates
    # -------------------------------------------------------------------------
    "create_marketing_template": handle_create_marketing_template,
    "send_marketing_message": handle_send_marketing_message,
    "send_utility_template": handle_send_utility_template,
    "send_auth_template": handle_send_auth_template,
    "send_catalog_template": handle_send_catalog_template,
    "send_coupon_template": handle_send_coupon_template,
    "send_limited_offer_template": handle_send_limited_offer_template,
    "send_carousel_template": handle_send_carousel_template,
    "send_mpm_template": handle_send_mpm_template,
    "get_template_analytics": handle_get_template_analytics,
    "get_template_pacing": handle_get_template_pacing,
    "set_template_ttl": handle_set_template_ttl,
    
    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------
    "register_webhook": handle_register_webhook,
    "process_wix_webhook": handle_process_wix_webhook,
    "get_webhook_events": handle_get_webhook_events,
    "process_webhook_event": handle_process_webhook_event,
    "get_wix_orders": handle_get_wix_orders,
    
    # -------------------------------------------------------------------------
    # Calling
    # -------------------------------------------------------------------------
    "initiate_call": handle_initiate_call,
    "update_call_status": handle_update_call_status,
    "get_call_logs": handle_get_call_logs,
    "update_call_settings": handle_update_call_settings,
    "get_call_settings": handle_get_call_settings,
    "create_call_deeplink": handle_create_call_deeplink,
    
    # -------------------------------------------------------------------------
    # Groups
    # -------------------------------------------------------------------------
    "create_group": handle_create_group,
    "add_group_participant": handle_add_group_participant,
    "remove_group_participant": handle_remove_group_participant,
    "get_group_info": handle_get_group_info,
    "get_groups": handle_get_groups,
    "send_group_message": handle_send_group_message,
    "get_group_messages": handle_get_group_messages,
    
    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------
    "get_analytics": handle_get_analytics,
    "get_ctwa_metrics": handle_get_ctwa_metrics,
    "get_funnel_insights": handle_get_funnel_insights,
    "track_ctwa_click": handle_track_ctwa_click,
    "setup_welcome_sequence": handle_setup_welcome_sequence,
    
    # -------------------------------------------------------------------------
    # Catalogs
    # -------------------------------------------------------------------------
    "upload_catalog": handle_upload_catalog,
    "get_catalog_products": handle_get_catalog_products,
    "send_catalog_message": handle_send_catalog_message,
    
    # -------------------------------------------------------------------------
    # Payments
    # -------------------------------------------------------------------------
    "payment_onboarding": handle_payment_onboarding,
    "create_payment_request": handle_create_payment_request,
    "get_payment_status": handle_get_payment_status,
    "update_payment_status": handle_update_payment_status,
    "send_payment_confirmation": handle_send_payment_confirmation,
    "get_payments": handle_get_payments,
    "send_payment_order": handle_send_payment_order,
    "send_order_status": handle_send_order_status,
    "process_payment_webhook": handle_process_payment_webhook,
    "send_checkout_template": handle_send_checkout_template,
    "meta_payment_onboarding": handle_meta_payment_onboarding,
    "get_payment_configurations": handle_get_payment_configurations,
    "verify_payment_configuration": handle_verify_payment_configuration,
    
    # -------------------------------------------------------------------------
    # Payment Configuration (Tenant-based)
    # -------------------------------------------------------------------------
    "seed_payment_configs": handle_seed_payment_configs,
    "list_payment_configurations": handle_list_payment_configurations,
    "get_payment_configuration": handle_get_payment_configuration,
    "set_default_payment_configuration": handle_set_default_payment_configuration,
    "validate_payment_config": handle_validate_payment_configuration,
    "send_order_details_with_payment": handle_send_order_details_with_payment,
    
    # -------------------------------------------------------------------------
    # AWS EUM Media
    # -------------------------------------------------------------------------
    "eum_download_media": handle_eum_download_media,
    "eum_upload_media": handle_eum_upload_media,
    "eum_validate_media": handle_eum_validate_media,
    "eum_get_supported_formats": handle_eum_get_supported_formats,
    "eum_setup_s3_lifecycle": handle_eum_setup_s3_lifecycle,
    "eum_get_media_stats": handle_eum_get_media_stats,
    
    # -------------------------------------------------------------------------
    # Refunds
    # -------------------------------------------------------------------------
    "create_refund": handle_create_refund,
    "process_refund": handle_process_refund,
    "complete_refund": handle_complete_refund,
    "fail_refund": handle_fail_refund,
    "cancel_refund": handle_cancel_refund,
    "get_refund": handle_get_refund,
    "get_refunds": handle_get_refunds,
    "process_refund_webhook": handle_process_refund_webhook,
    
    # -------------------------------------------------------------------------
    # Templates Meta API
    # -------------------------------------------------------------------------
    "get_templates_meta": handle_get_templates_meta,
    "cache_template_meta": handle_cache_template_meta,
    "create_template_meta": handle_create_template_meta,
    "edit_template_meta": handle_edit_template_meta,
    "delete_template_meta": handle_delete_template_meta,
    "get_template_quality": handle_get_template_quality,
    "sync_templates_meta": handle_sync_templates_meta,
    
    # -------------------------------------------------------------------------
    # Webhook Security
    # -------------------------------------------------------------------------
    "verify_webhook": handle_verify_webhook,
    "validate_webhook_signature": handle_validate_webhook_signature,
    "process_secure_webhook": handle_process_secure_webhook,
    "set_webhook_config": handle_set_webhook_config,
    "get_webhook_config": handle_get_webhook_config,
    "test_webhook_signature": handle_test_webhook_signature,
    "webhook_retry": handle_webhook_retry,
    
    # -------------------------------------------------------------------------
    # Address Messages
    # -------------------------------------------------------------------------
    "send_address_message": handle_send_address_message,
    "process_address_response": handle_process_address_response,
    "get_customer_addresses": handle_get_customer_addresses,
    "validate_address": handle_validate_address,
    "save_address": handle_save_address,
    "get_saved_addresses": handle_get_saved_addresses,
    "delete_saved_address": handle_delete_saved_address,
    
    # -------------------------------------------------------------------------
    # Flows Messaging
    # -------------------------------------------------------------------------
    "send_flow_message": handle_send_flow_message,
    "send_flow_template": handle_send_flow_template,
    "flow_data_exchange": handle_flow_data_exchange,
    "flow_completion": handle_flow_completion,
    "flow_health_check": handle_flow_health_check,
    "delete_flow": handle_delete_flow,
    "get_flow_responses": handle_get_flow_responses,
    
    # -------------------------------------------------------------------------
    # Carousels
    # -------------------------------------------------------------------------
    "send_media_carousel": handle_send_media_carousel,
    "send_product_carousel": handle_send_product_carousel,
    "send_single_product": handle_send_single_product,
    
    # -------------------------------------------------------------------------
    # Throughput Management
    # -------------------------------------------------------------------------
    "get_throughput_limits": handle_get_throughput_limits,
    "set_throughput_tier": handle_set_throughput_tier,
    "get_throughput_stats": handle_get_throughput_stats,
    "check_rate_limit": handle_check_rate_limit,
    
    # -------------------------------------------------------------------------
    # Template Library
    # -------------------------------------------------------------------------
    "get_template_library": handle_get_template_library,
    "use_library_template": handle_use_library_template,
    "get_local_templates": handle_get_local_templates,
    "customize_template": handle_customize_template,
    
    # -------------------------------------------------------------------------
    # AWS Event Destinations
    # -------------------------------------------------------------------------
    "create_event_destination": handle_create_event_destination,
    "get_event_destinations": handle_get_event_destinations,
    "update_event_destination": handle_update_event_destination,
    "delete_event_destination": handle_delete_event_destination,
    "test_event_destination": handle_test_event_destination,
    
    # -------------------------------------------------------------------------
    # AWS EUM Templates
    # -------------------------------------------------------------------------
    **EUM_TEMPLATE_HANDLERS,
}


# =============================================================================
# DISPATCH FUNCTION - Called from lambda_handler
# =============================================================================
def dispatch_extended_handler(action: str, event: Dict[str, Any], context: Any) -> Optional[Dict[str, Any]]:
    """
    Dispatch to extended handler if action is registered.
    
    This is the main entry point called from lambda_handler in app.py.
    Returns None if action is not an extended handler, allowing the
    main dispatcher to continue checking other handlers.
    
    Args:
        action: The action name from the event
        event: The full Lambda event
        context: The Lambda context
        
    Returns:
        Handler response dict, or None if action not found
    """
    handler = EXTENDED_HANDLERS.get(action)
    if handler:
        return handler(event, context)
    return None


# =============================================================================
# DOCUMENTATION FUNCTIONS
# =============================================================================
def list_extended_actions() -> Dict[str, str]:
    """
    List all extended actions with their descriptions.
    
    Returns:
        Dict mapping action names to their first-line descriptions
    """
    actions = {}
    for action, handler in EXTENDED_HANDLERS.items():
        doc = handler.__doc__ or "No description"
        first_line = doc.split("\n")[0].strip()
        actions[action] = first_line
    return actions


def get_extended_actions_by_category() -> Dict[str, List[str]]:
    """
    Get extended actions grouped by category.
    
    Returns:
        Dict mapping category names to lists of action names
    """
    return {
        "Core Messaging": [
            "send_text",
            "send_media",
            "send_image",
            "send_video",
            "send_audio",
            "send_document",
            "send_sticker",
            "send_location",
            "send_contact",
            "send_reaction",
            "remove_reaction",
            "send_interactive",
            "send_cta_url",
            "send_template",
            "send_reply",
            "mark_read",
        ],
        "Query & Search": [
            "get_messages",
            "get_conversations",
            "get_message",
            "get_message_by_wa_id",
            "get_conversation",
            "get_conversation_messages",
            "get_unread_count",
            "search_messages",
            "get_archived_conversations",
            "get_failed_messages",
            "get_delivery_status",
        ],
        "Config & Utility": [
            "ping",
            "get_config",
            "get_quality",
            "get_stats",
            "get_wabas",
            "get_phone_info",
            "get_infra",
            "get_media_types",
            "get_supported_formats",
            "list_actions",
            "get_best_practices",
        ],
        "Business Profile": [
            "get_business_profile",
            "update_business_profile",
            "upload_profile_picture",
            "get_business_profile_apply_instructions",
        ],
        "Marketing & Templates": [
            "create_marketing_template",
            "send_marketing_message",
            "send_utility_template",
            "send_auth_template",
            "send_catalog_template",
            "send_coupon_template",
            "send_limited_offer_template",
            "send_carousel_template",
            "send_mpm_template",
            "get_template_analytics",
            "get_template_pacing",
            "set_template_ttl",
        ],
        "Webhooks": [
            "register_webhook",
            "process_wix_webhook",
            "get_webhook_events",
            "process_webhook_event",
            "get_wix_orders",
        ],
        "Calling": [
            "initiate_call",
            "update_call_status",
            "get_call_logs",
            "update_call_settings",
            "get_call_settings",
            "create_call_deeplink",
        ],
        "Groups": [
            "create_group",
            "add_group_participant",
            "remove_group_participant",
            "get_group_info",
            "get_groups",
            "send_group_message",
            "get_group_messages",
        ],
        "Analytics": [
            "get_analytics",
            "get_ctwa_metrics",
            "get_funnel_insights",
            "track_ctwa_click",
            "setup_welcome_sequence",
        ],
        "Catalogs": [
            "upload_catalog",
            "get_catalog_products",
            "send_catalog_message",
        ],
        "Payments": [
            "payment_onboarding",
            "create_payment_request",
            "get_payment_status",
            "update_payment_status",
            "send_payment_confirmation",
            "get_payments",
            "send_payment_order",
            "send_order_status",
            "process_payment_webhook",
            "send_checkout_template",
            "meta_payment_onboarding",
            "get_payment_configurations",
            "verify_payment_configuration",
            # Tenant-based payment config
            "seed_payment_configs",
            "list_payment_configurations",
            "get_payment_configuration",
            "set_default_payment_configuration",
            "validate_payment_config",
            "send_order_details_with_payment",
        ],
        "AWS EUM Media": [
            "eum_download_media",
            "eum_upload_media",
            "eum_validate_media",
            "eum_get_supported_formats",
            "eum_setup_s3_lifecycle",
            "eum_get_media_stats",
        ],
        "Refunds": [
            "create_refund",
            "process_refund",
            "complete_refund",
            "fail_refund",
            "cancel_refund",
            "get_refund",
            "get_refunds",
            "process_refund_webhook",
        ],
        "Templates Meta API": [
            "get_templates_meta",
            "cache_template_meta",
            "create_template_meta",
            "edit_template_meta",
            "delete_template_meta",
            "get_template_quality",
            "sync_templates_meta",
        ],
        "Webhook Security": [
            "verify_webhook",
            "validate_webhook_signature",
            "process_secure_webhook",
            "set_webhook_config",
            "get_webhook_config",
            "test_webhook_signature",
            "webhook_retry",
        ],
        "Address Messages": [
            "send_address_message",
            "process_address_response",
            "get_customer_addresses",
            "validate_address",
            "save_address",
            "get_saved_addresses",
            "delete_saved_address",
        ],
        "Flows Messaging": [
            "send_flow_message",
            "send_flow_template",
            "flow_data_exchange",
            "flow_completion",
            "flow_health_check",
            "delete_flow",
            "get_flow_responses",
        ],
        "Carousels": [
            "send_media_carousel",
            "send_product_carousel",
            "send_single_product",
        ],
        "Throughput Management": [
            "get_throughput_limits",
            "set_throughput_tier",
            "get_throughput_stats",
            "check_rate_limit",
        ],
        "Template Library": [
            "get_template_library",
            "use_library_template",
            "get_local_templates",
            "customize_template",
        ],
        "AWS Event Destinations": [
            "create_event_destination",
            "get_event_destinations",
            "update_event_destination",
            "delete_event_destination",
            "test_event_destination",
        ],
        "AWS EUM Templates": [
            "eum_list_templates",
            "eum_get_template",
            "eum_create_template",
            "eum_update_template",
            "eum_delete_template",
            "eum_list_template_library",
            "eum_create_from_library",
            "eum_create_template_media",
            "eum_sync_templates",
            "eum_get_template_status",
        ],
    }


def get_extended_handler_count() -> int:
    """Get total count of extended handlers."""
    return len(EXTENDED_HANDLERS)


def is_extended_action(action: str) -> bool:
    """Check if an action is an extended handler."""
    return action in EXTENDED_HANDLERS
