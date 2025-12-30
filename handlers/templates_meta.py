# Templates Meta API Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates
#
# This module handles template management via Meta Graph API
# including listing, creating, editing, and deleting templates.
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_waba_config
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Template Categories
TEMPLATE_CATEGORIES = ["UTILITY", "MARKETING", "AUTHENTICATION"]

# Template Statuses
TEMPLATE_STATUSES = ["APPROVED", "PENDING", "REJECTED", "PAUSED", "DISABLED", "IN_APPEAL"]

# Template Component Types
COMPONENT_TYPES = ["HEADER", "BODY", "FOOTER", "BUTTONS"]

# Header Formats
HEADER_FORMATS = ["TEXT", "IMAGE", "VIDEO", "DOCUMENT", "LOCATION"]

# Button Types
BUTTON_TYPES = ["QUICK_REPLY", "URL", "PHONE_NUMBER", "COPY_CODE", "FLOW", "MPM", "CATALOG", "VOICE_CALL"]


def handle_get_templates_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get templates from Meta Graph API (cached locally).
    
    This fetches templates from Meta and caches them locally.
    In production, this would call the Meta Graph API:
    GET /{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates
    
    Test Event:
    {
        "action": "get_templates_meta",
        "metaWabaId": "1347766229904230",
        "status": "APPROVED",
        "category": "MARKETING",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    category = event.get("category", "")
    name_filter = event.get("name", "")
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if status and status not in TEMPLATE_STATUSES:
        return {"statusCode": 400, "error": f"Invalid status. Valid: {TEMPLATE_STATUSES}"}
    
    if category and category not in TEMPLATE_CATEGORIES:
        return {"statusCode": 400, "error": f"Invalid category. Valid: {TEMPLATE_CATEGORIES}"}
    
    try:
        # Query local template cache
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "TEMPLATE_META", ":waba": meta_waba_id}
        expr_names = {}
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
            expr_names["#st"] = "status"
        
        if category:
            filter_expr += " AND category = :cat"
            expr_values[":cat"] = category
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit
        }
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table().scan(**scan_kwargs)
        items = response.get("Items", [])
        
        # Filter by name if provided
        if name_filter:
            items = [i for i in items if name_filter.lower() in i.get("name", "").lower()]
        
        return {
            "statusCode": 200,
            "operation": "get_templates_meta",
            "wabaMetaId": meta_waba_id,
            "count": len(items),
            "templates": items,
            "note": "For live data, call Meta Graph API: GET /{waba_id}/message_templates"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_cache_template_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Cache a template from Meta Graph API response.
    
    Use this to store template data fetched from Meta.
    
    Test Event:
    {
        "action": "cache_template_meta",
        "metaWabaId": "1347766229904230",
        "template": {
            "id": "123456789",
            "name": "order_confirmation",
            "language": "en_US",
            "status": "APPROVED",
            "category": "UTILITY",
            "components": [
                {"type": "HEADER", "format": "TEXT", "text": "Order Confirmation"},
                {"type": "BODY", "text": "Hi {{1}}, your order {{2}} has been confirmed."},
                {"type": "FOOTER", "text": "Thank you for shopping with us!"},
                {"type": "BUTTONS", "buttons": [
                    {"type": "URL", "text": "Track Order", "url": "https://example.com/track/{{1}}"}
                ]}
            ],
            "quality_score": {"score": "GREEN"}
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template = event.get("template", {})
    
    error = validate_required_fields(event, ["metaWabaId", "template"])
    if error:
        return error
    
    template_id = template.get("id", "")
    template_name = template.get("name", "")
    language = template.get("language", "en_US")
    
    if not template_name:
        return {"statusCode": 400, "error": "Template name is required"}
    
    now = iso_now()
    template_pk = f"TEMPLATE_META#{meta_waba_id}#{template_name}#{language}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: template_pk,
            "itemType": "TEMPLATE_META",
            "wabaMetaId": meta_waba_id,
            "templateId": template_id,
            "name": template_name,
            "language": language,
            "status": template.get("status", "PENDING"),
            "category": template.get("category", "UTILITY"),
            "components": template.get("components", []),
            "qualityScore": template.get("quality_score", {}).get("score", "UNKNOWN"),
            "cachedAt": now,
            "lastUpdatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "cache_template_meta",
            "templatePk": template_pk,
            "name": template_name,
            "language": language,
            "status": template.get("status", "PENDING")
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_create_template_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a new template (prepare for Meta Graph API submission).
    
    This creates a template definition locally. In production, you would
    then submit it to Meta via:
    POST /{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates
    
    Test Event:
    {
        "action": "create_template_meta",
        "metaWabaId": "1347766229904230",
        "name": "order_shipped",
        "language": "en_US",
        "category": "UTILITY",
        "components": [
            {
                "type": "HEADER",
                "format": "TEXT",
                "text": "Order Shipped! 📦"
            },
            {
                "type": "BODY",
                "text": "Hi {{1}}, your order {{2}} has been shipped!\\n\\nTracking: {{3}}\\nEstimated delivery: {{4}}"
            },
            {
                "type": "FOOTER",
                "text": "Thank you for your order"
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {"type": "URL", "text": "Track Package", "url": "https://track.example.com/{{1}}"},
                    {"type": "QUICK_REPLY", "text": "Contact Support"}
                ]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    name = event.get("name", "")
    language = event.get("language", "en_US")
    category = event.get("category", "UTILITY")
    components = event.get("components", [])
    allow_category_change = event.get("allowCategoryChange", True)
    
    error = validate_required_fields(event, ["metaWabaId", "name", "components"])
    if error:
        return error
    
    if category not in TEMPLATE_CATEGORIES:
        return {"statusCode": 400, "error": f"Invalid category. Valid: {TEMPLATE_CATEGORIES}"}
    
    # Validate components
    validation_result = _validate_template_components(components)
    if not validation_result["valid"]:
        return {"statusCode": 400, "error": validation_result["error"]}
    
    now = iso_now()
    template_pk = f"TEMPLATE_META#{meta_waba_id}#{name}#{language}"
    
    try:
        # Check if template already exists
        existing = get_item(template_pk)
        if existing:
            return {"statusCode": 409, "error": f"Template already exists: {name} ({language})"}
        
        store_item({
            MESSAGES_PK_NAME: template_pk,
            "itemType": "TEMPLATE_META",
            "wabaMetaId": meta_waba_id,
            "name": name,
            "language": language,
            "status": "DRAFT",  # Local status before submission
            "category": category,
            "components": components,
            "allowCategoryChange": allow_category_change,
            "createdAt": now,
            "lastUpdatedAt": now,
            "submittedToMeta": False,
        })
        
        # Generate Meta API payload
        meta_payload = {
            "name": name,
            "language": language,
            "category": category,
            "components": components,
            "allow_category_change": allow_category_change
        }
        
        return {
            "statusCode": 200,
            "operation": "create_template_meta",
            "templatePk": template_pk,
            "name": name,
            "language": language,
            "status": "DRAFT",
            "metaApiPayload": meta_payload,
            "nextStep": f"POST /{meta_waba_id}/message_templates with the metaApiPayload"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def _validate_template_components(components: List[Dict]) -> Dict[str, Any]:
    """Validate template components structure."""
    has_body = False
    button_count = 0
    
    for comp in components:
        comp_type = comp.get("type", "")
        
        if comp_type not in COMPONENT_TYPES:
            return {"valid": False, "error": f"Invalid component type: {comp_type}"}
        
        if comp_type == "HEADER":
            format_type = comp.get("format", "")
            if format_type and format_type not in HEADER_FORMATS:
                return {"valid": False, "error": f"Invalid header format: {format_type}"}
        
        if comp_type == "BODY":
            has_body = True
            if not comp.get("text"):
                return {"valid": False, "error": "Body component must have text"}
        
        if comp_type == "BUTTONS":
            buttons = comp.get("buttons", [])
            if len(buttons) > 10:
                return {"valid": False, "error": "Maximum 10 buttons allowed"}
            
            for btn in buttons:
                btn_type = btn.get("type", "")
                if btn_type not in BUTTON_TYPES:
                    return {"valid": False, "error": f"Invalid button type: {btn_type}"}
                
                if btn_type == "URL" and not btn.get("url"):
                    return {"valid": False, "error": "URL button must have url"}
                
                if btn_type == "PHONE_NUMBER" and not btn.get("phone_number"):
                    return {"valid": False, "error": "Phone button must have phone_number"}
    
    if not has_body:
        return {"valid": False, "error": "Template must have a BODY component"}
    
    return {"valid": True}


def handle_edit_template_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Edit an existing template.
    
    Note: Only certain fields can be edited after approval.
    
    Test Event:
    {
        "action": "edit_template_meta",
        "metaWabaId": "1347766229904230",
        "name": "order_shipped",
        "language": "en_US",
        "components": [...]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    name = event.get("name", "")
    language = event.get("language", "en_US")
    components = event.get("components", [])
    
    error = validate_required_fields(event, ["metaWabaId", "name", "components"])
    if error:
        return error
    
    template_pk = f"TEMPLATE_META#{meta_waba_id}#{name}#{language}"
    now = iso_now()
    
    try:
        existing = get_item(template_pk)
        if not existing:
            return {"statusCode": 404, "error": f"Template not found: {name} ({language})"}
        
        # Validate components
        validation_result = _validate_template_components(components)
        if not validation_result["valid"]:
            return {"statusCode": 400, "error": validation_result["error"]}
        
        # Update template
        table().update_item(
            Key={MESSAGES_PK_NAME: template_pk},
            UpdateExpression="SET components = :comp, lastUpdatedAt = :lu, editedLocally = :el",
            ExpressionAttributeValues={
                ":comp": components,
                ":lu": now,
                ":el": True
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "edit_template_meta",
            "name": name,
            "language": language,
            "updated": True,
            "note": "To update on Meta, use POST /{template_id} with the new components"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_delete_template_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete a template.
    
    Test Event:
    {
        "action": "delete_template_meta",
        "metaWabaId": "1347766229904230",
        "name": "order_shipped",
        "language": "en_US"
    }
    
    Or delete all languages:
    {
        "action": "delete_template_meta",
        "metaWabaId": "1347766229904230",
        "name": "order_shipped",
        "deleteAllLanguages": true
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    name = event.get("name", "")
    language = event.get("language", "")
    delete_all_languages = event.get("deleteAllLanguages", False)
    
    error = validate_required_fields(event, ["metaWabaId", "name"])
    if error:
        return error
    
    if not language and not delete_all_languages:
        return {"statusCode": 400, "error": "Specify language or set deleteAllLanguages=true"}
    
    now = iso_now()
    deleted_count = 0
    
    try:
        if delete_all_languages:
            # Find all language versions
            response = table().scan(
                FilterExpression="itemType = :it AND wabaMetaId = :waba AND #n = :name",
                ExpressionAttributeNames={"#n": "name"},
                ExpressionAttributeValues={
                    ":it": "TEMPLATE_META",
                    ":waba": meta_waba_id,
                    ":name": name
                }
            )
            items = response.get("Items", [])
            
            for item in items:
                pk = item.get(MESSAGES_PK_NAME)
                table().update_item(
                    Key={MESSAGES_PK_NAME: pk},
                    UpdateExpression="SET #st = :st, deletedAt = :da",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":st": "DELETED",
                        ":da": now
                    }
                )
                deleted_count += 1
        else:
            template_pk = f"TEMPLATE_META#{meta_waba_id}#{name}#{language}"
            existing = get_item(template_pk)
            
            if not existing:
                return {"statusCode": 404, "error": f"Template not found: {name} ({language})"}
            
            table().update_item(
                Key={MESSAGES_PK_NAME: template_pk},
                UpdateExpression="SET #st = :st, deletedAt = :da",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":st": "DELETED",
                    ":da": now
                }
            )
            deleted_count = 1
        
        return {
            "statusCode": 200,
            "operation": "delete_template_meta",
            "name": name,
            "deletedCount": deleted_count,
            "note": f"To delete on Meta, use DELETE /{meta_waba_id}/message_templates?name={name}"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_template_quality(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get template quality score.
    
    Test Event:
    {
        "action": "get_template_quality",
        "metaWabaId": "1347766229904230",
        "name": "order_confirmation",
        "language": "en_US"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    name = event.get("name", "")
    language = event.get("language", "en_US")
    
    error = validate_required_fields(event, ["metaWabaId", "name"])
    if error:
        return error
    
    template_pk = f"TEMPLATE_META#{meta_waba_id}#{name}#{language}"
    
    try:
        template = get_item(template_pk)
        
        if not template:
            return {"statusCode": 404, "error": f"Template not found: {name} ({language})"}
        
        # Query template usage for quality estimation
        response = table().scan(
            FilterExpression="itemType = :it AND templateName = :tn AND wabaMetaId = :waba",
            ExpressionAttributeValues={
                ":it": "MESSAGE",
                ":tn": name,
                ":waba": meta_waba_id
            },
            Limit=500
        )
        items = response.get("Items", [])
        
        total_sent = len(items)
        delivered = len([i for i in items if i.get("deliveryStatus") == "delivered"])
        read = len([i for i in items if i.get("deliveryStatus") == "read"])
        failed = len([i for i in items if i.get("deliveryStatus") == "failed"])
        
        # Estimate quality score
        if total_sent == 0:
            estimated_score = "UNKNOWN"
        elif failed / total_sent > 0.1:
            estimated_score = "RED"
        elif failed / total_sent > 0.05:
            estimated_score = "YELLOW"
        else:
            estimated_score = "GREEN"
        
        return {
            "statusCode": 200,
            "operation": "get_template_quality",
            "name": name,
            "language": language,
            "quality": {
                "score": template.get("qualityScore", estimated_score),
                "estimatedScore": estimated_score,
                "metrics": {
                    "totalSent": total_sent,
                    "delivered": delivered,
                    "read": read,
                    "failed": failed,
                    "deliveryRate": round(delivered / total_sent * 100, 2) if total_sent > 0 else 0,
                    "readRate": round(read / total_sent * 100, 2) if total_sent > 0 else 0,
                }
            },
            "note": "For actual quality score, use Meta Graph API: GET /{template_id}?fields=quality_score"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_sync_templates_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Sync templates from Meta Graph API response.
    
    Use this to bulk update local cache from Meta API response.
    
    Test Event:
    {
        "action": "sync_templates_meta",
        "metaWabaId": "1347766229904230",
        "templates": [
            {"id": "123", "name": "template1", "language": "en_US", "status": "APPROVED", ...},
            {"id": "456", "name": "template2", "language": "en_US", "status": "PENDING", ...}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    templates = event.get("templates", [])
    
    error = validate_required_fields(event, ["metaWabaId", "templates"])
    if error:
        return error
    
    now = iso_now()
    synced_count = 0
    errors = []
    
    try:
        for template in templates:
            try:
                result = handle_cache_template_meta({
                    "metaWabaId": meta_waba_id,
                    "template": template
                }, None)
                
                if result.get("statusCode") == 200:
                    synced_count += 1
                else:
                    errors.append({
                        "name": template.get("name"),
                        "error": result.get("error")
                    })
            except Exception as e:
                errors.append({
                    "name": template.get("name"),
                    "error": str(e)
                })
        
        return {
            "statusCode": 200,
            "operation": "sync_templates_meta",
            "wabaMetaId": meta_waba_id,
            "syncedCount": synced_count,
            "totalTemplates": len(templates),
            "errors": errors if errors else None,
            "syncedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
