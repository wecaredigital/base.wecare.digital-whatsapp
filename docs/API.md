# WhatsApp Business API Documentation

## Overview

This API provides 167 handlers for WhatsApp Business messaging via AWS End User Messaging (EUM) Social.

**Base URL**: `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com`

**Authentication**: AWS IAM / API Key (configure in API Gateway)

**Request Format**: JSON POST
```json
{
  "action": "<action_name>",
  ...params
}
```

---

## Quick Start

### Send a Text Message
```bash
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -H "Content-Type: application/json" \
  -d '{
    "action": "send_text",
    "metaWabaId": "1347766229904230",
    "to": "+919903300044",
    "text": "Hello from WhatsApp API!"
  }'
```

### Health Check
```bash
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -d '{"action": "ping"}'
```

---

## WABA Configuration

| WABA | Meta ID | Phone | Business |
|------|---------|-------|----------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 | Primary |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 | Secondary |

---

## API Categories

### 1. Messaging (16 handlers)

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `send_text` | Send text message | `metaWabaId`, `to`, `text` |
| `send_image` | Send image | `metaWabaId`, `to`, `s3Key` or `mediaId` |
| `send_video` | Send video | `metaWabaId`, `to`, `s3Key` or `mediaId` |
| `send_audio` | Send audio | `metaWabaId`, `to`, `s3Key` or `mediaId` |
| `send_document` | Send document | `metaWabaId`, `to`, `s3Key`, `filename` |
| `send_sticker` | Send sticker | `metaWabaId`, `to`, `s3Key` or `mediaId` |
| `send_location` | Send location | `metaWabaId`, `to`, `latitude`, `longitude` |
| `send_contact` | Send contact card | `metaWabaId`, `to`, `contacts` |
| `send_interactive` | Send buttons/list | `metaWabaId`, `to`, `interactive` |
| `send_cta_url` | Send CTA URL button | `metaWabaId`, `to`, `text`, `buttonText`, `url` |
| `send_template` | Send template | `metaWabaId`, `to`, `templateName`, `languageCode` |
| `send_reaction` | React to message | `metaWabaId`, `to`, `messageId`, `emoji` |
| `send_reply` | Reply to message | `metaWabaId`, `to`, `replyToMessageId`, `text` |
| `mark_read` | Mark as read | `metaWabaId`, `messageId` |
| `remove_reaction` | Remove reaction | `metaWabaId`, `to`, `messageId` |
| `send_media` | Generic media send | `metaWabaId`, `to`, `mediaType`, `s3Key` |

#### Example: Send Image
```json
{
  "action": "send_image",
  "metaWabaId": "1347766229904230",
  "to": "+919903300044",
  "s3Key": "WhatsApp/images/promo.jpg",
  "caption": "Check out our new product!"
}
```

#### Example: Send Interactive Buttons
```json
{
  "action": "send_interactive",
  "metaWabaId": "1347766229904230",
  "to": "+919903300044",
  "interactive": {
    "type": "button",
    "body": {"text": "How can we help you?"},
    "action": {
      "buttons": [
        {"type": "reply", "reply": {"id": "support", "title": "Support"}},
        {"type": "reply", "reply": {"id": "sales", "title": "Sales"}}
      ]
    }
  }
}
```

---

### 2. Query Handlers (11 handlers)

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `get_messages` | List messages | `metaWabaId` (optional) |
| `get_conversations` | List conversations | `metaWabaId` (optional) |
| `get_message` | Get single message | `messageId` |
| `get_conversation` | Get conversation | `phoneId`, `fromNumber` |
| `get_conversation_messages` | Messages in conversation | `phoneId`, `fromNumber` |
| `get_unread_count` | Unread count | `metaWabaId` (optional) |
| `search_messages` | Search by text | `query` |
| `get_archived_conversations` | Archived convos | - |
| `get_failed_messages` | Failed messages | - |
| `get_delivery_status` | Message status | `messageId` |
| `get_message_by_wa_id` | Get by WA ID | `waMessageId` |

---

### 3. Config & Utility (11 handlers)

| Action | Description |
|--------|-------------|
| `ping` | Health check |
| `get_config` | Get Lambda config |
| `get_quality` | Phone quality ratings |
| `get_stats` | Message statistics |
| `get_wabas` | List linked WABAs |
| `get_phone_info` | Phone number details |
| `get_infra` | Infrastructure config |
| `get_media_types` | Supported media types |
| `get_supported_formats` | Media format details |
| `list_actions` | List all actions |
| `get_best_practices` | Usage best practices |

---

### 4. AWS EUM Templates (10 handlers)

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `eum_list_templates` | List templates | `wabaId` (AWS WABA ID) |
| `eum_get_template` | Get template details | `wabaId`, `templateId` |
| `eum_create_template` | Create template | `wabaId`, `name`, `language`, `category`, `components` |
| `eum_update_template` | Update template | `wabaId`, `templateId`, `components` |
| `eum_delete_template` | Delete template | `wabaId`, `templateId` |
| `eum_list_template_library` | Browse library | - |
| `eum_create_from_library` | Create from library | `wabaId`, `libraryTemplateId` |
| `eum_create_template_media` | Upload template media | `wabaId`, `s3Key` |
| `eum_sync_templates` | Sync templates | `wabaId` |
| `eum_get_template_status` | Template status | `wabaId`, `templateId` |

