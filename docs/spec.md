# WhatsApp Business API Specification Reference

This document serves as the canonical link index for Meta WhatsApp Business API specifications.
These docs define message formats, template rules, and webhook/event semantics.

> **Implementation Note:** This system uses AWS End User Messaging Social (socialmessaging) exclusively.
> Meta docs are schema + behavior specs only. AWS EUM passes WhatsApp Cloud API message objects through.

---

## 1. Business Profiles

- [Business Profiles Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-profiles)
- [Business Phone Numbers - Profiles](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/business-profiles)

---

## 2. Marketing + Templates

### Overview
- [Marketing Messages Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/marketing-messages/overview)
- [Send Marketing Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/marketing-messages/send-marketing-messages)

### Templates
- [Templates Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview)
- [Utility Templates](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/utility-templates/utility-templates)
- [Authentication Templates](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/authentication-templates/authentication-templates)
- [Marketing Templates](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/marketing-templates)
- [Template Management](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-management)
- [Template Library](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-library)

### Pacing & Limits
- [Portfolio Pacing](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/portfolio-pacing)
- [Template Pacing](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-pacing)
- [Time to Live (TTL)](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/time-to-live)
- [Tap Target URL Title Override](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/tap-target-url-title-override)

---

## 3. Send Messages + Types + Throughput

### Core Messaging
- [Send Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages)
- [Throughput](https://developers.facebook.com/documentation/business-messaging/whatsapp/throughput)

### Interactive Messages
- [Interactive List Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-list-messages)
- [Interactive CTA URL Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-cta-url-messages)
- [Interactive Media Carousel Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-media-carousel-messages)
- [Interactive Product Carousel Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-product-carousel-messages)
- [Interactive Reply Buttons Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-reply-buttons-messages)

---

## 4. Webhooks (ALL)

### Overview
- [Webhooks Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview)
- [Create Webhook Endpoint](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint)

### Message Types Reference
- [Messages Reference](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages)
- [Audio Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/audio/)
- [Button Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/button/)
- [Contacts Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/contacts/)
- [Document Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/document/)
- [Errors](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/errors)
- [Group Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/group/)
- [Image Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/image)
- [Interactive Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/interactive/)
- [Location Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/location/)
- [Order Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/order)
- [Reaction Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/reaction/)
- [Status Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/status)
- [Sticker Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/sticker/)
- [System Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/system/)
- [Text Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/text)
- [Unsupported Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/unsupported)
- [Video Messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/video/)

---

## 5. Calling / Groups / Analytics / CTWA / Catalogs / Payments

- [Calling](https://developers.facebook.com/documentation/business-messaging/whatsapp/calling)
- [Groups](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups)
- [Analytics](https://developers.facebook.com/documentation/business-messaging/whatsapp/analytics)
- [CTWA Welcome Message Sequences](https://developers.facebook.com/documentation/business-messaging/whatsapp/ctwa/welcome-message-sequences)
- [Catalogs - Sell Products and Services](https://developers.facebook.com/documentation/business-messaging/whatsapp/catalogs/sell-products-and-services)

### Payments (India)
- [Payments In Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/overview)
- [Payments Onboarding API](https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/onboarding-apis)
- [Payment Gateway Integration](https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/pg)
- [Checkout Button Templates](https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/checkout-button-templates/)

---

## 6. AWS End User Messaging Social

### Event Destinations
- [Managing Event Destinations](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations.html)
- [Add Event Destinations](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destinations-add.html)

### Media
- [Managing Media Files with S3](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-media-files-s3.html)
- [GetWhatsAppMessageMedia API](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_GetWhatsAppMessageMedia.html)
- [get-whatsapp-message-media CLI](https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/get-whatsapp-message-media.html)
- [post-whatsapp-message-media CLI](https://docs.aws.amazon.com/cli/latest/reference/socialmessaging/post-whatsapp-message-media.html)

### Automation & CLI
- [WhatsApp Automation Overview](https://docs.aws.amazon.com/social-messaging/latest/userguide/whatsapp-automation.html)

### Quotas
- [Service Quotas](https://docs.aws.amazon.com/social-messaging/latest/userguide/quotas.html)

---

## 7. AWS Lambda (Durable Functions)

> **Note:** Durable Lambda is NOT used for SQS ingestion due to 15-minute ESM cap.

- [Durable Functions Overview](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html)
- [Durable Functions Runtimes](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions-runtimes.html)
- [Durable Functions Limits](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions-limits.html)
- [Durable Functions Regions](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions-regions.html)

---

## Implementation Status

| Feature | Status | Handler Count |
|---------|--------|---------------|
| Templates (EUM) | ✅ Complete | 10 |
| Media (EUM) | ✅ Complete | 6 |
| Messaging | ✅ Complete | 16 |
| Webhooks | ✅ Complete | 12 |
| Payments | ✅ Complete | 19 |
| Business Profile | ✅ Complete | 4 |
| Welcome & Menu | ✅ Complete | 10 |
| Message Retry | ✅ Complete | 6 |

**Total Handlers:** 183+
