# WhatsApp API Quick Reference

## Endpoint
```
POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com
```

## WABAs
| Business | Meta WABA ID | Phone |
|----------|--------------|-------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 |

---

## Most Used Actions

### Send Text
```json
{"action": "send_text", "metaWabaId": "1347766229904230", "to": "+91...", "text": "Hello!"}
```

### Send Image
```json
{"action": "send_image", "metaWabaId": "1347766229904230", "to": "+91...", "s3Key": "WhatsApp/image.jpg", "caption": "Check this!"}
```

### Send Template
```json
{"action": "send_template", "metaWabaId": "1347766229904230", "to": "+91...", "templateName": "hello_world", "languageCode": "en"}
```

### Send Buttons
```json
{
  "action": "send_interactive",
  "metaWabaId": "1347766229904230",
  "to": "+91...",
  "interactive": {
    "type": "button",
    "body": {"text": "Choose an option:"},
    "action": {
      "buttons": [
        {"type": "reply", "reply": {"id": "opt1", "title": "Option 1"}},
        {"type": "reply", "reply": {"id": "opt2", "title": "Option 2"}}
      ]
    }
  }
}
```

### Send List Menu
```json
{
  "action": "send_interactive",
  "metaWabaId": "1347766229904230",
  "to": "+91...",
  "interactive": {
    "type": "list",
    "body": {"text": "Select from menu:"},
    "action": {
      "button": "View Options",
      "sections": [{
        "title": "Products",
        "rows": [
          {"id": "p1", "title": "Product 1", "description": "Description"},
          {"id": "p2", "title": "Product 2", "description": "Description"}
        ]
      }]
    }
  }
}
```

### Mark as Read
```json
{"action": "mark_read", "metaWabaId": "1347766229904230", "messageId": "wamid.xxx"}
```

### React with Emoji
```json
{"action": "send_reaction", "metaWabaId": "1347766229904230", "to": "+91...", "messageId": "wamid.xxx", "emoji": "👍"}
```

---

## Query Actions

### Get Messages
```json
{"action": "get_messages", "metaWabaId": "1347766229904230", "limit": 50}
```

### Get Conversations
```json
{"action": "get_conversations", "metaWabaId": "1347766229904230"}
```

### Search Messages
```json
{"action": "search_messages", "query": "order"}
```

### Get WABAs
```json
{"action": "get_wabas"}
```

---

## Utility Actions

### Health Check
```json
{"action": "ping"}
```

### List All Actions
```json
{"action": "list_actions"}
```

### Get Config
```json
{"action": "get_config"}
```

---

## AWS EUM Templates

### List Templates
```json
{"action": "eum_list_templates", "wabaId": "waba-60e8e476c4714b9f9ec14d78f5162ee7"}
```

### Create Template
```json
{
  "action": "eum_create_template",
  "wabaId": "waba-60e8e476c4714b9f9ec14d78f5162ee7",
  "name": "order_update",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {"type": "BODY", "text": "Your order {{1}} is {{2}}"}
  ]
}
```

---

## cURL Examples

```bash
# Send text
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -H "Content-Type: application/json" \
  -d '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919903300044","text":"Hello!"}'

# Health check
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -d '{"action":"ping"}'

# Get WABAs
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -d '{"action":"get_wabas"}'
```

---

## Response Format

Success:
```json
{"statusCode": 200, "operation": "send_text", "messageId": "xxx", "to": "+91..."}
```

Error:
```json
{"statusCode": 400, "error": "metaWabaId and to are required"}
```
