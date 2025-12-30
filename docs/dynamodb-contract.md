# DynamoDB Contract

Complete schema for the WhatsApp Business API - 167 handlers.

## Table Structure

**Table Name:** `base-wecare-digital-whatsapp` (configurable via `MESSAGES_TABLE_NAME`)

**Primary Key:** `pk` (String) - Partition key with composite format

**Billing Mode:** PAY_PER_REQUEST (On-Demand)

---

## Item Types and Key Patterns

### 1. Messages (Inbound/Outbound)

```
PK: MSG#{waMessageId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `MSG#{waMessageId}` |
| itemType | S | `MESSAGE` |
| direction | S | `INBOUND` or `OUTBOUND` |
| receivedAt | S | ISO timestamp |
| sentAt | S | Sent timestamp (outbound) |
| waTimestamp | S | WhatsApp timestamp |
| from | S | Sender WhatsApp ID |
| fromPk | S | Sender ID for GSI |
| to | S | Recipient WhatsApp ID |
| senderName | S | Sender profile name |
| conversationPk | S | Reference to conversation |
| type | S | text, image, video, audio, document, sticker, location, contacts, interactive, template |
| preview | S | Message preview text |
| textBody | S | Full text content |
| caption | S | Media caption |
| mediaId | S | WhatsApp media ID |
| mimeType | S | Media MIME type |
| s3Bucket | S | S3 bucket for media |
| s3Key | S | S3 key for media |
| deliveryStatus | S | sent, delivered, read, failed |
| deliveryStatusHistory | L | List of status updates |
| inboxPk | S | Phone ARN for inbox GSI |

### 2. Conversations

```
PK: CONV#{phoneArnSuffix}#{customerWaId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CONV#{phoneArnSuffix}#{customerWaId}` |
| itemType | S | `CONVERSATION` |
| inboxPk | S | Phone ARN for inbox GSI |
| from | S | Customer WhatsApp ID |
| receivedAt | S | Last message timestamp |
| unreadCount | N | Unread message count |
| lastMessagePk | S | Reference to last message |
| lastType | S | Last message type |
| lastPreview | S | Last message preview |
| archived | BOOL | Archive status |
| wabaMetaId | S | WABA Meta ID |
| businessAccountName | S | Business name |

### 3. Tenants

```
PK: TENANT#{tenantId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `TENANT#{tenantId}` |
| itemType | S | `TENANT` |
| tenantId | S | Unique tenant identifier |
| displayName | S | Business display name |
| wabaId | S | Meta WABA ID |
| phoneE164 | S | Phone in E.164 format |
| mcc | S | Merchant Category Code |
| purposeCode | S | Payment purpose code |
| defaultPaymentConfig | S | Default payment config name |
| createdAt | S | Creation timestamp |

### 4. Payment Configurations

```
PK: TENANT#{tenantId}#PAYCFG#{configName}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `TENANT#{tenantId}#PAYCFG#{configName}` |
| itemType | S | `PAYMENT_CONFIG` |
| tenantId | S | Tenant identifier |
| configName | S | Configuration name |
| type | S | `PG` or `UPI` |
| status | S | active, inactive, pending |
| paymentGatewayMid | S | Razorpay merchant ID (PG) |
| upiId | S | UPI ID (UPI type) |
| mcc | S | Merchant Category Code |
| purposeCode | S | Payment purpose code |
| lastValidatedAt | S | Last validation timestamp |

### 5. Payment Orders

```
PK: ORDER#{referenceId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `ORDER#{referenceId}` |
| itemType | S | `PAYMENT_ORDER` |
| tenantId | S | Tenant identifier |
| orderId | S | Order ID for GSI |
| referenceId | S | Order reference ID |
| configName | S | Payment config used |
| customerPhone | S | Customer phone |
| currency | S | Currency code (INR) |
| totalAmount | N | Total amount |
| status | S | pending, completed, failed |
| paymentStatus | S | Payment gateway status |
| transactionId | S | Gateway transaction ID |
| createdAt | S | Creation timestamp |

### 6. Refunds

```
PK: REFUND#{refundId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `REFUND#{refundId}` |
| itemType | S | `REFUND` |
| refundId | S | Unique refund ID |
| orderId | S | Original order ID |
| tenantId | S | Tenant identifier |
| customerPhone | S | Customer phone |
| amount | N | Refund amount |
| currency | S | Currency code |
| status | S | pending, processing, completed, failed, cancelled |
| reason | S | Refund reason |
| createdAt | S | Creation timestamp |
| processedAt | S | Processing timestamp |

### 7. Business Profiles

```
PK: PROFILE#{metaWabaId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `PROFILE#{metaWabaId}` |
| itemType | S | `BUSINESS_PROFILE` |
| wabaMetaId | S | Meta WABA ID |
| businessName | S | Business name |
| about | S | About text |
| address | S | Business address |
| description | S | Description |
| email | S | Contact email |
| websites | L | List of websites |
| vertical | S | Business category |
| syncStatus | S | local_only, pending_sync, synced |
| updatedAt | S | Last update timestamp |

