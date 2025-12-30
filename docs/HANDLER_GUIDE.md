# WhatsApp Business API - Handler Development Guide

## Overview

This guide explains how to work with the unified handler system for the WhatsApp Business API Lambda function.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        lambda_handler (app.py)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Parse event (API Gateway / SNS / Direct)                    │
│  2. Extract action from event                                    │
│  3. Core handlers (if-elif chain in app.py)                     │
│  4. unified_dispatch() → handlers/dispatcher.py                  │
│  5. SNS webhook processing (if no action)                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    handlers/dispatcher.py                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  unified_dispatch(action, event, context)                       │
│       │                                                          │
│       ├── Look up handler in _REGISTRY                          │
│       ├── Execute handler(event, context)                       │
│       └── Return response or None                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    handlers/extended.py                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  EXTENDED_HANDLERS = {                                          │
│      "get_business_profile": handle_get_business_profile,       │
│      "send_marketing_message": handle_send_marketing_message,   │
│      ...                                                         │
│  }                                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    handlers/<feature>.py                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  • handlers/business_profile.py                                 │
│  • handlers/marketing.py                                        │
│  • handlers/webhooks.py                                         │
│  • handlers/calling.py                                          │
│  • handlers/groups.py                                           │
│  • handlers/analytics.py                                        │
│  • handlers/catalogs.py                                         │
│  • handlers/payments.py                                         │
│  • handlers/media_eum.py                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Handler Categories

| Category | Description | Handler Count |
|----------|-------------|---------------|
| business_profile | Business profile management | 3 |
| marketing_templates | Marketing campaigns and templates | 12 |
| webhooks | Webhook configuration and processing | 5 |
| calling | WhatsApp calling features | 6 |
| groups | WhatsApp group management | 7 |
| analytics | Analytics and reporting | 5 |
| catalogs | Product catalog management | 3 |
| payments | Payment processing | 6 |
| aws_eum_media | AWS EUM media handling | 6 |

## Adding a New Handler

### Option 1: Add to Existing Feature Module (Recommended)

1. **Add handler function** to the appropriate module:

```python
# handlers/my_feature.py
from handlers.base import (
    validate_required_fields, store_item, get_phone_arn,
    iso_now, success_response, error_response
)
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()


def handle_my_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Brief description of what this handler does.
    
    Test Event:
    {
        "action": "my_action",
        "metaWabaId": "1347766229904230",
        "param1": "value1"
    }
    """
    # 1. Extract parameters
    meta_waba_id = event.get("metaWabaId", "")
    param1 = event.get("param1", "")
    
    # 2. Validate required fields
    error = validate_required_fields(event, ["metaWabaId", "param1"])
    if error:
        return error
    
    # 3. Get phone ARN
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    # 4. Business logic
    try:
        now = iso_now()
        result_pk = f"MY_ITEM#{now}"
        
        store_item({
            "pk": result_pk,
            "itemType": "MY_ITEM",
            "wabaMetaId": meta_waba_id,
            "param1": param1,
            "createdAt": now,
        })
        
        return success_response("my_action", resultPk=result_pk, success=True)
        
    except ClientError as e:
        logger.exception(f"Failed: {e}")
        return error_response(str(e), 500)
```

2. **Import and register** in `handlers/extended.py`:

```python
# Add import
from handlers.my_feature import handle_my_action

# Add to EXTENDED_HANDLERS dict
EXTENDED_HANDLERS = {
    # ... existing handlers ...
    "my_action": handle_my_action,
}
```

3. **Add to category** in `get_extended_actions_by_category()`:

```python
def get_extended_actions_by_category():
    return {
        # ... existing categories ...
        "My Feature": [
            "my_action",
        ],
    }
```

### Option 2: Create New Feature Module

1. **Create new module** `handlers/my_feature.py`

2. **Follow the handler pattern** (see Option 1)

3. **Import all handlers** in `handlers/extended.py`

4. **Add to EXTENDED_HANDLERS** and category mapping

### Option 3: Using the Decorator (Advanced)

```python
from handlers.dispatcher import register

@register("my_action", category="my_category", requires=["metaWabaId", "param1"])
def handle_my_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """My action description."""
    # Handler implementation
    return {"statusCode": 200, "operation": "my_action"}
```

## Handler Function Signature

```python
def handle_<action_name>(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Brief description (first line becomes the action description).
    
    Test Event:
    {
        "action": "<action_name>",
        "param1": "value1"
    }
    
    Returns:
        Success: {"statusCode": 200, "operation": "<action_name>", ...}
        Error: {"statusCode": 4xx|5xx, "error": "message"}
    """
```

