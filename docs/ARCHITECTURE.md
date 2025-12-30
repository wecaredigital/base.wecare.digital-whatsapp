# WhatsApp Business API Lambda Architecture

## Overview

This document describes the architecture patterns used in the WhatsApp Business API Lambda function for future upgrades and maintenance.

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Meta/WhatsApp │────▶│   AWS SNS       │────▶│   Lambda        │
│   Webhooks      │     │   Topic         │     │   Function      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   API Gateway   │────▶│   Lambda        │◀─────────────┘
│   HTTP API      │     │   (same)        │
└─────────────────┘     └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌───────────┐   ┌───────────┐   ┌───────────┐
        │ DynamoDB  │   │    S3     │   │ AWS EUM   │
        │  Table    │   │  Bucket   │   │  Social   │
        └───────────┘   └───────────┘   └───────────┘
```

## Entry Points

### 1. SNS Webhook Events (Inbound Messages)
- Source: Meta WhatsApp webhooks → SNS Topic → Lambda
- Event structure: `{"Records": [{"Sns": {"Message": "..."}}]}`
- Processing: Iterates through records, processes webhook entries

### 2. API Gateway Direct Invocation (Admin Actions)
- Source: HTTP API → Lambda
- Event structure: `{"action": "xxx", "param1": "value1", ...}`
- Processing: Dispatches to appropriate handler based on `action` field

### 3. Direct Lambda Invocation (Internal/Testing)
- Source: AWS SDK, CLI, or Console
- Event structure: `{"action": "xxx", ...}`
- Processing: Same as API Gateway

## Handler Architecture

### Unified Handler System

The codebase uses a unified handler architecture:

```
app.py (lambda_handler)
    │
    ├── Core handlers (defined in app.py)
    │   └── send_text, send_image, get_messages, etc.
    │
    └── Extended handlers (via dispatch_extended_handler)
        └── handlers/extended.py
            ├── handlers/business_profile.py
            ├── handlers/marketing.py
            ├── handlers/webhooks.py
            ├── handlers/calling.py
            ├── handlers/groups.py
            ├── handlers/analytics.py
            ├── handlers/catalogs.py
            ├── handlers/payments.py
            └── handlers/media_eum.py
