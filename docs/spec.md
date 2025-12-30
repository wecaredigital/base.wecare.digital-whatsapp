# WhatsApp Business API - Technical Specification

## Reference Documentation Links

### 1) Meta — Access Tokens + Business Profiles

- https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens
- https://developers.facebook.com/documentation/business-messaging/whatsapp/business-profiles
- https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/business-profiles

### 2) Meta — Marketing + Templates

- https://developers.facebook.com/documentation/business-messaging/whatsapp/marketing-messages/overview
- https://developers.facebook.com/documentation/business-messaging/whatsapp/marketing-messages/send-marketing-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/utility-templates/utility-templates
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/authentication-templates/authentication-templates
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/marketing-templates
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-management
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-library
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/portfolio-pacing
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-pacing
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/time-to-live
- https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/tap-target-url-title-override

### 3) Meta — Send Messages + Types + Throughput

- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-list-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-cta-url-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-media-carousel-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-product-carousel-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-reply-buttons-messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/throughput

### 4) Meta — Webhooks (ALL)

#### Overview & Setup
- https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview
- https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint

#### Webhook Reference - Messages
- https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages

#### Webhook Event Types
- **Account Events**
  - account_update
  - account_review_update
  - phone_number_name_update
  - phone_number_quality_update
  - template_category_update

- **Message Events**
  - text
  - audio
  - button
  - contacts
  - document
  - errors
  - image
  - interactive
  - location
  - order
  - reaction
  - sticker
  - system
  - unsupported
  - video

- **Status Events**
  - sent
  - delivered
  - read
  - failed

### 5) Meta — Calling / Groups / Analytics / CTWA / Catalogs / Payments (India)

#### Calling
- https://developers.facebook.com/documentation/business-messaging/whatsapp/calling

#### Groups
- https://developers.facebook.com/documentation/business-messaging/whatsapp/groups

#### Analytics
- https://developers.facebook.com/documentation/business-messaging/whatsapp/analytics

#### Click-to-WhatsApp (CTWA)
- https://developers.facebook.com/documentation/business-messaging/whatsapp/ctwa/welcome-message-sequences

#### Catalogs
- https://developers.facebook.com/documentation/business-messaging/whatsapp/catalogs/sell-products-and-services

#### Payments (India)
- https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/overview
- https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/onboarding-apis
- https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/pg
- https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/checkout-button-templates/

### 6) AWS — EUM Social Event Destinations + Media

#### Event Destinations
- https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations.html
- https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations-add.html

#### Media Handling
- https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-media-files-s3.html
- https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_GetWhatsAppMessageMedia.html
- https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/get-whatsapp-message-media.html
- https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/post-whatsapp-message-media.html

#### Quotas & Limits
- https://docs.aws.amazon.com/social-messaging/latest/userguide/quotas.html

---

## Implementation Status

### BLOCK 1 — Business Profiles ✅
- [x] `get_business_profile` - Fetch profile details
- [x] `update_business_profile` - Update profile with payload
- [x] `upload_profile_picture` - Avatar/image upload → S3 → WhatsApp

### BLOCK 2 — Marketing Messages & Templates ✅
- [x] `create_marketing_template` - Create template definitions
- [x] `send_marketing_message` - Send marketing messages
- [x] `send_utility_template` - Utility templates
- [x] `send_auth_template` - Authentication templates (OTP)
- [x] `send_catalog_template` - Catalog templates
- [x] `send_coupon_template` - Coupon code templates
- [x] `send_limited_offer_template` - Limited-time offers
- [x] `send_carousel_template` - Media/product card carousel
- [x] `send_mpm_template` - Multi-Product Message templates
- [x] `get_template_analytics` - Template performance
- [x] `get_template_pacing` - Pacing information
- [x] `set_template_ttl` - Template TTL configuration

### BLOCK 3 — Message Types ✅
- [x] Text messages
- [x] Image messages
- [x] Video messages
- [x] Audio messages
- [x] Document messages
- [x] Sticker messages
- [x] Location messages
- [x] Contact messages
- [x] Interactive (buttons, lists)
- [x] CTA URL buttons
- [x] Reply buttons
- [x] Product messages (SPM/MPM)
- [x] Carousel messages
- [x] Address collection
- [x] Location request
- [x] WhatsApp Flows

### BLOCK 4 — Webhooks ✅
- [x] `register_webhook` - Register webhook endpoint
- [x] `process_webhook_event` - Process all webhook types
- [x] `get_webhook_events` - Query webhook history
- [x] `process_wix_webhook` - Wix e-commerce integration
- [x] `get_wix_orders` - Get Wix orders

### BLOCK 5 — Calling ✅
- [x] `initiate_call` - Business-initiated calls
- [x] `update_call_status` - Update call status
- [x] `get_call_logs` - Call history
- [x] `update_call_settings` - Call configuration
- [x] `get_call_settings` - Get call settings
- [x] `create_call_deeplink` - Deep link buttons

### BLOCK 6 — Groups ✅
- [x] `create_group` - Create group
- [x] `add_group_participant` - Add participant
- [x] `remove_group_participant` - Remove participant
- [x] `get_group_info` - Group details
- [x] `get_groups` - List groups
- [x] `send_group_message` - Send to group
- [x] `get_group_messages` - Group message history

### BLOCK 7 — Analytics ✅
- [x] `get_analytics` - Comprehensive analytics
- [x] `get_ctwa_metrics` - CTWA metrics
- [x] `get_funnel_insights` - Delivery funnel
- [x] `track_ctwa_click` - Track CTWA clicks
- [x] `setup_welcome_sequence` - CTWA welcome sequences

