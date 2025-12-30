# WhatsApp Business API - AWS Integration

A serverless WhatsApp Business API integration using AWS Social Messaging, Lambda, API Gateway, DynamoDB, S3, and SNS.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              WhatsApp Business API                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         AWS Social Messaging Service                                 │
│                    (Manages WhatsApp Business Accounts)                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
                    ▼                                         ▼
        ┌───────────────────┐                     ┌───────────────────┐
        │    SNS Topic      │                     │   API Gateway     │
        │ base-wecare-      │                     │   HTTP API        │
        │ digital           │                     │ (External Access) │
        └───────────────────┘                     └───────────────────┘
                    │                                         │
                    │  ┌──────────────────────────────────────┘
                    │  │
                    ▼  ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                      Lambda Function                           │
        │              base-wecare-digital-whatsapp:live                 │
        │                                                                │
        │  ┌─────────────────────────────────────────────────────────┐  │
        │  │                    app.py                                │  │
        │  │                                                          │  │
        │  │  • Inbound Message Processing                           │  │
        │  │  • Outbound Message Sending (text, image, video, etc.)  │  │
        │  │  • Media Upload/Download                                │  │
        │  │  • Template Management                                  │  │
        │  │  • Conversation Tracking                                │  │
        │  │  • Auto-reply, Reactions, Read Receipts                 │  │
        │  │  • Email Notifications                                  │  │
        │  └─────────────────────────────────────────────────────────┘  │
        └───────────────────────────────────────────────────────────────┘
                    │                   │                    │
                    ▼                   ▼                    ▼
        ┌───────────────┐   ┌───────────────────┐   ┌───────────────┐
        │   DynamoDB    │   │        S3         │   │      SNS      │
        │   Messages    │   │   Media Storage   │   │    Email      │
        │   Table       │   │   dev.wecare.     │   │  Notifications│
        └───────────────┘   │   digital         │   └───────────────┘
                            └───────────────────┘
```

## Message Flow

### Inbound Messages (Customer → Business)

```
Customer WhatsApp → Meta → AWS Social Messaging → SNS → Lambda → DynamoDB
                                                              ↓
                                                         S3 (media)
                                                              ↓
                                                    Email Notification
```

### Outbound Messages (Business → Customer)

```
Lambda Invoke/API Gateway → Lambda → AWS Social Messaging → Meta → Customer WhatsApp
         ↓
    DynamoDB (store)
         ↓
    S3 (media upload)