## Response Format

### Success Response

```python
return {
    "statusCode": 200,
    "operation": "action_name",
    "data": result,
    "message": "Optional success message"
}

# Or use helper:
from handlers.base import success_response
return success_response("action_name", data=result, message="Success")
```

### Error Response

```python
return {
    "statusCode": 400,  # or 404, 500
    "error": "Clear error message"
}

# Or use helpers:
from handlers.base import error_response, not_found_response
return error_response("Invalid input", 400)
return not_found_response("Item", "123")
```

## Available Base Utilities

### AWS Clients (Lazy-loaded)

```python
from handlers.base import table, social, s3, sns

# DynamoDB
table().put_item(Item={...})
table().get_item(Key={...})

# WhatsApp Social Messaging
social().send_whatsapp_message(...)

# S3
s3().get_object(Bucket=..., Key=...)

# SNS
sns().publish(TopicArn=..., Message=...)
```

### DynamoDB Operations

```python
from handlers.base import store_item, get_item, update_item, query_items, delete_item

# Store
store_item({"pk": "...", "itemType": "...", ...})

# Get
item = get_item("pk_value")

# Update
update_item("pk_value", {"field1": "new_value"})

# Query
items = query_items(
    filter_expr="itemType = :it",
    expr_values={":it": "MY_TYPE"},
    limit=50
)

# Delete
delete_item("pk_value")
```

### Validation

```python
from handlers.base import validate_required_fields, validate_enum

# Required fields
error = validate_required_fields(event, ["field1", "field2"])
if error:
    return error

# Enum validation
error = validate_enum(value, ["option1", "option2"], "fieldName")
if error:
    return error
```

### WhatsApp Messaging

```python
from handlers.base import send_whatsapp_message, format_wa_number

# Send message
result = send_whatsapp_message(phone_arn, {
    "messaging_product": "whatsapp",
    "to": format_wa_number("+1234567890"),
    "type": "text",
    "text": {"body": "Hello!"}
})

if result["success"]:
    message_id = result["messageId"]
```

### Utilities

```python
from handlers.base import (
    iso_now,           # Current UTC timestamp
    jdump,             # JSON dump with defaults
    safe,              # Sanitize string for S3 keys
    format_wa_number,  # Add + prefix to phone
    origination_id_for_api,  # Convert ARN to API format
    arn_suffix,        # Extract suffix from ARN
    get_phone_arn,     # Get phone ARN for WABA
    get_waba_config,   # Get WABA configuration
    generate_s3_presigned_url,  # Generate presigned URL
)
```

## Testing

### Create Test Event

Create `tests/test-my-action.json`:

```json
{
  "action": "my_action",
  "metaWabaId": "1347766229904230",
  "param1": "test_value"
}
```

### Run Tests

```bash
# Run unified handler tests
python tests/test_unified_handlers.py

# Test specific handler
python -c "
import os
os.environ['MESSAGES_TABLE_NAME'] = 'test'
os.environ['MESSAGES_PK_NAME'] = 'pk'
os.environ['MEDIA_BUCKET'] = 'test'

from handlers import unified_dispatch
result = unified_dispatch('my_action', {'metaWabaId': '123', 'param1': 'test'}, None)
print(result)
"
```

## Upgrade Checklist

When adding new handlers:

- [ ] Create handler function with proper signature
- [ ] Add docstring with test event example
- [ ] Import in `handlers/extended.py`
- [ ] Add to `EXTENDED_HANDLERS` dict
- [ ] Add to `get_extended_actions_by_category()`
- [ ] Create DynamoDB item type if needed
- [ ] Update IAM policy if new AWS services used
- [ ] Create test event in `tests/` folder
- [ ] Run `python tests/test_unified_handlers.py`
- [ ] Update documentation

## File Structure

```
handlers/
├── __init__.py          # Package exports
├── dispatcher.py        # Unified dispatcher
├── base.py              # Shared utilities
├── extended.py          # Extended handler registry
├── registry.py          # Legacy registry
├── business_profile.py  # Business profile handlers
├── marketing.py         # Marketing handlers
├── webhooks.py          # Webhook handlers
├── calling.py           # Calling handlers
├── groups.py            # Group handlers
├── analytics.py         # Analytics handlers
├── catalogs.py          # Catalog handlers
├── payments.py          # Payment handlers
└── media_eum.py         # AWS EUM media handlers
```
