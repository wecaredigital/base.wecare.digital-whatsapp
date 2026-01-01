# =============================================================================
# Welcome Message & Interactive Menu System (Production-Ready)
# =============================================================================
# AWS EUM-only implementation with:
# - 4 internal actions: send_menu_main, send_menu_services, send_menu_selfservice, send_menu_support
# - Inbound interactive list reply handler
# - Keyword triggers + cooldown (anti-spam)
# - Seed menu CLI/admin action
# - Verified live URLs from wecare.digital
# =============================================================================

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from handlers.base import (
    table, social, MESSAGES_PK_NAME, WABA_PHONE_MAP, META_API_VERSION,
    iso_now, store_item, get_item, update_item, query_items,
    validate_required_fields, success_response, error_response,
    origination_id_for_api, format_wa_number,
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_WELCOME_TEXT = """Welcome to WECARE.DIGITAL 👋

Pick an option from the menu below, or type what you need help with."""

# Menu keywords that trigger auto-menu (case-insensitive)
MENU_KEYWORDS = ["menu", "help", "start", "hi"]

# Default cooldown for welcome/menu (hours)
DEFAULT_COOLDOWN_HOURS = 72

# WhatsApp Interactive List constraints
MAX_ROWS_PER_MENU = 10
MAX_TITLE_LENGTH = 24
MAX_DESCRIPTION_LENGTH = 72
MAX_BUTTON_LENGTH = 20

# =============================================================================
# MENU DEFINITIONS (Verified Live URLs)
# =============================================================================

MENU_MAIN = {
    "menuId": "main",
    "buttonText": "Menu",
    "bodyText": "Welcome to WECARE.DIGITAL 👋\nPick an option below:",
    "sections": [
        {
            "title": "START HERE",
            "rows": [
                {"rowId": "go_services", "title": "Services", "description": "Explore brands like BNB, No Fault, Legal Champ.", "actionType": "invoke_action", "actionValue": "send_menu_services"},
                {"rowId": "go_selfservice", "title": "Self Service", "description": "Submit, track, amend, upload docs, RX slot.", "actionType": "invoke_action", "actionValue": "send_menu_selfservice"},
                {"rowId": "go_support", "title": "Support", "description": "FAQ, contact, app, careers, legal.", "actionType": "invoke_action", "actionValue": "send_menu_support"},
            ]
        },
        {
            "title": "QUICK ACTIONS",
            "rows": [
                {"rowId": "qa_submit", "title": "Submit Request", "description": "Start a new request in the portal.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/submit-request", "answerText": "Submit a Request ✅\nStart a new service request in the portal.\nhttps://www.wecare.digital/submit-request"},
                {"rowId": "qa_track", "title": "Request Tracking", "description": "Check status of an existing request.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/request-tracking", "answerText": "Request Tracking 🔎\nCheck the current status of an existing request.\nhttps://www.wecare.digital/request-tracking"},
                {"rowId": "qa_drop", "title": "Drop Docs", "description": "Upload documents securely.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/drop-docs", "answerText": "Drop Docs 📄\nUpload your documents securely for your request.\nhttps://www.wecare.digital/drop-docs"},
                {"rowId": "qa_app", "title": "Download App", "description": "Track, book, upload & pay on the go.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/one", "answerText": "WECARE App 📱\nTrack, book, upload, and pay on the go.\nhttps://www.wecare.digital/one"},
                {"rowId": "qa_contact", "title": "Contact", "description": "Call / email / address.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/contact", "answerText": "Contact WECARE.DIGITAL ☎️\nCall or email us (details on the page).\nhttps://www.wecare.digital/contact"},
                {"rowId": "qa_gift", "title": "Gift Card", "description": "Buy a WECARE.DIGITAL gift card.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/gift-card", "answerText": "Gift Card 🎁\nSend a WECARE.DIGITAL gift card (any amount).\nhttps://www.wecare.digital/gift-card"},
            ]
        }
    ]
}

MENU_SERVICES = {
    "menuId": "services",
    "buttonText": "Services",
    "bodyText": "Which WECARE.DIGITAL service do you want?",
    "sections": [
        {
            "title": "MICROSERVICE BRANDS",
            "rows": [
                {"rowId": "svc_bnb", "title": "BNB CLUB", "description": "Travel agency + tourism support.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/bnb", "answerText": "BNB CLUB (Travel) ✈️\nTourism and travel agency support.\nhttps://www.wecare.digital/bnb"},
                {"rowId": "svc_expoweek", "title": "EXPO WEEK", "description": "Digital events + expo experiences.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/expoweek", "answerText": "EXPO WEEK (Events) 🎟️\nDigital events and expo experiences.\nhttps://www.wecare.digital/expoweek"},
                {"rowId": "svc_legalchamp", "title": "LEGAL CHAMP", "description": "Business documentation services.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/legal-champ", "answerText": "LEGAL CHAMP (Documentation) 📑\nBusiness documentation & registration support.\nhttps://www.wecare.digital/legal-champ"},
                {"rowId": "svc_nofault", "title": "NO FAULT", "description": "Online dispute resolution platform.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/no-fault", "answerText": "NO FAULT (ODR) ⚖️\nOnline dispute resolution in one secure interface.\nhttps://www.wecare.digital/no-fault"},
                {"rowId": "svc_ritual", "title": "RITUAL GURU", "description": "Puja kits + step-by-step guides.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/ritual", "answerText": "RITUAL GURU (Culture) 🪔\nTemple-grade puja kits with step-by-step guides.\nhttps://www.wecare.digital/ritual"},
                {"rowId": "svc_swdhya", "title": "SWDHYA", "description": "Self-inquiry conversations for clarity.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/swdhya", "answerText": "SWDHYA (Clarity) 💬\nConversational self-inquiry for clarity and action.\nhttps://www.wecare.digital/swdhya"},
                {"rowId": "svc_partner", "title": "PARTNER UP", "description": "Partner with WECARE.DIGITAL.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/partner-up", "answerText": "Partner Up 🤝\nExplore collaboration with WECARE.DIGITAL.\nhttps://www.wecare.digital/partner-up"},
                {"rowId": "svc_about", "title": "About WECARE", "description": "What is WECARE.DIGITAL?", "actionType": "send_text", "actionValue": "WECARE.DIGITAL is a microservice company ecosystem. Pick a brand above or open Self Service to start a request.\nhttps://www.wecare.digital/"},
                {"rowId": "back_main", "title": "⬅ Back", "description": "Return to Main Menu.", "actionType": "invoke_action", "actionValue": "send_menu_main"},
            ]
        }
    ]
}

MENU_SELFSERVICE = {
    "menuId": "selfservice",
    "buttonText": "Self Service",
    "bodyText": "Choose a Self Service action:",
    "sections": [
        {
            "title": "PORTAL ACTIONS",
            "rows": [
                {"rowId": "ss_hub", "title": "Self Service Hub", "description": "All actions in one place.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/selfservice", "answerText": "Self Service Hub 🏠\nAll self-service actions in one place.\nhttps://www.wecare.digital/selfservice"},
                {"rowId": "ss_submit", "title": "Submit Request", "description": "Start a new service request.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/submit-request", "answerText": "Submit a Request ✅\nStart a new service request in the portal.\nhttps://www.wecare.digital/submit-request"},
                {"rowId": "ss_amend", "title": "Request Amendment", "description": "Update an existing request.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/request-amendment", "answerText": "Request Amendment ✏️\nUpdate or modify an existing request.\nhttps://www.wecare.digital/request-amendment"},
                {"rowId": "ss_track", "title": "Request Tracking", "description": "Check request status.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/request-tracking", "answerText": "Request Tracking 🔎\nCheck the current status of an existing request.\nhttps://www.wecare.digital/request-tracking"},
                {"rowId": "ss_rx", "title": "RX Slot", "description": "Book or manage an RX slot.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/rx-slot", "answerText": "RX Slot 📅\nBook or manage your RX slot.\nhttps://www.wecare.digital/rx-slot"},
                {"rowId": "ss_docs", "title": "Drop Docs", "description": "Upload documents securely.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/drop-docs", "answerText": "Drop Docs 📄\nUpload your documents securely for your request.\nhttps://www.wecare.digital/drop-docs"},
                {"rowId": "ss_enterprise", "title": "Enterprise Assist", "description": "Enterprise support intake.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/enterprise-assist", "answerText": "Enterprise Assist 🏢\nEnterprise-level support and intake.\nhttps://www.wecare.digital/enterprise-assist"},
                {"rowId": "ss_review", "title": "Leave Review", "description": "Share feedback or rating.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/leave-review", "answerText": "Leave Review ⭐\nShare your feedback or rating.\nhttps://www.wecare.digital/leave-review"},
                {"rowId": "back_main", "title": "⬅ Back", "description": "Return to Main Menu.", "actionType": "invoke_action", "actionValue": "send_menu_main"},
            ]
        }
    ]
}

MENU_SUPPORT = {
    "menuId": "support",
    "buttonText": "Support",
    "bodyText": "Need help or info? Choose below:",
    "sections": [
        {
            "title": "HELP & INFO",
            "rows": [
                {"rowId": "sup_faq", "title": "FAQ", "description": "Quick answers + portal links.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/faq", "answerText": "FAQ ❓\nQuick answers to common questions.\nhttps://www.wecare.digital/faq"},
                {"rowId": "sup_hours", "title": "Business Hours", "description": "Mon–Fri, 9am–6pm IST.", "actionType": "send_text", "actionValue": "Business Hours 🕐\nMonday–Friday, 9:00am–6:00pm IST.\nhttps://www.wecare.digital/faq"},
                {"rowId": "sup_contact", "title": "Contact Us", "description": "Phone + email + address.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/contact", "answerText": "Contact WECARE.DIGITAL ☎️\nCall or email us (details on the page).\nhttps://www.wecare.digital/contact"},
                {"rowId": "sup_app", "title": "Download App", "description": "Track, book, upload & pay.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/one", "answerText": "WECARE App 📱\nTrack, book, upload, and pay on the go.\nhttps://www.wecare.digital/one"},
                {"rowId": "sup_gift", "title": "Gift Card", "description": "Buy a WECARE gift card.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/gift-card", "answerText": "Gift Card 🎁\nSend a WECARE.DIGITAL gift card (any amount).\nhttps://www.wecare.digital/gift-card"},
                {"rowId": "sup_careers", "title": "Careers + Culture", "description": "Join the team.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/careers-plus-culture", "answerText": "Careers + Culture 💼\nJoin the WECARE.DIGITAL team.\nhttps://www.wecare.digital/careers-plus-culture"},
                {"rowId": "sup_legal", "title": "Legal Stuff", "description": "Policies + legal info.", "actionType": "open_url", "actionValue": "https://www.wecare.digital/legal-stuff", "answerText": "Legal Stuff 📜\nPolicies, terms, and legal information.\nhttps://www.wecare.digital/legal-stuff"},
                {"rowId": "back_main", "title": "⬅ Back", "description": "Return to Main Menu.", "actionType": "invoke_action", "actionValue": "send_menu_main"},
            ]
        }
    ]
}

# Menu ID to definition mapping
MENU_DEFINITIONS = {
    "main": MENU_MAIN,
    "services": MENU_SERVICES,
    "selfservice": MENU_SELFSERVICE,
    "support": MENU_SUPPORT,
}

# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_menu_constraints(menu_config: Dict[str, Any]) -> List[str]:
    """Validate menu against WhatsApp Interactive List constraints.
    
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    button_text = menu_config.get("buttonText", "")
    if len(button_text) > MAX_BUTTON_LENGTH:
        errors.append(f"buttonText exceeds {MAX_BUTTON_LENGTH} chars: {len(button_text)}")
    
    total_rows = 0
    for section in menu_config.get("sections", []):
        for row in section.get("rows", []):
            total_rows += 1
            title = row.get("title", "")
            desc = row.get("description", "")
            
            if len(title) > MAX_TITLE_LENGTH:
                errors.append(f"Row '{row.get('rowId')}' title exceeds {MAX_TITLE_LENGTH} chars: {len(title)}")
            if len(desc) > MAX_DESCRIPTION_LENGTH:
                errors.append(f"Row '{row.get('rowId')}' description exceeds {MAX_DESCRIPTION_LENGTH} chars: {len(desc)}")
    
    if total_rows > MAX_ROWS_PER_MENU:
        errors.append(f"Total rows ({total_rows}) exceeds max {MAX_ROWS_PER_MENU}")
    
    return errors


def get_phone_config(meta_waba_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Get phone ARN and formatted number from WABA config."""
    config = WABA_PHONE_MAP.get(str(meta_waba_id), {})
    if not config:
        return None, None
    return config.get("phoneArn"), config.get("phoneE164")


# =============================================================================
# CORE: SEND INTERACTIVE LIST MENU
# =============================================================================

def _build_interactive_list_payload(to: str, menu_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build WhatsApp interactive list payload from menu config."""
    sections = []
    for section in menu_config.get("sections", []):
        rows = []
        for row in section.get("rows", []):
            rows.append({
                "id": row["rowId"],
                "title": row["title"][:MAX_TITLE_LENGTH],
                "description": row.get("description", "")[:MAX_DESCRIPTION_LENGTH],
            })
        sections.append({
            "title": section["title"][:MAX_TITLE_LENGTH],
            "rows": rows[:MAX_ROWS_PER_MENU],
        })
    
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": menu_config.get("bodyText", "Select an option:")},
            "action": {
                "button": menu_config.get("buttonText", "Menu")[:MAX_BUTTON_LENGTH],
                "sections": sections[:10],
            }
        }
    }


def _send_whatsapp_message(phone_arn: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send WhatsApp message via AWS EUM."""
    try:
        response = social().send_whatsapp_message(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            metaApiVersion=str(META_API_VERSION),
            message=json.dumps(payload).encode("utf-8"),
        )
        return {"success": True, "messageId": response.get("messageId", "")}
    except ClientError as e:
        logger.exception(f"Failed to send WhatsApp message: {e}")
        return {"success": False, "error": str(e)}

# =============================================================================
# STEP 2: INTERNAL ACTIONS (send_menu_main, send_menu_services, etc.)
# =============================================================================

def _send_menu_by_id(meta_waba_id: str, to: str, menu_id: str, context: Any = None) -> Dict[str, Any]:
    """Core function to send a menu by ID. Used by all send_menu_* handlers."""
    phone_arn, _ = get_phone_config(meta_waba_id)
    if not phone_arn:
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    to_formatted = format_wa_number(to)
    
    # Try to get menu from DDB first, fall back to defaults
    menu_config = _get_menu_from_ddb(meta_waba_id, menu_id)
    if not menu_config:
        menu_config = MENU_DEFINITIONS.get(menu_id)
    
    if not menu_config:
        return error_response(f"Menu not found: {menu_id}", 404)
    
    # Validate constraints
    errors = validate_menu_constraints(menu_config)
    if errors:
        logger.warning(f"Menu validation warnings for {menu_id}: {errors}")
    
    # Build and send
    payload = _build_interactive_list_payload(to_formatted, menu_config)
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        # Log menu sent
        store_item({
            MESSAGES_PK_NAME: f"MENU_SENT#{to_formatted}#{iso_now()}",
            "itemType": "MENU_SENT",
            "wabaMetaId": meta_waba_id,
            "to": to_formatted,
            "menuId": menu_id,
            "messageId": result.get("messageId"),
            "sentAt": iso_now(),
        })
        return success_response(f"send_menu_{menu_id}", messageId=result.get("messageId"), to=to_formatted, menuId=menu_id)
    
    return error_response(result.get("error", "Failed to send menu"), 500)


def _get_menu_from_ddb(tenant_id: str, menu_id: str) -> Optional[Dict[str, Any]]:
    """Get menu config from DynamoDB."""
    pk = f"TENANT#{tenant_id}#MENU#{menu_id}"
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: pk})
        item = response.get("Item")
        if item:
            return {
                "menuId": item.get("menuId", menu_id),
                "buttonText": item.get("buttonText", "Menu"),
                "bodyText": item.get("bodyText", "Select an option:"),
                "sections": item.get("sections", []),
            }
    except ClientError as e:
        logger.warning(f"Failed to get menu from DDB: {e}")
    return None