```

## AWS Resources

| Resource | Name/ID | Description |
|----------|---------|-------------|
| Lambda | `base-wecare-digital-whatsapp:live` | Main handler (v47) |
| API Gateway | `o0wjog0nl4` | HTTP API endpoint |
| DynamoDB | `base-wecare-digital-whatsapp` | Messages & conversations |
| S3 Bucket | `dev.wecare.digital` | Media storage (prefix: `WhatsApp/`) |
| SNS Topic | `base-wecare-digital` | Inbound message routing |

## Endpoints

- **API Gateway**: `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com`
- **Lambda ARN**: `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp:live`

## WhatsApp Business Accounts

| WABA ID | Business Name | Phone | Phone Number ID |
|---------|---------------|-------|-----------------|
| `1390647332755815` | Manish Agarwal | +91 99033 00044 | `0b0d77d6d54645d991db7aa9cf1b0eb2` |
| `1347766229904230` | WECARE.DIGITAL | +91 93309 94400 | `3f8934395ae24a4583a413087a3d3fb0` |

## Features

### Message Types Supported
- ✅ Text messages
- ✅ Images (JPEG, PNG)
- ✅ Videos (MP4, 3GP)
- ✅ Audio (MP3, AAC, AMR, OGG)
- ✅ Documents (PDF, DOC, XLS, PPT, TXT)
- ✅ Stickers (WebP)
- ✅ Location
- ✅ Contacts
- ✅ Interactive (buttons, lists)
- ✅ Templates

### Auto-Features
- ✅ Auto-reply to inbound messages
- ✅ Mark messages as read (blue ticks)
- ✅ React with emoji based on message type
- ✅ Email notifications for new messages
- ✅ Media echo-back

### Actions Available (71 total)

Run `{"action": "list_actions"}` to see all actions grouped by category.

| Category | Actions |
|----------|---------|
| **Send Messages** | `send_text`, `send_image`, `send_video`, `send_audio`, `send_document`, `send_media`, `send_sticker`, `send_reaction`, `send_location`, `send_contact`, `send_interactive`, `send_cta_url`, `send_reply`, `send_template`, `bulk_send`, `send_flow`, `send_address_message`, `send_product`, `send_product_list`, `send_location_request` |
| **Templates** | `templates`, `get_templates`, `refresh_templates` |
| **Message Actions** | `mark_read`, `remove_reaction`, `delete_message`, `resend_message`, `retry_failed_messages` |
| **Conversation** | `update_conversation`, `mark_conversation_read`, `archive_conversation`, `unarchive_conversation` |
| **Media** | `upload_media`, `download_media`, `delete_media`, `get_media_url`, `validate_media`, `get_supported_formats` |
| **Query Single** | `get_message`, `get_message_by_wa_id`, `get_conversation`, `get_delivery_status` |
| **Query Lists** | `get_messages`, `get_conversations`, `get_conversation_messages`, `get_archived_conversations`, `get_failed_messages`, `search_messages`, `get_unread_count` |
| **Config/Status** | `get_quality`, `get_stats`, `get_wabas`, `get_phone_info`, `get_infra`, `get_media_types`, `get_config` |
| **Export** | `export_messages` |
| **Refresh** | `refresh_quality`, `refresh_infra`, `refresh_media_types` |
| **Utility** | `help`, `ping`, `list_actions`, `get_best_practices` |

### New Interactive Message Types

| Type | Action | Description |
|------|--------|-------------|
| **WhatsApp Flows** | `send_flow` | Send structured forms, surveys, appointments |
| **Address Collection** | `send_address_message` | Collect shipping addresses (IN/SG only) |
| **Product Message** | `send_product` | Send single product from catalog |
| **Product List** | `send_product_list` | Send multi-product list from catalog |
| **Location Request** | `send_location_request` | Request user's current location |
| **CTA URL Button** | `send_cta_url` | Send call-to-action URL button |

## Quick Start

### Send a Text Message
```json
{
  "action": "send_text",
  "metaWabaId": "1347766229904230",
  "to": "+919876543210",
  "text": "Hello from WhatsApp!"
}
```

### Send an Image
```json
{
  "action": "send_image",
  "metaWabaId": "1347766229904230",
  "to": "+919876543210",
  "s3Key": "WhatsApp/images/photo.jpg",
  "caption": "Check this out!"
}
```

### Get Templates
```json
{
  "action": "get_templates",
  "metaWabaId": "1347766229904230"
}
```

## Deployment

```powershell
# Deploy Lambda
cd deploy
.\deploy-lambda.ps1

# Or deploy everything
.\deploy-all.ps1
```

## Project Structure

```
├── app.py                 # Main Lambda handler (5000+ lines)
├── requirements.txt       # Python dependencies
├── deploy/               # Deployment scripts & configs
│   ├── deploy-lambda.ps1
│   ├── deploy-all.ps1
│   ├── env-vars.json
│   ├── iam-policy.json
│   └── ...
├── tests/                # Test payloads & scripts
│   ├── test-send-text-lambda.json
│   ├── test-send-image-lambda.json
│   └── ...
├── tools/                # Utility scripts
│   ├── dashboard.py
│   ├── show_messages.py
│   └── ...
├── docs/                 # Documentation
│   └── README.md
└── archive/              # One-time setup files
```

## Environment Variables

Key environment variables (see `deploy/env-vars.json`):

| Variable | Description |
|----------|-------------|
| `MESSAGES_TABLE_NAME` | DynamoDB table name |
| `MEDIA_BUCKET` | S3 bucket for media |
| `WABA_PHONE_MAP_JSON` | WABA to phone mapping |
| `AUTO_REPLY_ENABLED` | Enable auto-reply |
| `MARK_AS_READ_ENABLED` | Send read receipts |
| `REACT_EMOJI_ENABLED` | React with emoji |
| `EMAIL_NOTIFICATION_ENABLED` | Send email alerts |

## DynamoDB Schema

### Table: `base-wecare-digital-whatsapp`

**Primary Key:**
- `pk` (String) - Partition key with format:
  - `MSG#<wamid>` - For messages
  - `CONV#<phone_arn>#<wa_id>` - For conversations
  - `CONFIG#<type>` - For configuration items

