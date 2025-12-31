# =============================================================================
# Welcome Message & Interactive Menu System
# =============================================================================
# Production-grade welcome message and interactive list menu for WhatsApp.
# Implements §13 of Kiro spec v7.
#
# Features:
# - Configurable welcome messages per tenant
# - Interactive list menu with WECARE.DIGITAL navigation
# - Menu selection handling with action routing
# - Auto-send rules with cooldown and window respect
# =============================================================================

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, social, MESSAGES_PK_NAME, WABA_PHONE_MAP, META_API_VERSION,
    iso_now, store_item, get_item, update_item, query_items,
    validate_required_fields, success_response, error_response,
    origination_id_for_api, format_wa_number,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# DEFAULT CONFIGURATIONS
# =============================================================================

DEFAULT_WELCOME_TEXT = """Welcome to WECARE.DIGITAL 👋

Choose an option from the menu below, or type what you need help with."""

DEFAULT_MENU_BODY = "How can we help you today? Select an option:"
DEFAULT_MENU_BUTTON = "📋 Menu"

# Default menu sections based on WECARE.DIGITAL website
DEFAULT_MENU_SECTIONS = [
    {
        "title": "MICROSERVICE BRANDS",
        "rows": [
            {"id": "brand_bnb_club", "title": "BNB CLUB", "description": "Travel", "actionType": "open_url", "actionValue": "https://www.wecare.digital/bnb-club"},
            {"id": "brand_no_fault", "title": "NO FAULT", "description": "ODR", "actionType": "open_url", "actionValue": "https://www.wecare.digital/no-fault"},
            {"id": "brand_expo_week", "title": "EXPO WEEK", "description": "Digital events", "actionType": "open_url", "actionValue": "https://www.wecare.digital/expo-week"},
            {"id": "brand_ritual_guru", "title": "RITUAL GURU", "description": "Culture", "actionType": "open_url", "actionValue": "https://www.wecare.digital/ritual-guru"},
            {"id": "brand_legal_champ", "title": "LEGAL CHAMP", "description": "Documentation", "actionType": "open_url", "actionValue": "https://www.wecare.digital/legal-champ"},
            {"id": "brand_swdhya", "title": "SWDHYA", "description": "Samvad", "actionType": "open_url", "actionValue": "https://www.wecare.digital/swdhya"},
        ]
    },
    {
        "title": "SELF SERVICE",
        "rows": [
            {"id": "ss_submit_request", "title": "Submit Request", "description": "New request", "actionType": "open_url", "actionValue": "https://www.wecare.digital/submit-request"},
            {"id": "ss_request_amendment", "title": "Request Amendment", "description": "Modify request", "actionType": "open_url", "actionValue": "https://www.wecare.digital/request-amendment"},
            {"id": "ss_request_tracking", "title": "Request Tracking", "description": "Track status", "actionType": "open_url", "actionValue": "https://www.wecare.digital/request-tracking"},
            {"id": "ss_rx_slot", "title": "RX Slot", "description": "Book slot", "actionType": "open_url", "actionValue": "https://www.wecare.digital/rx-slot"},
            {"id": "ss_drop_docs", "title": "Drop Docs", "description": "Upload documents", "actionType": "open_url", "actionValue": "https://www.wecare.digital/drop-docs"},
            {"id": "ss_enterprise_assist", "title": "Enterprise Assist", "description": "Business help", "actionType": "open_url", "actionValue": "https://www.wecare.digital/enterprise-assist"},
        ]
    },
    {
        "title": "MORE",
        "rows": [
            {"id": "ss_leave_review", "title": "Leave Review", "description": "Share feedback", "actionType": "open_url", "actionValue": "https://www.wecare.digital/leave-review"},
            {"id": "ss_faq", "title": "FAQ", "description": "Common questions", "actionType": "open_url", "actionValue": "https://www.wecare.digital/faq"},
            {"id": "more_gift_card", "title": "Gift Card", "description": "Purchase gift card", "actionType": "open_url", "actionValue": "https://www.wecare.digital/gift-card"},
            {"id": "more_download_app", "title": "Download App", "description": "Get our app", "actionType": "open_url", "actionValue": "https://www.wecare.digital/app"},
            {"id": "more_contact", "title": "Contact Us", "description": "Get in touch", "actionType": "open_url", "actionValue": "https://www.wecare.digital/contact"},
            {"id": "more_careers", "title": "Careers + Culture", "description": "Join our team", "actionType": "open_url", "actionValue": "https://www.wecare.digital/careers"},
        ]
    }
]