**Note**: `wabaId` is the AWS WABA ID (e.g., `waba-60e8e476c4714b9f9ec14d78f5162ee7`), not Meta WABA ID.

---

### 5. AWS EUM Media (6 handlers)

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `eum_download_media` | Download to S3 | `metaWabaId`, `mediaId` |
| `eum_upload_media` | Upload from S3 | `metaWabaId`, `s3Key` |
| `eum_validate_media` | Validate media | `mimeType`, `fileSizeBytes` |
| `eum_get_supported_formats` | Get formats | `category` (optional) |
| `eum_setup_s3_lifecycle` | Setup lifecycle | - |
| `eum_get_media_stats` | Media statistics | `metaWabaId` |

---

### 6. Payments (19 handlers)

| Action | Description |
|--------|-------------|
| `payment_onboarding` | Onboard payment gateway |
| `create_payment_request` | Create payment link |
| `get_payment_status` | Check payment status |
| `send_payment_order` | Send order with payment |
| `send_order_status` | Send order status update |
| `get_payments` | List payments |
| `seed_payment_configs` | Seed payment configs |
| `list_payment_configurations` | List configs |
| `get_payment_configuration` | Get config |
| `set_default_payment_configuration` | Set default |
| `send_order_details_with_payment` | Order + payment |

---

### 7. Business Profile (4 handlers)

| Action | Description |
|--------|-------------|
| `get_business_profile` | Get profile |
| `update_business_profile` | Update profile |
| `upload_profile_picture` | Upload picture |
| `get_business_profile_apply_instructions` | Setup guide |

---

### 8. Marketing & Templates (12 handlers)

| Action | Description |
|--------|-------------|
| `create_marketing_template` | Create template |
| `send_marketing_message` | Send marketing msg |
| `send_utility_template` | Send utility template |
| `send_auth_template` | Send auth OTP |
| `send_catalog_template` | Send catalog |
| `send_coupon_template` | Send coupon |
| `send_carousel_template` | Send carousel |
| `get_template_analytics` | Template analytics |
| `get_template_pacing` | Template pacing |
| `set_template_ttl` | Set template TTL |

---

### 9. Webhooks (12 handlers)

| Action | Description |
|--------|-------------|
| `register_webhook` | Register webhook URL |
| `verify_webhook` | Verify webhook |
| `validate_webhook_signature` | Validate signature |
| `process_secure_webhook` | Process with security |
| `set_webhook_config` | Set config |
| `get_webhook_config` | Get config |
| `process_wix_webhook` | Process Wix events |
| `get_webhook_events` | Get events |

---

### 10. Flows (7 handlers)

| Action | Description |
|--------|-------------|
| `send_flow_message` | Send flow |
| `send_flow_template` | Send flow template |
| `flow_data_exchange` | Exchange data |
| `flow_completion` | Complete flow |
| `flow_health_check` | Check flow health |
| `delete_flow` | Delete flow |
| `get_flow_responses` | Get responses |

---

### 11. Groups (7 handlers)

| Action | Description |
|--------|-------------|
| `create_group` | Create group |
| `add_group_participant` | Add participant |
| `remove_group_participant` | Remove participant |
| `get_group_info` | Get group info |
| `get_groups` | List groups |
| `send_group_message` | Send to group |
| `get_group_messages` | Get group messages |

---

### 12. Analytics (5 handlers)

| Action | Description |
|--------|-------------|
| `get_analytics` | Get analytics |
| `get_ctwa_metrics` | Click-to-WhatsApp metrics |
| `get_funnel_insights` | Funnel insights |
| `track_ctwa_click` | Track CTWA click |
| `setup_welcome_sequence` | Setup welcome flow |

---

### 13. Calling (6 handlers)

| Action | Description |
|--------|-------------|
| `initiate_call` | Start call |
| `update_call_status` | Update status |
| `get_call_logs` | Get logs |
| `update_call_settings` | Update settings |
| `get_call_settings` | Get settings |
| `create_call_deeplink` | Create deeplink |

---

### 14. Catalogs (3 handlers)

| Action | Description |
|--------|-------------|
| `upload_catalog` | Upload catalog |
| `get_catalog_products` | Get products |
| `send_catalog_message` | Send catalog |

---

### 15. Refunds (8 handlers)

| Action | Description |
|--------|-------------|
| `create_refund` | Create refund |
| `process_refund` | Process refund |
| `complete_refund` | Complete refund |
| `fail_refund` | Mark failed |
| `cancel_refund` | Cancel refund |
| `get_refund` | Get refund |
| `get_refunds` | List refunds |
| `process_refund_webhook` | Process webhook |

---

## Error Handling

All responses include `statusCode`:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (missing params) |
| 404 | Not found |
| 500 | Internal error |

Error response format:
```json
{
  "statusCode": 400,
  "error": "metaWabaId and to are required"
}
```

---

## Rate Limits

- **Messaging**: 250 msg/sec (HIGH tier)
- **API calls**: 1000 req/sec (API Gateway)
- **Template creation**: 100/day

---

## Support

- **Email**: base@wecare.digital
- **CloudWatch Logs**: `/aws/lambda/base-wecare-digital-whatsapp`
- **Alarms**: SNS topic `base-wecare-digital`