### Global Secondary Indexes (4 GSIs)

| Index Name | Partition Key | Sort Key | Use Case |
|------------|---------------|----------|----------|
| `gsi_conversation` | `conversationPk` | `receivedAt` | Get messages in a conversation |
| `gsi_from` | `fromPk` | `receivedAt` | Get messages from a sender |
| `gsi_inbox` | `inboxPk` | `receivedAt` | Get messages for a phone number |
| `gsi_direction` | `direction` | `receivedAt` | Get INBOUND or OUTBOUND messages |

### Item Types

| itemType | Description | Key Fields |
|----------|-------------|------------|
| `MESSAGE` | WhatsApp message | `pk`, `conversationPk`, `from`, `to`, `type`, `direction` |
| `CONVERSATION` | Conversation summary | `pk`, `inboxPk`, `from`, `lastMessagePk`, `unreadCount` |
| `MESSAGE_STATUS` | Delivery status only | `pk`, `deliveryStatus`, `deliveryStatusHistory` |
| `CONFIG_INFRA` | Infrastructure config | `pk=CONFIG#INFRA` |
| `CONFIG_MEDIA_TYPES` | Media type config | `pk=CONFIG#MEDIA_TYPES` |
| `CONFIG_TEMPLATES` | Cached templates | `pk=CONFIG#TEMPLATES#<waba_id>` |
| `CONFIG_QUALITY` | Phone quality rating | `pk=CONFIG#QUALITY#<phone_arn>` |

## Phone Number Format

AWS Social Messaging API requires phone numbers WITH `+` prefix:
- ✅ Correct: `+919903300044`
- ❌ Wrong: `919903300044`

The `format_wa_number()` function handles this automatically.

## Version History

| Version | Description |
|---------|-------------|
| v48 | Fix SNS Notification handling bug |
| v47 | Handle SNS Notification messages via HTTPS |
| v46 | Add SNS subscription confirmation |
| v43 | API Gateway response wrapper |
| v42 | Fix phone number format (+prefix) |

---

*Last updated: December 29, 2025*


---

## Extended Features (v49+)

### New Handler Modules

The extended handlers are organized in the `handlers/` directory:

| Module | Description | Actions |
|--------|-------------|---------|
| `business_profile.py` | Business profile management | 3 |
| `marketing.py` | Marketing messages & templates | 12 |
| `webhooks.py` | Webhook processing & Wix integration | 5 |
| `calling.py` | WhatsApp calling features | 6 |
| `groups.py` | Group management | 7 |
| `analytics.py` | Analytics & CTWA metrics | 5 |
| `catalogs.py` | Product catalogs | 3 |
| `payments.py` | Payment processing (India) | 6 |
| `media_eum.py` | AWS EUM media handling | 6 |

### New Actions (50+)

#### Business Profile
```json
{"action": "get_business_profile", "metaWabaId": "xxx"}
{"action": "update_business_profile", "metaWabaId": "xxx", "data": {...}}
{"action": "upload_profile_picture", "metaWabaId": "xxx", "s3Key": "path/to/image.jpg"}
```

#### Marketing & Templates
```json
{"action": "send_marketing_message", "metaWabaId": "xxx", "to": "+91xxx", "templateName": "xxx", "bodyParams": [...]}
{"action": "send_auth_template", "metaWabaId": "xxx", "to": "+91xxx", "templateName": "otp", "otpCode": "123456"}
{"action": "send_carousel_template", "metaWabaId": "xxx", "to": "+91xxx", "templateName": "xxx", "cards": [...]}
{"action": "send_coupon_template", "metaWabaId": "xxx", "to": "+91xxx", "templateName": "xxx", "couponCode": "SAVE20"}
```

