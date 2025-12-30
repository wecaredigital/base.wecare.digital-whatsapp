# Carousel Message Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-media-carousel-messages
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-product-carousel-messages
#
# This module handles media and product carousel messages
# =============================================================================

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_phone_arn,
    validate_required_fields, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Maximum cards in a carousel
MAX_CAROUSEL_CARDS = 10
MIN_CAROUSEL_CARDS = 2


def handle_send_media_carousel(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send interactive media carousel message (images/videos with buttons).
    
    Media carousels allow sending 2-10 cards, each with:
    - Image or video header
    - Body text
    - Up to 2 buttons per card
    
    Test Event:
    {
        "action": "send_media_carousel",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "bodyText": "Check out our latest collection!",
        "cards": [
            {
                "header": {"type": "image", "mediaId": "123456"},
                "body": "Summer Collection 2024",
                "buttons": [
                    {"type": "quick_reply", "text": "View Details", "payload": "view_summer"},
                    {"type": "url", "text": "Shop Now", "url": "https://example.com/summer"}
                ]
            },
            {
                "header": {"type": "video", "mediaId": "789012"},
                "body": "Winter Collection 2024",
                "buttons": [
                    {"type": "quick_reply", "text": "View Details", "payload": "view_winter"}
                ]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body_text = event.get("bodyText", "")
    cards = event.get("cards", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "cards"])
    if error:
        return error
    
    if len(cards) < MIN_CAROUSEL_CARDS:
        return {"statusCode": 400, "error": f"Minimum {MIN_CAROUSEL_CARDS} cards required"}
    if len(cards) > MAX_CAROUSEL_CARDS:
        return {"statusCode": 400, "error": f"Maximum {MAX_CAROUSEL_CARDS} cards allowed"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build carousel cards
        carousel_cards = []
        for idx, card in enumerate(cards):
            header = card.get("header", {})
            header_type = header.get("type", "image")
            
            card_obj = {
                "card_index": idx,
                "components": []
            }
            
            # Header component (image or video)
            header_component = {"type": "header", "parameters": []}
            if header.get("mediaId"):
                header_component["parameters"].append({
                    "type": header_type,
                    header_type: {"id": header.get("mediaId")}
                })
            elif header.get("link"):
                header_component["parameters"].append({
                    "type": header_type,
                    header_type: {"link": header.get("link")}
                })
            card_obj["components"].append(header_component)
            
            # Body component
            if card.get("body"):
                card_obj["components"].append({
                    "type": "body",
                    "parameters": [{"type": "text", "text": card.get("body")}]
                })
            
            # Button components (max 2 per card)
            buttons = card.get("buttons", [])[:2]
            for btn_idx, btn in enumerate(buttons):
                btn_component = {
                    "type": "button",
                    "sub_type": btn.get("type", "quick_reply"),
                    "index": str(btn_idx),
                    "parameters": []
                }
                if btn.get("type") == "url" and btn.get("url"):
                    btn_component["parameters"].append({"type": "text", "text": btn.get("url")})
                elif btn.get("payload"):
                    btn_component["parameters"].append({"type": "payload", "payload": btn.get("payload")})
                card_obj["components"].append(btn_component)
            
            carousel_cards.append(card_obj)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": {
                "type": "carousel",
                "body": {"text": body_text or "Browse our collection"},
                "action": {
                    "cards": carousel_cards
                }
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            store_item({
                MESSAGES_PK_NAME: f"CAROUSEL#{result.get('messageId')}",
                "itemType": "MEDIA_CAROUSEL",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "cardCount": len(cards),
                "messageId": result.get("messageId"),
                "createdAt": iso_now()
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_media_carousel",
            "cardCount": len(cards),
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_product_carousel(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send interactive product carousel message from catalog.
    
    Product carousels display products from your catalog with:
    - Product image from catalog
    - Product name and price
    - View product button
    
    Test Event:
    {
        "action": "send_product_carousel",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "catalogId": "123456789",
        "bodyText": "Check out these products!",
        "sections": [
            {
                "title": "Featured Products",
                "productIds": ["SKU001", "SKU002", "SKU003"]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    catalog_id = event.get("catalogId", "")
    body_text = event.get("bodyText", "")
    sections = event.get("sections", [])
    header_text = event.get("headerText", "")
    footer_text = event.get("footerText", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "catalogId", "sections"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    # Count total products
    total_products = sum(len(s.get("productIds", [])) for s in sections)
    if total_products < 1:
        return {"statusCode": 400, "error": "At least 1 product required"}
    if total_products > 30:
        return {"statusCode": 400, "error": "Maximum 30 products allowed"}
    
    try:
        # Build product sections
        product_sections = []
        for section in sections:
            product_items = [
                {"product_retailer_id": pid}
                for pid in section.get("productIds", [])
            ]
            product_sections.append({
                "title": section.get("title", "Products"),
                "product_items": product_items
            })
        
        interactive = {
            "type": "product_list",
            "body": {"text": body_text or "Browse our products"},
            "action": {
                "catalog_id": catalog_id,
                "sections": product_sections
            }
        }
        
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            store_item({
                MESSAGES_PK_NAME: f"PRODUCT_CAROUSEL#{result.get('messageId')}",
                "itemType": "PRODUCT_CAROUSEL",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "catalogId": catalog_id,
                "productCount": total_products,
                "messageId": result.get("messageId"),
                "createdAt": iso_now()
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_product_carousel",
            "catalogId": catalog_id,
            "productCount": total_products,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_single_product(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send single product message (SPM) from catalog.
    
    Test Event:
    {
        "action": "send_single_product",
        "metaWabaId": "1347766229904230",
        "to": "+447447840003",
        "catalogId": "123456789",
        "productId": "SKU001",
        "bodyText": "Check out this product!"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    catalog_id = event.get("catalogId", "")
    product_id = event.get("productId", "")
    body_text = event.get("bodyText", "")
    footer_text = event.get("footerText", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "catalogId", "productId"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        interactive = {
            "type": "product",
            "body": {"text": body_text or "View product details"},
            "action": {
                "catalog_id": catalog_id,
                "product_retailer_id": product_id
            }
        }
        
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_single_product",
            "catalogId": catalog_id,
            "productId": product_id,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
