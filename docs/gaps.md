# AWS EUM Social - Feature Gaps & Workarounds

**Last Updated:** 2026-01-01

This document lists WhatsApp Business API features that are NOT available via AWS End User Messaging Social today, along with implemented workarounds.

> **Policy:** If any feature is impossible with AWS EUM today, implement a "capability-stub + runbook/manual-flow".
> **Region:** ap-south-1 (Mumbai) is primary for all services.

---

## Summary Table

| Feature | AWS EUM Support | Workaround |
|---------|-----------------|------------|
| Business Profile GET/UPDATE | ❌ Not supported | Local DynamoDB + manual apply |
| Template Analytics (detailed) | ❌ Not supported | Local tracking via webhooks |
| Phone Quality History | ❌ Not supported | Local snapshots |
| Conversation Analytics | ❌ Not supported | Local estimation |
| Catalog Management | ❌ Not supported | Local DynamoDB |
| Flow Builder | ❌ Not supported | Manual creation + local tracking |
| Group Management | ❌ Not supported | Local metadata |
| Calling Features | ❌ Not supported | Deep links only |
| Templates CRUD | ✅ Supported | AWS EUM APIs |
| Media Upload/Download | ✅ Supported | AWS EUM APIs |
| Send Messages | ✅ Supported | AWS EUM APIs |
| Event Destinations | ✅ Supported | SNS/EventBridge |

---

## 1. Business Profile GET/UPDATE

### Gap
AWS EUM Social API does **not** provide operations to:
- Get business profile details
- Update business profile (about, description, address, etc.)
- Upload/update profile picture

### Workaround Implemented
We store business profile data locally in DynamoDB and provide manual apply instructions.

**Handlers:**
- `get_business_profile` - Returns locally stored profile
- `update_business_profile` - Updates local DynamoDB record (with version history)
- `upload_business_profile_avatar` - Uploads to S3, optionally to WhatsApp media store
- `get_business_profile_apply_instructions` - Returns AWS Console URL + checklist
- `mark_business_profile_applied` - Acknowledges manual application

**DynamoDB Schema:**
```
PK: TENANT#{tenantId}
SK: BIZPROFILE#{phoneNumberId}
Fields: about, address, description, email, websites[], vertical, 
        profile_picture_s3_key, appliedState, appliedAt, versionHistory[]
```

**Upgrade Hook:**
```python
# handlers/business_profile.py
class AwsEumProvider:
    @staticmethod
    def update_business_profile(phone_arn, profile_data):
        """STUB: Returns NotSupportedYet until AWS adds this API."""
        return {"success": False, "error": "NotSupported"}
```

**Manual Flow:**
1. Update profile via API (stored in DynamoDB)
2. Call `get_business_profile_apply_instructions`
3. Follow instructions to apply in AWS Console / Meta Business Suite
4. Call `mark_business_profile_applied` to acknowledge

---

## 2. Template Analytics (Detailed)

### Gap
AWS EUM does not expose detailed template analytics like:
- Click-through rates
- Conversion metrics
- A/B test results

### Workaround
- Track template sends in DynamoDB
- Track delivery/read status via webhooks
- Calculate basic metrics locally

**Handlers:**
- `get_template_analytics` - Returns locally computed metrics

---

## 3. Phone Number Quality Score History

### Gap
AWS EUM provides current quality rating but not historical data.

### Workaround
- Store quality snapshots on each check
- Query history from DynamoDB

**Handlers:**
- `get_quality` - Fetches current + stores snapshot
- Query GSI for historical data

---

## 4. Conversation Analytics

### Gap
AWS EUM does not provide conversation-level analytics (cost, category breakdown).

### Workaround
- Track conversations locally
- Estimate costs based on message types

---

## 5. Catalog Management

### Gap
AWS EUM does not provide catalog CRUD operations.

### Workaround
- Store catalog data in DynamoDB
- Reference in product messages

**Handlers:**
- `upload_catalog` - Stores in DynamoDB
- `get_catalog_products` - Queries local data
- `send_catalog_message` - Sends product list

---

## 6. Flow Builder

### Gap
AWS EUM does not provide Flow Builder API access.

### Workaround
- Store flow definitions in DynamoDB
- Handle flow responses via webhooks
- Manual flow creation in Meta Business Suite

**Handlers:**
- `send_flow_message` - Sends flow reference
- `flow_data_exchange` - Handles flow callbacks
- `get_flow_responses` - Queries stored responses

---

## 7. Group Management

### Gap
AWS EUM does not provide WhatsApp Group APIs.

### Workaround
- Store group metadata locally
- Track group messages via webhooks

**Handlers:**
- `create_group`, `get_groups` - Local storage only
- `send_group_message` - Sends to group (if supported)

---

## 8. Calling Features

### Gap
AWS EUM does not provide WhatsApp Calling APIs.

### Workaround
- Store call settings locally
- Generate deep links for calls

**Handlers:**
- `create_call_deeplink` - Generates wa.me link
- `get_call_settings` - Local config

---

## Capability Flags

All gaps are tracked via capability flags in the codebase:

```python
CAPABILITIES = {
    "business_profile_get": False,      # AWS EUM not supported
    "business_profile_update": False,   # AWS EUM not supported
    "template_analytics_detailed": False,
    "conversation_analytics": False,
    "catalog_crud": False,              # Local only
    "flow_builder": False,              # Local only
    "group_management": False,          # Local only
    "calling": False,                   # Deep links only
    
    # Supported via AWS EUM
    "templates_crud": True,
    "media_upload_download": True,
    "send_messages": True,
    "webhooks_events": True,
    "event_destinations": True,
}
```

---

## Future AWS EUM Updates

When AWS adds new capabilities:
1. Update capability flag to `True`
2. Implement real API call in provider layer
3. Keep local storage as cache/backup
4. Update this document

---

## Manual Runbooks

### Apply Business Profile Changes
1. Go to AWS Console → End User Messaging → Social
2. Select your WABA
3. Navigate to Business Profile section
4. Update fields manually
5. Save changes
6. Call `mark_business_profile_applied` API

### Create WhatsApp Flow
1. Go to Meta Business Suite
2. Navigate to WhatsApp Manager → Flows
3. Create flow using Flow Builder
4. Note the Flow ID
5. Store in DynamoDB via `create_flow` handler
6. Use `send_flow_message` to trigger

### Link New Phone Number
1. Go to AWS Console → End User Messaging → Social
2. Click "Link WhatsApp Business Account"
3. Follow OAuth flow
4. Update `WABA_PHONE_MAP_JSON` environment variable
5. Redeploy Lambda
