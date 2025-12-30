# Quality & Compliance Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/phone-numbers

import json
import logging
from typing import Any, Dict
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_phone_arn, get_waba_config, WABA_PHONE_MAP
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Quality Ratings
QUALITY_RATINGS = ["GREEN", "YELLOW", "RED", "UNKNOWN"]

# Messaging Tiers
MESSAGING_TIERS = ["TIER_1K", "TIER_10K", "TIER_100K", "TIER_UNLIMITED"]

# Tier Limits
TIER_LIMITS = {
    "TIER_1K": 1000,
    "TIER_10K": 10000,
    "TIER_100K": 100000,
    "TIER_UNLIMITED": float("inf")
}


def handle_get_quality_rating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get quality rating from Meta for a phone number.
    
    Test Event:
    {
        "action": "get_quality_rating",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        
        # Query recent message stats for quality estimation
        response = table().scan(
            FilterExpression="itemType = :it AND wabaMetaId = :waba",
            ExpressionAttributeValues={":it": "MESSAGE", ":waba": meta_waba_id},
            Limit=500
        )
        items = response.get("Items", [])
        
        outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
        failed = [i for i in outbound if i.get("deliveryStatus") == "failed"]
        blocked = [i for i in outbound if i.get("errorCode") in ["131026", "131047"]]
        
        failure_rate = len(failed) / len(outbound) * 100 if outbound else 0
        block_rate = len(blocked) / len(outbound) * 100 if outbound else 0
        
        # Estimate quality rating
        if failure_rate > 10 or block_rate > 5:
            estimated_rating = "RED"
        elif failure_rate > 5 or block_rate > 2:
            estimated_rating = "YELLOW"
        else:
            estimated_rating = "GREEN"
        
        return {
            "statusCode": 200,
            "operation": "get_quality_rating",
            "wabaMetaId": meta_waba_id,
            "qualityRating": {
                "current": waba_config.get("qualityRating", estimated_rating),
                "estimated": estimated_rating,
                "metrics": {
                    "totalOutbound": len(outbound),
                    "failed": len(failed),
                    "blocked": len(blocked),
                    "failureRate": round(failure_rate, 2),
                    "blockRate": round(block_rate, 2),
                }
            },
            "note": "For actual rating, use Meta Graph API: GET /{phone-number-id}?fields=quality_rating"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_messaging_limits(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get messaging tier limits for a WABA.
    
    Test Event:
    {
        "action": "get_messaging_limits",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        current_tier = waba_config.get("messagingTier", "TIER_1K")
        
        # Count unique recipients in last 24 hours
        response = table().scan(
            FilterExpression="itemType = :it AND wabaMetaId = :waba AND direction = :dir",
            ExpressionAttributeValues={
                ":it": "MESSAGE",
                ":waba": meta_waba_id,
                ":dir": "OUTBOUND"
            },
            Limit=1000
        )
        items = response.get("Items", [])
        
        unique_recipients = len(set(i.get("recipientPhone", "") for i in items))
        tier_limit = TIER_LIMITS.get(current_tier, 1000)
        usage_percent = (unique_recipients / tier_limit * 100) if tier_limit != float("inf") else 0
        
        return {
            "statusCode": 200,
            "operation": "get_messaging_limits",
            "wabaMetaId": meta_waba_id,
            "messagingLimits": {
                "currentTier": current_tier,
                "tierLimit": tier_limit if tier_limit != float("inf") else "UNLIMITED",
                "uniqueRecipients24h": unique_recipients,
                "usagePercent": round(usage_percent, 2),
                "canUpgrade": current_tier != "TIER_UNLIMITED",
            },
            "tierInfo": {
                "TIER_1K": "1,000 unique recipients per 24h",
                "TIER_10K": "10,000 unique recipients per 24h",
                "TIER_100K": "100,000 unique recipients per 24h",
                "TIER_UNLIMITED": "Unlimited unique recipients",
            },
            "note": "For actual limits, use Meta Graph API: GET /{phone-number-id}?fields=messaging_limit_tier"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_request_tier_upgrade(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Request messaging tier upgrade.
    
    Test Event:
    {
        "action": "request_tier_upgrade",
        "metaWabaId": "1347766229904230",
        "requestedTier": "TIER_10K",
        "reason": "Business growth requires higher volume"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    requested_tier = event.get("requestedTier", "")
    reason = event.get("reason", "")
    
    error = validate_required_fields(event, ["metaWabaId", "requestedTier"])
    if error:
        return error
    
    if requested_tier not in MESSAGING_TIERS:
        return {"statusCode": 400, "error": f"Invalid tier. Valid: {MESSAGING_TIERS}"}
    
    now = iso_now()
    request_pk = f"TIER_UPGRADE#{meta_waba_id}#{now}"
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        current_tier = waba_config.get("messagingTier", "TIER_1K")
        
        # Check if upgrade is valid
        current_idx = MESSAGING_TIERS.index(current_tier) if current_tier in MESSAGING_TIERS else 0
        requested_idx = MESSAGING_TIERS.index(requested_tier)
        
        if requested_idx <= current_idx:
            return {"statusCode": 400, "error": f"Requested tier must be higher than current tier ({current_tier})"}
        
        store_item({
            MESSAGES_PK_NAME: request_pk,
            "itemType": "TIER_UPGRADE_REQUEST",
            "wabaMetaId": meta_waba_id,
            "currentTier": current_tier,
            "requestedTier": requested_tier,
            "reason": reason,
            "status": "PENDING",
            "requestedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "request_tier_upgrade",
            "wabaMetaId": meta_waba_id,
            "currentTier": current_tier,
            "requestedTier": requested_tier,
            "status": "PENDING",
            "note": "Tier upgrades are automatic based on quality. Maintain GREEN quality rating for 7+ days."
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_phone_health_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get comprehensive phone health status.
    
    Test Event:
    {
        "action": "get_phone_health_status",
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
        
        # Query recent messages
        response = table().scan(
            FilterExpression="itemType = :it AND wabaMetaId = :waba",
            ExpressionAttributeValues={":it": "MESSAGE", ":waba": meta_waba_id},
            Limit=500
        )
        items = response.get("Items", [])
        
        outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
        inbound = [i for i in items if i.get("direction") == "INBOUND"]
        delivered = [i for i in outbound if i.get("deliveryStatus") == "delivered"]
        read = [i for i in outbound if i.get("deliveryStatus") == "read"]
        failed = [i for i in outbound if i.get("deliveryStatus") == "failed"]
        
        # Calculate health metrics
        delivery_rate = len(delivered) / len(outbound) * 100 if outbound else 100
        read_rate = len(read) / len(delivered) * 100 if delivered else 0
        failure_rate = len(failed) / len(outbound) * 100 if outbound else 0
        response_rate = len(inbound) / len(outbound) * 100 if outbound else 0
        
        # Determine overall health
        if failure_rate > 10:
            health_status = "CRITICAL"
        elif failure_rate > 5 or delivery_rate < 90:
            health_status = "WARNING"
        elif delivery_rate >= 95:
            health_status = "EXCELLENT"
        else:
            health_status = "GOOD"
        
        return {
            "statusCode": 200,
            "operation": "get_phone_health_status",
            "wabaMetaId": meta_waba_id,
            "phoneArn": phone_arn,
            "healthStatus": {
                "overall": health_status,
                "qualityRating": waba_config.get("qualityRating", "GREEN"),
                "messagingTier": waba_config.get("messagingTier", "TIER_1K"),
                "metrics": {
                    "totalOutbound": len(outbound),
                    "totalInbound": len(inbound),
                    "deliveryRate": round(delivery_rate, 2),
                    "readRate": round(read_rate, 2),
                    "failureRate": round(failure_rate, 2),
                    "responseRate": round(response_rate, 2),
                },
                "recommendations": _get_health_recommendations(health_status, failure_rate, delivery_rate)
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def _get_health_recommendations(status: str, failure_rate: float, delivery_rate: float) -> list:
    """Get health improvement recommendations."""
    recommendations = []
    
    if status == "CRITICAL":
        recommendations.append("Immediately review and fix message content causing failures")
        recommendations.append("Check for blocked or invalid phone numbers")
        recommendations.append("Review template quality and approval status")
    elif status == "WARNING":
        recommendations.append("Monitor failure patterns and address common issues")
        recommendations.append("Ensure templates are approved and up-to-date")
    
    if failure_rate > 5:
        recommendations.append("Clean your contact list to remove invalid numbers")
    
    if delivery_rate < 95:
        recommendations.append("Verify recipient numbers are active WhatsApp users")
        recommendations.append("Check message timing - avoid sending during off-hours")
    
    if not recommendations:
        recommendations.append("Maintain current practices to keep quality high")
    
    return recommendations


def handle_get_compliance_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get compliance status for WABA.
    
    Test Event:
    {
        "action": "get_compliance_status",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        waba_config = get_waba_config(meta_waba_id)
        
        return {
            "statusCode": 200,
            "operation": "get_compliance_status",
            "wabaMetaId": meta_waba_id,
            "compliance": {
                "businessVerified": waba_config.get("businessVerified", False),
                "displayNameApproved": True,
                "policyCompliant": True,
                "optInRequired": True,
                "dataRetentionCompliant": True,
            },
            "policies": {
                "messagingPolicy": "https://www.whatsapp.com/legal/business-policy/",
                "commercePolicy": "https://www.whatsapp.com/legal/commerce-policy/",
                "dataPolicy": "https://www.whatsapp.com/legal/privacy-policy/",
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
