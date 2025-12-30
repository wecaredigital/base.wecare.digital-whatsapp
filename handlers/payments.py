# Payments Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/payments

import json
import logging
from typing import Any, Dict
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Payment Status
PAYMENT_STATUSES = ["pending", "processing", "completed", "failed", "refunded", "cancelled"]

# Payment Providers
PAYMENT_PROVIDERS = ["razorpay", "paytm", "phonepe", "stripe", "paypal"]


def handle_payment_onboarding(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Onboard payment gateway for a WABA.
    
    Test Event:
    {
        "action": "payment_onboarding",
        "metaWabaId": "1347766229904230",
        "provider": "razorpay",
        "credentials": {
            "keyId": "rzp_test_xxx",
            "keySecret": "encrypted_secret"
        },
        "webhookUrl": "https://api.example.com/payment-webhook"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    provider = event.get("provider", "")
    credentials = event.get("credentials", {})
    webhook_url = event.get("webhookUrl", "")
    
    error = validate_required_fields(event, ["metaWabaId", "provider", "credentials"])
    if error:
        return error
    
    if provider not in PAYMENT_PROVIDERS:
        return {"statusCode": 400, "error": f"Invalid provider. Valid: {PAYMENT_PROVIDERS}"}
    
    now = iso_now()
    payment_config_pk = f"PAYMENT_CONFIG#{meta_waba_id}#{provider}"
    
    try:
        # Store payment configuration (credentials should be encrypted in production)
        config_data = {
            MESSAGES_PK_NAME: payment_config_pk,
            "itemType": "PAYMENT_CONFIG",
            "wabaMetaId": meta_waba_id,
            "provider": provider,
            "credentials": credentials,  # Should be encrypted
            "webhookUrl": webhook_url,
            "status": "active",
            "onboardedAt": now,
            "lastUpdatedAt": now,
        }
        
        store_item(config_data)
        
        return {
            "statusCode": 200,
            "operation": "payment_onboarding",
            "configPk": payment_config_pk,
            "provider": provider,
            "status": "active",
            "message": f"Payment gateway {provider} onboarded successfully"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_create_payment_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a payment request and send to customer.
    
    Test Event:
    {
        "action": "create_payment_request",
        "metaWabaId": "1347766229904230",
        "to": "+919876543210",
        "orderId": "ORD-12345",
        "amount": 2500,
        "currency": "INR",
        "description": "Order payment",
        "provider": "razorpay"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    order_id = event.get("orderId", "")
    amount = event.get("amount", 0)
    currency = event.get("currency", "INR")
    description = event.get("description", "")
    provider = event.get("provider", "razorpay")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "orderId", "amount"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    now = iso_now()
    payment_id = f"PAY_{now.replace(':', '').replace('-', '').replace('.', '')}"
    payment_pk = f"PAYMENT#{payment_id}"
    
    try:
        # Create payment record
        payment_data = {
            MESSAGES_PK_NAME: payment_pk,
            "itemType": "PAYMENT",
            "paymentId": payment_id,
            "wabaMetaId": meta_waba_id,
            "customerPhone": to_number,
            "orderId": order_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "provider": provider,
            "status": "pending",
            "createdAt": now,
            "statusHistory": [{"status": "pending", "timestamp": now}],
        }
        
        store_item(payment_data)
        
        # Generate payment link (mock - actual implementation depends on provider)
        payment_link = f"https://pay.example.com/{payment_id}"
        
        # Send payment request message
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {
                    "text": f"Payment Request\n\nOrder: {order_id}\nAmount: {currency} {amount}\n{description}"
                },
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": "Pay Now",
                        "url": payment_link
                    }
                }
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            # Update payment with message ID
            table().update_item(
                Key={MESSAGES_PK_NAME: payment_pk},
                UpdateExpression="SET messageId = :mid, paymentLink = :pl",
                ExpressionAttributeValues={
                    ":mid": result.get("messageId", ""),
                    ":pl": payment_link
                }
            )
        
        return {
            "statusCode": 200,
            "operation": "create_payment_request",
            "paymentId": payment_id,
            "paymentLink": payment_link,
            "amount": amount,
            "currency": currency,
            "messageSent": result.get("success", False)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_payment_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get payment status.
    
    Test Event:
    {
        "action": "get_payment_status",
        "paymentId": "PAY_20241230120000"
    }
    
    Or by order:
    {
        "action": "get_payment_status",
        "orderId": "ORD-12345"
    }
    """
    payment_id = event.get("paymentId", "")
    order_id = event.get("orderId", "")
    
    if not payment_id and not order_id:
        return {"statusCode": 400, "error": "paymentId or orderId is required"}
    
    try:
        if payment_id:
            payment_pk = f"PAYMENT#{payment_id}"
            payment = get_item(payment_pk)
        else:
            # Search by order ID
            response = table().scan(
                FilterExpression="itemType = :it AND orderId = :oid",
                ExpressionAttributeValues={":it": "PAYMENT", ":oid": order_id},
                Limit=1
            )
            items = response.get("Items", [])
            payment = items[0] if items else None
        
        if not payment:
            return {"statusCode": 404, "error": "Payment not found"}
        
        return {
            "statusCode": 200,
            "operation": "get_payment_status",
            "payment": payment
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_update_payment_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update payment status (from webhook or manual).
    
    Test Event:
    {
        "action": "update_payment_status",
        "paymentId": "PAY_20241230120000",
        "status": "completed",
        "providerPaymentId": "pay_xxx",
        "providerData": {}
    }
    """
    payment_id = event.get("paymentId", "")
    status = event.get("status", "")
    provider_payment_id = event.get("providerPaymentId", "")
    provider_data = event.get("providerData", {})
    
    error = validate_required_fields(event, ["paymentId", "status"])
    if error:
        return error
    
    if status not in PAYMENT_STATUSES:
        return {"statusCode": 400, "error": f"Invalid status. Valid: {PAYMENT_STATUSES}"}
    
    payment_pk = f"PAYMENT#{payment_id}"
    now = iso_now()
    
    try:
        payment = get_item(payment_pk)
        if not payment:
            return {"statusCode": 404, "error": f"Payment not found: {payment_id}"}
        
        # Update status history
        status_history = payment.get("statusHistory", [])
        status_history.append({"status": status, "timestamp": now})
        
        update_expr = "SET #st = :st, lastUpdatedAt = :lu, statusHistory = :sh"
        expr_values = {":st": status, ":lu": now, ":sh": status_history}
        expr_names = {"#st": "status"}
        
        if provider_payment_id:
            update_expr += ", providerPaymentId = :ppid"
            expr_values[":ppid"] = provider_payment_id
        
        if provider_data:
            update_expr += ", providerData = :pd"
            expr_values[":pd"] = provider_data
        
        if status == "completed":
            update_expr += ", completedAt = :ca"
            expr_values[":ca"] = now
        
        table().update_item(
            Key={MESSAGES_PK_NAME: payment_pk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        return {
            "statusCode": 200,
            "operation": "update_payment_status",
            "paymentId": payment_id,
            "status": status
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_send_payment_confirmation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send payment confirmation message.
    
    Test Event:
    {
        "action": "send_payment_confirmation",
        "paymentId": "PAY_20241230120000"
    }
    """
    payment_id = event.get("paymentId", "")
    
    error = validate_required_fields(event, ["paymentId"])
    if error:
        return error
    
    payment_pk = f"PAYMENT#{payment_id}"
    
    try:
        payment = get_item(payment_pk)
        if not payment:
            return {"statusCode": 404, "error": f"Payment not found: {payment_id}"}
        
        if payment.get("status") != "completed":
            return {"statusCode": 400, "error": "Payment not completed yet"}
        
        phone_arn = get_phone_arn(payment.get("wabaMetaId", ""))
        if not phone_arn:
            return {"statusCode": 404, "error": "Phone not found"}
        
        # Send confirmation message
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(payment.get("customerPhone", "")),
            "type": "text",
            "text": {
                "body": f"✅ Payment Confirmed!\n\n"
                        f"Payment ID: {payment_id}\n"
                        f"Order: {payment.get('orderId', '')}\n"
                        f"Amount: {payment.get('currency', 'INR')} {payment.get('amount', 0)}\n\n"
                        f"Thank you for your payment!"
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            table().update_item(
                Key={MESSAGES_PK_NAME: payment_pk},
                UpdateExpression="SET confirmationSent = :cs, confirmationMessageId = :cmid",
                ExpressionAttributeValues={
                    ":cs": True,
                    ":cmid": result.get("messageId", "")
                }
            )
        
        return {
            "statusCode": 200,
            "operation": "send_payment_confirmation",
            "paymentId": payment_id,
            "confirmationSent": result.get("success", False)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_payments(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get payments list.
    
    Test Event:
    {
        "action": "get_payments",
        "metaWabaId": "1347766229904230",
        "status": "completed",
        "limit": 50
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    status = event.get("status", "")
    customer_phone = event.get("customerPhone", "")
    limit = event.get("limit", 50)
    
    try:
        filter_expr = "itemType = :it"
        expr_values = {":it": "PAYMENT"}
        expr_names = {}
        
        if meta_waba_id:
            filter_expr += " AND wabaMetaId = :waba"
            expr_values[":waba"] = meta_waba_id
        
        if status:
            filter_expr += " AND #st = :st"
            expr_values[":st"] = status
            expr_names["#st"] = "status"
        
        if customer_phone:
            filter_expr += " AND customerPhone = :cp"
            expr_values[":cp"] = customer_phone
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit
        }
        
        if expr_names:
            scan_kwargs["ExpressionAttributeNames"] = expr_names
        
        response = table().scan(**scan_kwargs)
        items = response.get("Items", [])
        
        # Calculate totals
        total_amount = sum(i.get("amount", 0) for i in items if i.get("status") == "completed")
        
        return {
            "statusCode": 200,
            "operation": "get_payments",
            "count": len(items),
            "totalCompletedAmount": total_amount,
            "payments": items
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


# =============================================================================
# NATIVE WHATSAPP PAYMENTS (India - Razorpay/PayU/UPI Intent)
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in
# =============================================================================

# Payment Configuration Types
PAYMENT_CONFIG_TYPES = {
    "UPI_INTENT": "Opens user's UPI app with pre-filled payment details",
    "PG_RAZORPAY": "Embedded Razorpay checkout within WhatsApp",
    "PG_PAYU": "Embedded PayU checkout within WhatsApp"
}

# Order Status for order_status messages
ORDER_STATUSES = ["pending", "processing", "shipped", "partially_shipped", "completed", "canceled"]


def handle_send_payment_order(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send native WhatsApp Payment order_details message (India only).
    
    This sends an interactive order_details message that triggers the configured
    payment gateway (Razorpay/PayU) or UPI Intent directly within WhatsApp.
    
    Prerequisites:
    - Payment configuration must be set up in WhatsApp Manager
    - For PG_RAZORPAY/PG_PAYU: Gateway must be connected and active
    - For UPI_INTENT: No configuration needed
    
    Test Event (Razorpay):
    {
        "action": "send_payment_order",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "referenceId": "ORDER-001",
        "paymentType": "PG_RAZORPAY",
        "paymentConfigurationName": "wecare_razorpay",
        "currency": "INR",
        "totalAmount": 100,
        "order": {
            "status": "pending",
            "items": [
                {
                    "name": "Test Item",
                    "amount": 100,
                    "quantity": 1,
                    "retailerId": "SKU-001"
                }
            ]
        }
    }
    
    Test Event (UPI Intent):
    {
        "action": "send_payment_order",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "referenceId": "ORDER-002",
        "paymentType": "UPI_INTENT",
        "upiIntentLink": "upi://pay?pa=merchant@upi&pn=Merchant&am=100&cu=INR&tr=ORDER-002",
        "currency": "INR",
        "totalAmount": 100,
        "order": {
            "status": "pending",
            "items": [
                {
                    "name": "Test Item",
                    "amount": 100,
                    "quantity": 1
                }
            ]
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    reference_id = event.get("referenceId", "")
    payment_type = event.get("paymentType", "PG_RAZORPAY")
    payment_config_name = event.get("paymentConfigurationName", "")
    upi_intent_link = event.get("upiIntentLink", "")
    currency = event.get("currency", "INR")
    total_amount = event.get("totalAmount", 0)
    order = event.get("order", {})
    beneficiary = event.get("beneficiary", {})
    expiration_seconds = event.get("expirationSeconds", 300)  # 5 min default
    
    # Validation
    error = validate_required_fields(event, ["metaWabaId", "to", "referenceId", "totalAmount"])
    if error:
        return error
    
    if payment_type not in PAYMENT_CONFIG_TYPES:
        return {"statusCode": 400, "error": f"Invalid paymentType. Valid: {list(PAYMENT_CONFIG_TYPES.keys())}"}
    
    if payment_type in ["PG_RAZORPAY", "PG_PAYU"] and not payment_config_name:
        return {"statusCode": 400, "error": "paymentConfigurationName is required for PG_RAZORPAY/PG_PAYU"}
    
    if payment_type == "UPI_INTENT" and not upi_intent_link:
        return {"statusCode": 400, "error": "upiIntentLink is required for UPI_INTENT"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build order items
        items = order.get("items", [])
        order_items = []
        for item in items:
            order_item = {
                "retailer_id": item.get("retailerId", item.get("retailer_id", f"ITEM-{len(order_items)+1}")),
                "name": item.get("name", "Item"),
                "amount": {
                    "value": int(item.get("amount", 0) * 1000),  # Convert to milliunits
                    "offset": 1000
                },
                "quantity": item.get("quantity", 1),
            }
            if item.get("saleAmount"):
                order_item["sale_amount"] = {
                    "value": int(item.get("saleAmount") * 1000),
                    "offset": 1000
                }
            if item.get("countryOfOrigin"):
                order_item["country_of_origin"] = item.get("countryOfOrigin")
            if item.get("importerName"):
                order_item["importer_name"] = item.get("importerName")
            if item.get("importerAddress"):
                order_item["importer_address"] = item.get("importerAddress")
            order_items.append(order_item)
        
        # Build payment settings based on type
        payment_settings = []
        if payment_type == "UPI_INTENT":
            payment_settings.append({
                "type": "payment_gateway",
                "payment_gateway": {
                    "type": "upi_intent",
                    "upi_intent": {
                        "upi_intent_link": upi_intent_link
                    }
                }
            })
        else:
            # PG_RAZORPAY or PG_PAYU
            payment_settings.append({
                "type": "payment_gateway",
                "payment_gateway": {
                    "type": payment_type.lower().replace("pg_", ""),
                    "configuration_name": payment_config_name
                }
            })
        
        # Build the order_details interactive message
        interactive = {
            "type": "order_details",
            "body": {
                "text": f"Order #{reference_id}"
            },
            "footer": {
                "text": "Powered by WECARE.DIGITAL"
            },
            "action": {
                "name": "review_and_pay",
                "parameters": {
                    "reference_id": reference_id,
                    "type": "digital-goods",  # or "physical-goods"
                    "payment_settings": payment_settings,
                    "currency": currency,
                    "total_amount": {
                        "value": int(total_amount * 1000),  # Convert to milliunits
                        "offset": 1000
                    },
                    "order": {
                        "status": order.get("status", "pending"),
                        "catalog_id": order.get("catalogId", ""),
                        "items": order_items,
                        "subtotal": {
                            "value": int(total_amount * 1000),
                            "offset": 1000
                        }
                    }
                }
            }
        }
        
        # Add optional fields
        if beneficiary:
            interactive["action"]["parameters"]["beneficiary"] = {
                "name": beneficiary.get("name", ""),
                "email": beneficiary.get("email", ""),
                "phone_number": beneficiary.get("phone", "")
            }
        
        if expiration_seconds:
            interactive["action"]["parameters"]["expiration_seconds"] = expiration_seconds
        
        # Add tax if provided
        if order.get("tax"):
            interactive["action"]["parameters"]["order"]["tax"] = {
                "value": int(order.get("tax", 0) * 1000),
                "offset": 1000,
                "description": order.get("taxDescription", "Tax")
            }
        
        # Add shipping if provided
        if order.get("shipping"):
            interactive["action"]["parameters"]["order"]["shipping"] = {
                "value": int(order.get("shipping", 0) * 1000),
                "offset": 1000,
                "description": order.get("shippingDescription", "Shipping")
            }
        
        # Add discount if provided
        if order.get("discount"):
            interactive["action"]["parameters"]["order"]["discount"] = {
                "value": int(order.get("discount", 0) * 1000),
                "offset": 1000,
                "description": order.get("discountDescription", "Discount"),
                "discount_program_name": order.get("discountProgramName", "")
            }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        now = iso_now()
        
        if result.get("success"):
            # Store payment order
            payment_pk = f"PAYMENT_ORDER#{reference_id}"
            store_item({
                MESSAGES_PK_NAME: payment_pk,
                "itemType": "PAYMENT_ORDER",
                "referenceId": reference_id,
                "wabaMetaId": meta_waba_id,
                "customerPhone": to_number,
                "paymentType": payment_type,
                "paymentConfigurationName": payment_config_name,
                "currency": currency,
                "totalAmount": total_amount,
                "orderItems": order_items,
                "status": "pending",
                "messageId": result.get("messageId", ""),
                "createdAt": now,
                "expiresAt": now,  # Would calculate based on expiration_seconds
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_payment_order",
            "referenceId": reference_id,
            "paymentType": payment_type,
            "totalAmount": total_amount,
            "currency": currency,
            **result
        }
    except ClientError as e:
        logger.exception(f"Failed to send payment order: {e}")
        return {"statusCode": 500, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error sending payment order: {e}")
        return {"statusCode": 500, "error": str(e)}


def handle_send_order_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send order status update message after payment.
    
    Test Event:
    {
        "action": "send_order_status",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "referenceId": "ORDER-001",
        "status": "completed",
        "description": "Payment received successfully"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    reference_id = event.get("referenceId", "")
    status = event.get("status", "completed")
    description = event.get("description", "")
    
    error = validate_required_fields(event, ["metaWabaId", "to", "referenceId", "status"])
    if error:
        return error
    
    if status not in ORDER_STATUSES:
        return {"statusCode": 400, "error": f"Invalid status. Valid: {ORDER_STATUSES}"}
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        interactive = {
            "type": "order_status",
            "body": {
                "text": f"Order #{reference_id} - {status.upper()}"
            },
            "action": {
                "name": "review_order",
                "parameters": {
                    "reference_id": reference_id,
                    "order": {
                        "status": status,
                        "description": description or f"Order status: {status}"
                    }
                }
            }
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "interactive",
            "interactive": interactive
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            # Update payment order status
            payment_pk = f"PAYMENT_ORDER#{reference_id}"
            now = iso_now()
            try:
                table().update_item(
                    Key={MESSAGES_PK_NAME: payment_pk},
                    UpdateExpression="SET #st = :st, statusUpdatedAt = :su, statusDescription = :sd",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":st": status,
                        ":su": now,
                        ":sd": description
                    }
                )
            except Exception:
                pass  # Order might not exist in DB
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_order_status",
            "referenceId": reference_id,
            "status": status,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_process_payment_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process payment webhook from WhatsApp/Razorpay.
    
    This handles the webhook notification when a payment is completed or fails.
    
    Test Event:
    {
        "action": "process_payment_webhook",
        "webhookType": "payment_status",
        "referenceId": "ORDER-001",
        "paymentStatus": "captured",
        "transactionId": "pay_xxx",
        "amount": 100,
        "currency": "INR"
    }
    """
    webhook_type = event.get("webhookType", "payment_status")
    reference_id = event.get("referenceId", "")
    payment_status = event.get("paymentStatus", "")
    transaction_id = event.get("transactionId", "")
    amount = event.get("amount", 0)
    currency = event.get("currency", "INR")
    error_message = event.get("errorMessage", "")
    
    error = validate_required_fields(event, ["referenceId", "paymentStatus"])
    if error:
        return error
    
    payment_pk = f"PAYMENT_ORDER#{reference_id}"
    now = iso_now()
    
    try:
        # Map payment status to order status
        status_map = {
            "captured": "completed",
            "authorized": "processing",
            "failed": "canceled",
            "pending": "pending",
            "refunded": "canceled"
        }
        order_status = status_map.get(payment_status, "pending")
        
        # Update payment order
        update_expr = "SET paymentStatus = :ps, orderStatus = :os, transactionId = :tid, webhookReceivedAt = :wr"
        expr_values = {
            ":ps": payment_status,
            ":os": order_status,
            ":tid": transaction_id,
            ":wr": now
        }
        
        if error_message:
            update_expr += ", errorMessage = :em"
            expr_values[":em"] = error_message
        
        table().update_item(
            Key={MESSAGES_PK_NAME: payment_pk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        # Get payment order to send status update
        payment_order = get_item(payment_pk)
        
        if payment_order and payment_status in ["captured", "failed"]:
            # Send order status message
            handle_send_order_status({
                "metaWabaId": payment_order.get("wabaMetaId", ""),
                "to": payment_order.get("customerPhone", ""),
                "referenceId": reference_id,
                "status": order_status,
                "description": f"Payment {payment_status}" + (f": {error_message}" if error_message else "")
            }, context)
        
        return {
            "statusCode": 200,
            "operation": "process_payment_webhook",
            "referenceId": reference_id,
            "paymentStatus": payment_status,
            "orderStatus": order_status,
            "transactionId": transaction_id
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


# =============================================================================
# CHECKOUT BUTTON TEMPLATES (India Payments)
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/checkout-button-templates
# =============================================================================

def handle_send_checkout_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send checkout button template for payments (India only).
    
    Checkout button templates allow sending payment requests via approved templates
    with a "Pay" button that triggers the payment flow.
    
    Test Event:
    {
        "action": "send_checkout_template",
        "metaWabaId": "1347766229904230",
        "to": "+919903300044",
        "templateName": "payment_request",
        "language": "en",
        "paymentConfigurationName": "WECARE-DIGITAL",
        "referenceId": "ORDER-001",
        "currency": "INR",
        "totalAmount": 1000,
        "bodyParams": ["John", "ORDER-001", "1000"],
        "order": {
            "items": [{"name": "Product", "amount": 1000, "quantity": 1}]
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    to_number = event.get("to", "")
    template_name = event.get("templateName", "")
    language = event.get("language", "en")
    payment_config_name = event.get("paymentConfigurationName", "")
    reference_id = event.get("referenceId", "")
    currency = event.get("currency", "INR")
    total_amount = event.get("totalAmount", 0)
    body_params = event.get("bodyParams", [])
    order = event.get("order", {})
    expiration_seconds = event.get("expirationSeconds", 300)
    
    error = validate_required_fields(event, ["metaWabaId", "to", "templateName", "paymentConfigurationName", "referenceId", "totalAmount"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Build order items
        order_items = []
        for item in order.get("items", []):
            order_items.append({
                "retailer_id": item.get("retailerId", f"ITEM-{len(order_items)+1}"),
                "name": item.get("name", "Item"),
                "amount": {"value": int(item.get("amount", 0) * 1000), "offset": 1000},
                "quantity": item.get("quantity", 1)
            })
        
        # Build template components
        components = []
        
        # Body parameters
        if body_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in body_params]
            })
        
        # Checkout button component
        checkout_button = {
            "type": "button",
            "sub_type": "order_details",
            "index": "0",
            "parameters": [{
                "type": "action",
                "action": {
                    "order_details": {
                        "reference_id": reference_id,
                        "type": "digital-goods",
                        "payment_configuration": payment_config_name,
                        "currency": currency,
                        "total_amount": {
                            "value": int(total_amount * 1000),
                            "offset": 1000
                        },
                        "order": {
                            "status": "pending",
                            "items": order_items,
                            "subtotal": {
                                "value": int(total_amount * 1000),
                                "offset": 1000
                            }
                        }
                    }
                }
            }]
        }
        
        if expiration_seconds:
            checkout_button["parameters"][0]["action"]["order_details"]["expiration_seconds"] = expiration_seconds
        
        components.append(checkout_button)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": format_wa_number(to_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components
            }
        }
        
        result = send_whatsapp_message(phone_arn, payload)
        
        if result.get("success"):
            store_item({
                MESSAGES_PK_NAME: f"CHECKOUT_TEMPLATE#{reference_id}",
                "itemType": "CHECKOUT_TEMPLATE",
                "wabaMetaId": meta_waba_id,
                "to": to_number,
                "templateName": template_name,
                "referenceId": reference_id,
                "totalAmount": total_amount,
                "currency": currency,
                "messageId": result.get("messageId"),
                "createdAt": iso_now()
            })
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "operation": "send_checkout_template",
            "templateName": template_name,
            "referenceId": reference_id,
            "totalAmount": total_amount,
            **result
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


# =============================================================================
# META GRAPH API PAYMENT ONBOARDING
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/onboarding-api
# =============================================================================

def handle_meta_payment_onboarding(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Onboard payment configuration via Meta Graph API.
    
    This creates/updates payment configuration in Meta's system.
    
    Test Event:
    {
        "action": "meta_payment_onboarding",
        "metaWabaId": "1347766229904230",
        "configurationName": "WECARE-DIGITAL",
        "paymentGateway": "razorpay",
        "merchantId": "acc_HDfub6wOfQybuH",
        "mcc": "4722",
        "purposeCode": "03"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    config_name = event.get("configurationName", "")
    payment_gateway = event.get("paymentGateway", "razorpay")
    merchant_id = event.get("merchantId", "")
    mcc = event.get("mcc", "4722")
    purpose_code = event.get("purposeCode", "03")
    upi_id = event.get("upiId", "")
    
    error = validate_required_fields(event, ["metaWabaId", "configurationName"])
    if error:
        return error
    
    now = iso_now()
    config_pk = f"META_PAYMENT_CONFIG#{meta_waba_id}#{config_name}"
    
    try:
        config_data = {
            MESSAGES_PK_NAME: config_pk,
            "itemType": "META_PAYMENT_CONFIG",
            "wabaMetaId": meta_waba_id,
            "configurationName": config_name,
            "paymentGateway": payment_gateway,
            "merchantId": merchant_id,
            "mcc": mcc,
            "purposeCode": purpose_code,
            "status": "pending_verification",
            "createdAt": now
        }
        
        if upi_id:
            config_data["upiId"] = upi_id
            config_data["paymentType"] = "UPI"
        else:
            config_data["paymentType"] = "PG"
        
        store_item(config_data)
        
        return {
            "statusCode": 200,
            "operation": "meta_payment_onboarding",
            "configurationName": config_name,
            "paymentGateway": payment_gateway,
            "status": "pending_verification",
            "note": "Configuration created. Verify in Meta Business Manager."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_payment_configurations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all payment configurations for a WABA.
    
    Test Event:
    {
        "action": "get_payment_configurations",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        response = table().scan(
            FilterExpression="(itemType = :it1 OR itemType = :it2) AND wabaMetaId = :waba",
            ExpressionAttributeValues={
                ":it1": "META_PAYMENT_CONFIG",
                ":it2": "PAYMENT_CONFIG",
                ":waba": meta_waba_id
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "get_payment_configurations",
            "count": len(response.get("Items", [])),
            "configurations": response.get("Items", [])
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_verify_payment_configuration(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Verify/test a payment configuration.
    
    Test Event:
    {
        "action": "verify_payment_configuration",
        "metaWabaId": "1347766229904230",
        "configurationName": "WECARE-DIGITAL"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    config_name = event.get("configurationName", "")
    
    error = validate_required_fields(event, ["metaWabaId", "configurationName"])
    if error:
        return error
    
    config_pk = f"META_PAYMENT_CONFIG#{meta_waba_id}#{config_name}"
    now = iso_now()
    
    try:
        config = get_item(config_pk)
        if not config:
            return {"statusCode": 404, "error": f"Configuration not found: {config_name}"}
        
        # Update status to verified (in production, would call Meta API)
        table().update_item(
            Key={MESSAGES_PK_NAME: config_pk},
            UpdateExpression="SET #st = :st, verifiedAt = :va",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "active", ":va": now}
        )
        
        return {
            "statusCode": 200,
            "operation": "verify_payment_configuration",
            "configurationName": config_name,
            "status": "active",
            "verifiedAt": now
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