### 8. Templates (AWS EUM)

```
PK: TEMPLATE_EUM#{wabaId}#{templateName}#{language}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `TEMPLATE_EUM#{wabaId}#{templateName}#{language}` |
| itemType | S | `TEMPLATE_EUM` |
| wabaId | S | AWS WABA ID |
| templateName | S | Template name |
| metaTemplateId | S | Meta template ID |
| templateStatus | S | APPROVED, PENDING, REJECTED, PAUSED, DISABLED |
| templateCategory | S | UTILITY, MARKETING, AUTHENTICATION |
| templateLanguage | S | Language code |
| qualityScore | S | GREEN, YELLOW, RED |
| components | L | Template components |
| cachedAt | S | Cache timestamp |
| syncedAt | S | Sync timestamp |

### 9. Templates (Meta Cache)

```
PK: TEMPLATE_META#{wabaId}#{templateName}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `TEMPLATE_META#{wabaId}#{templateName}` |
| itemType | S | `TEMPLATE_META` |
| wabaMetaId | S | Meta WABA ID |
| templateName | S | Template name |
| templateId | S | Meta template ID |
| status | S | Template status |
| category | S | Template category |
| language | S | Language code |
| cachedAt | S | Cache timestamp |

### 10. Template Media

```
PK: TEMPLATE_MEDIA#{mediaId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `TEMPLATE_MEDIA#{mediaId}` |
| itemType | S | `TEMPLATE_MEDIA` |
| mediaId | S | Media ID |
| wabaId | S | WABA ID |
| s3Bucket | S | S3 bucket |
| s3Key | S | S3 key |
| contentType | S | MIME type |
| contentLength | N | File size |
| uploadedAt | S | Upload timestamp |

### 11. Media Records

```
PK: MEDIA#{mediaId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `MEDIA#{mediaId}` |
| itemType | S | `MEDIA` |
| mediaId | S | WhatsApp media ID |
| s3Bucket | S | S3 bucket |
| s3Key | S | S3 key |
| contentType | S | MIME type |
| contentLength | N | File size in bytes |
| uploadedAt | S | Upload timestamp |
| expiresAt | S | Expiration timestamp |
| wabaMetaId | S | WABA Meta ID |

### 12. Groups

```
PK: GROUP#{groupId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `GROUP#{groupId}` |
| itemType | S | `GROUP` |
| groupId | S | Group ID |
| wabaMetaId | S | WABA Meta ID |
| name | S | Group name |
| description | S | Group description |
| participants | L | List of participants |
| admins | L | List of admin phone numbers |
| createdAt | S | Creation timestamp |
| updatedAt | S | Last update timestamp |

### 13. Catalogs

```
PK: CATALOG#{catalogId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CATALOG#{catalogId}` |
| itemType | S | `CATALOG` |
| catalogId | S | Catalog ID |
| wabaMetaId | S | WABA Meta ID |
| name | S | Catalog name |
| productCount | N | Number of products |
| syncedAt | S | Last sync timestamp |

### 14. Catalog Products

```
PK: PRODUCT#{catalogId}#{retailerId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `PRODUCT#{catalogId}#{retailerId}` |
| itemType | S | `PRODUCT` |
| catalogId | S | Catalog ID |
| retailerId | S | Retailer product ID |
| name | S | Product name |
| description | S | Product description |
| price | N | Price |
| currency | S | Currency code |
| imageUrl | S | Product image URL |
| availability | S | in_stock, out_of_stock |

### 15. Campaigns

```
PK: CAMPAIGN#{campaignId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CAMPAIGN#{campaignId}` |
| itemType | S | `CAMPAIGN` |
| campaignId | S | Campaign ID |
| wabaMetaId | S | WABA Meta ID |
| name | S | Campaign name |
| templateName | S | Template used |
| status | S | draft, scheduled, running, completed, paused |
| totalRecipients | N | Total recipients |
| sentCount | N | Messages sent |
| deliveredCount | N | Messages delivered |
| readCount | N | Messages read |
| createdAt | S | Creation timestamp |
| scheduledAt | S | Scheduled time |

### 16. Webhook Events

```
PK: WEBHOOK#{eventId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `WEBHOOK#{eventId}` |
| itemType | S | `WEBHOOK_EVENT` |
| webhookEventType | S | Event type for GSI |
| eventId | S | Event ID |
| eventType | S | message, status, etc. |
| wabaMetaId | S | WABA Meta ID |
| payload | M | Event payload |
| processedAt | S | Processing timestamp |
| receivedAt | S | Receipt timestamp |

### 17. Webhook Configurations

```
PK: WEBHOOK_CONFIG#{wabaId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `WEBHOOK_CONFIG#{wabaId}` |
| itemType | S | `WEBHOOK_CONFIG` |
| wabaMetaId | S | WABA Meta ID |
| verifyToken | S | Webhook verify token |
| appSecret | S | App secret for signature |
| enabled | BOOL | Webhook enabled |
| updatedAt | S | Last update timestamp |

### 18. Call Logs