### BLOCK 8 — Catalogs ✅
- [x] `upload_catalog` - Upload product catalog
- [x] `get_catalog_products` - Get products
- [x] `send_catalog_message` - Send SPM/MPM

### BLOCK 9 — Payments ✅
- [x] `payment_onboarding` - Onboard payment gateway
- [x] `create_payment_request` - Create payment request
- [x] `get_payment_status` - Get payment status
- [x] `update_payment_status` - Update from webhook
- [x] `send_payment_confirmation` - Send confirmation
- [x] `get_payments` - List payments

### BLOCK 10 — AWS EUM Social Media ✅
- [x] `eum_download_media` - Download via GetWhatsAppMessageMedia
- [x] `eum_upload_media` - Upload via PostWhatsAppMessageMedia
- [x] `eum_validate_media` - Validate against requirements
- [x] `eum_get_supported_formats` - Get supported formats
- [x] `eum_setup_s3_lifecycle` - S3 lifecycle rules
- [x] `eum_get_media_stats` - Media statistics

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WhatsApp Business API (Meta)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AWS Social Messaging Service (EUM)                      │
│                    (Manages WhatsApp Business Accounts)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
                 ▼                                         ▼
     ┌───────────────────┐                     ┌───────────────────┐
     │    SNS Topic      │                     │   API Gateway     │
     │ (Inbound Events)  │                     │   (HTTP API)      │
     └───────────────────┘                     └───────────────────┘
                 │                                         │
                 └────────────────┬────────────────────────┘
                                  │
                                  ▼
     ┌─────────────────────────────────────────────────────────────────────┐
     │                        Lambda Function                               │
     │                                                                      │
     │  ┌─────────────────────────────────────────────────────────────┐   │
     │  │                      app.py (Main)                          │   │
     │  │  + handlers/                                                 │   │
     │  │    ├── business_profile.py                                  │   │
     │  │    ├── marketing.py                                         │   │
     │  │    ├── webhooks.py                                          │   │
     │  │    ├── calling.py                                           │   │
     │  │    ├── groups.py                                            │   │
     │  │    ├── analytics.py                                         │   │
     │  │    ├── catalogs.py                                          │   │
     │  │    ├── payments.py                                          │   │
     │  │    └── media_eum.py                                         │   │
     │  └─────────────────────────────────────────────────────────────┘   │
     └─────────────────────────────────────────────────────────────────────┘
                 │                   │                    │
                 ▼                   ▼                    ▼
     ┌───────────────┐   ┌───────────────────┐   ┌───────────────┐
     │   DynamoDB    │   │        S3         │   │      SNS      │
     │   (Storage)   │   │   (Media Files)   │   │  (Notifications)│
     └───────────────┘   └───────────────────┘   └───────────────┘
```

---

## DynamoDB Item Types

| itemType | PK Pattern | Description |
|----------|------------|-------------|
| MESSAGE | MSG#{waMessageId} | WhatsApp messages |
| CONVERSATION | CONV#{phoneId}#{from} | Conversation summaries |
| MESSAGE_STATUS | MSG#{waMessageId} | Delivery status only |
| BUSINESS_PROFILE | PROFILE#{wabaMetaId} | Business profiles |
| TEMPLATE_DEFINITION | TEMPLATE#{wabaMetaId}#{name}#{lang} | Template definitions |
| MARKETING_MESSAGE | MSG#MARKETING#{messageId} | Marketing messages |
| AUTH_MESSAGE | MSG#AUTH#{messageId} | Authentication messages |
| WEBHOOK_CONFIG | WEBHOOK#{wabaMetaId} | Webhook configuration |
| WEBHOOK_EVENT | WEBHOOK_EVENT#{wabaMetaId}#{timestamp}#{type} | Webhook events |
| WIX_ORDER | WIX_ORDER#{orderId} | Wix e-commerce orders |
| CALL | CALL#{callId} | Call records |
| CALL_SETTINGS | CALL_SETTINGS#{wabaMetaId} | Call settings |
| GROUP | GROUP#{groupId} | WhatsApp groups |
| GROUP_PARTICIPANT | GROUP_PARTICIPANT#{groupId}#{phone} | Group participants |
| GROUP_MESSAGE | GROUP_MSG#{groupId}#{timestamp} | Group messages |
| CTWA_EVENT | CTWA_EVENT#{wabaMetaId}#{timestamp} | CTWA click events |
| WELCOME_SEQUENCE | WELCOME_SEQUENCE#{wabaMetaId}#{name} | Welcome sequences |
| ANALYTICS_SNAPSHOT | ANALYTICS#{wabaMetaId}#{timestamp} | Analytics snapshots |
| CATALOG | CATALOG#{wabaMetaId}#{catalogId} | Product catalogs |
| PRODUCT | PRODUCT#{catalogId}#{retailerId} | Catalog products |
| PAYMENT_CONFIG | PAYMENT_CONFIG#{wabaMetaId}#{provider} | Payment gateway config |
| PAYMENT | PAYMENT#{paymentId} | Payment records |
| MEDIA_UPLOAD | MEDIA_UPLOAD#{mediaId} | Media upload records |
| MEDIA_DOWNLOAD | MEDIA_DOWNLOAD#{mediaId} | Media download records |
| S3_LIFECYCLE_CONFIG | S3_LIFECYCLE#{bucket} | S3 lifecycle config |

---

## Final Statement

All in all, we have integrated the AWS EUM Social documentation recommendations in our design for robust media handling.

---

*Last updated: December 30, 2024*
