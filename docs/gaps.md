# AWS EUM Social Feature Gaps & Workarounds

This document lists features that are impossible or limited via AWS End User Messaging Social today, along with capability stubs and manual workarounds.

---

## Current Gaps

### 1. Template Creation/Management via API
**Status:** Partial Support  
**Issue:** AWS EUM Social supports `CreateWhatsAppMessageTemplate` but some advanced template features may require Meta Business Manager.

**Workaround:**
- Use AWS EUM API for basic template creation
- For complex templates (carousel, multi-product), create via Meta Business Manager
- Templates sync automatically to AWS EUM once approved

**Runbook:**
1. Log into Meta Business Manager
2. Navigate to WhatsApp Manager → Message Templates
3. Create template with required components
4. Wait for approval (typically 24-48 hours)
5. Template will be available via `ListWhatsAppMessageTemplates` API

---

### 2. Catalog/Product Management
**Status:** Not Supported via AWS EUM  
**Issue:** Product catalog management requires Meta Commerce Manager.

**Workaround:**
- Manage catalogs via Meta Commerce Manager
- Use catalog IDs in messages via AWS EUM

**Runbook:**
1. Set up catalog in Meta Commerce Manager
2. Link catalog to WhatsApp Business Account
3. Use `send_product_message` action with catalog_id and product_retailer_id

---

### 3. WhatsApp Flows (Advanced)
**Status:** Limited Support  
**Issue:** Flow creation/management requires Meta Business Manager.

**Workaround:**
- Create flows in Meta Business Manager
- Trigger flows via AWS EUM using flow_id

**Runbook:**
1. Create flow in Meta Business Manager → WhatsApp Flows
2. Publish flow and note the flow_id
3. Use `send_flow` action with flow_id

---

### 4. Business Profile Updates
**Status:** Not Supported via AWS EUM  
**Issue:** Business profile (about, address, description, email, websites) must be managed via Meta Business Manager.

**Workaround:**
- Update profile in Meta Business Manager
- Read-only access may be available via AWS EUM

**Runbook:**
1. Log into Meta Business Manager
2. Navigate to WhatsApp Manager → Phone Numbers → Profile
3. Update business information
4. Changes reflect immediately

---

### 5. Quality Rating Notifications
**Status:** Webhook Only  
**Issue:** Quality rating changes come via webhooks but cannot be queried on-demand.

**Workaround:**
- Store quality rating updates from webhooks in DynamoDB
- Query stored ratings for historical data

**Implementation:**
- Webhook handler stores quality updates with timestamp
- `get_quality_history` action retrieves stored ratings

---

### 6. Conversation Analytics (Detailed)
**Status:** Limited  
**Issue:** Detailed conversation analytics require Meta Business Manager.

**Workaround:**
- Track conversations locally in DynamoDB
- Use stored message data for analytics

**Implementation:**
- All messages stored with metadata
- `get_analytics` action computes metrics from stored data

---

### 7. Payment Status Webhooks
**Status:** Webhook Processing Only  
**Issue:** Payment webhooks from Meta are processed but payment initiation requires Meta Pay setup.

**Workaround:**
- Use Razorpay/UPI for payment links
- Process payment confirmations via webhooks

**Runbook:**
1. Configure payment provider (Razorpay/UPI)
2. Generate payment links via `create_payment_request`
3. Process payment webhooks for status updates

---

## Capability Stubs

The following actions are implemented as stubs that return guidance:

| Action | Status | Notes |
|--------|--------|-------|
| `manage_catalog` | Stub | Returns Meta Business Manager instructions |
| `update_business_profile` | Stub | Returns Meta Business Manager instructions |
| `create_flow` | Stub | Returns Meta Business Manager instructions |
| `get_conversation_analytics` | Partial | Returns locally computed metrics |

---

## Future AWS EUM Enhancements (Requested)

1. Full catalog management API
2. Business profile update API
3. Flow creation/management API
4. On-demand quality rating query
5. Detailed analytics API

---

## Last Updated
2026-01-01
