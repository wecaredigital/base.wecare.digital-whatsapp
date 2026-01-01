# =============================================================================
# PAYMENT CONFIGURATION HANDLERS (India Payments)
# =============================================================================
# Tenant-based payment configuration management for WhatsApp Payments (India).
# 
# Supports:
# - PG (Payment Gateway): Razorpay, PayU
# - UPI Intent: Direct UPI payments
#
# DynamoDB Schema:
# - PK: TENANT#{tenantId}  SK: PAYCFG#{configName}
#
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, send_whatsapp_message, format_wa_number,
    success_response, error_response
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Payment Configuration Types
PAYMENT_CONFIG_TYPES = {
    "PG": "Payment Gateway (Razorpay/PayU)",
    "UPI": "UPI Intent"
}

# MCC Codes (Merchant Category Codes)
MCC_CODES = {
    "4722": "Travel agencies and tour operators",
    "5411": "Grocery stores and supermarkets",
    "5812": "Eating places and restaurants",
    "5912": "Drug stores and pharmacies",
    "7299": "Miscellaneous recreation services",
}

# Purpose Codes (India specific)
PURPOSE_CODES = {
    "00": "Personal",
    "01": "Goods",
    "02": "Services",
    "03": "Travel",
    "04": "Education",
    "05": "Medical",
}

# =============================================================================
# PRE-CONFIGURED TENANT PAYMENT CONFIGURATIONS
# =============================================================================
# These are the known active payment configurations for existing tenants.
# They will be seeded to DynamoDB on first access or via seed_payment_configs action.

# =============================================================================
# PRE-CONFIGURED TENANT PAYMENT CONFIGURATIONS (EXACT SPEC VALUES)
# =============================================================================
# 8A) WECARE-DIGITAL
#   WABA ID: 1347766229904230
#   Phone: +91 9330994400
#   Gateway MID: acc_HDfub6wOfQybuH
#   UPI: 9330994400@sbi
#   MCC: 4722, Purpose: 03
#   Names: WECARE-DIGITAL (gateway), wecare-digital-upi (UPI)
#
# 8B) ManishAgarwal
#   WABA ID: 1390647332755815
#   Phone: +91 9903300044
#   Gateway MID: acc_HDfub6wOfQybuH
#   UPI: 9330994400@sbi
#   MCC: 4722, Purpose: 03
#   Names: ManishAgarwal (gateway), manish-agarwal-upi (UPI)
# =============================================================================

