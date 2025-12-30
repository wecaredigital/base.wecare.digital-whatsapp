# Analytics Handlers
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/analytics

import json
import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta
from handlers.base import (
    table, MESSAGES_PK_NAME, iso_now, store_item, get_item,
    validate_required_fields, get_waba_config
)
from botocore.exceptions import ClientError

logger = logging.getLogger()


def handle_get_analytics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get comprehensive analytics for a WABA.
    
    Test Event:
    {
        "action": "get_analytics",
        "metaWabaId": "1347766229904230",
        "startDate": "2024-12-01",
        "endDate": "2024-12-30",
        "granularity": "daily"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    start_date = event.get("startDate", "")
    end_date = event.get("endDate", "")
    granularity = event.get("granularity", "daily")  # daily, weekly, monthly
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query all messages for this WABA
        filter_expr = "wabaMetaId = :waba AND itemType = :it"
        expr_values = {":waba": meta_waba_id, ":it": "MESSAGE"}
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=10000
        )
        
        items = response.get("Items", [])
        
        # Calculate analytics
        total_messages = len(items)
        inbound = [i for i in items if i.get("direction") == "INBOUND"]
        outbound = [i for i in items if i.get("direction") == "OUTBOUND"]
        
        # Message type breakdown
        type_counts = {}
        for item in items:
            msg_type = item.get("type", "unknown")
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
        
        # Delivery status breakdown
        status_counts = {}
        for item in outbound:
            status = item.get("deliveryStatus", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Response time analysis (for conversations)
        response_times = []
        conversations = [i for i in items if i.get("itemType") == "CONVERSATION"]
        
        # Unique contacts
        unique_contacts = set()
        for item in items:
            if item.get("from"):
                unique_contacts.add(item.get("from"))
            if item.get("to"):
                unique_contacts.add(item.get("to"))
        
        analytics = {
            "summary": {
                "totalMessages": total_messages,
                "inboundMessages": len(inbound),
                "outboundMessages": len(outbound),
                "uniqueContacts": len(unique_contacts),
                "conversations": len(conversations),
            },
            "messageTypes": type_counts,
            "deliveryStatus": status_counts,
            "deliveryRate": round(status_counts.get("delivered", 0) / len(outbound) * 100, 2) if outbound else 0,
            "readRate": round(status_counts.get("read", 0) / len(outbound) * 100, 2) if outbound else 0,
            "failureRate": round(status_counts.get("failed", 0) / len(outbound) * 100, 2) if outbound else 0,
        }
        
        # Store analytics snapshot
        now = iso_now()
        store_item({
            MESSAGES_PK_NAME: f"ANALYTICS#{meta_waba_id}#{now}",
            "itemType": "ANALYTICS_SNAPSHOT",
            "wabaMetaId": meta_waba_id,
            "analytics": analytics,
            "generatedAt": now,
            "startDate": start_date,
            "endDate": end_date,
        })
        
        return {
            "statusCode": 200,
            "operation": "get_analytics",
            "wabaMetaId": meta_waba_id,
            "period": {"start": start_date, "end": end_date},
            "analytics": analytics
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_ctwa_metrics(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get Click-to-WhatsApp (CTWA) metrics.
    
    Test Event:
    {
        "action": "get_ctwa_metrics",
        "metaWabaId": "1347766229904230",
        "campaignId": "campaign_123"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    campaign_id = event.get("campaignId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query CTWA events
        filter_expr = "itemType = :it AND wabaMetaId = :waba"
        expr_values = {":it": "CTWA_EVENT", ":waba": meta_waba_id}
        
        if campaign_id:
            filter_expr += " AND campaignId = :cid"
            expr_values[":cid"] = campaign_id
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=1000
        )
        
        items = response.get("Items", [])
        
        # Calculate CTWA metrics
        total_clicks = len(items)
        conversations_started = len([i for i in items if i.get("conversationStarted")])
        messages_sent = sum(i.get("messageCount", 0) for i in items)
        
        # Attribution by source
        source_breakdown = {}
        for item in items:
            source = item.get("source", "unknown")
            source_breakdown[source] = source_breakdown.get(source, 0) + 1
        
        metrics = {
            "totalClicks": total_clicks,
            "conversationsStarted": conversations_started,
            "conversionRate": round(conversations_started / total_clicks * 100, 2) if total_clicks > 0 else 0,
            "totalMessagesSent": messages_sent,
            "avgMessagesPerConversation": round(messages_sent / conversations_started, 2) if conversations_started > 0 else 0,
            "sourceBreakdown": source_breakdown,
        }
        
        return {
            "statusCode": 200,
            "operation": "get_ctwa_metrics",
            "wabaMetaId": meta_waba_id,
            "campaignId": campaign_id or "all",
            "metrics": metrics
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_get_funnel_insights(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get funnel insights for message delivery.
    
    Test Event:
    {
        "action": "get_funnel_insights",
        "metaWabaId": "1347766229904230",
        "templateName": "order_confirmation"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    template_name = event.get("templateName", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    try:
        # Query outbound messages
        filter_expr = "direction = :dir AND wabaMetaId = :waba"
        expr_values = {":dir": "OUTBOUND", ":waba": meta_waba_id}
        
        if template_name:
            filter_expr += " AND templateName = :tn"
            expr_values[":tn"] = template_name
        
        response = table().scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values,
            Limit=5000
        )
        
        items = response.get("Items", [])
        
        # Build funnel
        total_sent = len(items)
        delivered = len([i for i in items if i.get("deliveryStatus") in ["delivered", "read"]])
        read = len([i for i in items if i.get("deliveryStatus") == "read"])
        replied = len([i for i in items if i.get("hasReply")])
        converted = len([i for i in items if i.get("converted")])
        
        funnel = {
            "sent": {"count": total_sent, "rate": 100},
            "delivered": {
                "count": delivered,
                "rate": round(delivered / total_sent * 100, 2) if total_sent > 0 else 0
            },
            "read": {
                "count": read,
                "rate": round(read / total_sent * 100, 2) if total_sent > 0 else 0
            },
            "replied": {
                "count": replied,
                "rate": round(replied / total_sent * 100, 2) if total_sent > 0 else 0
            },
            "converted": {
                "count": converted,
                "rate": round(converted / total_sent * 100, 2) if total_sent > 0 else 0
            },
        }
        
        # Drop-off analysis
        dropoff = {
            "sentToDelivered": round((total_sent - delivered) / total_sent * 100, 2) if total_sent > 0 else 0,
            "deliveredToRead": round((delivered - read) / delivered * 100, 2) if delivered > 0 else 0,
            "readToReplied": round((read - replied) / read * 100, 2) if read > 0 else 0,
        }
        
        return {
            "statusCode": 200,
            "operation": "get_funnel_insights",
            "wabaMetaId": meta_waba_id,
            "templateName": template_name or "all",
            "funnel": funnel,
            "dropoff": dropoff,
            "recommendations": _get_funnel_recommendations(funnel, dropoff)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def _get_funnel_recommendations(funnel: Dict, dropoff: Dict) -> List[str]:
    """Generate recommendations based on funnel analysis."""
    recommendations = []
    
    if dropoff.get("sentToDelivered", 0) > 10:
        recommendations.append("High delivery failure rate. Check phone number validity and opt-in status.")
    
    if dropoff.get("deliveredToRead", 0) > 50:
        recommendations.append("Low read rate. Consider optimizing message timing and content preview.")
    
    if dropoff.get("readToReplied", 0) > 80:
        recommendations.append("Low reply rate. Add clear CTAs and interactive elements.")
    
    if funnel.get("delivered", {}).get("rate", 0) < 90:
        recommendations.append("Delivery rate below 90%. Review phone number quality and message content.")
    
    if not recommendations:
        recommendations.append("Funnel performance is healthy. Continue monitoring.")
    
    return recommendations


def handle_track_ctwa_click(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Track a Click-to-WhatsApp click event.
    
    Test Event:
    {
        "action": "track_ctwa_click",
        "metaWabaId": "1347766229904230",
        "campaignId": "campaign_123",
        "source": "facebook_ad",
        "adId": "ad_456",
        "userId": "user_789"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    campaign_id = event.get("campaignId", "")
    source = event.get("source", "unknown")
    ad_id = event.get("adId", "")
    user_id = event.get("userId", "")
    
    error = validate_required_fields(event, ["metaWabaId"])
    if error:
        return error
    
    now = iso_now()
    click_pk = f"CTWA_EVENT#{meta_waba_id}#{now}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: click_pk,
            "itemType": "CTWA_EVENT",
            "wabaMetaId": meta_waba_id,
            "campaignId": campaign_id,
            "source": source,
            "adId": ad_id,
            "userId": user_id,
            "clickedAt": now,
            "conversationStarted": False,
            "messageCount": 0,
        })
        
        return {
            "statusCode": 200,
            "operation": "track_ctwa_click",
            "clickPk": click_pk,
            "tracked": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}


def handle_setup_welcome_sequence(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Setup CTWA welcome message sequence.
    
    Test Event:
    {
        "action": "setup_welcome_sequence",
        "metaWabaId": "1347766229904230",
        "sequenceName": "new_customer_welcome",
        "messages": [
            {"delay": 0, "type": "text", "text": "Welcome! How can we help you today?"},
            {"delay": 60, "type": "interactive", "body": "Choose an option:", "buttons": [
                {"id": "sales", "title": "Sales"},
                {"id": "support", "title": "Support"}
            ]}
        ]
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    sequence_name = event.get("sequenceName", "")
    messages = event.get("messages", [])
    
    error = validate_required_fields(event, ["metaWabaId", "sequenceName", "messages"])
    if error:
        return error
    
    now = iso_now()
    sequence_pk = f"WELCOME_SEQUENCE#{meta_waba_id}#{sequence_name}"
    
    try:
        store_item({
            MESSAGES_PK_NAME: sequence_pk,
            "itemType": "WELCOME_SEQUENCE",
            "wabaMetaId": meta_waba_id,
            "sequenceName": sequence_name,
            "messages": messages,
            "messageCount": len(messages),
            "status": "active",
            "createdAt": now,
            "lastUpdatedAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "setup_welcome_sequence",
            "sequencePk": sequence_pk,
            "sequenceName": sequence_name,
            "messageCount": len(messages)
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
