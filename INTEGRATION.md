# Integration Guide for Extended Handlers

## Quick Integration

Add this code to `app.py` after the imports section:

```python
# Import extended handlers
try:
    from handlers import dispatch_extended_handler, list_extended_actions, get_extended_actions_by_category
    EXTENDED_HANDLERS_AVAILABLE = True
except ImportError:
    EXTENDED_HANDLERS_AVAILABLE = False
    dispatch_extended_handler = None
```

Then add this code in the `lambda_handler` function, right after checking for the `action`:

```python
    # Check for extended handlers first
    if EXTENDED_HANDLERS_AVAILABLE and action:
        extended_result = dispatch_extended_handler(action, event, context)
        if extended_result is not None:
            return maybe_wrap(extended_result)
```

## Full List of New Actions (50+ handlers)

### Business Profile
- `get_business_profile` - Fetch profile details
- `update_business_profile` - Update profile with payload
- `upload_profile_picture` - Upload avatar to S3 → WhatsApp

### Marketing & Templates
- `create_marketing_template` - Create template definitions
- `send_marketing_message` - Send marketing messages
- `send_utility_template` - Utility templates (order updates)
- `send_auth_template` - Authentication templates (OTP)
- `send_catalog_template` - Catalog templates
- `send_coupon_template` - Coupon code templates
- `send_limited_offer_template` - Limited-time offers
- `send_carousel_template` - Media/product card carousel
- `send_mpm_template` - Multi-Product Message templates
- `get_template_analytics` - Template performance
- `get_template_pacing` - Pacing information
- `set_template_ttl` - Template TTL configuration

### Webhooks
- `register_webhook` - Register webhook endpoint
- `process_webhook_event` - Process all webhook types
- `get_webhook_events` - Query webhook history
- `process_wix_webhook` - Wix e-commerce integration
- `get_wix_orders` - Get Wix orders

### Calling
- `initiate_call` - Business-initiated calls
- `update_call_status` - Update call status
- `get_call_logs` - Call history
- `update_call_settings` - Call configuration
- `get_call_settings` - Get call settings
- `create_call_deeplink` - Deep link buttons

### Groups
- `create_group` - Create group
- `add_group_participant` - Add participant
- `remove_group_participant` - Remove participant
- `get_group_info` - Group details
- `get_groups` - List groups
- `send_group_message` - Send to group
- `get_group_messages` - Group message history

### Analytics
- `get_analytics` - Comprehensive analytics
- `get_ctwa_metrics` - CTWA metrics
- `get_funnel_insights` - Delivery funnel
- `track_ctwa_click` - Track CTWA clicks
- `setup_welcome_sequence` - CTWA welcome sequences

### Catalogs
- `upload_catalog` - Upload product catalog
- `get_catalog_products` - Get products
- `send_catalog_message` - Send SPM/MPM

### Payments
- `payment_onboarding` - Onboard payment gateway
- `create_payment_request` - Create payment request
- `get_payment_status` - Get payment status
- `update_payment_status` - Update from webhook
- `send_payment_confirmation` - Send confirmation
- `get_payments` - List payments

### AWS EUM Media
- `eum_download_media` - Download via GetWhatsAppMessageMedia
- `eum_upload_media` - Upload via PostWhatsAppMessageMedia
- `eum_validate_media` - Validate against requirements
- `eum_get_supported_formats` - Get supported formats
- `eum_setup_s3_lifecycle` - S3 lifecycle rules
- `eum_get_media_stats` - Media statistics

## DynamoDB Setup

Run the extended schema setup:

```powershell
cd deploy
.\setup-dynamodb-extended.ps1
```

This adds the following GSIs:
- `gsi_waba_itemtype` - Query by WABA ID + item type
- `gsi_customer_phone` - Query by customer phone
- `gsi_group` - Query group messages
- `gsi_catalog` - Query catalog products
- `gsi_order` - Query by order ID

## Adding New Handlers

To add a new handler:

1. Create handler function in appropriate module:
```python
# handlers/my_feature.py
def handle_my_action(event, context):
    """My action description."""
    # Implementation
    return {"statusCode": 200, "result": "success"}
```

2. Import in `handlers/extended.py`:
```python
from handlers.my_feature import handle_my_action
```

3. Add to `EXTENDED_HANDLERS` dict:
```python
EXTENDED_HANDLERS = {
    # ... existing handlers ...
    "my_action": handle_my_action,
}
```

4. The handler is now available via `{"action": "my_action", ...}`

## Testing

Test extended handlers:

```powershell
aws lambda invoke `
    --function-name base-wecare-digital-whatsapp:live `
    --payload (Get-Content tests/test-extended-handlers.json -Raw | ConvertTo-Json) `
    --cli-binary-format raw-in-base64-out `
    response.json

Get-Content response.json
```

## File Structure

```
handlers/
├── __init__.py          # Main exports
├── base.py              # Shared utilities
├── extended.py          # Handler registry & dispatch
├── registry.py          # Decorator-based registration (optional)
├── business_profile.py  # Business profile handlers
├── marketing.py         # Marketing & template handlers
├── webhooks.py          # Webhook handlers
├── calling.py           # Calling handlers
├── groups.py            # Group handlers
├── analytics.py         # Analytics handlers
├── catalogs.py          # Catalog handlers
├── payments.py          # Payment handlers
└── media_eum.py         # AWS EUM media handlers
```