#### Webhooks & Wix Integration
```json
{"action": "register_webhook", "metaWabaId": "xxx", "webhookUrl": "https://...", "verifyToken": "xxx"}
{"action": "process_wix_webhook", "metaWabaId": "xxx", "wixEvent": {"eventType": "order_created", ...}}
{"action": "get_wix_orders", "customerPhone": "+91xxx"}
```

#### Calling
```json
{"action": "initiate_call", "metaWabaId": "xxx", "to": "+91xxx", "callType": "business_initiated"}
{"action": "get_call_logs", "metaWabaId": "xxx", "limit": 50}
{"action": "create_call_deeplink", "phoneNumber": "+91xxx", "callType": "voice"}
```

#### Groups
```json
{"action": "create_group", "metaWabaId": "xxx", "groupName": "Support", "participants": [...]}
{"action": "send_group_message", "groupId": "xxx", "messageType": "text", "text": "Hello group!"}
```

#### Analytics
```json
{"action": "get_analytics", "metaWabaId": "xxx", "startDate": "2024-12-01", "endDate": "2024-12-30"}
{"action": "get_ctwa_metrics", "metaWabaId": "xxx", "campaignId": "xxx"}
{"action": "get_funnel_insights", "metaWabaId": "xxx", "templateName": "xxx"}
```

#### Catalogs
```json
{"action": "upload_catalog", "metaWabaId": "xxx", "catalogName": "Main", "products": [...]}
{"action": "send_catalog_message", "metaWabaId": "xxx", "to": "+91xxx", "catalogId": "xxx", "messageType": "product_list"}
```

#### Payments (India)
```json
{"action": "payment_onboarding", "metaWabaId": "xxx", "provider": "razorpay", "credentials": {...}}
{"action": "create_payment_request", "metaWabaId": "xxx", "to": "+91xxx", "orderId": "xxx", "amount": 2500}
{"action": "get_payment_status", "paymentId": "xxx"}
```

#### AWS EUM Media
```json
{"action": "eum_download_media", "metaWabaId": "xxx", "mediaId": "xxx"}
{"action": "eum_upload_media", "metaWabaId": "xxx", "s3Key": "path/to/file"}
{"action": "eum_validate_media", "mimeType": "image/jpeg", "fileSizeBytes": 1048576}
{"action": "eum_get_supported_formats"}
```

### New DynamoDB Item Types

| itemType | Description |
|----------|-------------|
| BUSINESS_PROFILE | Business profile data |
| TEMPLATE_DEFINITION | Template definitions |
| MARKETING_MESSAGE | Marketing messages sent |
| AUTH_MESSAGE | Authentication messages |
| WEBHOOK_CONFIG | Webhook configuration |
| WEBHOOK_EVENT | Webhook event history |
| WIX_ORDER | Wix e-commerce orders |
| CALL | Call records |
| CALL_SETTINGS | Call settings |
| GROUP | WhatsApp groups |
| GROUP_PARTICIPANT | Group participants |
| GROUP_MESSAGE | Group messages |
| CTWA_EVENT | CTWA click events |
| WELCOME_SEQUENCE | Welcome sequences |
| ANALYTICS_SNAPSHOT | Analytics snapshots |
| CATALOG | Product catalogs |
| PRODUCT | Catalog products |
| PAYMENT_CONFIG | Payment gateway config |
| PAYMENT | Payment records |
| MEDIA_UPLOAD | Media upload records |
| MEDIA_DOWNLOAD | Media download records |

### Deployment

```powershell
# Deploy extended handlers
cd deploy
.\deploy-extended.ps1

# Setup extended DynamoDB schema
.\setup-dynamodb-extended.ps1

# Update IAM policy
.\update-iam-role.ps1 -PolicyFile iam-policy-extended.json
```

### Reference Documentation

See `docs/spec.md` for complete API reference links.

---

*Extended features added: December 30, 2024*
