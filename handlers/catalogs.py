# Catalogs Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/catalogs

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, s3, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    iso_now, store_item, get_item, validate_required_fields,
    get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()


def handle_upload_catalog(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload product catalog.
    
    Test Event:
    {
        "action": "upload_catalog",
        "metaWabaId": "1347766229904230",
        "catalogName": "Main Catalog",
        "products": [
            {
                "retailerId": "SKU001",
                "name": "Product A",
                "description": "Description of Product A",
                "price": 999,
                "currency": "INR",
                "imageUrl": "https://example.com/product-a.jpg",
                "category": "Electronics",
                "availability": "in_stock"
            },
            {
                "retailerId": "SKU002",
                "name": "Product B",
                "description": "Description of Product B",
                "price": 1499,
                "currency": "INR",
                "imageUrl": "https://example.com/product-b.jpg",
                "category": "Electronics",
                "availability": "in_stock"
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    catalog_name = event.get("catalogName", "")
    products = event.get("products", [])
    
    error = validate_required_fields(event, ["metaWabaId", "catalogName", "products"])
    if error:
        return error
    
    now = iso_now()
    catalog_id = f"CATALOG_{now.replace(':', '').replace('-', '').replace('.', '')}"
    catalog_pk = f"CATALOG#{meta_waba_id}#{catalog_id}"
    
    try:
        # Store catalog
        catalog_data = {
            MESSAGES_PK_NAME: catalog_pk,
            "itemType": "CATALOG",
            "catalogId": catalog_id,
            "wabaMetaId": meta_waba_id,
            "catalogName": catalog_name,
            "productCount": len(products),
            "createdAt": now,
            "lastUpdatedAt": now,
            "status": "active",
        }
        store_item(catalog_data)
        
        # Store each product
        for product in products:
            product_pk = f"PRODUCT#{catalog_id}#{product.get('retailerId', '')}"
            store_item({
                MESSAGES_PK_NAME: product_pk,
                "itemType": "PRODUCT",
                "catalogId": catalog_id,
                "wabaMetaId": meta_waba_id,
                "retailerId": product.get("retailerId", ""),
                "name": product.get("name", ""),
                "description": product.get("description", ""),
                "price": product.get("price", 0),
                "currency": product.get("currency", "INR"),
                "imageUrl": product.get("imageUrl", ""),
                "category": product.get("category", ""),
                "availability": product.get("availability", "in_stock"),
                "createdAt": now,
            })
        
        return {
            "statusCode": 200,
            "operation": "upload_catalog",
            "catalogId": catalog_id,
            "catalogPk": catalog_pk,
            "productCount": len(products)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_catalog_products(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get products from a catalog.
    
    Test Event:
    {
        "action": "get_catalog_products",
        "catalogId": "CATALOG_20241230120000",
        "category": "Electronics",
        "limit": 50
    }
    """
    catalog_id = event.get("catalogId", "")
    category = event.get("category", "")
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["catalogId"])
    if error:
        return error
    
    try:
        filter_expr = "itemType = :it AND catalogId = :cid"
        expr_values = {":it": "PRODUCT", ":cid": catalog_id}
        
        if category:
            filter_expr += " AND category = :cat"
            expr_values[":cat"] = category
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        
        items = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "operation": "get_catalog_products",
            "catalogId": catalog_id,
            "count": len(items),
            "products": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_catalog_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send catalog/product message.
    
    Test Event (Single Product):
    {
        "action": "send_catalog_message",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "messageType": "product",
        "catalogId": "CATALOG_123",
        "productRetailerId": "SKU001",
        "body": "Check out this product!"
    }
    
    Test Event (Product List):
    {
        "action": "send_catalog_message",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "messageType": "product_list",
        "catalogId": "CATALOG_123",
        "header": "Our Products",
        "body": "Browse our collection",
        "sections": [
            {
                "title": "Featured",
                "productRetailerIds": ["SKU001", "SKU002"]
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    message_type = event.get("messageType", "product")
    catalog_id = event.get("catalogId", "")
    product_retailer_id = event.get("productRetailerId", "")
    header = event.get("header", "")
    body = event.get("body", "")
    footer = event.get("footer", "")
    sections = event.get("sections", [])
    
    error = validate_required_fields(event, ["metaWabaId", "to", "catalogId"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        if message_type == "product":
            # Single Product Message (SPM)
            payload = {
                "messaging_product": "whatsapp",
                "to": format_wa_number(to_number),
                "type": "interactive",
                "interactive": {
                    "type": "product",
                    "body": {"text": body} if body else None,
                    "footer": {"text": footer} if footer else None,
                    "action": {
                        "catalog_id": catalog_id,
                        "product_retailer_id": product_retailer_id
                    }
                }
            }
        else:
            # Multi-Product Message (MPM)
            mpm_sections = []
            for section in sections:
                mpm_sections.append({
                    "title": section.get("title", "Products"),
                    "product_items": [
                        {"product_retailer_id": pid} 
                        for pid in section.get("productRetailerIds", [])
                    ]
                })
            
            payload = {
                "messaging_product": "whatsapp",
                "to": format_wa_number(to_number),
                "type": "interactive",
                "interactive": {
                    "type": "product_list",
                    "header": {"type": "text", "text": header} if header else None,
                    "body": {"text": body} if body else None,
                    "footer": {"text": footer} if footer else None,
                    "action": {
                        "catalog_id": catalog_id,
                        "sections": mpm_sections
                    }
                }
            }
        
        # Clean None values
        if payload["interactive"].get("body") is None:
            del payload["interactive"]["body"]
        if payload["interactive"].get("footer") is None:
            del payload["interactive"]["footer"]
        if payload["interactive"].get("header") is None:
            del payload["interactive"]["header"]
        
        result = send_whatsapp_message(phone_arn, payload)
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_catalog_message",
            "messageType": message_type,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
