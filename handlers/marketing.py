# Marketing Messages & Templates Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET,
    iso_now, get_phone_arn, get_waba_config, validate_required_fields,
    store_item, format_wa_number, send_whatsapp_message, origination_id_for_api,
    META_API_VERSION
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Template Categories
TEMPLATE_CATEGORIES = {
    "UTILITY": "Transactional messages - order updates, shipping, appointments",
    "AUTHENTICATION": "OTP, verification codes, login confirmations", 
    "MARKETING": "Promotional messages, offers, announcements"
}

# Marketing Template Types
MARKETING_TEMPLATE_TYPES = [
    "custom", "call_permission", "catalog", "coupon", 
    "limited_time_offer", "media_card_carousel", "mpm", "spm", "product_card_carousel"
]


def handle_create_marketing_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a marketing message template.
    
    Test Event:
    {
        "action": "create_marketing_template",
        "metaWabaId": "1347766229904230",
        "templateName": "summer_sale",
        "language": "en_US",
        "category": "MARKETING",
        "templateType": "custom",
        "components": [
            {"type": "HEADER", "format": "IMAGE"},
            {"type": "BODY", "text": "Summer sale! Get {{1}}% off on all items. Use code: {{2}}"},
            {"type": "FOOTER", "text": "Valid until {{3}}"},
            {"type": "BUTTONS", "buttons": [
                {"type": "URL", "text": "Shop Now", "url": "https://shop.com/sale/{{1}}"}
            ]}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    language = event.get("language", "en_US")
    category = event.get("category", "MARKETING")
    template_type = event.get("templateType", "custom")
    components = event.get("components", [])
    
    error = validate_required_fields(event, ["metaWabaId", "templateName", "components"])
    if error:
        return error
    
    if category not in TEMPLATE_CATEGORIES:
        return {"statusCode": 400, "error": f"Invalid category. Valid: {list(TEMPLATE_CATEGORIES.keys())}"}
    
    now = iso_now()
    template_pk = f"TEMPLATE#{meta_waba_id}#{template_name}#{language}"
    
    try:
        template_data = {
            MESSAGES_PK_NAME: template_pk,
            "itemType": "TEMPLATE_DEFINITION",
            "wabaMetaId": meta_waba_id,
            "templateName": template_name,
            "language": language,
            "category": category,
            "templateType": template_type,
            "components": components,
            "status": "PENDING",
            "createdAt": now,
            "lastUpdatedAt": now,
        }
        
        store_item(template_data)
        
        return {
            "statusCode": 200,
            "operation": "create_marketing_template",
            "templatePk": template_pk,
            "templateName": template_name,
            "status": "PENDING",
            "message": "Template created. Submit to Meta for approval."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_marketing_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send a marketing message using approved template.
    
    Test Event:
    {
        "action": "send_marketing_message",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "summer_sale",
        "languageCode": "en_US",
        "headerMediaId": "123456789",
        "bodyParams": ["50", "SUMMER50", "Aug 31"],
        "buttonParams": [{"index": 0, "urlSuffix": "summer2024"}]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    header_media_id = event.get("headerMediaId", "")
    header_media_link = event.get("headerMediaLink", "")
    body_params = event.get("bodyParams", [])
    button_params = event.get("buttonParams", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build template components
        components = []
        
        # Header component (if media)
        if header_media_id or header_media_link:
            header_param = {"type": "image"}
            if header_media_id:
                header_param["image"] = {"id": header_media_id}
            else:
                header_param["image"] = {"link": header_media_link}
            components.append({"type": "header", "parameters": [header_param]})
        
        # Body component
        if body_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in body_params]
            })
        
        # Button components
        for btn in button_params:
            components.append({
                "type": "button",
                "sub_type": "url",
                "index": str(btn.get("index", 0)),
                "parameters": [{"type": "text", "text": btn.get("urlSuffix", "")}]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            # Store sent message
            now = iso_now()
            msg_pk = f"MSG#MARKETING#{result['messageId']}"
            store_item({
                MESSAGES_PK_NAME: msg_pk,
                "itemType": "MARKETING_MESSAGE",
                "direction": "OUTBOUND",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "templateName": template_name,
                "languageCode": language_code,
                "messageId": result["messageId"],
                "sentAt": now,
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_marketing_message",
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_utility_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send utility template (order updates, shipping, appointments).
    
    Test Event:
    {
        "action": "send_utility_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "order_confirmation",
        "languageCode": "en_US",
        "bodyParams": ["ORD-12345", "John Doe", "Dec 30, 2024"]
    }
    """
    event["category"] = "UTILITY"
    return handle_send_marketing_message(event, context)


def handle_send_auth_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send authentication template (OTP, verification).
    
    Test Event:
    {
        "action": "send_auth_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "otp_verification",
        "languageCode": "en_US",
        "otpCode": "123456",
        "expiryMinutes": 10
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    otp_code = event.get("otpCode", "")
    expiry_minutes = event.get("expiryMinutes", 10)
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "otpCode"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Auth template with copy code button
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": otp_code},
                            {"type": "text", "text": str(expiry_minutes)}
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": "0",
                        "parameters": [{"type": "text", "text": otp_code}]
                    }
                ]
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            now = iso_now()
            store_item({
                MESSAGES_PK_NAME: f"MSG#AUTH#{result['messageId']}",
                "itemType": "AUTH_MESSAGE",
                "direction": "OUTBOUND",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "templateName": template_name,
                "otpSent": True,
                "expiryMinutes": expiry_minutes,
                "sentAt": now,
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_auth_template",
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_catalog_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send catalog template with product information.
    
    Test Event:
    {
        "action": "send_catalog_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "product_catalog",
        "languageCode": "en_US",
        "thumbnailProductRetailerId": "SKU123"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    thumbnail_product_id = event.get("thumbnailProductRetailerId", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        components = []
        if thumbnail_product_id:
            components.append({
                "type": "header",
                "parameters": [{
                    "type": "product",
                    "product": {"product_retailer_id": thumbnail_product_id}
                }]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        return {"statusCode": 200 if result.get("success") else 500, "operation": "send_catalog_template", **result}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_coupon_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send coupon code template.
    
    Test Event:
    {
        "action": "send_coupon_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "discount_coupon",
        "languageCode": "en_US",
        "couponCode": "SAVE20",
        "discountPercent": "20",
        "expiryDate": "Dec 31, 2024"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    coupon_code = event.get("couponCode", "")
    discount_percent = event.get("discountPercent", "")
    expiry_date = event.get("expiryDate", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "couponCode"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        body_params = []
        if discount_percent:
            body_params.append({"type": "text", "text": discount_percent})
        if expiry_date:
            body_params.append({"type": "text", "text": expiry_date})
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [
                    {"type": "body", "parameters": body_params} if body_params else None,
                    {
                        "type": "button",
                        "sub_type": "copy_code",
                        "index": "0",
                        "parameters": [{"type": "coupon_code", "coupon_code": coupon_code}]
                    }
                ]
            }
        }
        # Remove None components
        payload["template"]["components"] = [c for c in payload["template"]["components"] if c]
        
        result = send_whatsapp_message(phone_arn, payload)
        return {"statusCode": 200 if result.get("success") else 500, "operation": "send_coupon_template", **result}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_limited_offer_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send limited-time offer template with countdown.
    
    Test Event:
    {
        "action": "send_limited_offer_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "flash_sale",
        "languageCode": "en_US",
        "offerExpirationTimestamp": 1735689600,
        "couponCode": "FLASH50",
        "bodyParams": ["50%", "Electronics"]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    expiration_ts = event.get("offerExpirationTimestamp", 0)
    coupon_code = event.get("couponCode", "")
    body_params = event.get("bodyParams", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "offerExpirationTimestamp"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        components = [
            {
                "type": "limited_time_offer",
                "parameters": [{"type": "limited_time_offer", "limited_time_offer": {"expiration_time_ms": expiration_ts * 1000}}]
            }
        ]
        
        if body_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in body_params]
            })
        
        if coupon_code:
            components.append({
                "type": "button",
                "sub_type": "copy_code",
                "index": "0",
                "parameters": [{"type": "coupon_code", "coupon_code": coupon_code}]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        return {"statusCode": 200 if result.get("success") else 500, "operation": "send_limited_offer_template", **result}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_carousel_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send carousel template (media card or product card).
    
    Test Event:
    {
        "action": "send_carousel_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "product_showcase",
        "languageCode": "en_US",
        "cards": [
            {
                "headerMediaId": "media123",
                "bodyParams": ["Product 1", "$99"],
                "buttonUrlSuffix": "product1"
            },
            {
                "headerMediaId": "media456",
                "bodyParams": ["Product 2", "$149"],
                "buttonUrlSuffix": "product2"
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    cards = event.get("cards", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "cards"])
    if error:
        return error
    
    if len(cards) < 2 or len(cards) > 10:
        return {"statusCode": 400, "error": "Carousel requires 2-10 cards"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        carousel_cards = []
        for idx, card in enumerate(cards):
            card_components = []
            
            # Header (image/video)
            if card.get("headerMediaId"):
                card_components.append({
                    "type": "header",
                    "parameters": [{"type": "image", "image": {"id": card["headerMediaId"]}}]
                })
            
            # Body params
            if card.get("bodyParams"):
                card_components.append({
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in card["bodyParams"]]
                })
            
            # Button
            if card.get("buttonUrlSuffix"):
                card_components.append({
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": card["buttonUrlSuffix"]}]
                })
            
            carousel_cards.append({"card_index": idx, "components": card_components})
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [{"type": "carousel", "cards": carousel_cards}]
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        return {"statusCode": 200 if result.get("success") else 500, "operation": "send_carousel_template", **result}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_mpm_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send Multi-Product Message (MPM) template.
    
    Test Event:
    {
        "action": "send_mpm_template",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "templateName": "multi_product",
        "languageCode": "en_US",
        "catalogId": "catalog123",
        "sections": [
            {
                "title": "Featured Products",
                "productRetailerIds": ["SKU001", "SKU002", "SKU003"]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language_code = event.get("languageCode", "en_US")
    catalog_id = event.get("catalogId", "")
    sections = event.get("sections", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "catalogId", "sections"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build MPM action
        mpm_sections = []
        for section in sections:
            mpm_sections.append({
                "title": section.get("title", "Products"),
                "product_items": [{"product_retailer_id": pid} for pid in section.get("productRetailerIds", [])]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [{
                    "type": "button",
                    "sub_type": "mpm",
                    "index": "0",
                    "parameters": [{
                        "type": "action",
                        "action": {
                            "thumbnail_product_retailer_id": sections[0]["productRetailerIds"][0] if sections and sections[0].get("productRetailerIds") else "",
                            "sections": mpm_sections
                        }
                    }]
                }]
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        return {"statusCode": 200 if result.get("success") else 500, "operation": "send_mpm_template", **result}
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_template_analytics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get template performance analytics.
    
    Test Event:
    {
        "action": "get_template_analytics",
        "metaWabaId": "1347766229904230",
        "templateName": "summer_sale",
        "startDate": "2024-12-01",
        "endDate": "2024-12-30"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query sent messages for this template
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "MARKETING_MESSAGE", ":waba": meta_waba_id}
        
        if template_name:
            filter_expr += " AND templateName = :tn"
            expr_values[":tn"] = template_name
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        
        items = response.get("Items", [])
        
        # Calculate analytics
        total_sent = len(items)
        delivered = len([i for i in items if i.get("deliveryStatus") == "delivered"])
        read = len([i for i in items if i.get("deliveryStatus") == "read"])
        failed = len([i for i in items if i.get("deliveryStatus") == "failed"])
        
        return {
            "statusCode": 200,
            "operation": "get_template_analytics",
            "wabaMetaId": meta_waba_id,
            "templateName": template_name or "all",
            "analytics": {
                "totalSent": total_sent,
                "delivered": delivered,
                "read": read,
                "failed": failed,
                "deliveryRate": round(delivered / total_sent * 100, 2) if total_sent > 0 else 0,
                "readRate": round(read / total_sent * 100, 2) if total_sent > 0 else 0,
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_template_pacing(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get template pacing information.
    
    Test Event:
    {
        "action": "get_template_pacing",
        "metaWabaId": "1347766229904230",
        "templateName": "summer_sale"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    
    error = validate_required_fields(event, ["metaWabaId", "templateName"])
    if error:
        return error
    
    # Get template from cache
    template_pk = f"TEMPLATES#{meta_waba_id}"
    try:
        response = table().get_item(Key={MESSAGES_PK_NAME: template_pk})
        templates_data = response.get("Item", {})
        templates = templates_data.get("templates", [])
        
        template_info = next((t for t in templates if t.get("templateName") == template_name), None)
        
        if not template_info:
            return {"statusCode": 404, "error": f"Template not found: {template_name}"}
        
        return {
            "statusCode": 200,
            "operation": "get_template_pacing",
            "templateName": template_name,
            "pacing": {
                "qualityScore": template_info.get("templateQualityScore", "UNKNOWN"),
                "status": template_info.get("templateStatus", "UNKNOWN"),
                "pacingInfo": {
                    "description": "Templates may be subject to pacing limits based on quality",
                    "recommendation": "Maintain GREEN quality score for maximum throughput"
                }
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_template_ttl(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set template message TTL (Time To Live).
    
    Test Event:
    {
        "action": "set_template_ttl",
        "metaWabaId": "1347766229904230",
        "templateName": "flash_sale",
        "ttlSeconds": 3600
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    ttl_seconds = event.get("ttlSeconds", 86400)
    
    error = validate_required_fields(event, ["metaWabaId", "templateName"])
    if error:
        return error
    
    now = iso_now()
    ttl_pk = f"TEMPLATE_TTL#{meta_waba_id}#{template_name}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: ttl_pk,
            "itemType": "TEMPLATE_TTL",
            "wabaMetaId": meta_waba_id,
            "templateName": template_name,
            "ttlSeconds": ttl_seconds,
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_template_ttl",
            "templateName": template_name,
            "ttlSeconds": ttl_seconds,
            "message": f"TTL set to {ttl_seconds} seconds"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