# Auto-send keywords
MENU_KEYWORDS = ["menu", "help", "start", "hi", "hello", "hey", "options", "main menu"]

# =============================================================================
# WELCOME CONFIG HANDLERS
# =============================================================================

def handle_get_welcome_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get welcome message configuration for a tenant.
    
    Required: tenantId (or metaWabaId as alias)
    
    Test Event:
    {
        "action": "get_welcome_config",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    config_pk = f"TENANT#{tenant_id}"
    config_sk = "WELCOME#default"
    
    try:
        # Try to get existing config
        response = table().get_item(
            Key={MESSAGES_PK_NAME: f"{config_pk}#{config_sk}"}
        )
        config = response.get("Item")
        
        if not config:
            # Return default config
            return success_response("get_welcome_config",
                tenantId=tenant_id,
                config={
                    "welcomeText": DEFAULT_WELCOME_TEXT,
                    "enabled": True,
                    "onlyOnFirstContact": True,
                    "cooldownHours": 72,
                    "outsideWindowTemplateName": "",
                    "isDefault": True,
                }
            )
        
        return success_response("get_welcome_config",
            tenantId=tenant_id,
            config={
                "welcomeText": config.get("welcomeText", DEFAULT_WELCOME_TEXT),
                "enabled": config.get("enabled", True),
                "onlyOnFirstContact": config.get("onlyOnFirstContact", True),
                "cooldownHours": config.get("cooldownHours", 72),
                "outsideWindowTemplateName": config.get("outsideWindowTemplateName", ""),
                "isDefault": False,
                "updatedAt": config.get("updatedAt", ""),
            }
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_update_welcome_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update welcome message configuration for a tenant.
    
    Required: tenantId
    Optional: welcomeText, enabled, onlyOnFirstContact, cooldownHours, outsideWindowTemplateName
    
    Test Event:
    {
        "action": "update_welcome_config",
        "tenantId": "wecare-digital",
        "welcomeText": "Welcome! How can we help?",
        "enabled": true,
        "cooldownHours": 48
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    now = iso_now()
    config_pk = f"TENANT#{tenant_id}#WELCOME#default"
    
    config_item = {
        MESSAGES_PK_NAME: config_pk,
        "itemType": "WELCOME_CONFIG",
        "tenantId": tenant_id,
        "welcomeText": event.get("welcomeText", DEFAULT_WELCOME_TEXT),
        "enabled": event.get("enabled", True),
        "onlyOnFirstContact": event.get("onlyOnFirstContact", True),
        "cooldownHours": event.get("cooldownHours", 72),
        "outsideWindowTemplateName": event.get("outsideWindowTemplateName", ""),
        "updatedAt": now,
        "createdAt": now,
    }
    
    try:
        store_item(config_item)
        
        return success_response("update_welcome_config",
            tenantId=tenant_id,
            message="Welcome config updated",
            config=config_item,
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_send_welcome(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Manually send welcome message to a user.
    
    Required: metaWabaId, to
    Optional: customText (override welcome text)
    
    Test Event:
    {
        "action": "send_welcome",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    custom_text = event.get("customText", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to"])
    if error:
        return error
    
    # Get WABA config
    config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
    if not config or not config.get("phoneArn"):
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    # Get welcome config
    welcome_config = handle_get_welcome_config({"tenantId": meta_waba_id}, context)
    welcome_text = custom_text or welcome_config.get("config", {}).get("welcomeText", DEFAULT_WELCOME_TEXT)
    
    # Send welcome message
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "text",
        "text": {"body": welcome_text}
    }
    
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        
        message_id = response.get("messageId", "")
        
        # Store welcome sent record
        store_item({
            MESSAGES_PK_NAME: f"WELCOME_SENT#{to_formatted}#{iso_now()}",
            "itemType": "WELCOME_SENT",
            "wabaMetaId": meta_waba_id,
            "to": to_formatted,
            "messageId": message_id,
            "sentAt": iso_now(),
        })
        
        return success_response("send_welcome",
            messageId=message_id,
            to=to_formatted,
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# MENU CONFIG HANDLERS
# =============================================================================

def handle_get_menu_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get interactive menu configuration for a tenant.
    
    Required: tenantId (or metaWabaId)
    
    Test Event:
    {
        "action": "get_menu_config",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    config_pk = f"TENANT#{tenant_id}#MENU#main"
    
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: config_pk})
        config = response.get("Item")
        
        if not config:
            # Return default menu config
            return success_response("get_menu_config",
                tenantId=tenant_id,
                config={
                    "buttonText": DEFAULT_MENU_BUTTON,
                    "bodyText": DEFAULT_MENU_BODY,
                    "sections": DEFAULT_MENU_SECTIONS,
                    "isDefault": True,
                }
            )
        
        return success_response("get_menu_config",
            tenantId=tenant_id,
            config={
                "buttonText": config.get("buttonText", DEFAULT_MENU_BUTTON),
                "bodyText": config.get("bodyText", DEFAULT_MENU_BODY),
                "sections": config.get("sections", DEFAULT_MENU_SECTIONS),
                "isDefault": False,
                "updatedAt": config.get("updatedAt", ""),
            }
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_update_menu_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update interactive menu configuration for a tenant.
    
    Required: tenantId
    Optional: buttonText, bodyText, sections
    
    Test Event:
    {
        "action": "update_menu_config",
        "tenantId": "wecare-digital",
        "buttonText": "Options",
        "bodyText": "Select an option:"
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    now = iso_now()
    config_pk = f"TENANT#{tenant_id}#MENU#main"
    
    config_item = {
        MESSAGES_PK_NAME: config_pk,
        "itemType": "MENU_CONFIG",
        "tenantId": tenant_id,
        "buttonText": event.get("buttonText", DEFAULT_MENU_BUTTON),
        "bodyText": event.get("bodyText", DEFAULT_MENU_BODY),
        "sections": event.get("sections", DEFAULT_MENU_SECTIONS),
        "updatedAt": now,
        "createdAt": now,
    }
    
    try:
        store_item(config_item)
        
        return success_response("update_menu_config",
            tenantId=tenant_id,
            message="Menu config updated",
        )
    except ClientError as e:
        return error_response(str(e), 500)


def handle_send_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send interactive list menu to a user.
    
    Required: metaWabaId, to
    
    Test Event:
    {
        "action": "send_menu",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to"])
    if error:
        return error
    
    # Get WABA config
    config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
    if not config or not config.get("phoneArn"):
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    # Get menu config
    menu_result = handle_get_menu_config({"tenantId": meta_waba_id}, context)
    menu_config = menu_result.get("config", {})
    
    # Build interactive list payload
    sections = []
    for section in menu_config.get("sections", DEFAULT_MENU_SECTIONS):
        rows = []
        for row in section.get("rows", []):
            rows.append({
                "id": row["id"],
                "title": row["title"][:24],  # WhatsApp limit
                "description": row.get("description", "")[:72],  # WhatsApp limit
            })
        sections.append({
            "title": section["title"][:24],
            "rows": rows[:10],  # Max 10 rows per section
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": menu_config.get("bodyText", DEFAULT_MENU_BODY)},
            "action": {
                "button": menu_config.get("buttonText", DEFAULT_MENU_BUTTON)[:20],
                "sections": sections[:10],  # Max 10 sections
            }
        }
    }
    
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        
        message_id = response.get("messageId", "")
        
        # Store menu sent record
        store_item({
            MESSAGES_PK_NAME: f"MENU_SENT#{to_formatted}#{iso_now()}",
            "itemType": "MENU_SENT",
            "wabaMetaId": meta_waba_id,
            "to": to_formatted,
            "messageId": message_id,
            "sentAt": iso_now(),
        })
        
        return success_response("send_menu",
            messageId=message_id,
            to=to_formatted,
            sectionsCount=len(sections),
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# MENU SELECTION HANDLER
# =============================================================================

def handle_menu_selection(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle user's menu selection (interactive list reply).
    
    Required: metaWabaId, to, selectionId
    Optional: from (sender number for context)
    
    Test Event:
    {
        "action": "handle_menu_selection",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "selectionId": "brand_bnb_club"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    selection_id = event.get("selectionId", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "selectionId"])
    if error:
        return error
    
    # Get WABA config
    config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
    if not config or not config.get("phoneArn"):
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    phone_arn = config["phoneArn"]
    to_formatted = format_wa_number(to_number)
    
    # Get menu config to find the selected row
    menu_result = handle_get_menu_config({"tenantId": meta_waba_id}, context)
    menu_config = menu_result.get("config", {})
    
    # Find the selected row
    selected_row = None
    for section in menu_config.get("sections", DEFAULT_MENU_SECTIONS):
        for row in section.get("rows", []):
            if row["id"] == selection_id:
                selected_row = row
                break
        if selected_row:
            break
    
    if not selected_row:
        return error_response(f"Menu selection not found: {selection_id}", 404)
    
    # Execute action based on type
    action_type = selected_row.get("actionType", "open_url")
    action_value = selected_row.get("actionValue", "")
    row_title = selected_row.get("title", "")
    row_description = selected_row.get("description", "")
    
    if action_type == "open_url":
        # Send message with the URL
        response_text = f"🔗 *{row_title}*\n\n{row_description}\n\n👉 {action_value}"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_formatted,
            "type": "text",
            "text": {"body": response_text, "preview_url": True}
        }
    
    elif action_type == "send_text":
        # Send configured text
        payload = {
            "messaging_product": "whatsapp",
            "to": to_formatted,
            "type": "text",
            "text": {"body": action_value}
        }
    
    elif action_type == "invoke_action":
        # Dispatch internal action (recursive call)
        # This allows menu items to trigger other handlers
        return success_response("handle_menu_selection",
            selectionId=selection_id,
            actionType="invoke_action",
            actionValue=action_value,
            message="Action should be dispatched separately",
        )
    
    else:
        return error_response(f"Unknown action type: {action_type}", 400)
    
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=META_API_VERSION,
            message=json.dumps(payload).encode("utf-8"),
        )
        
        message_id = response.get("messageId", "")
        
        # Log selection
        store_item({
            MESSAGES_PK_NAME: f"MENU_SELECTION#{to_formatted}#{iso_now()}",
            "itemType": "MENU_SELECTION",
            "wabaMetaId": meta_waba_id,
            "to": to_formatted,
            "selectionId": selection_id,
            "actionType": action_type,
            "responseMessageId": message_id,
            "selectedAt": iso_now(),
        })
        
        return success_response("handle_menu_selection",
            messageId=message_id,
            selectionId=selection_id,
            actionType=action_type,
            rowTitle=row_title,
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# AUTO-SEND HANDLERS
# =============================================================================

def handle_check_auto_welcome(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if auto-welcome should be sent and send if appropriate.
    
    Required: metaWabaId, from (sender number)
    
    Test Event:
    {
        "action": "check_auto_welcome",
        "metaWabaId": "1347766229904230",
        "from": "+447447840003"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    
    error = validate_required_fields(event, ["metaWabaId", "from"])
    if error:
        return error
    
    from_formatted = format_wa_number(from_number)
    
    # Get welcome config
    welcome_result = handle_get_welcome_config({"tenantId": meta_waba_id}, context)
    welcome_config = welcome_result.get("config", {})
    
    if not welcome_config.get("enabled", True):
        return success_response("check_auto_welcome",
            sent=False,
            reason="Welcome disabled",
        )
    
    # Check cooldown
    cooldown_hours = welcome_config.get("cooldownHours", 72)
    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
    
    try:
        # Check if welcome was sent recently
        recent_welcomes = query_items(
            filter_expr="itemType = :it AND #to = :to AND sentAt > :cutoff",
            expr_values={
                ":it": "WELCOME_SENT",
                ":to": from_formatted,
                ":cutoff": cooldown_cutoff,
            },
            expr_names={"#to": "to"},
            limit=1,
        )
        
        if recent_welcomes:
            return success_response("check_auto_welcome",
                sent=False,
                reason=f"Welcome sent within {cooldown_hours} hours",
                lastSentAt=recent_welcomes[0].get("sentAt"),
            )
        
        # Check if first contact only
        if welcome_config.get("onlyOnFirstContact", True):
            # Check for any previous messages from this user
            previous_messages = query_items(
                filter_expr="itemType = :it AND #from = :from",
                expr_values={
                    ":it": "MESSAGE",
                    ":from": from_formatted,
                },
                expr_names={"#from": "from"},
                limit=2,  # If more than 1, not first contact
            )
            
            if len(previous_messages) > 1:
                return success_response("check_auto_welcome",
                    sent=False,
                    reason="Not first contact",
                )
        
        # Send welcome
        result = handle_send_welcome({
            "metaWabaId": meta_waba_id,
            "to": from_formatted,
        }, context)
        
        return success_response("check_auto_welcome",
            sent=True,
            messageId=result.get("messageId"),
        )
    
    except ClientError as e:
        return error_response(str(e), 500)


def handle_check_auto_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if message matches menu keywords and send menu if so.
    
    Required: metaWabaId, from, messageText
    
    Test Event:
    {
        "action": "check_auto_menu",
        "metaWabaId": "1347766229904230",
        "from": "+447447840003",
        "messageText": "menu"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    message_text = event.get("messageText", "").lower().strip()
    
    error = validate_required_fields(event, ["metaWabaId", "from", "messageText"])
    if error:
        return error
    
    from_formatted = format_wa_number(from_number)
    
    # Check if message matches menu keywords
    if message_text not in MENU_KEYWORDS:
        return success_response("check_auto_menu",
            sent=False,
            reason="Message does not match menu keywords",
            keywords=MENU_KEYWORDS,
        )
    
    # Send menu
    result = handle_send_menu({
        "metaWabaId": meta_waba_id,
        "to": from_formatted,
    }, context)
    
    return success_response("check_auto_menu",
        sent=True,
        messageId=result.get("messageId"),
        matchedKeyword=message_text,
    )


def handle_seed_default_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Seed default menu configuration for a tenant.
    
    Required: tenantId (or metaWabaId)
    
    Test Event:
    {
        "action": "seed_default_menu",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    now = iso_now()
    
    # Seed welcome config
    welcome_pk = f"TENANT#{tenant_id}#WELCOME#default"
    store_item({
        MESSAGES_PK_NAME: welcome_pk,
        "itemType": "WELCOME_CONFIG",
        "tenantId": tenant_id,
        "welcomeText": DEFAULT_WELCOME_TEXT,
        "enabled": True,
        "onlyOnFirstContact": True,
        "cooldownHours": 72,
        "outsideWindowTemplateName": "",
        "updatedAt": now,
        "createdAt": now,
    })
    
    # Seed menu config
    menu_pk = f"TENANT#{tenant_id}#MENU#main"
    store_item({
        MESSAGES_PK_NAME: menu_pk,
        "itemType": "MENU_CONFIG",
        "tenantId": tenant_id,
        "buttonText": DEFAULT_MENU_BUTTON,
        "bodyText": DEFAULT_MENU_BODY,
        "sections": DEFAULT_MENU_SECTIONS,
        "updatedAt": now,
        "createdAt": now,
    })
    
    return success_response("seed_default_menu",
        tenantId=tenant_id,
        message="Default welcome and menu configs seeded",
        welcomePk=welcome_pk,
        menuPk=menu_pk,
    )


# =============================================================================
# HANDLER MAPPING
# =============================================================================

WELCOME_MENU_HANDLERS = {
    # Welcome config
    "get_welcome_config": handle_get_welcome_config,
    "update_welcome_config": handle_update_welcome_config,
    "send_welcome": handle_send_welcome,
    
    # Menu config
    "get_menu_config": handle_get_menu_config,
    "update_menu_config": handle_update_menu_config,
    "send_menu": handle_send_menu,
    
    # Menu selection
    "handle_menu_selection": handle_menu_selection,
    
    # Auto-send
    "check_auto_welcome": handle_check_auto_welcome,
    "check_auto_menu": handle_check_auto_menu,
    
    # Seeding
    "seed_default_menu": handle_seed_default_menu,
}
