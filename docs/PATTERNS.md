# WhatsApp Business API - Architecture Patterns Guide

## Overview

This document describes the architecture patterns used in the WhatsApp Business API Lambda function. It serves as a reference for future upgrades, maintenance, and adding new features.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Handler Pattern](#handler-pattern)
3. [Dispatcher Pattern](#dispatcher-pattern)
4. [DynamoDB Schema](#dynamodb-schema)
5. [SNS Integration](#sns-integration)
6. [API Gateway Integration](#api-gateway-integration)
7. [Adding New Handlers](#adding-new-handlers)
8. [Best Practices](#best-practices)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENTRY POINTS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   Meta/WhatsApp │────▶│   AWS SNS       │────▶│                 │       │
│  │   Webhooks      │     │   Topic         │     │                 │       │
│  └─────────────────┘     └─────────────────┘     │                 │       │
│                                                   │    Lambda       │       │
│  ┌─────────────────┐                             │    Function     │       │
│  │   API Gateway   │────────────────────────────▶│                 │       │
│  │   HTTP API      │                             │                 │       │
│  └─────────────────┘                             └────────┬────────┘       │
│                                                           │                 │
└───────────────────────────────────────────────────────────┼─────────────────┘
                                                            │
┌───────────────────────────────────────────────────────────┼─────────────────┐
│                           SERVICES                        │                 │
├───────────────────────────────────────────────────────────┼─────────────────┤
│                                                           │                 │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐                 │
│  │   DynamoDB    │   │      S3       │   │   AWS EUM     │                 │
│  │   Table       │◀──┤    Bucket     │◀──┤   Social      │◀────────────────┘
│  │               │   │               │   │   Messaging   │                 │
│  └───────────────┘   └───────────────┘   └───────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| Lambda Function | Main entry point, handles all requests |
| DynamoDB | Message storage, conversations, config |
| S3 | Media file storage |
| AWS EUM Social | WhatsApp API integration |
| SNS | Webhook event delivery, email notifications |
| API Gateway | HTTP API for admin actions |

---

## Handler Pattern

### Handler Function Signature

All handlers follow this consistent pattern:

```python
def handle_<action_name>(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Brief description of what this handler does.
    
    Test Event:
    {
        "action": "<action_name>",
        "param1": "value1",
        "param2": "value2"
    }
    
    Returns:
        Success: {"statusCode": 200, "operation": "<action_name>", ...}
        Error: {"statusCode": 4xx|5xx, "error": "message"}
    """
    # 1. Extract parameters
    param1 = event.get("param1", "")
    param2 = event.get("param2", "")
    
    # 2. Validate required fields
    error = validate_required_fields(event, ["param1"])
    if error:
        return error
    
    # 3. Business logic
    try:
        result = do_something(param1, param2)
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
    
    # 4. Return response
    return {
        "statusCode": 200,
        "operation": "<action_name>",
        "data": result
    }
```

### Handler Categories

| Category | Description | Examples |
|----------|-------------|----------|
| messaging | Send WhatsApp messages | send_text, send_image, send_template |
| media | Media file operations | upload_media, download_media |
| conversations | Conversation management | get_conversations, archive_conversation |
| templates | Template management | get_templates, create_marketing_template |
| business_profile | Profile management | get_business_profile, update_business_profile |
| marketing | Marketing features | send_marketing_message, send_carousel_template |
| webhooks | Webhook handling | register_webhook, process_wix_webhook |
| calling | Calling features | initiate_call, get_call_logs |
| groups | Group management | create_group, send_group_message |
| analytics | Analytics & reporting | get_analytics, get_funnel_insights |
| catalogs | Product catalogs | upload_catalog, send_catalog_message |
| payments | Payment processing | create_payment_request, get_payments |
| media_eum | AWS EUM media | eum_upload_media, eum_download_media |
| config | Configuration | get_config, get_quality |
| utility | Utility actions | help, ping, list_actions |

---

## Dispatcher Pattern

### Main Dispatcher (app.py)

The `lambda_handler` function uses a dispatcher pattern to route actions:

```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # 1. Parse API Gateway body if present
    if "body" in event:
        body = json.loads(event["body"])
        event.update(body)
    
    # 2. Get action
    action = event.get("action", "")
    
    # 3. Helper for API Gateway response wrapping
    def maybe_wrap(response):
        if is_api_gateway:
            return api_response(response)
        return response
    
    # 4. Dispatch to core handlers (in app.py)
    if action == "help":
        return maybe_wrap(handle_help(event, context))
    elif action == "send_text":
        return maybe_wrap(handle_send_text(event, context))
    # ... more core handlers ...
    
    # 5. Dispatch to extended handlers (in handlers/)
    result = dispatch_extended_handler(action, event, context)
    if result is not None:
        return maybe_wrap(result)
    
    # 6. Process SNS webhook records (no action specified)
    # ... process inbound messages ...
```

### Extended Handler Dispatcher (handlers/extended.py)

```python
EXTENDED_HANDLERS = {
    "get_business_profile": handle_get_business_profile,
    "send_marketing_message": handle_send_marketing_message,
    # ... more handlers ...
}

def dispatch_extended_handler(action: str, event: Dict, context: Any) -> Optional[Dict]:
    """Dispatch to extended handler if action exists."""
    handler = EXTENDED_HANDLERS.get(action)
    if handler:
        return handler(event, context)
    return None
```

---

## DynamoDB Schema

### Table Structure

- **Table Name**: `base-wecare-digital-whatsapp`
- **Primary Key**: `pk` (String)

### Item Types

| itemType | pk Pattern | Description |
|----------|------------|-------------|
| MESSAGE | `MSG#{waMessageId}` | Individual messages |
| CONVERSATION | `CONV#{phoneArn}#{fromNumber}` | Conversation threads |
| TEMPLATE | `TEMPLATES#{wabaAwsId}` | Cached templates |
| TEMPLATE_DEFINITION | `TEMPLATE#{wabaMetaId}#{name}#{lang}` | Template definitions |
| QUALITY | `QUALITY#{phoneNumberId}` | Phone quality ratings |
| BUSINESS_PROFILE | `PROFILE#{wabaMetaId}` | Business profiles |
| WEBHOOK_CONFIG | `WEBHOOK#{wabaMetaId}` | Webhook configurations |
| WEBHOOK_EVENT | `WEBHOOK_EVENT#{wabaId}#{timestamp}#{field}` | Webhook events |
| CALL | `CALL#{callId}` | Call records |
| CALL_SETTINGS | `CALL_SETTINGS#{wabaMetaId}` | Call settings |
| GROUP | `GROUP#{groupId}` | WhatsApp groups |
| GROUP_MESSAGE | `GROUP_MSG#{groupId}#{timestamp}` | Group messages |
| GROUP_PARTICIPANT | `GROUP_PARTICIPANT#{groupId}#{phone}` | Group participants |
| ANALYTICS_SNAPSHOT | `ANALYTICS#{wabaMetaId}#{timestamp}` | Analytics snapshots |
| CTWA_EVENT | `CTWA_EVENT#{wabaMetaId}#{timestamp}` | Click-to-WhatsApp events |
| WELCOME_SEQUENCE | `WELCOME_SEQUENCE#{wabaMetaId}#{name}` | Welcome sequences |
| CATALOG | `CATALOG#{wabaMetaId}#{catalogId}` | Product catalogs |
| PRODUCT | `PRODUCT#{catalogId}#{retailerId}` | Catalog products |
| PAYMENT | `PAYMENT#{paymentId}` | Payment records |
| PAYMENT_CONFIG | `PAYMENT_CONFIG#{wabaMetaId}#{provider}` | Payment gateway config |
| WIX_ORDER | `WIX_ORDER#{orderId}` | Wix e-commerce orders |
| MEDIA_UPLOAD | `MEDIA_UPLOAD#{mediaId}` | Uploaded media tracking |
| MEDIA_DOWNLOAD | `MEDIA_DOWNLOAD#{mediaId}` | Downloaded media tracking |
| S3_LIFECYCLE_CONFIG | `S3_LIFECYCLE#{bucket}` | S3 lifecycle config |

### Global Secondary Indexes (GSIs)

| GSI Name | Partition Key | Sort Key | Use Case |
|----------|---------------|----------|----------|
| gsi-inbox | inboxPk | receivedAt | List conversations by phone |
| gsi-conversation | conversationPk | receivedAt | Messages in conversation |
| gsi-direction | direction | receivedAt | Filter INBOUND/OUTBOUND |
| gsi-from | from | receivedAt | Messages from specific number |
| gsi-itemType | itemType | createdAt | Query by item type |

---

## SNS Integration

### Inbound Webhook Flow

```
Meta WhatsApp → SNS Topic → Lambda
```

### SNS Record Structure

```json
{
  "Records": [
    {
      "Sns": {
        "Message": "{\"whatsAppWebhookEntry\": {...}}",
        "MessageId": "xxx",
        "Timestamp": "2024-12-30T12:00:00.000Z",
        "TopicArn": "arn:aws:sns:..."
      }
    }
  ]
}
```

### Processing SNS Records

```python
records = event.get("Records", [])
for r in records:
    sns_record = r.get("Sns", {})
    msg_obj = json.loads(sns_record.get("Message", "{}"))
    entry = msg_obj.get("whatsAppWebhookEntry", {})
    
    # Process messages
    for change in entry.get("changes", []):
        value = change.get("value", {})
        messages = value.get("messages", [])
        statuses = value.get("statuses", [])
        # ... process each message/status ...
```

---

## API Gateway Integration

### Request Format

```json
{
  "requestContext": {...},
  "body": "{\"action\": \"send_text\", \"to\": \"+1234567890\", \"text\": \"Hello\"}",
  "headers": {...}
}
```

### Response Format

```python
def api_response(data: Dict, status_code: int = None) -> Dict:
    return {
        "statusCode": status_code or data.get("statusCode", 200),
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data)
    }
```

---

## Adding New Handlers

### Step-by-Step Guide

#### 1. Create Handler Function

Create in appropriate module (e.g., `handlers/my_feature.py`):

```python
# handlers/my_feature.py
from handlers.base import (
    table, validate_required_fields, store_item, get_item,
    iso_now, get_phone_arn, send_whatsapp_message, format_wa_number
)
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()


def handle_my_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Description of my action.
    
    Test Event:
    {
        "action": "my_action",
        "metaWabaId": "1347766229904230",
        "param1": "value1"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    param1 = event.get("param1", "")
    
    # Validate
    error = validate_required_fields(event, ["metaWabaId", "param1"])
    if error:
        return error
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return {"statusCode": 404, "error": f"Phone not found for WABA: {meta_waba_id}"}
    
    try:
        # Business logic
        now = iso_now()
        result_pk = f"MY_ITEM#{now}"
        
        store_item({
            "pk": result_pk,
            "itemType": "MY_ITEM",
            "wabaMetaId": meta_waba_id,
            "param1": param1,
            "createdAt": now,
        })
        
        return {
            "statusCode": 200,
            "operation": "my_action",
            "resultPk": result_pk,
            "success": True
        }
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
```

#### 2. Import in extended.py

```python
# In handlers/extended.py

from handlers.my_feature import (
    handle_my_action,
)

EXTENDED_HANDLERS = {
    # ... existing handlers ...
    
    # My Feature
    "my_action": handle_my_action,
}
```

#### 3. Add to Category Documentation

```python
# In handlers/extended.py

def get_extended_actions_by_category() -> Dict[str, List[str]]:
    return {
        # ... existing categories ...
        
        "My Feature": [
            "my_action",
        ],
    }
```

#### 4. Create Test Event

Create `tests/test-my-action.json`:

```json
{
  "action": "my_action",
  "metaWabaId": "1347766229904230",
  "param1": "test_value"
}
```

#### 5. Update IAM Policy (if needed)

If your handler uses new AWS services, update `deploy/iam-policy-extended.json`.

---

## Best Practices

### 1. Handler Design

- Keep handlers focused on single responsibility
- Use `validate_required_fields()` for input validation
- Return consistent response format
- Include docstring with test event example
- Handle errors gracefully with try/except

### 2. DynamoDB

- Use consistent pk patterns
- Include `itemType` for filtering
- Add timestamps (`createdAt`, `updatedAt`)
- Use GSIs for common query patterns
- Avoid scans in production code

### 3. Error Handling

```python
try:
    # Business logic
except ClientError as e:
    logger.exception(f"Operation failed: {e}")
    return {"statusCode": 500, "error": str(e)}
```

### 4. Logging

```python
logger.info(f"Processing action={action} for waba={meta_waba_id}")
logger.warning(f"Unexpected state: {state}")
logger.exception(f"Failed to process: {e}")
```

### 5. Response Format

```python
# Success
return {
    "statusCode": 200,
    "operation": "action_name",
    "data": result,
    "message": "Optional success message"
}

# Error
return {
    "statusCode": 400,  # or 404, 500
    "error": "Clear error message"
}
```

### 6. Testing

- Create test events in `tests/` folder
- Test with Lambda console or CLI
- Verify DynamoDB items created correctly
- Check CloudWatch logs for errors

---

## File Structure

```
├── app.py                      # Main Lambda handler (core handlers)
├── handlers/
│   ├── __init__.py             # Package exports
│   ├── base.py                 # Shared utilities and clients
│   ├── registry.py             # Handler registration system
│   ├── extended.py             # Extended handler dispatcher
│   ├── business_profile.py     # Business profile handlers
│   ├── marketing.py            # Marketing handlers
│   ├── webhooks.py             # Webhook handlers
│   ├── calling.py              # Calling handlers
│   ├── groups.py               # Group handlers
│   ├── analytics.py            # Analytics handlers
│   ├── catalogs.py             # Catalog handlers
│   ├── payments.py             # Payment handlers
│   └── media_eum.py            # AWS EUM media handlers
├── deploy/
│   ├── deploy-lambda.ps1       # Deploy Lambda code
│   ├── deploy-extended.ps1     # Deploy with extended handlers
│   ├── setup-dynamodb.ps1      # Create DynamoDB table
│   ├── setup-dynamodb-extended.ps1  # Extended DynamoDB setup
│   ├── create-gsis.ps1         # Create GSIs
│   ├── iam-policy.json         # Core IAM permissions
│   ├── iam-policy-extended.json # Extended IAM permissions
│   └── env-vars.json           # Environment variables
├── tests/
│   └── test-*.json             # Test events
└── docs/
    ├── README.md               # User documentation
    ├── spec.md                 # API specification
    ├── ARCHITECTURE.md         # Architecture overview
    └── PATTERNS.md             # This file
```

---

## Upgrade Checklist

When adding new features:

- [ ] Create handler function with proper signature
- [ ] Add to EXTENDED_HANDLERS in extended.py
- [ ] Add to get_extended_actions_by_category()
- [ ] Create DynamoDB item type if needed
- [ ] Add GSI if query pattern requires it
- [ ] Update IAM policy if new AWS services used
- [ ] Create test event in tests/ folder
- [ ] Test locally and in Lambda console
- [ ] Update documentation

---

## All in all, we have integrated the AWS EUM Social documentation recommendations in our design for robust media handling.
