# Automation & Bots Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/phone-numbers/conversational-components

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Max limits
MAX_ICE_BREAKERS = 4
MAX_COMMANDS = 30
MAX_MENU_ITEMS = 10


def handle_set_ice_breakers(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set conversation starter ice breakers.
    
    Test Event:
    {
        "action": "set_ice_breakers",
        "metaWabaId": "1347766229904230",
        "iceBreakers": [
            {"content": "What services do you offer?", "payload": "services"},
            {"content": "Track my order", "payload": "track_order"},
            {"content": "Contact support", "payload": "support"},
            {"content": "View catalog", "payload": "catalog"}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    ice_breakers = event.get("iceBreakers", [])
    
    error = validate_required_fields(event, ["metaWabaId", "iceBreakers"])
    if error:
        return error

    if len(ice_breakers) > MAX_ICE_BREAKERS:
        return {"statusCode": 400, "error": f"Maximum {MAX_ICE_BREAKERS} ice breakers allowed"}
    
    now = iso_now()
    ice_breakers_pk = f"ICE_BREAKERS#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: ice_breakers_pk,
            "itemType": "ICE_BREAKERS",
            "wabaMetaId": meta_waba_id,
            "iceBreakers": ice_breakers,
            "enabled": True,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_ice_breakers",
            "wabaMetaId": meta_waba_id,
            "iceBreakersCount": len(ice_breakers),
            "iceBreakers": ice_breakers,
            "note": "Actual ice breakers require Meta Graph API: POST /{phone-number-id}/conversational_automation"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_ice_breakers(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get current ice breakers configuration.
    
    Test Event:
    {
        "action": "get_ice_breakers",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    ice_breakers_pk = f"ICE_BREAKERS#{meta_waba_id}"
    
    try:
        config = get_item(ice_breakers_pk)
        
        return {
            "statusCode": 200,
            "operation": "get_ice_breakers",
            "wabaMetaId": meta_waba_id,
            "iceBreakers": config.get("iceBreakers", []) if config else [],
            "enabled": config.get("enabled", False) if config else False
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_commands(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set bot commands (slash commands).
    
    Test Event:
    {
        "action": "set_commands",
        "metaWabaId": "1347766229904230",
        "commands": [
            {"command": "help", "description": "Get help and support"},
            {"command": "order", "description": "Place a new order"},
            {"command": "track", "description": "Track your order"},
            {"command": "catalog", "description": "Browse our catalog"},
            {"command": "contact", "description": "Contact customer support"}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    commands = event.get("commands", [])
    
    error = validate_required_fields(event, ["metaWabaId", "commands"])
    if error:
        return error
    
    if len(commands) > MAX_COMMANDS:
        return {"statusCode": 400, "error": f"Maximum {MAX_COMMANDS} commands allowed"}
    
    # Validate command format
    for cmd in commands:
        if not cmd.get("command") or not cmd.get("description"):
            return {"statusCode": 400, "error": "Each command must have 'command' and 'description'"}
        if len(cmd["command"]) > 32:
            return {"statusCode": 400, "error": "Command name must be 32 characters or less"}
        if len(cmd["description"]) > 256:
            return {"statusCode": 400, "error": "Command description must be 256 characters or less"}
    
    now = iso_now()
    commands_pk = f"COMMANDS#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: commands_pk,
            "itemType": "BOT_COMMANDS",
            "wabaMetaId": meta_waba_id,
            "commands": commands,
            "enabled": True,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_commands",
            "wabaMetaId": meta_waba_id,
            "commandsCount": len(commands),
            "commands": commands,
            "note": "Actual commands require Meta Graph API: POST /{phone-number-id}/conversational_automation"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_commands(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get current bot commands configuration.
    
    Test Event:
    {
        "action": "get_commands",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    commands_pk = f"COMMANDS#{meta_waba_id}"
    
    try:
        config = get_item(commands_pk)
        
        return {
            "statusCode": 200,
            "operation": "get_commands",
            "wabaMetaId": meta_waba_id,
            "commands": config.get("commands", []) if config else [],
            "enabled": config.get("enabled", False) if config else False
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_persistent_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set persistent menu for the bot.
    
    Test Event:
    {
        "action": "set_persistent_menu",
        "metaWabaId": "1347766229904230",
        "menuItems": [
            {"title": "🛍️ Shop Now", "payload": "shop"},
            {"title": "📦 Track Order", "payload": "track"},
            {"title": "💬 Support", "payload": "support"},
            {"title": "ℹ️ About Us", "payload": "about"}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    menu_items = event.get("menuItems", [])
    
    error = validate_required_fields(event, ["metaWabaId", "menuItems"])
    if error:
        return error
    
    if len(menu_items) > MAX_MENU_ITEMS:
        return {"statusCode": 400, "error": f"Maximum {MAX_MENU_ITEMS} menu items allowed"}
    
    # Validate menu items
    for item in menu_items:
        if not item.get("title") or not item.get("payload"):
            return {"statusCode": 400, "error": "Each menu item must have 'title' and 'payload'"}
        if len(item["title"]) > 20:
            return {"statusCode": 400, "error": "Menu item title must be 20 characters or less"}
    
    now = iso_now()
    menu_pk = f"PERSISTENT_MENU#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: menu_pk,
            "itemType": "PERSISTENT_MENU",
            "wabaMetaId": meta_waba_id,
            "menuItems": menu_items,
            "enabled": True,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_persistent_menu",
            "wabaMetaId": meta_waba_id,
            "menuItemsCount": len(menu_items),
            "menuItems": menu_items,
            "note": "Persistent menu is a local feature. WhatsApp doesn't have native persistent menu."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_persistent_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get current persistent menu configuration.
    
    Test Event:
    {
        "action": "get_persistent_menu",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    menu_pk = f"PERSISTENT_MENU#{meta_waba_id}"
    
    try:
        config = get_item(menu_pk)
        
        return {
            "statusCode": 200,
            "operation": "get_persistent_menu",
            "wabaMetaId": meta_waba_id,
            "menuItems": config.get("menuItems", []) if config else [],
            "enabled": config.get("enabled", False) if config else False
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_welcome_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set automatic welcome message for new conversations.
    
    Test Event:
    {
        "action": "set_welcome_message",
        "metaWabaId": "1347766229904230",
        "welcomeMessage": "👋 Welcome to WECARE Digital! How can we help you today?",
        "enabled": true
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    welcome_message = event.get("welcomeMessage", "")
    enabled = event.get("enabled", True)
    
    error = validate_required_fields(event, ["metaWabaId", "welcomeMessage"])
    if error:
        return error
    
    now = iso_now()
    welcome_pk = f"WELCOME_MESSAGE#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: welcome_pk,
            "itemType": "WELCOME_MESSAGE",
            "wabaMetaId": meta_waba_id,
            "welcomeMessage": welcome_message,
            "enabled": enabled,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_welcome_message",
            "wabaMetaId": meta_waba_id,
            "welcomeMessage": welcome_message,
            "enabled": enabled
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_away_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set automatic away/out-of-office message.
    
    Test Event:
    {
        "action": "set_away_message",
        "metaWabaId": "1347766229904230",
        "awayMessage": "Thanks for reaching out! We're currently away but will respond within 24 hours.",
        "schedule": {
            "enabled": true,
            "startTime": "18:00",
            "endTime": "09:00",
            "timezone": "Asia/Kolkata"
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    away_message = event.get("awayMessage", "")
    schedule = event.get("schedule", {})
    
    error = validate_required_fields(event, ["metaWabaId", "awayMessage"])
    if error:
        return error
    
    now = iso_now()
    away_pk = f"AWAY_MESSAGE#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: away_pk,
            "itemType": "AWAY_MESSAGE",
            "wabaMetaId": meta_waba_id,
            "awayMessage": away_message,
            "schedule": schedule,
            "enabled": schedule.get("enabled", True),
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_away_message",
            "wabaMetaId": meta_waba_id,
            "awayMessage": away_message,
            "schedule": schedule
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
