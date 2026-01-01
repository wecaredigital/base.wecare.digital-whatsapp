# Development Guide

**Last Updated:** 2026-01-01

## Handler Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            lambda_handler (app.py)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Parse event (API GW, SNS, SQS, EventBridge, direct, CLI)                │
│  2. Extract action                                                           │
│  3. Dispatch to unified_dispatch (handlers/dispatcher.py)                    │
│                                                                              │
│     ┌─────────────────────────────────────────────────────────────────────┐ │
│     │                    Unified Dispatcher (201+ handlers)               │ │
│     │                                                                     │ │
│     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │ │
│     │  │ messaging   │  │ payments    │  │ templates   │  │ bedrock   │ │ │
│     │  │ queries     │  │ webhooks    │  │ media_eum   │  │ welcome   │ │ │
│     │  │ config      │  │ analytics   │  │ flows       │  │ notify    │ │ │
│     │  │ groups      │  │ catalogs    │  │ carousels   │  │ retry     │ │ │
│     │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │ │
│     └─────────────────────────────────────────────────────────────────────┘ │
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
- `gsi_template_waba` - Template + WABA
- `gsi_campaign` - Campaigns
- `gsi_webhook_event` - Webhook events

## Deploy

```powershell
# Deploy Lambda (201+ handlers)
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
| Lambda (Main) | `base-wecare-digital-whatsapp` |
| Lambda (Email) | `base-wecare-digital-whatsapp-email-notifier` |
| Lambda (Bedrock) | `base-wecare-digital-whatsapp-bedrock-worker` |
| Lambda (Agent Core) | `base-wecare-digital-whatsapp-agent-core` |
| DynamoDB | `base-wecare-digital-whatsapp` (16 GSIs) |
| S3 | `dev.wecare.digital/WhatsApp/` |
| SNS | `base-wecare-digital` |
| SQS | 7 queues (webhooks, notify, bedrock, DLQs) |
| EventBridge | 5 rules |
| Bedrock Agent | `UFVSBWGCIU` |
| Knowledge Base | `NVF0OLULMG` |
| Region | `ap-south-1` |
