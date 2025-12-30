# Commerce Advanced Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/sell-products-and-services

import json
import logging
from typing import Any, Dict, List
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Catalog Sync Status
SYNC_STATUSES = ["PENDING", "SYNCING", "SYNCED", "FAILED"]

# Product Availability
AVAILABILITY_OPTIONS = ["in stock", "out of stock", "preorder", "available for order"]


def handle_create_catalog_meta(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a catalog in Meta Commerce Manager.
    
    Test Event:
    {
        "action": "create_catalog_meta",
        "metaWabaId": "1347766229904230",
        "catalogName": "My Products",
        "catalogType": "ECOMMERCE"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    catalog_name = event.get("catalogName", "")
    catalog_type = event.get("catalogType", "ECOMMERCE")
    
    error = validate_required_fields(event, ["metaWabaId", "catalogName"])
    if error:
        return error

    now = iso_now()
    catalog_id = f"CAT_{now.replace(':', '').replace('-', '').replace('.', '')}"
    catalog_pk = f"CATALOG#{meta_waba_id}#{catalog_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: catalog_pk,
            "itemType": "CATALOG",
            "catalogId": catalog_id,
            "wabaMetaId": meta_waba_id,
            "catalogName": catalog_name,
            "catalogType": catalog_type,
            "syncStatus": "PENDING",
            "productCount": 0,
            "createdAt": now,
            "lastUpdatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "create_catalog_meta",
            "catalogId": catalog_id,
            "catalogName": catalog_name,
            "syncStatus": "PENDING",
            "note": "Actual catalog creation requires Meta Commerce Manager API"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_sync_catalog(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Sync catalog with Meta Commerce Manager.
    
    Test Event:
    {
        "action": "sync_catalog",
        "metaWabaId": "1347766229904230",
        "catalogId": "CAT_xxx",
        "products": [
            {"retailerId": "SKU001", "name": "Product 1", "price": 1000, "currency": "INR"}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    catalog_id = event.get("catalogId", "")
    products = event.get("products", [])
    
    error = validate_required_fields(event, ["metaWabaId", "catalogId"])
    if error:
        return error
    
    catalog_pk = f"CATALOG#{meta_waba_id}#{catalog_id}"
    now = iso_now()
    
    try:
        catalog = get_item(catalog_pk)
        if not catalog:
            return {"statusCode": 404, "error": f"Catalog not found: {catalog_id}"}
        
        # Update sync status
        table().update_item(
            Key={MESSAGES_PK_NAME: catalog_pk},
            UpdateExpression="SET syncStatus = :ss, lastSyncAt = :ls, productCount = :pc",
            ExpressionAttributeValues={
                ":ss": "SYNCING",
                ":ls": now,
                ":pc": len(products)
            }
        )
        
        # Store products
        for product in products:
            product_pk = f"PRODUCT#{catalog_id}#{product.get('retailerId', '')}"
            store_item({
                MESSAGES_PK_NAME: product_pk,
                "itemType": "PRODUCT",
                "catalogId": catalog_id,
                "wabaMetaId": meta_waba_id,
                **product,
                "syncedAt": now,
            })
        
        # Mark as synced
        table().update_item(
            Key={MESSAGES_PK_NAME: catalog_pk},
            UpdateExpression="SET syncStatus = :ss",
            ExpressionAttributeValues={":ss": "SYNCED"}
        )
        
        return {
            "statusCode": 200,
            "operation": "sync_catalog",
            "catalogId": catalog_id,
            "productsSynced": len(products),
            "syncStatus": "SYNCED"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_catalog_insights(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get catalog performance insights.
    
    Test Event:
    {
        "action": "get_catalog_insights",
        "metaWabaId": "1347766229904230",
        "catalogId": "CAT_xxx"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    catalog_id = event.get("catalogId", "")
    
    error = validate_required_fields(event, ["metaWabaId", "catalogId"])
    if error:
        return error
    
    try:
        # Query catalog messages
        response = table().scan(
            FilterExpression="itemType = :it AND catalogId = :cid",
            ExpressionAttributeValues={":it": "CATALOG_MESSAGE", ":cid": catalog_id},
            Limit=500
        )
        items = response.get("Items", [])
        
        # Query products
        products_response = table().scan(
            FilterExpression="itemType = :it AND catalogId = :cid",
            ExpressionAttributeValues={":it": "PRODUCT", ":cid": catalog_id},
            Limit=500
        )
        products = products_response.get("Items", [])
        
        # Calculate insights
        views = len([i for i in items if i.get("action") == "view"])
        clicks = len([i for i in items if i.get("action") == "click"])
        purchases = len([i for i in items if i.get("action") == "purchase"])
        
        return {
            "statusCode": 200,
            "operation": "get_catalog_insights",
            "catalogId": catalog_id,
            "insights": {
                "totalProducts": len(products),
                "catalogViews": views,
                "productClicks": clicks,
                "purchases": purchases,
                "conversionRate": round(purchases / clicks * 100, 2) if clicks > 0 else 0,
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_product_availability(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update product availability/stock status.
    
    Test Event:
    {
        "action": "update_product_availability",
        "catalogId": "CAT_xxx",
        "retailerId": "SKU001",
        "availability": "in stock",
        "quantity": 100
    }
    """
    catalog_id = event.get("catalogId", "")
    retailer_id = event.get("retailerId", "")
    availability = event.get("availability", "in stock")
    quantity = event.get("quantity", 0)
    
    error = validate_required_fields(event, ["catalogId", "retailerId"])
    if error:
        return error
    
    if availability not in AVAILABILITY_OPTIONS:
        return {"statusCode": 400, "error": f"Invalid availability. Valid: {AVAILABILITY_OPTIONS}"}
    
    product_pk = f"PRODUCT#{catalog_id}#{retailer_id}"
    now = iso_now()
    
    try:
        table().update_item(
            Key={MESSAGES_PK_NAME: product_pk},
            UpdateExpression="SET availability = :av, quantity = :qty, lastUpdatedAt = :lu",
            ExpressionAttributeValues={
                ":av": availability,
                ":qty": quantity,
                ":lu": now
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "update_product_availability",
            "catalogId": catalog_id,
            "retailerId": retailer_id,
            "availability": availability,
            "quantity": quantity
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_abandoned_carts(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get abandoned cart data for remarketing.
    
    Test Event:
    {
        "action": "get_abandoned_carts",
        "metaWabaId": "1347766229904230",
        "hoursAgo": 24,
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    hours_ago = event.get("hoursAgo", 24)
    limit = event.get("limit", 50)
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query abandoned carts
        response = table().scan(
            FilterExpression="itemType = :it AND wabaMetaId = :waba AND cartStatus = :cs",
            ExpressionAttributeValues={
                ":it": "CART",
                ":waba": meta_waba_id,
                ":cs": "abandoned"
            },
            Limit=limit
        )
        items = response.get("Items", [])
        
        # Calculate totals
        total_value = sum(i.get("cartValue", 0) for i in items)
        
        return {
            "statusCode": 200,
            "operation": "get_abandoned_carts",
            "wabaMetaId": meta_waba_id,
            "abandonedCarts": {
                "count": len(items),
                "totalValue": total_value,
                "carts": items
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_abandoned_cart_reminder(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send abandoned cart reminder message.
    
    Test Event:
    {
        "action": "send_abandoned_cart_reminder",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "cartId": "CART_xxx",
        "templateName": "abandoned_cart_reminder"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    cart_id = event.get("cartId", "")
    template_name = event.get("templateName", "abandoned_cart_reminder")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "cartId"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    cart_pk = f"CART#{cart_id}"
    
    try:
        cart = get_item(cart_pk)
        if not cart:
            return {"statusCode": 404, "error": f"Cart not found: {cart_id}"}
        
        # Build reminder message
        items_text = "\n".join([
            f"• {item.get('name', 'Item')} x{item.get('quantity', 1)}"
            for item in cart.get("items", [])[:5]
        ])
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "text",
            "text": {
                "body": f"🛒 You left items in your cart!\n\n{items_text}\n\nComplete your purchase now and enjoy special offers!"
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            table().update_item(
                Key={MESSAGES_PK_NAME: cart_pk},
                UpdateExpression="SET reminderSent = :rs, reminderSentAt = :rsa",
                ExpressionAttributeValues={":rs": True, ":rsa": iso_now()}
            )
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_abandoned_cart_reminder",
            "cartId": cart_id,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
