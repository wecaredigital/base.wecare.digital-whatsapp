# Technical Specification

## Reference Documentation

### Meta WhatsApp Business Platform
- [Business Profiles](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/business-profiles)
- [Templates](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#template-messages)
- [Messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)
- [Webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- [Payments (India)](https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api)

### AWS End User Messaging Social
- [Event Destinations](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations.html)
- [Media Handling](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-media-files-s3.html)
- [API Reference](https://docs.aws.amazon.com/social-messaging/latest/APIReference/)
- [Quotas](https://docs.aws.amazon.com/social-messaging/latest/userguide/quotas.html)

## Architecture

```
WhatsApp → Meta → AWS EUM Social → SNS → Lambda → DynamoDB
                                              ↓
                                           S3 (media)
```

## Handler Categories

| Category | Count | Module |
|----------|-------|--------|
| Messaging | 16 | messaging.py |
| Queries | 11 | queries.py |
| Config | 11 | config.py |
| Templates (EUM) | 10 | templates_eum.py |
| Templates (Meta) | 7 | templates_meta.py |
| Payments | 19 | payments.py, payment_config.py |
| Webhooks | 12 | webhooks.py, webhook_security.py |
| Media | 6 | media_eum.py |
| Flows | 15 | flows.py, flows_messaging.py |
| Analytics | 5 | analytics.py |
| Groups | 7 | groups.py |
| Calling | 6 | calling.py |
| Business Profile | 4 | business_profile.py |
| Catalogs | 3 | catalogs.py |
| Refunds | 8 | refunds.py |
| Address | 7 | address_messages.py |
| Automation | 8 | automation.py |
| Quality | 5 | quality.py |
| Phone Mgmt | 8 | phone_management.py |
| WABA Mgmt | 6 | waba_management.py |
| Carousels | 3 | carousels.py |
| Throughput | 4 | throughput.py |
| Template Library | 4 | template_library.py |
| Event Destinations | 5 | event_destinations.py |

## DynamoDB Item Types

| Type | PK Pattern |
|------|------------|
| MESSAGE | MSG#{waMessageId} |
| CONVERSATION | CONV#{phoneId}#{from} |
| TEMPLATE | TEMPLATE#{wabaId}#{name} |
| PAYMENT | PAYMENT#{paymentId} |
| REFUND | REFUND#{refundId} |
| WEBHOOK_CONFIG | WEBHOOK#{wabaId} |
| GROUP | GROUP#{groupId} |
| CALL | CALL#{callId} |
| CATALOG | CATALOG#{catalogId} |
| FLOW | FLOW#{flowId} |
