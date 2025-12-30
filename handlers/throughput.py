# Throughput Management Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/overview/throughput
#
# This module handles throughput/rate limiting management
# =============================================================================

import logging
from typing import Any, Dict
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, WABA_PHONE_MAP
)
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Throughput tiers (messages per second)
THROUGHPUT_TIERS = {
    "STANDARD": {"mps": 80, "description": "Standard tier - 80 messages/second"},
    "HIGH": {"mps": 250, "description": "High throughput - 250 messages/second"},
    "HIGHER": {"mps": 500, "description": "Higher throughput - 500 messages/second"},
    "HIGHEST": {"mps": 1000, "description": "Highest throughput - 1000 messages/second"}
}


def handle_get_throughput_limits(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get current throughput limits for a WABA.
    
    Test Event:
    {
        "action": "get_throughput_limits",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    throughput_pk = f"THROUGHPUT#{meta_waba_id}"
    
    try:
        # Get cached throughput info
        cached = get_item(throughput_pk)
        
        if cached:
            return {
                "statusCode": 200,
                "operation": "get_throughput_limits",
                "wabaMetaId": meta_waba_id,
                "currentTier": cached.get("tier", "STANDARD"),
                "messagesPerSecond": cached.get("mps", 80),
                "dailyLimit": cached.get("dailyLimit", 100000),
                "usedToday": cached.get("usedToday", 0),
                "lastUpdated": cached.get("lastUpdated", ""),
                "cached": True
            }
        
        # Return default values
        return {
            "statusCode": 200,
            "operation": "get_throughput_limits",
            "wabaMetaId": meta_waba_id,
            "currentTier": "STANDARD",
            "messagesPerSecond": 80,
            "dailyLimit": 100000,
            "usedToday": 0,
            "availableTiers": THROUGHPUT_TIERS,
            "cached": False
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_set_throughput_tier(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set throughput tier for a WABA (requires Meta approval).
    
    Test Event:
    {
        "action": "set_throughput_tier",
        "metaWabaId": "1347766229904230",
        "tier": "HIGH"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    tier = event.get("tier", "STANDARD")
    
    error = validate_required_fields(event, ["metaWabaId", "tier"])
    if error:
        return error
    
    if tier not in THROUGHPUT_TIERS:
        return {"statusCode": 400, "error": f"Invalid tier. Valid: {list(THROUGHPUT_TIERS.keys())}"}
    
    throughput_pk = f"THROUGHPUT#{meta_waba_id}"
    now = iso_now()
    
    try:
        tier_info = THROUGHPUT_TIERS[tier]
        
        store_item({
            MESSAGES_PK_NAME: throughput_pk,
            "itemType": "THROUGHPUT_CONFIG",
            "wabaMetaId": meta_waba_id,
            "tier": tier,
            "mps": tier_info["mps"],
            "dailyLimit": tier_info["mps"] * 86400,  # Theoretical max
            "usedToday": 0,
            "lastUpdated": now,
            "requestedAt": now,
            "status": "pending_approval"
        })
        
        return {
            "statusCode": 200,
            "operation": "set_throughput_tier",
            "wabaMetaId": meta_waba_id,
            "requestedTier": tier,
            "messagesPerSecond": tier_info["mps"],
            "status": "pending_approval",
            "note": "Tier upgrade requires Meta approval"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_throughput_stats(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get throughput usage statistics.
    
    Test Event:
    {
        "action": "get_throughput_stats",
        "metaWabaId": "1347766229904230",
        "period": "today"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    period = event.get("period", "today")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Get message counts from DynamoDB
        response = table().scan(
            FilterExpression="wabaMetaId = :waba AND itemType = :it AND direction = :dir",
            ExpressionAttributeValues={
                ":waba": meta_waba_id,
                ":it": "MESSAGE",
                ":dir": "OUTBOUND"
            },
            Select="COUNT"
        )
        
        total_sent = response.get("Count", 0)
        
        # Get throughput config
        throughput_pk = f"THROUGHPUT#{meta_waba_id}"
        config = get_item(throughput_pk) or {}
        
        current_mps = config.get("mps", 80)
        daily_limit = config.get("dailyLimit", 100000)
        
        return {
            "statusCode": 200,
            "operation": "get_throughput_stats",
            "wabaMetaId": meta_waba_id,
            "period": period,
            "totalMessagesSent": total_sent,
            "currentTier": config.get("tier", "STANDARD"),
            "messagesPerSecond": current_mps,
            "dailyLimit": daily_limit,
            "utilizationPercent": round((total_sent / daily_limit) * 100, 2) if daily_limit > 0 else 0
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_check_rate_limit(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check if rate limit allows sending more messages.
    
    Test Event:
    {
        "action": "check_rate_limit",
        "metaWabaId": "1347766229904230",
        "messageCount": 100
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    message_count = event.get("messageCount", 1)
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        throughput_pk = f"THROUGHPUT#{meta_waba_id}"
        config = get_item(throughput_pk) or {}
        
        current_mps = config.get("mps", 80)
        daily_limit = config.get("dailyLimit", 100000)
        used_today = config.get("usedToday", 0)
        
        remaining = daily_limit - used_today
        can_send = message_count <= remaining
        
        # Calculate estimated time to send
        estimated_seconds = message_count / current_mps if current_mps > 0 else 0
        
        return {
            "statusCode": 200,
            "operation": "check_rate_limit",
            "wabaMetaId": meta_waba_id,
            "requestedCount": message_count,
            "canSend": can_send,
            "remainingToday": remaining,
            "messagesPerSecond": current_mps,
            "estimatedSeconds": round(estimated_seconds, 2),
            "recommendation": "OK" if can_send else "Wait or reduce batch size"
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