```
PK: CALL#{callId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CALL#{callId}` |
| itemType | S | `CALL` |
| callId | S | Call ID |
| wabaMetaId | S | WABA Meta ID |
| from | S | Caller |
| to | S | Recipient |
| status | S | initiated, ringing, answered, ended, failed |
| duration | N | Call duration in seconds |
| startedAt | S | Call start timestamp |
| endedAt | S | Call end timestamp |

### 19. Analytics Records

```
PK: ANALYTICS#{wabaId}#{date}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `ANALYTICS#{wabaId}#{date}` |
| itemType | S | `ANALYTICS` |
| wabaMetaId | S | WABA Meta ID |
| date | S | Date (YYYY-MM-DD) |
| messagesSent | N | Messages sent |
| messagesDelivered | N | Messages delivered |
| messagesRead | N | Messages read |
| messagesFailed | N | Messages failed |
| templatesUsed | M | Template usage counts |

### 20. Phone Quality

```
PK: QUALITY#{phoneNumberId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `QUALITY#{phoneNumberId}` |
| itemType | S | `QUALITY_RATING` |
| wabaMetaId | S | WABA Meta ID |
| qualityRating | S | GREEN, YELLOW, RED |
| throughputStatus | S | Throughput eligibility |
| lastCheckedAt | S | Last check timestamp |
| qualityHistory | L | Quality rating history |

### 21. Infrastructure Config

```
PK: CONFIG#INFRA
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CONFIG#INFRA` |
| itemType | S | `CONFIG` |
| vpcEndpoint | S | VPC endpoint ID |
| serviceLinkedRole | S | Service-linked role ARN |
| updatedAt | S | Last update timestamp |

### 22. Media Types Config

```
PK: CONFIG#MEDIA_TYPES
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `CONFIG#MEDIA_TYPES` |
| itemType | S | `CONFIG` |
| supportedTypes | M | Supported media types |
| updatedAt | S | Last update timestamp |

### 23. Customer Addresses

```
PK: ADDRESS#{customerPhone}#{addressId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `ADDRESS#{customerPhone}#{addressId}` |
| itemType | S | `ADDRESS` |
| customerPhone | S | Customer phone |
| addressId | S | Address ID |
| name | S | Recipient name |
| phoneNumber | S | Contact phone |
| address | S | Full address |
| city | S | City |
| state | S | State |
| postalCode | S | Postal code |
| country | S | Country code |
| isDefault | BOOL | Default address |
| createdAt | S | Creation timestamp |

### 24. Flow Responses

```
PK: FLOW_RESPONSE#{flowId}#{responseId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `FLOW_RESPONSE#{flowId}#{responseId}` |
| itemType | S | `FLOW_RESPONSE` |
| flowId | S | Flow ID |
| responseId | S | Response ID |
| customerPhone | S | Customer phone |
| screenId | S | Screen ID |
| data | M | Response data |
| completedAt | S | Completion timestamp |

### 25. Idempotency Records

```
PK: IDEMPOTENCY#{requestId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | `IDEMPOTENCY#{requestId}` |
| itemType | S | `IDEMPOTENCY` |
| requestId | S | Unique request ID |
| processedAt | S | Processing timestamp |
| ttl | N | TTL for auto-deletion |
| result | M | Cached result |

---

## Global Secondary Indexes (GSIs)

### Core Message GSIs

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| gsi_direction | direction | receivedAt | Query by INBOUND/OUTBOUND |
| gsi_from | fromPk | receivedAt | Query by sender |
| gsi_inbox | inboxPk | receivedAt | Inbox view |
| gsi_conversation | conversationPk | receivedAt | Conversation timeline |
| gsi_status | deliveryStatus | sentAt | Delivery status queries |

### Extended Feature GSIs

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| gsi_waba_itemtype | wabaMetaId | itemType | WABA + item type queries |
| gsi_customer_phone | customerPhone | createdAt | Customer queries |
| gsi_group | groupId | sentAt | Group messages |
| gsi_catalog | catalogId | retailerId | Catalog products |
| gsi_order | orderId | createdAt | Order queries |

### Tenant & Payment GSIs

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| gsi_tenant | tenantId | itemType | Tenant items |
| gsi_payment_status | paymentStatus | createdAt | Payment status |

### Template GSIs

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| gsi_template_waba | wabaId | templateStatus | Templates by WABA |
| gsi_template_name | templateName | templateLanguage | Templates by name |

### Analytics & Webhook GSIs

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| gsi_campaign | campaignId | sentAt | Campaign messages |
| gsi_webhook_event | webhookEventType | receivedAt | Webhook events |

---

## TTL Configuration

Enable TTL on the `ttl` attribute for automatic cleanup:
- Idempotency records: 24 hours
- Temporary media references: 7 days
- Old webhook events: 30 days

---

## Setup Script

Run the complete setup:
```powershell
.\deploy\setup-dynamodb-complete.ps1
```

Verify GSIs:
```bash
aws dynamodb describe-table \
  --table-name base-wecare-digital-whatsapp \
  --region ap-south-1 \
  --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]' \
  --output table
```
