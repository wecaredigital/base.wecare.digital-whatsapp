# Template Library Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates/template-library
#
# This module handles pre-built template library management
# =============================================================================

import logging
from typing import Any, Dict, List
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Pre-built template categories
TEMPLATE_CATEGORIES = [
    "UTILITY",
    "MARKETING", 
    "AUTHENTICATION",
    "SERVICE",
    "ALERT",
    "APPOINTMENT",
    "SHIPPING",
    "PAYMENT",
    "FEEDBACK",
    "WELCOME"
]

# Sample pre-built templates
PREBUILT_TEMPLATES = {
    "order_confirmation": {
        "category": "UTILITY",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}, your order #{{2}} has been confirmed. Total: {{3}}"}
        ],
        "variables": ["customer_name", "order_id", "total_amount"]
    },
    "shipping_update": {
        "category": "UTILITY", 
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}, your order #{{2}} has been shipped. Track: {{3}}"}
        ],
        "variables": ["customer_name", "order_id", "tracking_url"]
    },
    "appointment_reminder": {
        "category": "UTILITY",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}, reminder: Your appointment is on {{2}} at {{3}}"}
        ],
        "variables": ["customer_name", "date", "time"]
    },
    "payment_received": {
        "category": "UTILITY",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}, we received your payment of {{2}} for order #{{3}}. Thank you!"}
        ],
        "variables": ["customer_name", "amount", "order_id"]
    },
    "otp_verification": {
        "category": "AUTHENTICATION",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Your verification code is {{1}}. Valid for {{2}} minutes."}
        ],
        "variables": ["otp_code", "validity_minutes"]
    },
    "welcome_message": {
        "category": "MARKETING",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Welcome to {{1}}! We're excited to have you. Reply HELP for assistance."}
        ],
        "variables": ["business_name"]
    },
    "feedback_request": {
        "category": "MARKETING",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}, how was your experience with order #{{2}}? Rate us: {{3}}"}
        ],
        "variables": ["customer_name", "order_id", "rating_url"]
    },
    "promotional_offer": {
        "category": "MARKETING",
        "language": "en",
        "components": [
            {"type": "BODY", "text": "Hi {{1}}! Get {{2}}% off on your next order. Use code: {{3}}. Valid till {{4}}"}
        ],
        "variables": ["customer_name", "discount_percent", "coupon_code", "expiry_date"]
    }
}


def handle_get_template_library(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get available pre-built templates from library.
    
    Test Event:
    {
        "action": "get_template_library",
        "category": "UTILITY"
    }
    """
    category = event.get("category", "")
    language = event.get("language", "en")
    
    try:
        templates = []
        for name, template in PREBUILT_TEMPLATES.items():
            if category and template.get("category") != category:
                continue
            if language and template.get("language") != language:
                continue
            templates.append({
                "name": name,
                **template
            })
        
        return {
            "statusCode": 200,
            "operation": "get_template_library",
            "count": len(templates),
            "categories": TEMPLATE_CATEGORIES,
            "templates": templates
        }
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_use_library_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Use a pre-built template from library (creates local copy).
    
    Test Event:
    {
        "action": "use_library_template",
        "metaWabaId": "1347766229904230",
        "templateName": "order_confirmation",
        "customName": "my_order_confirmation"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    custom_name = event.get("customName", "")
    
    error = validate_required_fields(event, ["metaWabaId", "templateName"])
    if error:
        return error
    
    if template_name not in PREBUILT_TEMPLATES:
        return {"statusCode": 404, "error": f"Template not found: {template_name}"}
    
    try:
        source_template = PREBUILT_TEMPLATES[template_name]
        final_name = custom_name or template_name
        
        template_pk = f"TEMPLATE_LOCAL#{meta_waba_id}#{final_name}"
        now = iso_now()
        
        store_item({
            MESSAGES_PK_NAME: template_pk,
            "itemType": "TEMPLATE_LOCAL",
            "wabaMetaId": meta_waba_id,
            "name": final_name,
            "sourceTemplate": template_name,
            "category": source_template["category"],
            "language": source_template["language"],
            "components": source_template["components"],
            "variables": source_template["variables"],
            "status": "draft",
            "createdAt": now,
            "fromLibrary": True
        })
        
        return {
            "statusCode": 200,
            "operation": "use_library_template",
            "templateName": final_name,
            "sourceTemplate": template_name,
            "category": source_template["category"],
            "status": "draft",
            "note": "Template created locally. Submit to Meta for approval."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_local_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get locally created templates.
    
    Test Event:
    {
        "action": "get_local_templates",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "TEMPLATE_LOCAL", ":waba": meta_waba_id}
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values
        }
        if status:
            scan_kwargs["ExpressionAttributeNames"] = {"#st": "status"}
        
        response = table().scan(**scan_kwargs)
        
        return {
            "statusCode": 200,
            "operation": "get_local_templates",
            "count": len(response.get("Items", [])),
            "templates": response.get("Items", [])
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_customize_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Customize a local template before submission.
    
    Test Event:
    {
        "action": "customize_template",
        "metaWabaId": "1347766229904230",
        "templateName": "my_order_confirmation",
        "components": [
            {"type": "BODY", "text": "Hello {{1}}, order #{{2}} confirmed! Amount: {{3}}"}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    components = event.get("components", [])
    header = event.get("header", {})
    footer = event.get("footer", "")
    buttons = event.get("buttons", [])
    
    error = validate_required_fields(event, ["metaWabaId", "templateName"])
    if error:
        return error
    
    template_pk = f"TEMPLATE_LOCAL#{meta_waba_id}#{template_name}"
    now = iso_now()
    
    try:
        existing = get_item(template_pk)
        if not existing:
            return {"statusCode": 404, "error": f"Template not found: {template_name}"}
        
        update_expr = "SET lastModifiedAt = :lm"
        expr_values = {":lm": now}
        
        if components:
            update_expr += ", components = :comp"
            expr_values[":comp"] = components
        if header:
            update_expr += ", header = :hdr"
            expr_values[":hdr"] = header
        if footer:
            update_expr += ", footer = :ftr"
            expr_values[":ftr"] = footer
        if buttons:
            update_expr += ", buttons = :btns"
            expr_values[":btns"] = buttons
        
        table().update_item(
            Key={MESSAGES_PK_NAME: template_pk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        return {
            "statusCode": 200,
            "operation": "customize_template",
            "templateName": template_name,
            "updated": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