```

### Handler Function Signature
```python
def handle_<action_name>(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Description of what this handler does.
    
    Test Event:
    {
        "action": "<action_name>",
        "param1": "value1"
    }
    """
    # 1. Extract and validate parameters
    param1 = event.get("param1", "")
    error = validate_required_fields(event, ["param1"])
    if error:
        return error
    
    # 2. Business logic
    try:
        result = some_operation()
    except ClientError as e:
        return {"statusCode": 500, "error": str(e)}
    
    # 3. Return response
    return {
        "statusCode": 200,
        "operation": "<action_name>",
        "data": result
    }
```

### Adding a New Extended Handler

1. **Create handler function** in appropriate module (e.g., `handlers/my_feature.py`):
```python
from handlers.base import (
    validate_required_fields, store_item, get_phone_arn, iso_now
)

def handle_my_action(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """My action description."""
    # Implementation
    return {"statusCode": 200, "operation": "my_action", ...}
```

2. **Import and register** in `handlers/extended.py`:
```python
from handlers.my_feature import handle_my_action

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
        "My Feature": ["my_action"],
    }
```

## Dispatcher Pattern

Location: Inside `lambda_handler()` function in `app.py`

```python
def lambda_handler(event, context):
    # ... setup code ...
    
    action = event.get("action", "")
    
    def maybe_wrap(response):
        if is_api_gateway:
            return api_response(response)
        return response
    
    # Core handlers dispatcher chain
    if action == "help":
        return maybe_wrap(handle_help(event, context))
    elif action == "send_text":
        return maybe_wrap(handle_send_text(event, context))
    # ... more core handlers ...
    
    # Extended handlers - unified dispatcher
    else:
        result = dispatch_extended_handler(action, event, context)
        if result is not None:
            return maybe_wrap(result)
    
    # SNS webhook processing (no action specified)
    processed = 0
    # ... process SNS records ...
```

## DynamoDB Schema

### Table: `base-wecare-digital-whatsapp`
- Primary Key: `pk` (String)

### Item Types (itemType field)

| itemType | pk Pattern | Description |
|----------|------------|-------------|
| MESSAGE | `MSG#{waMessageId}` | Individual messages |
| CONVERSATION | `CONV#{phoneArn}#{fromNumber}` | Conversation threads |
| TEMPLATE | `TEMPLATES#{wabaMetaId}` | Cached templates |
| QUALITY | `QUALITY#{wabaMetaId}` | Phone quality ratings |
| INFRA | `INFRA#CONFIG` | Infrastructure config |
| MEDIA_TYPES | `MEDIA_TYPES#CONFIG` | Supported media types |
| CAMPAIGN | `CAMPAIGN#{campaignId}` | Marketing campaigns |
| BUSINESS_PROFILE | `PROFILE#{wabaMetaId}` | Business profiles |
| WEBHOOK_CONFIG | `WEBHOOK#{wabaMetaId}` | Webhook configurations |
| CALL | `CALL#{callId}` | Call records |
| GROUP | `GROUP#{groupId}` | WhatsApp groups |
| CATALOG | `CATALOG#{wabaMetaId}#{catalogId}` | Product catalogs |
| PRODUCT | `PRODUCT#{catalogId}#{retailerId}` | Catalog products |
| PAYMENT | `PAYMENT#{paymentId}` | Payment records |
| PAYMENT_CONFIG | `PAYMENT_CONFIG#{wabaMetaId}#{provider}` | Payment gateway config |
| WIX_ORDER | `WIX_ORDER#{orderId}` | Wix e-commerce orders |
| MEDIA_UPLOAD | `MEDIA_UPLOAD#{mediaId}` | Uploaded media tracking |
| MEDIA_DOWNLOAD | `MEDIA_DOWNLOAD#{mediaId}` | Downloaded media tracking |

### Global Secondary Indexes (GSIs)

| GSI Name | Partition Key | Sort Key | Use Case |
|----------|---------------|----------|----------|
| gsi-inbox | inboxPk | receivedAt | List conversations by phone |
| gsi-conversation | conversationPk | receivedAt | Messages in conversation |
| gsi-direction | direction | receivedAt | Filter by INBOUND/OUTBOUND |
| gsi-from | from | receivedAt | Messages from specific number |
| gsi-itemType | itemType | createdAt | Query by item type |

## AWS Services Integration

### AWS Social Messaging (EUM)
```python
# Send message
social.send_whatsapp_message(
    originationPhoneNumberId=origination_id_for_api(phone_arn),
    metaApiVersion=META_API_VERSION,
    message=json.dumps(payload).encode("utf-8"),
)

# Download media to S3
social.get_whatsapp_message_media(
    mediaId=media_id,
    originationPhoneNumberId=origination_id_for_api(phone_arn),
    destinationS3File={"bucketName": MEDIA_BUCKET, "key": s3_key}
)

# Upload media from S3
social.post_whatsapp_message_media(
    originationPhoneNumberId=origination_id_for_api(phone_arn),
    sourceS3File={"bucketName": MEDIA_BUCKET, "key": s3_key}
)
```

### Phone ARN Format
```python
def origination_id_for_api(phone_arn: str) -> str:
    # Convert ARN to API format
    # arn:aws:social-messaging:region:account:phone-number-id/xxx
    # → phone-number-id-xxx
    if "phone-number-id/" in phone_arn:
        suffix = phone_arn.split("phone-number-id/")[-1]
        return f"phone-number-id-{suffix}"
    return phone_arn
```

### WhatsApp Number Format
```python
def format_wa_number(wa_id: str) -> str:
    # AWS Social Messaging requires + prefix
    if not wa_id.startswith("+"):
        return f"+{wa_id}"
    return wa_id
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| MESSAGES_TABLE_NAME | Yes | DynamoDB table name |
| MESSAGES_PK_NAME | Yes | Primary key attribute name |
| MEDIA_BUCKET | Yes | S3 bucket for media |
| MEDIA_PREFIX | No | S3 key prefix (default: WhatsApp/) |
| META_API_VERSION | No | Meta API version (default: v20.0) |
| WABA_PHONE_MAP_JSON | Yes | JSON mapping WABA IDs to phone ARNs |
| AUTO_REPLY_ENABLED | No | Enable auto-reply (default: false) |
| MARK_AS_READ_ENABLED | No | Mark messages as read (default: true) |
| REACT_EMOJI_ENABLED | No | React with emoji (default: true) |
| EMAIL_NOTIFICATION_ENABLED | No | Send email notifications (default: true) |
| EMAIL_SNS_TOPIC_ARN | No | SNS topic for email notifications |

## Response Format

### Success Response
```json
{
    "statusCode": 200,
    "operation": "action_name",
    "data": { ... }
}
```

### Error Response
```json
{
    "statusCode": 400|404|500,
    "error": "Error message"
}
```

### API Gateway Wrapped Response
```json
{
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": "{\"statusCode\": 200, ...}"
}
```

## Handler Categories

### Send Messages
- `send_text`, `send_image`, `send_video`, `send_audio`, `send_document`
- `send_media`, `send_sticker`, `send_location`, `send_contact`
- `send_interactive`, `send_reaction`, `send_reply`, `send_template`
- `send_flow`, `send_product`, `send_product_list`, `send_cta_url`
- `send_address_message`, `send_location_request`, `bulk_send`

### Message Actions
- `mark_read`, `remove_reaction`, `delete_message`
- `resend_message`, `retry_failed_messages`

### Conversation Actions
- `update_conversation`, `mark_conversation_read`
- `archive_conversation`, `unarchive_conversation`

### Media Management
- `upload_media`, `download_media`, `delete_media`
- `get_media_url`, `validate_media`, `get_supported_formats`

### Query Data
- `get_message`, `get_messages`, `get_conversation`, `get_conversations`
- `get_conversation_messages`, `get_archived_conversations`
- `get_failed_messages`, `search_messages`, `get_unread_count`
- `get_message_by_wa_id`, `get_delivery_status`

### Configuration
- `get_quality`, `get_stats`, `get_wabas`, `get_phone_info`
- `get_infra`, `get_media_types`, `get_config`
- `get_templates`, `refresh_templates`, `templates`

### Refresh/Sync
- `refresh_quality`, `refresh_infra`, `refresh_media_types`

### Campaigns
- `create_campaign`, `get_campaigns`, `get_campaign`, `get_campaign_stats`

### Utility
- `help`, `ping`, `list_actions`, `get_best_practices`

### Extended Handlers (via handlers/ module)

All extended handlers are managed through the unified dispatcher in `handlers/extended.py`:

| Category | Actions |
|----------|---------|
| Business Profile | get_business_profile, update_business_profile, upload_profile_picture |
| Marketing & Templates | create_marketing_template, send_marketing_message, send_utility_template, send_auth_template, send_catalog_template, send_coupon_template, send_limited_offer_template, send_carousel_template, send_mpm_template, get_template_analytics, get_template_pacing, set_template_ttl |
| Webhooks | register_webhook, process_wix_webhook, get_webhook_events, process_webhook_event, get_wix_orders |
| Calling | initiate_call, update_call_status, get_call_logs, update_call_settings, get_call_settings, create_call_deeplink |
| Groups | create_group, add_group_participant, remove_group_participant, get_group_info, get_groups, send_group_message, get_group_messages |
| Analytics | get_analytics, get_ctwa_metrics, get_funnel_insights, track_ctwa_click, setup_welcome_sequence |
| Catalogs | upload_catalog, get_catalog_products, send_catalog_message |
| Payments | payment_onboarding, create_payment_request, get_payment_status, update_payment_status, send_payment_confirmation, get_payments |
| AWS EUM Media | eum_download_media, eum_upload_media, eum_validate_media, eum_get_supported_formats, eum_setup_s3_lifecycle, eum_get_media_stats |

## Upgrade Checklist

When adding new features:

### For Extended Handlers (recommended for new features):
1. [ ] Create handler function in `handlers/<feature>.py`
2. [ ] Import handler in `handlers/extended.py`
3. [ ] Add to `EXTENDED_HANDLERS` dict in `handlers/extended.py`
4. [ ] Add to `get_extended_actions_by_category()` for documentation
5. [ ] Create DynamoDB item type if needed
6. [ ] Add GSI if query pattern requires it
7. [ ] Update IAM policy if new AWS services used
8. [ ] Create test event in `tests/` folder
9. [ ] Run `python tests/test_handlers_import.py` to verify
10. [ ] Update `docs/PATTERNS.md` documentation

### For Core Handlers (in app.py):
1. [ ] Define handler function before `lambda_handler`
2. [ ] Add dispatcher entry in `lambda_handler`
3. [ ] Add to `handle_help` actions dictionary
4. [ ] Add to `handle_list_actions` if categorized
5. [ ] Create test event in `tests/` folder
6. [ ] Update documentation

## File Structure

```
├── app.py                      # Main Lambda handler (core handlers)
├── handlers/
│   ├── __init__.py             # Package exports
│   ├── base.py                 # Shared utilities, clients, helpers
│   ├── registry.py             # Handler registration system
│   ├── extended.py             # Extended handler dispatcher
│   ├── business_profile.py     # Business profile handlers
│   ├── marketing.py            # Marketing & template handlers
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
│   ├── test_handlers_import.py # Handler import tests
│   └── test-*.json             # Test events
└── docs/
    ├── README.md               # User documentation
    ├── spec.md                 # API specification
    ├── ARCHITECTURE.md         # Architecture overview
    └── PATTERNS.md             # Detailed patterns guide
```

## All in all, we have integrated the AWS EUM Social documentation recommendations in our design for robust media handling.
