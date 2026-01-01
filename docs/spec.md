# WhatsApp Integration Specification

## Implementation Constraint
**All WhatsApp functionality is implemented exclusively via AWS End User Messaging Social (socialmessaging).**
- NO Meta Graph API clients
- NO HTTP calls to Meta endpoints  
- NO Meta webhook verification/signature logic
- NO Meta token storage for runtime calls

Meta documentation is used only as schema + behavior specs (message formats, template rules, webhook/event semantics).

---

## Reference Links

### AWS End User Messaging Social
- [AWS EUM Endpoints (ap-south-1)](https://docs.aws.amazon.com/general/latest/gr/end-user-messaging.html)
- [AWS EUM Social Overview](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [AWS EUM Social API Reference](https://docs.aws.amazon.com/social-messaging/latest/APIReference/Welcome.html)
- [AWS EUM WhatsApp + Bedrock Sample](https://github.com/aws-samples/generative-ai-ml-latam-samples/tree/main/samples/end-user-messaging-bedrock)
- [AWS EUM Social WhatsApp Blog](https://aws.amazon.com/es/blogs/messaging-and-targeting/whatsapp-aws-end-user-messaging-social/)

### AWS Lambda
- [Lambda Durable Functions (ap-south-1 supported)](https://aws.amazon.com/about-aws/whats-new/2025/12/lambda-durable-functions-14-additional-regions/)
- [Lambda Durable Multi-Step Applications](https://aws.amazon.com/about-aws/whats-new/2025/12/lambda-durable-multi-step-applications-ai-workflows/)

### Amazon Bedrock
- [Bedrock Agents Supported Regions (ap-south-1)](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-supported.html)
- [Bedrock Model Region Availability](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html)
- [Bedrock KB Web Crawler Connector](https://docs.aws.amazon.com/bedrock/latest/userguide/webcrawl-data-source-connector.html)
- [Bedrock KB Data Source Sync/Ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)
- [Bedrock Data Automation](https://docs.aws.amazon.com/bedrock/latest/userguide/bda.html)
- [Bedrock Data Automation API](https://docs.aws.amazon.com/bedrock/latest/userguide/bda-using-api.html)

### Meta WhatsApp (Schema/Behavior Specs Only)
- [WhatsApp Cloud API Message Types](https://developers.facebook.com/docs/whatsapp/cloud-api/messages)
- [WhatsApp Template Message Guidelines](https://developers.facebook.com/docs/whatsapp/message-templates)
- [WhatsApp Interactive Messages](https://developers.facebook.com/docs/whatsapp/guides/interactive-messages)
- [WhatsApp Webhook Events](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components)

---

## Message Format Specifications

### Text Message
```json
{
  "messaging_product": "whatsapp",
  "to": "+919XXXXXXXXX",
  "type": "text",
  "text": {"preview_url": false, "body": "Hello!"}
}
```

### Interactive List (Max 10 rows total)
```json
{
  "messaging_product": "whatsapp",
  "to": "+919XXXXXXXXX",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {"type": "text", "text": "Header"},
    "body": {"text": "Body text"},
    "footer": {"text": "Footer"},
    "action": {
      "button": "Menu",
      "sections": [
        {
          "title": "Section 1",
          "rows": [
            {"id": "row1", "title": "Option 1", "description": "Description"}
          ]
        }
      ]
    }
  }
}
```

### Reaction Message
```json
{
  "messaging_product": "whatsapp",
  "to": "+919XXXXXXXXX",
  "type": "reaction",
  "reaction": {"message_id": "wamid.xxx", "emoji": "👍"}
}
```

### Mark as Read
```json
{
  "messaging_product": "whatsapp",
  "message_id": "wamid.xxx",
  "status": "read"
}
```

---

## Webhook Event Structure

Webhooks are delivered via AWS SNS → Lambda (NOT direct Meta webhooks).

### Inbound Message Event
```json
{
  "context": {
    "MetaWabaIds": [{"wabaId": "xxx", "arn": "arn:aws:..."}],
    "MetaPhoneNumberIds": [{"metaPhoneNumberId": "xxx", "arn": "arn:aws:..."}]
  },
  "whatsAppWebhookEntry": "{\"id\":\"xxx\",\"changes\":[{\"value\":{...},\"field\":\"messages\"}]}"
}
```

---

## Region Constraint
All resources MUST be deployed in **ap-south-1 (Mumbai)**.