def handle_send_menu_main(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send main menu. Internal action target for invoke_action."""
    err = validate_required_fields(event, ["metaWabaId", "to"])
    if err:
        return err
    return _send_menu_by_id(event["metaWabaId"], event["to"], "main", context)


def handle_send_menu_services(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send services submenu. Internal action target for invoke_action."""
    err = validate_required_fields(event, ["metaWabaId", "to"])
    if err:
        return err
    return _send_menu_by_id(event["metaWabaId"], event["to"], "services", context)


def handle_send_menu_selfservice(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send self-service submenu. Internal action target for invoke_action."""
    err = validate_required_fields(event, ["metaWabaId", "to"])
    if err:
        return err
    return _send_menu_by_id(event["metaWabaId"], event["to"], "selfservice", context)


def handle_send_menu_support(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send support submenu. Internal action target for invoke_action."""
    err = validate_required_fields(event, ["metaWabaId", "to"])
    if err:
        return err
    return _send_menu_by_id(event["metaWabaId"], event["to"], "support", context)

# =============================================================================
# STEP 3: INBOUND INTERACTIVE LIST REPLY HANDLER
# =============================================================================

def _find_row_in_menus(row_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """Find a row by ID across all menus (DDB first, then defaults)."""
    # Check all menu IDs
    for menu_id in ["main", "services", "selfservice", "support"]:
        # Try DDB first
        menu_config = _get_menu_from_ddb(tenant_id, menu_id)
        if not menu_config:
            menu_config = MENU_DEFINITIONS.get(menu_id, {})
        
        for section in menu_config.get("sections", []):
            for row in section.get("rows", []):
                if row.get("rowId") == row_id:
                    return row
    return None


def handle_list_reply(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle inbound interactive list reply.
    
    Detects messages[].interactive.list_reply.id, looks up row, executes action.
    
    Required: metaWabaId, to (recipient = original sender), listReplyId
    """
    meta_waba_id = event.get("metaWabaId", "")
    to = event.get("to", "")  # Reply goes back to the user who selected
    list_reply_id = event.get("listReplyId", "")
    
    err = validate_required_fields(event, ["metaWabaId", "to", "listReplyId"])
    if err:
        return err
    
    phone_arn, _ = get_phone_config(meta_waba_id)
    if not phone_arn:
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    to_formatted = format_wa_number(to)
    
    # Find the row
    row = _find_row_in_menus(list_reply_id, meta_waba_id)
    if not row:
        logger.warning(f"List reply ID not found: {list_reply_id}")
        return error_response(f"Menu selection not found: {list_reply_id}", 404)
    
    action_type = row.get("actionType", "open_url")
    action_value = row.get("actionValue", "")
    answer_text = row.get("answerText", "")
    
    # Log selection
    store_item({
        MESSAGES_PK_NAME: f"MENU_SELECTION#{to_formatted}#{iso_now()}",
        "itemType": "MENU_SELECTION",
        "wabaMetaId": meta_waba_id,
        "to": to_formatted,
        "rowId": list_reply_id,
        "actionType": action_type,
        "selectedAt": iso_now(),
    })
    
    # Execute action
    if action_type == "invoke_action":
        # Dispatch in-process (no HTTP, no lambda invoke)
        action_name = action_value  # e.g., "send_menu_services"
        return _dispatch_internal_action(action_name, meta_waba_id, to_formatted, context)
    
    elif action_type == "open_url":
        # Send crisp Q/A + link
        text = answer_text if answer_text else f"{row.get('title', '')}\n{action_value}"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_formatted,
            "type": "text",
            "text": {"body": text, "preview_url": True}
        }
        result = _send_whatsapp_message(phone_arn, payload)
        return success_response("handle_list_reply", messageId=result.get("messageId"), rowId=list_reply_id, actionType=action_type)
    
    elif action_type == "send_text":
        # Send configured text
        payload = {
            "messaging_product": "whatsapp",
            "to": to_formatted,
            "type": "text",
            "text": {"body": action_value}
        }
        result = _send_whatsapp_message(phone_arn, payload)
        return success_response("handle_list_reply", messageId=result.get("messageId"), rowId=list_reply_id, actionType=action_type)
    
    else:
        return error_response(f"Unknown action type: {action_type}", 400)


def _dispatch_internal_action(action_name: str, meta_waba_id: str, to: str, context: Any) -> Dict[str, Any]:
    """Dispatch internal action in-process (no HTTP, no lambda invoke)."""
    action_event = {"metaWabaId": meta_waba_id, "to": to}
    
    if action_name == "send_menu_main":
        return handle_send_menu_main(action_event, context)
    elif action_name == "send_menu_services":
        return handle_send_menu_services(action_event, context)
    elif action_name == "send_menu_selfservice":
        return handle_send_menu_selfservice(action_event, context)
    elif action_name == "send_menu_support":
        return handle_send_menu_support(action_event, context)
    else:
        return error_response(f"Unknown internal action: {action_name}", 400)

# =============================================================================
# STEP 4: KEYWORD TRIGGERS + COOLDOWN (Anti-Spam)
# =============================================================================

def _check_cooldown(to: str, item_type: str, cooldown_hours: int) -> Tuple[bool, Optional[str]]:
    """Check if cooldown has passed for a given item type.
    
    Returns (cooldown_passed, last_sent_at).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
    
    try:
        # Query recent sends
        response = table().scan(
            FilterExpression="itemType = :it AND #to = :to AND sentAt > :cutoff",
            ExpressionAttributeValues={
                ":it": item_type,
                ":to": to,
                ":cutoff": cutoff,
            },
            ExpressionAttributeNames={"#to": "to"},
            Limit=1,
        )
        items = response.get("Items", [])
        if items:
            return False, items[0].get("sentAt")
        return True, None
    except ClientError as e:
        logger.warning(f"Cooldown check failed: {e}")
        return True, None  # Allow on error


def handle_check_keyword_trigger(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if inbound message matches menu keywords and handle with cooldown.
    
    Called from IngestLambda for cheap keyword detection.
    
    Required: metaWabaId, from, messageText
    Optional: cooldownHours (default 72)
    """
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    message_text = event.get("messageText", "").lower().strip()
    cooldown_hours = event.get("cooldownHours", DEFAULT_COOLDOWN_HOURS)
    
    err = validate_required_fields(event, ["metaWabaId", "from", "messageText"])
    if err:
        return err
    
    from_formatted = format_wa_number(from_number)
    
    # Check if message matches keywords
    if message_text not in MENU_KEYWORDS:
        return success_response("check_keyword_trigger",
            triggered=False,
            reason="Message does not match keywords",
            keywords=MENU_KEYWORDS,
        )
    
    # Check cooldown
    cooldown_passed, last_sent = _check_cooldown(from_formatted, "MENU_SENT", cooldown_hours)
    
    if not cooldown_passed:
        # Optionally send a short reminder instead of full menu
        return success_response("check_keyword_trigger",
            triggered=False,
            reason=f"Cooldown active (sent within {cooldown_hours}h)",
            lastSentAt=last_sent,
            hint="Type MENU anytime to see options.",
        )
    
    # Send main menu
    result = _send_menu_by_id(meta_waba_id, from_formatted, "main", context)
    
    return success_response("check_keyword_trigger",
        triggered=True,
        matchedKeyword=message_text,
        menuSent="main",
        messageId=result.get("messageId"),
    )


def handle_send_welcome(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send welcome message with optional menu.
    
    Required: metaWabaId, to
    Optional: includeMenu (default True), cooldownHours
    """
    meta_waba_id = event.get("metaWabaId", "")
    to = event.get("to", "")
    include_menu = event.get("includeMenu", True)
    cooldown_hours = event.get("cooldownHours", DEFAULT_COOLDOWN_HOURS)
    
    err = validate_required_fields(event, ["metaWabaId", "to"])
    if err:
        return err
    
    phone_arn, _ = get_phone_config(meta_waba_id)
    if not phone_arn:
        return error_response(f"WABA not found: {meta_waba_id}", 404)
    
    to_formatted = format_wa_number(to)
    
    # Check cooldown
    cooldown_passed, last_sent = _check_cooldown(to_formatted, "WELCOME_SENT", cooldown_hours)
    if not cooldown_passed:
        return success_response("send_welcome",
            sent=False,
            reason=f"Cooldown active (sent within {cooldown_hours}h)",
            lastSentAt=last_sent,
        )
    
    # Send welcome text
    payload = {
        "messaging_product": "whatsapp",
        "to": to_formatted,
        "type": "text",
        "text": {"body": DEFAULT_WELCOME_TEXT}
    }
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        store_item({
            MESSAGES_PK_NAME: f"WELCOME_SENT#{to_formatted}#{iso_now()}",
            "itemType": "WELCOME_SENT",
            "wabaMetaId": meta_waba_id,
            "to": to_formatted,
            "messageId": result.get("messageId"),
            "sentAt": iso_now(),
        })
    
    # Optionally send menu after welcome
    menu_result = None
    if include_menu and result.get("success"):
        menu_result = _send_menu_by_id(meta_waba_id, to_formatted, "main", context)
    
    return success_response("send_welcome",
        sent=True,
        welcomeMessageId=result.get("messageId"),
        menuMessageId=menu_result.get("messageId") if menu_result else None,
    )

# =============================================================================
# STEP 6: SEED MENU CLI/ADMIN ACTION
# =============================================================================

def handle_seed_menu_configs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Seed menu configurations from /deploy/menu-data/*.json or defaults.
    
    Reads menu JSON files and upserts to DynamoDB.
    
    Required: tenantId
    Optional: fromFiles (default False - use embedded defaults)
    """
    tenant_id = event.get("tenantId", "")
    from_files = event.get("fromFiles", False)
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    now = iso_now()
    results = []
    
    # Menu IDs to seed
    menu_ids = ["main", "services", "selfservice", "support"]
    
    for menu_id in menu_ids:
        menu_config = None
        
        if from_files:
            # Try to load from file (for CLI usage)
            try:
                file_path = f"deploy/menu-data/menu-{menu_id}.json"
                with open(file_path, "r", encoding="utf-8") as f:
                    menu_config = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")
        
        # Fall back to embedded defaults
        if not menu_config:
            menu_config = MENU_DEFINITIONS.get(menu_id)
        
        if not menu_config:
            results.append({"menuId": menu_id, "status": "not_found"})
            continue
        
        # Validate
        errors = validate_menu_constraints(menu_config)
        if errors:
            logger.warning(f"Menu {menu_id} validation warnings: {errors}")
        
        # Upsert to DDB
        pk = f"TENANT#{tenant_id}#MENU#{menu_id}"
        item = {
            MESSAGES_PK_NAME: pk,
            "itemType": "MENU_CONFIG",
            "tenantId": tenant_id,
            "menuId": menu_id,
            "buttonText": menu_config.get("buttonText", "Menu"),
            "bodyText": menu_config.get("bodyText", "Select an option:"),
            "sections": menu_config.get("sections", []),
            "updatedAt": now,
            "createdAt": now,
        }
        
        try:
            store_item(item)
            results.append({"menuId": menu_id, "status": "seeded", "pk": pk})
        except ClientError as e:
            results.append({"menuId": menu_id, "status": "error", "error": str(e)})
    
    # Also seed welcome config
    welcome_pk = f"TENANT#{tenant_id}#WELCOME#default"
    try:
        store_item({
            MESSAGES_PK_NAME: welcome_pk,
            "itemType": "WELCOME_CONFIG",
            "tenantId": tenant_id,
            "welcomeText": DEFAULT_WELCOME_TEXT,
            "enabled": True,
            "onlyOnFirstContact": False,
            "cooldownHours": DEFAULT_COOLDOWN_HOURS,
            "autoMenuKeywords": MENU_KEYWORDS,
            "updatedAt": now,
            "createdAt": now,
        })
        results.append({"menuId": "welcome", "status": "seeded", "pk": welcome_pk})
    except ClientError as e:
        results.append({"menuId": "welcome", "status": "error", "error": str(e)})
    
    return success_response("seed_menu_configs",
        tenantId=tenant_id,
        results=results,
        menusSeeded=len([r for r in results if r.get("status") == "seeded"]),
    )


# =============================================================================
# ADDITIONAL HANDLERS
# =============================================================================

def handle_get_menu_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get menu configuration for a tenant.
    
    Required: tenantId
    Optional: menuId (default "main")
    """
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    menu_id = event.get("menuId", "main")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    # Try DDB first
    menu_config = _get_menu_from_ddb(tenant_id, menu_id)
    is_default = False
    
    if not menu_config:
        menu_config = MENU_DEFINITIONS.get(menu_id)
        is_default = True
    
    if not menu_config:
        return error_response(f"Menu not found: {menu_id}", 404)
    
    return success_response("get_menu_config",
        tenantId=tenant_id,
        menuId=menu_id,
        isDefault=is_default,
        config=menu_config,
    )


def handle_get_welcome_config(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get welcome configuration for a tenant."""
    tenant_id = event.get("tenantId") or event.get("metaWabaId", "")
    
    if not tenant_id:
        return error_response("tenantId is required")
    
    pk = f"TENANT#{tenant_id}#WELCOME#default"
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: pk})
        item = response.get("Item")
        
        if item:
            return success_response("get_welcome_config",
                tenantId=tenant_id,
                isDefault=False,
                config={
                    "welcomeText": item.get("welcomeText", DEFAULT_WELCOME_TEXT),
                    "enabled": item.get("enabled", True),
                    "onlyOnFirstContact": item.get("onlyOnFirstContact", False),
                    "cooldownHours": item.get("cooldownHours", DEFAULT_COOLDOWN_HOURS),
                    "autoMenuKeywords": item.get("autoMenuKeywords", MENU_KEYWORDS),
                },
            )
    except ClientError as e:
        logger.warning(f"Failed to get welcome config: {e}")
    
    # Return defaults
    return success_response("get_welcome_config",
        tenantId=tenant_id,
        isDefault=True,
        config={
            "welcomeText": DEFAULT_WELCOME_TEXT,
            "enabled": True,
            "onlyOnFirstContact": False,
            "cooldownHours": DEFAULT_COOLDOWN_HOURS,
            "autoMenuKeywords": MENU_KEYWORDS,
        },
    )

# =============================================================================
# AUTO-TRIGGER HANDLERS (called from app.py lambda_handler)
# =============================================================================

def handle_check_auto_welcome(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if we should send welcome message (first contact or cooldown expired).
    
    Called automatically from lambda_handler for every inbound message.
    
    Required: metaWabaId, from
    """
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    
    if not meta_waba_id or not from_number:
        return {"sent": False, "reason": "Missing metaWabaId or from"}
    
    from_formatted = format_wa_number(from_number)
    
    # Check cooldown
    cooldown_passed, last_sent = _check_cooldown(from_formatted, "WELCOME_SENT", DEFAULT_COOLDOWN_HOURS)
    
    if not cooldown_passed:
        return {"sent": False, "reason": f"Cooldown active (sent within {DEFAULT_COOLDOWN_HOURS}h)", "lastSentAt": last_sent}
    
    # Send welcome + menu
    phone_arn, _ = get_phone_config(meta_waba_id)
    if not phone_arn:
        return {"sent": False, "reason": f"WABA not found: {meta_waba_id}"}
    
    # Send welcome text
    payload = {
        "messaging_product": "whatsapp",
        "to": from_formatted,
        "type": "text",
        "text": {"body": DEFAULT_WELCOME_TEXT}
    }
    result = _send_whatsapp_message(phone_arn, payload)
    
    if result.get("success"):
        # Log welcome sent
        store_item({
            MESSAGES_PK_NAME: f"WELCOME_SENT#{from_formatted}#{iso_now()}",
            "itemType": "WELCOME_SENT",
            "wabaMetaId": meta_waba_id,
            "to": from_formatted,
            "messageId": result.get("messageId"),
            "sentAt": iso_now(),
        })
        
        # Also send main menu
        menu_result = _send_menu_by_id(meta_waba_id, from_formatted, "main", context)
        
        return {
            "sent": True,
            "welcomeMessageId": result.get("messageId"),
            "menuMessageId": menu_result.get("messageId") if menu_result else None,
        }
    
    return {"sent": False, "reason": result.get("error", "Failed to send welcome")}


def handle_check_auto_menu(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if inbound message matches menu keywords and send menu.
    
    Called automatically from lambda_handler for every inbound text message.
    
    Required: metaWabaId, from, messageText
    """
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    message_text = event.get("messageText", "").lower().strip()
    
    if not meta_waba_id or not from_number or not message_text:
        return {"sent": False, "reason": "Missing required fields"}
    
    from_formatted = format_wa_number(from_number)
    
    # Check if message matches keywords
    if message_text not in MENU_KEYWORDS:
        return {"sent": False, "reason": "Message does not match keywords", "keywords": MENU_KEYWORDS}
    
    # Check cooldown (shorter for menu - 1 hour)
    cooldown_passed, last_sent = _check_cooldown(from_formatted, "MENU_SENT", 1)
    
    if not cooldown_passed:
        return {"sent": False, "reason": "Menu cooldown active (sent within 1h)", "lastSentAt": last_sent}
    
    # Send main menu
    result = _send_menu_by_id(meta_waba_id, from_formatted, "main", context)
    
    if result.get("statusCode") == 200:
        return {
            "sent": True,
            "matchedKeyword": message_text,
            "menuSent": "main",
            "messageId": result.get("messageId"),
        }
    
    return {"sent": False, "reason": result.get("error", "Failed to send menu")}


# =============================================================================
# HANDLER MAPPING (for dispatcher registration)
# =============================================================================

WELCOME_MENU_HANDLERS = {
    # Step 2: Internal menu actions
    "send_menu_main": handle_send_menu_main,
    "send_menu_services": handle_send_menu_services,
    "send_menu_selfservice": handle_send_menu_selfservice,
    "send_menu_support": handle_send_menu_support,
    
    # Step 3: List reply handler
    "handle_list_reply": handle_list_reply,
    
    # Step 4: Keyword trigger + welcome
    "check_keyword_trigger": handle_check_keyword_trigger,
    "send_welcome": handle_send_welcome,
    
    # Auto-trigger handlers (called from lambda_handler)
    "check_auto_welcome": handle_check_auto_welcome,
    "check_auto_menu": handle_check_auto_menu,
    
    # Step 6: Seed menu configs
    "seed_menu_configs": handle_seed_menu_configs,
    
    # Config getters
    "get_menu_config": handle_get_menu_config,
    "get_welcome_config": handle_get_welcome_config,
}
