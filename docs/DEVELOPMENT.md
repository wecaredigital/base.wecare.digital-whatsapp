# Development Guide

## Handler Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            lambda_handler (app.py)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Parse event                                                              │
│  2. Extract action                                                           │
│  3. Dispatch to handler                                                      │
│                                                                              │
│     ┌─────────────────┐         ┌─────────────────────────────────────────┐ │
│     │  Core Handlers  │         │        Extended Handlers                │ │
│     │   (app.py)      │         │     (handlers/extended.py)              │ │
│     │                 │         │                                         │ │
│     │  send_text      │         │  ┌─────────────┐  ┌─────────────┐      │ │
│     │  send_image     │         │  │ messaging   │  │ payments    │      │ │
│     │  get_messages   │         │  │ queries     │  │ webhooks    │      │ │
│     │  ...            │         │  │ templates   │  │ analytics   │      │ │
│     └─────────────────┘         │  │ media_eum   │  │ groups      │      │ │
│                                 │  └─────────────┘  └─────────────┘      │ │
│                                 └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Adding a Handler

### 1. Create handler function

```python
# handlers/my_feature.py
from handlers.base import validate_required_fields, success_response, error_response

def handle_my_action(event, context):
    """My action description."""
    error = validate_required_fields(event, ["metaWabaId", "param1"])
    if error:
        return error
    
    # Business logic
    return success_response("my_action", data={"result": "ok"})
```

### 2. Register in extended.py

```python
# handlers/extended.py
from handlers.my_feature import handle_my_action

EXTENDED_HANDLERS = {
    ...
    "my_action": handle_my_action,
}
```

### 3. Add to category

```python
def get_extended_actions_by_category():
    return {
        ...
        "My Feature": ["my_action"],
    }
```

## DynamoDB Schema

**Table:** `base-wecare-digital-whatsapp`
**Primary Key:** `pk` (String)

| Item Type | PK Pattern |
|-----------|------------|
| MESSAGE | `MSG#{waMessageId}` |
| CONVERSATION | `CONV#{phoneId}#{from}` |
| TEMPLATE | `TEMPLATE#{wabaId}#{name}` |
| PAYMENT | `PAYMENT#{paymentId}` |
| WEBHOOK_CONFIG | `WEBHOOK#{wabaId}` |

**GSIs (16):**
- `gsi_conversation` - Messages by conversation
- `gsi_from` - Messages by sender
- `gsi_inbox` - Messages by phone
- `gsi_direction` - INBOUND/OUTBOUND
- `gsi_status` - By delivery status
- `gsi_waba_itemtype` - By WABA + type
- `gsi_customer_phone` - By customer
- `gsi_group` - Group messages
- `gsi_catalog` - Catalog products
- `gsi_order` - By order ID
- `gsi_tenant` - Multi-tenant
- `gsi_payment_status` - Payment status
- `gsi_template_name` - Templates
- `gsi_campaign` - Campaigns
- `gsi_webhook_event` - Webhook events

## Deploy

```powershell
# Deploy Lambda
.\deploy\deploy-167-handlers.ps1

# Setup DynamoDB
.\deploy\setup-dynamodb-complete.ps1

# Create GSIs
.\deploy\create-all-gsis.ps1
```

## Test

```bash
python -m pytest tests/ -v
```

## Infrastructure

| Resource | Name |
|----------|------|
| Lambda | `base-wecare-digital-whatsapp` |
| DynamoDB | `base-wecare-digital-whatsapp` |
| S3 | `dev.wecare.digital/WhatsApp/` |
| SNS | `base-wecare-digital` |
| SQS | `base-wecare-digital-whatsapp-webhooks` |
| EventBridge | `base-wecare-digital-whatsapp` |
| Region | `ap-south-1` |