TENANT_PAYMENT_CONFIGS = {
    "wecare-digital": {
        "tenantId": "wecare-digital",
        "displayName": "WECARE-DIGITAL",
        "wabaId": "1347766229904230",
        "phoneE164": "+919330994400",
        "mcc": "4722",
        "purposeCode": "03",
        "configs": [
            {
                "configName": "WECARE-DIGITAL",
                "type": "PG",
                "status": "active",
                "paymentGatewayMid": "acc_HDfub6wOfQybuH",
                "notes": "Payment Gateway (Razorpay)"
            },
            {
                "configName": "wecare-digital-upi",
                "type": "UPI",
                "status": "active",
                "upiId": "9330994400@sbi",
                "notes": "UPI Intent"
            }
        ]
    },
    "manish-agarwal": {
        "tenantId": "manish-agarwal",
        "displayName": "ManishAgarwal",
        "wabaId": "1390647332755815",
        "phoneE164": "+919903300044",
        "mcc": "4722",
        "purposeCode": "03",
        "configs": [
            {
                "configName": "ManishAgarwal",
                "type": "PG",
                "status": "active",
                "paymentGatewayMid": "acc_HDfub6wOfQybuH",
                "notes": "Payment Gateway (Razorpay)"
            },
            {
                "configName": "manish-agarwal-upi",
                "type": "UPI",
                "status": "active",
                "upiId": "9330994400@sbi",
                "notes": "UPI Intent"
            }
        ]
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _build_payment_config_pk(tenant_id: str, config_name: str) -> str:
    """Build DynamoDB PK for payment configuration."""
    return f"TENANT#{tenant_id}#PAYCFG#{config_name}"


def _build_tenant_pk(tenant_id: str) -> str:
    """Build DynamoDB PK for tenant."""
    return f"TENANT#{tenant_id}"


def _get_tenant_config(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Get pre-configured tenant data."""
    return TENANT_PAYMENT_CONFIGS.get(tenant_id)


# =============================================================================
# SEED PAYMENT CONFIGURATIONS
# =============================================================================

def handle_seed_payment_configs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Seed pre-configured payment configurations to DynamoDB.
    
    This creates the payment configuration records for known tenants.
    Safe to run multiple times - uses conditional writes.
    
    Test Event:
    {
        "action": "seed_payment_configs"
    }
    
    Or for specific tenant:
    {
        "action": "seed_payment_configs",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId")
    now = iso_now()
    
    tenants_to_seed = [tenant_id] if tenant_id else list(TENANT_PAYMENT_CONFIGS.keys())
    results = []
    
    for tid in tenants_to_seed:
        tenant_data = TENANT_PAYMENT_CONFIGS.get(tid)
        if not tenant_data:
            results.append({"tenantId": tid, "status": "not_found"})
            continue
        
        # Create tenant record
        tenant_pk = _build_tenant_pk(tid)
        try:
            table().put_item(
                Item={
                    MESSAGES_PK_NAME: tenant_pk,
                    "sk": "PROFILE",
                    "itemType": "TENANT",
                    "tenantId": tid,
                    "displayName": tenant_data["displayName"],
                    "wabaId": tenant_data["wabaId"],
                    "phoneE164": tenant_data["phoneE164"],
                    "mcc": tenant_data["mcc"],
                    "purposeCode": tenant_data["purposeCode"],
                    "createdAt": now,
                    "updatedAt": now,
                },
                ConditionExpression="attribute_not_exists(pk)"
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                logger.warning(f"Failed to create tenant {tid}: {e}")
        
        # Create payment config records
        configs_created = 0
        for cfg in tenant_data["configs"]:
            config_pk = _build_payment_config_pk(tid, cfg["configName"])
            
            item = {
                MESSAGES_PK_NAME: config_pk,
                "sk": f"PAYCFG#{cfg['configName']}",
                "itemType": "PAYMENT_CONFIG",
                "tenantId": tid,
                "configName": cfg["configName"],
                "displayName": tenant_data["displayName"],
                "type": cfg["type"],
                "status": cfg["status"],
                "wabaId": tenant_data["wabaId"],
                "phoneE164": tenant_data["phoneE164"],
                "mcc": tenant_data["mcc"],
                "purposeCode": tenant_data["purposeCode"],
                "notes": cfg.get("notes", ""),
                "createdAt": now,
                "updatedAt": now,
                "lastValidatedAt": now if cfg["status"] == "active" else None,
            }
            
            if cfg["type"] == "PG":
                item["paymentGatewayMid"] = cfg.get("paymentGatewayMid", "")
            elif cfg["type"] == "UPI":
                item["upiId"] = cfg.get("upiId", "")
            
            try:
                table().put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(pk)"
                )
                configs_created += 1
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    logger.warning(f"Failed to create config {cfg['configName']}: {e}")
                else:
                    configs_created += 1  # Already exists
        
        results.append({
            "tenantId": tid,
            "status": "seeded",
            "configsCreated": configs_created
        })
    
    return success_response(
        "seed_payment_configs",
        results=results,
        tenantsProcessed=len(results)
    )


# =============================================================================
# LIST PAYMENT CONFIGURATIONS
# =============================================================================

def handle_list_payment_configurations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List payment configurations for a tenant.
    
    Test Event:
    {
        "action": "list_payment_configurations",
        "tenantId": "wecare-digital"
    }
    """
    tenant_id = event.get("tenantId", "")
    
    err = validate_required_fields(event, ["tenantId"])
    if err:
        return err
    
    try:
        # Query all payment configs for tenant
        response = table().scan(
            FilterExpression="itemType = :it AND tenantId = :tid",
            ExpressionAttributeValues={
                ":it": "PAYMENT_CONFIG",
                ":tid": tenant_id
            }
        )
        
        configs = response.get("Items", [])
        
        # If no configs found, check if we have pre-configured data
        if not configs:
            tenant_data = _get_tenant_config(tenant_id)
            if tenant_data:
                return success_response(
                    "list_payment_configurations",
                    tenantId=tenant_id,
                    count=0,
                    configurations=[],
                    hint="Run action='seed_payment_configs' to create configurations"
                )
        
        return success_response(
            "list_payment_configurations",
            tenantId=tenant_id,
            count=len(configs),
            configurations=configs
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET PAYMENT CONFIGURATION
# =============================================================================

def handle_get_payment_configuration(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a specific payment configuration.
    
    Test Event:
    {
        "action": "get_payment_configuration",
        "tenantId": "wecare-digital",
        "configName": "WECARE-DIGITAL"
    }
    """
    tenant_id = event.get("tenantId", "")
    config_name = event.get("configName", "")
    
    err = validate_required_fields(event, ["tenantId", "configName"])
    if err:
        return err
    
    config_pk = _build_payment_config_pk(tenant_id, config_name)
    
    try:
        config = get_item(config_pk)
        
        if not config:
            # Check pre-configured data
            tenant_data = _get_tenant_config(tenant_id)
            if tenant_data:
                for cfg in tenant_data["configs"]:
                    if cfg["configName"] == config_name:
                        return success_response(
                            "get_payment_configuration",
                            tenantId=tenant_id,
                            configName=config_name,
                            configuration=None,
                            preConfigured=cfg,
                            hint="Run action='seed_payment_configs' to persist this configuration"
                        )
            return error_response(f"Configuration not found: {config_name}", 404)
        
        return success_response(
            "get_payment_configuration",
            tenantId=tenant_id,
            configName=config_name,
            configuration=config
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# SET DEFAULT PAYMENT CONFIGURATION
# =============================================================================

def handle_set_default_payment_configuration(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set the default payment configuration for a tenant/phone.
    
    Test Event:
    {
        "action": "set_default_payment_configuration",
        "tenantId": "wecare-digital",
        "phoneNumberId": "phone-number-id-xxx",
        "configName": "WECARE-DIGITAL"
    }
    """
    tenant_id = event.get("tenantId", "")
    phone_number_id = event.get("phoneNumberId", "")
    config_name = event.get("configName", "")
    
    err = validate_required_fields(event, ["tenantId", "configName"])
    if err:
        return err
    
    # Verify config exists
    config_pk = _build_payment_config_pk(tenant_id, config_name)
    config = get_item(config_pk)
    
    if not config:
        return error_response(f"Configuration not found: {config_name}", 404)
    
    now = iso_now()
    
    try:
        # Update tenant record with default config
        tenant_pk = _build_tenant_pk(tenant_id)
        
        update_expr = "SET defaultPaymentConfig = :cfg, defaultPaymentConfigUpdatedAt = :now"
        expr_values = {":cfg": config_name, ":now": now}
        
        if phone_number_id:
            update_expr += ", defaultPaymentConfigPhoneId = :pid"
            expr_values[":pid"] = phone_number_id
        
        table().update_item(
            Key={MESSAGES_PK_NAME: tenant_pk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        return success_response(
            "set_default_payment_configuration",
            tenantId=tenant_id,
            configName=config_name,
            phoneNumberId=phone_number_id,
            setAt=now
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# VALIDATE PAYMENT CONFIGURATION
# =============================================================================

def handle_validate_payment_configuration(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate a payment configuration and optionally send test order.
    
    Test Event:
    {
        "action": "validate_payment_configuration",
        "tenantId": "wecare-digital",
        "configName": "WECARE-DIGITAL",
        "sendTestOrder": true,
        "testPhone": "+919903300044"
    }
    """
    tenant_id = event.get("tenantId", "")
    config_name = event.get("configName", "")
    send_test_order = event.get("sendTestOrder", False)
    test_phone = event.get("testPhone", "")
    
    err = validate_required_fields(event, ["tenantId", "configName"])
    if err:
        return err
    
    config_pk = _build_payment_config_pk(tenant_id, config_name)
    config = get_item(config_pk)
    
    if not config:
        return error_response(f"Configuration not found: {config_name}", 404)
    
    now = iso_now()
    validation_result = {
        "configName": config_name,
        "type": config.get("type"),
        "status": config.get("status"),
        "validatedAt": now,
        "checks": []
    }
    
    # Validation checks
    checks = []
    
    # Check required fields based on type
    if config.get("type") == "PG":
        if config.get("paymentGatewayMid"):
            checks.append({"check": "paymentGatewayMid", "status": "pass"})
        else:
            checks.append({"check": "paymentGatewayMid", "status": "fail", "error": "Missing merchant ID"})
    elif config.get("type") == "UPI":
        if config.get("upiId"):
            checks.append({"check": "upiId", "status": "pass"})
        else:
            checks.append({"check": "upiId", "status": "fail", "error": "Missing UPI ID"})
    
    # Check MCC and purpose code
    if config.get("mcc"):
        checks.append({"check": "mcc", "status": "pass", "value": config.get("mcc")})
    else:
        checks.append({"check": "mcc", "status": "fail", "error": "Missing MCC"})
    
    if config.get("purposeCode"):
        checks.append({"check": "purposeCode", "status": "pass", "value": config.get("purposeCode")})
    else:
        checks.append({"check": "purposeCode", "status": "fail", "error": "Missing purpose code"})
    
    validation_result["checks"] = checks
    validation_result["allPassed"] = all(c.get("status") == "pass" for c in checks)
    
    # Update last validated timestamp
    try:
        table().update_item(
            Key={MESSAGES_PK_NAME: config_pk},
            UpdateExpression="SET lastValidatedAt = :now, lastValidationResult = :result",
            ExpressionAttributeValues={
                ":now": now,
                ":result": validation_result
            }
        )
    except ClientError as e:
        logger.warning(f"Failed to update validation result: {e}")
    
    # Send test order if requested
    test_order_result = None
    if send_test_order and test_phone and validation_result["allPassed"]:
        test_order_result = _send_test_order(config, test_phone)
    
    return success_response(
        "validate_payment_configuration",
        tenantId=tenant_id,
        validation=validation_result,
        testOrderResult=test_order_result
    )


def _send_test_order(config: Dict[str, Any], test_phone: str) -> Dict[str, Any]:
    """Send a test order details message."""
    from handlers.payments import handle_send_payment_order
    
    test_event = {
        "action": "send_payment_order",
        "metaWabaId": config.get("wabaId"),
        "to": test_phone,
        "referenceId": f"TEST-{iso_now().replace(':', '').replace('-', '').replace('.', '')[:14]}",
        "paymentType": "PG_RAZORPAY" if config.get("type") == "PG" else "UPI_INTENT",
        "currency": "INR",
        "totalAmount": 1,  # ₹1 test amount
        "order": {
            "status": "pending",
            "items": [
                {
                    "name": "Test Payment Validation",
                    "amount": 1,
                    "quantity": 1,
                    "retailerId": "TEST-001"
                }
            ]
        }
    }
    
    if config.get("type") == "PG":
        test_event["paymentConfigurationName"] = config.get("configName")
    else:
        # Build UPI intent link
        upi_id = config.get("upiId", "")
        test_event["upiIntentLink"] = f"upi://pay?pa={upi_id}&pn=Test&am=1&cu=INR&tr={test_event['referenceId']}"
    
    return handle_send_payment_order(test_event, None)


# =============================================================================
# SEND ORDER DETAILS WITH PAYMENT
# =============================================================================

def handle_send_order_details_with_payment(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send order details message using stored payment configuration.
    
    This is the main action for sending payment requests using tenant configs.
    
    Test Event:
    {
        "action": "send_order_details_with_payment",
        "tenantId": "wecare-digital",
        "toPhone": "+919903300044",
        "configName": "WECARE-DIGITAL",
        "order": {
            "referenceId": "ORDER-001",
            "items": [
                {"name": "Product A", "amount": 500, "quantity": 2, "retailerId": "SKU-001"}
            ],
            "subtotal": 1000,
            "tax": 180,
            "shipping": 50,
            "discount": 100,
            "total": 1130
        }
    }
    """
    tenant_id = event.get("tenantId", "")
    to_phone = event.get("toPhone", "")
    config_name = event.get("configName", "")
    order = event.get("order", {})
    expiration_seconds = event.get("expirationSeconds", 300)
    
    err = validate_required_fields(event, ["tenantId", "toPhone", "order"])
    if err:
        return err
    
    # Get payment configuration
    if not config_name:
        # Try to get default config for tenant
        tenant_pk = _build_tenant_pk(tenant_id)
        tenant = get_item(tenant_pk)
        if tenant:
            config_name = tenant.get("defaultPaymentConfig")
    
    if not config_name:
        return error_response("configName is required (no default set)", 400)
    
    config_pk = _build_payment_config_pk(tenant_id, config_name)
    config = get_item(config_pk)
    
    if not config:
        return error_response(f"Payment configuration not found: {config_name}", 404)
    
    if config.get("status") != "active":
        return error_response(f"Payment configuration not active: {config_name}", 400)
    
    # Build order details message
    reference_id = order.get("referenceId", f"ORD-{iso_now().replace(':', '').replace('-', '')[:14]}")
    total_amount = order.get("total", order.get("subtotal", 0))
    
    # Build order items in Meta format
    order_items = []
    for item in order.get("items", []):
        order_items.append({
            "retailer_id": item.get("retailerId", f"ITEM-{len(order_items)+1}"),
            "name": item.get("name", "Item"),
            "amount": {
                "value": int(item.get("amount", 0) * 1000),
                "offset": 1000
            },
            "quantity": item.get("quantity", 1)
        })
    
    # Build payment settings based on config type
    payment_settings = []
    if config.get("type") == "PG":
        payment_settings.append({
            "type": "payment_gateway",
            "payment_gateway": {
                "type": "razorpay",
                "configuration_name": config_name
            }
        })
    elif config.get("type") == "UPI":
        upi_id = config.get("upiId", "")
        upi_link = f"upi://pay?pa={upi_id}&pn={config.get('displayName', 'Merchant')}&am={total_amount}&cu=INR&tr={reference_id}"
        payment_settings.append({
            "type": "payment_gateway",
            "payment_gateway": {
                "type": "upi_intent",
                "upi_intent": {
                    "upi_intent_link": upi_link
                }
            }
        })
    
    # Build interactive order_details message
    interactive = {
        "type": "order_details",
        "body": {
            "text": f"Order #{reference_id}"
        },
        "footer": {
            "text": f"Powered by {config.get('displayName', tenant_id)}"
        },
        "action": {
            "name": "review_and_pay",
            "parameters": {
                "reference_id": reference_id,
                "type": "digital-goods",
                "payment_settings": payment_settings,
                "currency": "INR",
                "total_amount": {
                    "value": int(total_amount * 1000),
                    "offset": 1000
                },
                "order": {
                    "status": "pending",
                    "items": order_items,
                    "subtotal": {
                        "value": int(order.get("subtotal", total_amount) * 1000),
                        "offset": 1000
                    }
                },
                "expiration_seconds": expiration_seconds
            }
        }
    }
    
    # Add optional order fields
    if order.get("tax"):
        interactive["action"]["parameters"]["order"]["tax"] = {
            "value": int(order.get("tax") * 1000),
            "offset": 1000,
            "description": order.get("taxDescription", "Tax")
        }
    
    if order.get("shipping"):
        interactive["action"]["parameters"]["order"]["shipping"] = {
            "value": int(order.get("shipping") * 1000),
            "offset": 1000,
            "description": order.get("shippingDescription", "Shipping")
        }
    
    if order.get("discount"):
        interactive["action"]["parameters"]["order"]["discount"] = {
            "value": int(order.get("discount") * 1000),
            "offset": 1000,
            "description": order.get("discountDescription", "Discount")
        }
    
    # Send message
    phone_arn = get_phone_arn(config.get("wabaId"))
    if not phone_arn:
        return error_response(f"Phone ARN not found for WABA: {config.get('wabaId')}", 404)
    
    payload = {
        "messaging_product": "whatsapp",
        "to": format_wa_number(to_phone),
        "type": "interactive",
        "interactive": interactive
    }
    
    result = send_whatsapp_message(phone_arn, payload)
    
    now = iso_now()
    
    if result.get("success"):
        # Store order record
        order_pk = f"ORDER#{reference_id}"
        store_item({
            MESSAGES_PK_NAME: order_pk,
            "itemType": "PAYMENT_ORDER",
            "tenantId": tenant_id,
            "referenceId": reference_id,
            "configName": config_name,
            "configType": config.get("type"),
            "wabaId": config.get("wabaId"),
            "customerPhone": to_phone,
            "currency": "INR",
            "totalAmount": total_amount,
            "orderItems": order_items,
            "status": "pending",
            "messageId": result.get("messageId"),
            "createdAt": now,
            "expiresAt": now,  # Would calculate based on expiration_seconds
        })
    
    return success_response(
        "send_order_details_with_payment",
        tenantId=tenant_id,
        configName=config_name,
        referenceId=reference_id,
        totalAmount=total_amount,
        currency="INR",
        **result
    )
