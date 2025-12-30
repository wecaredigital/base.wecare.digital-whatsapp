# Address Messages Handler
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/address-messages
#
# Address messages allow businesses to collect shipping/delivery addresses
# from customers in a structured format within WhatsApp.
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Address Message Types
ADDRESS_MESSAGE_TYPES = ["address_message"]

# Saved Address Types
SAVED_ADDRESS_TYPES = ["saved_address"]

# Country Codes (ISO 3166-1 alpha-2)
SUPPORTED_COUNTRIES = [
    "IN", "US", "GB", "CA", "AU", "DE", "FR", "IT", "ES", "BR", 
    "MX", "JP", "SG", "AE", "SA", "ZA", "NG", "KE", "EG", "PH"
]


def handle_send_address_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send an address collection message to collect shipping/delivery address.
    
    This interactive message allows customers to:
    1. Enter a new address
    2. Select from saved addresses
    3. Share their current location as address
    
    Test Event:
    {
        "action": "send_address_message",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "body": "Please share your delivery address for order #ORD-12345",
        "footer": "Your address will be used for delivery only",
        "country": "IN",
        "values": {
            "name": "John Doe",
            "phone_number": "+919903300044"
        },
        "validationErrors": {},
        "savedAddresses": [
            {
                "id": "addr_001",
                "value": {
                    "name": "John Doe",
                    "phone_number": "+919903300044",
                    "in_pin_code": "400001",
                    "floor_number": "5",
                    "building_name": "ABC Tower",
                    "address": "123 Main Street",
                    "landmark_area": "Near Central Mall",
                    "city": "Mumbai"
                }
            }
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    body = event.get("body", "Please share your delivery address")
    footer = event.get("footer", "")
    country = event.get("country", "IN")
    values = event.get("values", {})
    validation_errors = event.get("validationErrors", {})
    saved_addresses = event.get("savedAddresses", [])
    
    # Validation
    error = validate_required_fields(event, ["metaWabaId", "to"])
    if error:
        return error
    
    if country not in SUPPORTED_COUNTRIES:
        return {"statusCode": 400, "error": f"Unsupported country. Supported: {SUPPORTED_COUNTRIES}"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build address message action parameters
        action_params = {
            "country": country
        }
        
        # Add pre-filled values if provided
        if values:
            action_params["values"] = values
        
        # Add validation errors if any (for re-submission)
        if validation_errors:
            action_params["validation_errors"] = validation_errors
        
        # Add saved addresses if available
        if saved_addresses:
            action_params["saved_addresses"] = saved_addresses
        
        # Build the interactive address message
        interactive = {
            "type": "address_message",
            "body": {"text": body},
            "action": {
                "name": "address_message",
                "parameters": action_params
            }
        }
        
        # Add optional footer
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        now = iso_now()
        
        if result.get("success"):
            # Store address message record
            addr_msg_pk = f"ADDRESS_MESSAGE#{meta_waba_id}#{result['messageId']}"
            store_item({
                MESSAGES_PK_NAME: addr_msg_pk,
                "itemType": "ADDRESS_MESSAGE",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "country": country,
                "messageId": result["messageId"],
                "sentAt": now,
                "addressReceived": False,
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_address_message",
            "country": country,
            **result
        }
    except ClientError as e:
        logger.exception(f"Failed to send address message: {e}")
        return {"statusCode": 500, "error": str(e)}


def handle_process_address_response(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process address response from webhook.
    
    When a customer submits an address, this handler processes and stores it.
    
    Test Event:
    {
        "action": "process_address_response",
        "messageId": "wamid.xxx",
        "metaWabaId": "1347766229904230",
        "from": "+919903300044",
        "address": {
            "name": "John Doe",
            "phone_number": "+919903300044",
            "in_pin_code": "400001",
            "floor_number": "5",
            "building_name": "ABC Tower",
            "address": "123 Main Street",
            "landmark_area": "Near Central Mall",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "IN"
        }
    }
    """
    message_id = event.get("messageId", "")
    meta_waba_id = event.get("metaWabaId", "")
    from_number = event.get("from", "")
    address = event.get("address", {})
    
    error = validate_required_fields(event, ["messageId", "address"])
    if error:
        return error
    
    now = iso_now()
    
    try:
        # Store the received address
        address_pk = f"ADDRESS#{meta_waba_id}#{from_number}#{now}"
        store_item({
            MESSAGES_PK_NAME: address_pk,
            "itemType": "CUSTOMER_ADDRESS",
            "wabaMetaId": meta_waba_id,
            "customerPhone": from_number,
            "messageId": message_id,
            "address": address,
            "receivedAt": now,
            "validated": False,
        })
        
        # Update the original address message if found
        response = table().scan(
            FilterExpression="itemType = :it AND messageId = :mid",
            ExpressionAttributeValues={":it": "ADDRESS_MESSAGE", ":mid": message_id},
            Limit=1
        )
        items = response.get("Items", [])
        
        if items:
            addr_msg_pk = items[0].get(MESSAGES_PK_NAME)
            table().update_item(
                Key={MESSAGES_PK_NAME: addr_msg_pk},
                UpdateExpression="SET addressReceived = :ar, addressReceivedAt = :ara, addressPk = :apk",
                ExpressionAttributeValues={
                    ":ar": True,
                    ":ara": now,
                    ":apk": address_pk
                }
            )
        
        return {
            "statusCode": 200,
            "operation": "process_address_response",
            "addressPk": address_pk,
            "address": address,
            "processed": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_customer_addresses(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all addresses for a customer.
    
    Test Event:
    {
        "action": "get_customer_addresses",
        "customerPhone": "+919903300044",
        "metaWabaId": "1347766229904230",
        "limit": 10
    }
    """
    customer_phone = event.get("customerPhone", "")
    meta_waba_id = event.get("metaWabaId", "")
    limit = event.get("limit", 10)
    
    error = validate_required_fields(event, ["customerPhone"])
    if error:
        return error
    
    try:
        filter_expr = "itemType = :it AND customerPhone = :cp"
        expr_values = {":it": "CUSTOMER_ADDRESS", ":cp": customer_phone}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=limit
        )
        items = response.get("Items", [])
        
        # Sort by receivedAt descending
        items.sort(key=lambda x: x.get("receivedAt", ""), reverse=True)
        
        return {
            "statusCode": 200,
            "operation": "get_customer_addresses",
            "customerPhone": customer_phone,
            "count": len(items),
            "addresses": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_validate_address(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate an address and return any errors.
    
    Test Event:
    {
        "action": "validate_address",
        "address": {
            "name": "John Doe",
            "phone_number": "+919903300044",
            "in_pin_code": "400001",
            "address": "123 Main Street",
            "city": "Mumbai"
        },
        "country": "IN"
    }
    """
    address = event.get("address", {})
    country = event.get("country", "IN")
    
    error = validate_required_fields(event, ["address"])
    if error:
        return error
    
    validation_errors = {}
    warnings = []
    
    # Required fields by country
    required_fields = {
        "IN": ["name", "phone_number", "in_pin_code", "address", "city"],
        "US": ["name", "phone_number", "zip_code", "address", "city", "state"],
        "GB": ["name", "phone_number", "post_code", "address", "city"],
        "DEFAULT": ["name", "address", "city"]
    }
    
    fields_to_check = required_fields.get(country, required_fields["DEFAULT"])
    
    for field in fields_to_check:
        if not address.get(field):
            validation_errors[field] = f"{field.replace('_', ' ').title()} is required"
    
    # Validate phone number format
    phone = address.get("phone_number", "")
    if phone and not phone.startswith("+"):
        validation_errors["phone_number"] = "Phone number must include country code (e.g., +91)"
    
    # Validate PIN/ZIP code format
    if country == "IN":
        pin = address.get("in_pin_code", "")
        if pin and (not pin.isdigit() or len(pin) != 6):
            validation_errors["in_pin_code"] = "PIN code must be 6 digits"
    elif country == "US":
        zip_code = address.get("zip_code", "")
        if zip_code and len(zip_code) not in [5, 10]:  # 5 or 5+4 format
            validation_errors["zip_code"] = "ZIP code must be 5 or 9 digits"
    
    # Warnings (non-blocking)
    if not address.get("landmark_area"):
        warnings.append("Adding a landmark can help with delivery")
    
    is_valid = len(validation_errors) == 0
    
    return {
        "statusCode": 200,
        "operation": "validate_address",
        "valid": is_valid,
        "validationErrors": validation_errors,
        "warnings": warnings,
        "country": country
    }


def handle_save_address(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Save an address for future use.
    
    Test Event:
    {
        "action": "save_address",
        "customerPhone": "+919903300044",
        "metaWabaId": "1347766229904230",
        "addressLabel": "Home",
        "address": {
            "name": "John Doe",
            "phone_number": "+919903300044",
            "in_pin_code": "400001",
            "floor_number": "5",
            "building_name": "ABC Tower",
            "address": "123 Main Street",
            "landmark_area": "Near Central Mall",
            "city": "Mumbai",
            "state": "Maharashtra"
        },
        "isDefault": true
    }
    """
    customer_phone = event.get("customerPhone", "")
    meta_waba_id = event.get("metaWabaId", "")
    address_label = event.get("addressLabel", "Default")
    address = event.get("address", {})
    is_default = event.get("isDefault", False)
    
    error = validate_required_fields(event, ["customerPhone", "metaWabaId", "address"])
    if error:
        return error
    
    now = iso_now()
    address_id = f"addr_{now.replace(':', '').replace('-', '').replace('.', '')}"
    saved_addr_pk = f"SAVED_ADDRESS#{meta_waba_id}#{customer_phone}#{address_id}"
    
    try:
        # If setting as default, unset other defaults
        if is_default:
            response = table().scan(
                FilterExpression="itemType = :it AND customerPhone = :cp AND wabaMetaId = :waba AND isDefault = :d",
                ExpressionAttributeValues={
                    ":it": "SAVED_ADDRESS",
                    ":cp": customer_phone,
                    ":waba": meta_waba_id,
                    ":d": True
                }
            )
            for item in response.get("Items", []):
                table().update_item(
                    Key={MESSAGES_PK_NAME: item[MESSAGES_PK_NAME]},
                    UpdateExpression="SET isDefault = :d",
                    ExpressionAttributeValues={":d": False}
                )
        
        store_item({
            MESSAGES_PK_NAME: saved_addr_pk,
            "itemType": "SAVED_ADDRESS",
            "addressId": address_id,
            "wabaMetaId": meta_waba_id,
            "customerPhone": customer_phone,
            "addressLabel": address_label,
            "address": address,
            "isDefault": is_default,
            "createdAt": now,
            "lastUsedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "save_address",
            "addressId": address_id,
            "addressLabel": address_label,
            "isDefault": is_default,
            "saved": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_saved_addresses(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get saved addresses for a customer (for use in address_message).
    
    Test Event:
    {
        "action": "get_saved_addresses",
        "customerPhone": "+919903300044",
        "metaWabaId": "1347766229904230"
    }
    """
    customer_phone = event.get("customerPhone", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["customerPhone", "metaWabaId"])
    if error:
        return error
    
    try:
        response = table().scan(
            FilterExpression="itemType = :it AND customerPhone = :cp AND wabaMetaId = :waba",
            ExpressionAttributeValues={
                ":it": "SAVED_ADDRESS",
                ":cp": customer_phone,
                ":waba": meta_waba_id
            }
        )
        items = response.get("Items", [])
        
        # Format for address_message savedAddresses parameter
        saved_addresses = []
        for item in items:
            saved_addresses.append({
                "id": item.get("addressId", ""),
                "value": item.get("address", {})
            })
        
        return {
            "statusCode": 200,
            "operation": "get_saved_addresses",
            "customerPhone": customer_phone,
            "count": len(saved_addresses),
            "savedAddresses": saved_addresses
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_delete_saved_address(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete a saved address.
    
    Test Event:
    {
        "action": "delete_saved_address",
        "addressId": "addr_xxx",
        "customerPhone": "+919903300044",
        "metaWabaId": "1347766229904230"
    }
    """
    address_id = event.get("addressId", "")
    customer_phone = event.get("customerPhone", "")
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["addressId", "customerPhone", "metaWabaId"])
    if error:
        return error
    
    saved_addr_pk = f"SAVED_ADDRESS#{meta_waba_id}#{customer_phone}#{address_id}"
    
    try:
        # Check if exists
        item = get_item(saved_addr_pk)
        if not item:
            return {"statusCode": 404, "error": f"Address not found: {address_id}"}
        
        # Delete
        table().delete_item(Key={MESSAGES_PK_NAME: saved_addr_pk})
        
        return {
            "statusCode": 200,
            "operation": "delete_saved_address",
            "addressId": address_id,
            "deleted": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
