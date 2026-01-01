# WhatsApp Business API

## Architecture

```
┌──────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐
│   WhatsApp   │───▶│  AWS EUM    │───▶│         Lambda Function         │
│   (Meta)     │    │   Social    │    │   base-wecare-digital-whatsapp  │
└──────────────┘    └─────────────┘    └───────────────┬─────────────────┘
                                                       │
                    ┌──────────────────────────────────┼──────────────────────────────────┐
                    │                                  │                                  │
                    ▼                                  ▼                                  ▼
            ┌───────────────┐                 ┌───────────────┐                 ┌───────────────┐
            │   DynamoDB    │                 │      S3       │                 │     SNS       │
            │   (Storage)   │                 │   (Media)     │                 │  (Webhooks)   │
            └───────────────┘                 └───────────────┘                 └───────────────┘
```

## Quick Start

```bash
# Health check
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -d '{"action":"ping"}'

# Send text
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -H "Content-Type: application/json" \
  -d '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919903300044","text":"Hello!"}'
```

## WABAs

| Business | Meta WABA ID | Phone |
|----------|--------------|-------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 |

## Handlers (201+ total)

### Messaging (16)
| Action | Description |
|--------|-------------|
| `send_text` | Send text message |
| `send_image` | Send image |
| `send_video` | Send video |
| `send_audio` | Send audio |
| `send_document` | Send document |
| `send_sticker` | Send sticker |
| `send_location` | Send location |
| `send_contact` | Send contact |
| `send_reaction` | React to message |
| `send_interactive` | Send buttons/list |
| `send_cta_url` | Send CTA URL |
| `send_template` | Send template |
| `send_reply` | Reply to message |
| `mark_read` | Mark as read |
| `remove_reaction` | Remove reaction |
| `send_media` | Generic media |

### Queries (11)
| Action | Description |
|--------|-------------|
| `get_messages` | List messages |
| `get_conversations` | List conversations |
| `get_message` | Get single message |
| `get_conversation` | Get conversation |
| `get_conversation_messages` | Messages in conversation |
| `get_unread_count` | Unread count |
| `search_messages` | Search messages |
| `get_archived_conversations` | Archived convos |
| `get_failed_messages` | Failed messages |
| `get_delivery_status` | Message status |
| `get_message_by_wa_id` | Get by WA ID |

### Templates - AWS EUM (10)
| Action | Description |
|--------|-------------|
| `eum_list_templates` | List templates |
| `eum_get_template` | Get template |
| `eum_create_template` | Create template |
| `eum_update_template` | Update template |
| `eum_delete_template` | Delete template |
| `eum_list_template_library` | Browse library |
| `eum_create_from_library` | Create from library |
| `eum_create_template_media` | Upload media |
| `eum_sync_templates` | Sync templates |
| `eum_get_template_status` | Template status |

### Media - AWS EUM (6)
| Action | Description |
|--------|-------------|
| `eum_download_media` | Download to S3 |
| `eum_upload_media` | Upload from S3 |
| `eum_validate_media` | Validate media |
| `eum_get_supported_formats` | Get formats |
| `eum_setup_s3_lifecycle` | Setup lifecycle |
| `eum_get_media_stats` | Media stats |

### Payments (19)
| Action | Description |
|--------|-------------|
| `payment_onboarding` | Onboard gateway |
| `create_payment_request` | Create payment |
| `get_payment_status` | Get status |
| `send_payment_order` | Send order |
| `send_order_status` | Order status |
| `get_payments` | List payments |
| `create_refund` | Create refund |
| `process_refund` | Process refund |
| `get_refund` | Get refund |
| `get_refunds` | List refunds |

### Webhooks (12)
| Action | Description |
|--------|-------------|
| `register_webhook` | Register URL |
| `verify_webhook` | Verify challenge |
| `validate_webhook_signature` | Validate signature |
| `process_secure_webhook` | Process securely |
| `set_webhook_config` | Set config |
| `get_webhook_config` | Get config |

### Flows (15)
| Action | Description |
|--------|-------------|
| `send_flow_message` | Send flow |
| `send_flow_template` | Flow template |
| `flow_data_exchange` | Exchange data |
| `flow_completion` | Complete flow |
| `flow_health_check` | Health check |
| `delete_flow` | Delete flow |
| `get_flow_responses` | Get responses |

### Config (11)
| Action | Description |
|--------|-------------|
| `ping` | Health check |
| `get_config` | Get config |
| `get_quality` | Quality rating |
| `get_stats` | Statistics |
| `get_wabas` | List WABAs |
| `get_phone_info` | Phone info |
| `list_actions` | List all actions |

## Request Format

```json
{
  "action": "<action_name>",
  "metaWabaId": "1347766229904230",
  ...params
}
```

## Response Format

```json
{
  "statusCode": 200,
  "operation": "<action_name>",
  "data": {...}
}
```

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request |
| 404 | Not found |
| 500 | Internal error |
