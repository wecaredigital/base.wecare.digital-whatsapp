# Phone Number Management Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/phone-numbers

import json
import logging
from typing import Any, Dict
from handlers.base import (
    table, social, ec2, iam, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config, WABA_PHONE_MAP
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Verification Methods
VERIFICATION_METHODS = ["SMS", "VOICE"]

# Phone Status
PHONE_STATUSES = ["PENDING", "VERIFIED", "CONNECTED", "DISCONNECTED", "BANNED"]


def handle_request_verification_code(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Request phone number verification code.
    
    Test Event:
    {
        "action": "request_verification_code",
        "metaWabaId": "1347766229904230",
        "phoneNumber": "+919903300044",
        "method": "SMS",
        "language": "en"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    phone_number = event.get("phoneNumber", "")
    method = event.get("method", "SMS")
    language = event.get("language", "en")
    
    error = validate_required_fields(event, ["metaWabaId", "phoneNumber"])
    if error:
        return error
    
    if method not in VERIFICATION_METHODS:
        return {"statusCode": 400, "error": f"Invalid method. Valid: {VERIFICATION_METHODS}"}
    
    now = iso_now()
    verification_pk = f"VERIFICATION#{meta_waba_id}#{phone_number}"
    
    try:
        # Store verification request
        store_item({
            MESSAGES_PK_NAME: verification_pk,
            "itemType": "VERIFICATION_REQUEST",
            "wabaMetaId": meta_waba_id,
            "phoneNumber": phone_number,
            "method": method,
            "language": language,
            "status": "PENDING",
            "requestedAt": now,
            "expiresAt": now,  # Would add 10 minutes
        })
        
        return {
            "statusCode": 200,
            "operation": "request_verification_code",
            "phoneNumber": phone_number,
            "method": method,
            "status": "PENDING",
            "message": f"Verification code sent via {method}. Use verify_code action to complete.",
            "note": "Actual verification requires Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_verify_code(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Verify phone number with code.
    
    Test Event:
    {
        "action": "verify_code",
        "metaWabaId": "1347766229904230",
        "phoneNumber": "+919903300044",
        "code": "123456"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    phone_number = event.get("phoneNumber", "")
    code = event.get("code", "")
    
    error = validate_required_fields(event, ["metaWabaId", "phoneNumber", "code"])
    if error:
        return error
    
    verification_pk = f"VERIFICATION#{meta_waba_id}#{phone_number}"
    now = iso_now()
    
    try:
        verification = get_item(verification_pk)
        if not verification:
            return {"statusCode": 404, "error": "No pending verification found"}
        
        if verification.get("status") != "PENDING":
            return {"statusCode": 400, "error": f"Verification status: {verification.get('status')}"}
        
        # Update verification status
        table().update_item(
            Key={MESSAGES_PK_NAME: verification_pk},
            UpdateExpression="SET #st = :st, verifiedAt = :va, verificationCode = :vc",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "VERIFIED",
                ":va": now,
                ":vc": code
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "verify_code",
            "phoneNumber": phone_number,
            "status": "VERIFIED",
            "verifiedAt": now,
            "note": "Actual verification requires Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_two_step_verification(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Enable/disable two-step verification (2FA) for phone number.
    
    Test Event:
    {
        "action": "set_two_step_verification",
        "metaWabaId": "1347766229904230",
        "pin": "123456",
        "enabled": true
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    pin = event.get("pin", "")
    enabled = event.get("enabled", True)
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    if enabled and (not pin or len(pin) != 6 or not pin.isdigit()):
        return {"statusCode": 400, "error": "PIN must be exactly 6 digits"}
    
    now = iso_now()
    twofa_pk = f"2FA#{meta_waba_id}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: twofa_pk,
            "itemType": "TWO_FACTOR_AUTH",
            "wabaMetaId": meta_waba_id,
            "enabled": enabled,
            "pinHash": hash(pin) if pin else None,  # In production, use proper hashing
            "updatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "set_two_step_verification",
            "enabled": enabled,
            "updatedAt": now,
            "note": "Actual 2FA requires Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_phone_certificates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get phone number certificates.
    
    Test Event:
    {
        "action": "get_phone_certificates",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        phone_arn = waba_config.get("phoneArn", "")
        
        return {
            "statusCode": 200,
            "operation": "get_phone_certificates",
            "wabaMetaId": meta_waba_id,
            "phoneArn": phone_arn,
            "certificates": {
                "businessVerification": waba_config.get("businessVerified", False),
                "displayNameApproved": True,
                "qualityRating": waba_config.get("qualityRating", "GREEN"),
            },
            "note": "Actual certificates require Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_register_phone(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Register a phone number with WhatsApp Business.
    
    Test Event:
    {
        "action": "register_phone",
        "metaWabaId": "1347766229904230",
        "phoneNumber": "+919903300044",
        "displayName": "WECARE Digital",
        "pin": "123456"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    phone_number = event.get("phoneNumber", "")
    display_name = event.get("displayName", "")
    pin = event.get("pin", "")
    
    error = validate_required_fields(event, ["metaWabaId", "phoneNumber", "displayName"])
    if error:
        return error
    
    now = iso_now()
    phone_pk = f"PHONE#{meta_waba_id}#{phone_number}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: phone_pk,
            "itemType": "PHONE_REGISTRATION",
            "wabaMetaId": meta_waba_id,
            "phoneNumber": phone_number,
            "displayName": display_name,
            "status": "PENDING",
            "registeredAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "register_phone",
            "phoneNumber": phone_number,
            "displayName": display_name,
            "status": "PENDING",
            "note": "Actual registration requires Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_deregister_phone(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Deregister a phone number from WhatsApp Business.
    
    Test Event:
    {
        "action": "deregister_phone",
        "metaWabaId": "1347766229904230",
        "phoneNumber": "+919903300044"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    phone_number = event.get("phoneNumber", "")
    
    error = validate_required_fields(event, ["metaWabaId", "phoneNumber"])
    if error:
        return error
    
    phone_pk = f"PHONE#{meta_waba_id}#{phone_number}"
    now = iso_now()
    
    try:
        table().update_item(
            Key={MESSAGES_PK_NAME: phone_pk},
            UpdateExpression="SET #st = :st, deregisteredAt = :da",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "DEREGISTERED",
                ":da": now
            }
        )
        
        return {
            "statusCode": 200,
            "operation": "deregister_phone",
            "phoneNumber": phone_number,
            "status": "DEREGISTERED",
            "deregisteredAt": now,
            "note": "Actual deregistration requires Meta Graph API call"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_phone_numbers(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all registered phone numbers for a WABA.
    
    Test Event:
    {
        "action": "get_phone_numbers",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    try:
        # Get from environment config
        phones = []
        for waba_id, config in WABA_PHONE_MAP.items():
            if not meta_waba_id or waba_id == meta_waba_id:
                phones.append({
                    "wabaMetaId": waba_id,
                    "phoneArn": config.get("phoneArn", ""),
                    "businessAccountName": config.get("businessAccountName", ""),
                    "qualityRating": config.get("qualityRating", "GREEN"),
                })
        
        return {
            "statusCode": 200,
            "operation": "get_phone_numbers",
            "count": len(phones),
            "phones": phones
        }
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_health_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get phone number health status.
    
    Test Event:
    {
        "action": "get_health_status",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        phone_arn = waba_config.get("phoneArn", "")
        
        # Query recent messages for health metrics
        response = table().scan(
            FilterExpression="wabaMetaId = :waba AND itemType = :it",
            ExpressionAttributeValues={":waba": meta_waba_id, ":it": "MESSAGE"},
            Limit=100
        )
        items = response.get("Items", [])
        
        outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
        failed = [i for i in outbound if i.get("deliveryStatus") == "failed"]
        
        failure_rate = len(failed) / len(outbound) * 100 if outbound else 0
        
        # Determine health status
        if failure_rate > 10:
            health = "DEGRADED"
        elif failure_rate > 5:
            health = "WARNING"
        else:
            health = "HEALTHY"
        
        return {
            "statusCode": 200,
            "operation": "get_health_status",
            "wabaMetaId": meta_waba_id,
            "phoneArn": phone_arn,
            "health": {
                "status": health,
                "qualityRating": waba_config.get("qualityRating", "GREEN"),
                "messagingTier": waba_config.get("messagingTier", "STANDARD"),
                "failureRate": round(failure_rate, 2),
                "recentMessages": len(outbound),
                "recentFailures": len(failed),
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
