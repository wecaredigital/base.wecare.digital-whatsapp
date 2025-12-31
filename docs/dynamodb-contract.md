# DynamoDB Contract

Single-table design for WhatsApp Business API integration.

## Table Configuration

- **Table Name:** `base-wecare-digital-whatsapp`
- **Primary Key:** `pk` (String)
- **Billing Mode:** PAY_PER_REQUEST

## Entity Types

### Messages (INBOUND/OUTBOUND)

```
PK: MSG#{waMessageId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "MESSAGE" |
| direction | S | "INBOUND" or "OUTBOUND" |
| receivedAt / sentAt | S | ISO timestamp |
| waTimestamp | S | WhatsApp timestamp |
| from | S | Sender phone number |
| to | S | Recipient phone number |
| senderName | S | Sender profile name |
| originationPhoneNumberId | S | Phone ARN |
| wabaMetaId | S | Meta WABA ID |
| businessAccountName | S | Business name |
| conversationPk | S | Conversation reference |
| type | S | text, image, video, audio, document, etc. |
| preview | S | Message preview (truncated) |
| textBody | S | Full text content |
| caption | S | Media caption |
| filename | S | Document filename |
| mediaId | S | WhatsApp media ID |
| mimeType | S | MIME type |
| s3Bucket | S | S3 bucket |
| s3Key | S | S3 object key |
| s3Uri | S | Full S3 URI |
| deliveryStatus | S | sent, delivered, read, failed |
| deliveryStatusHistory | L | Status change history |
| markedAsRead | BOOL | Read receipt sent |
| reactedWithEmoji | S | Reaction emoji |

### Conversations

```
PK: CONV#{phoneArnSuffix}#{customerPhone}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "CONVERSATION" |
| inboxPk | S | Phone ARN for inbox grouping |
| from | S | Customer phone number |
| receivedAt | S | Last message timestamp |
| originationPhoneNumberId | S | Phone ARN |
| businessAccountName | S | Business name |
| businessPhone | S | Business phone |
| lastMessagePk | S | Last message PK |
| lastMessageId | S | Last message ID |
| lastType | S | Last message type |
| lastPreview | S | Last message preview |
| lastS3Uri | S | Last media S3 URI |
| unreadCount | N | Unread message count |
| archived | BOOL | Archived status |

### Templates (AWS EUM)

```
PK: TEMPLATE_EUM#{wabaId}#{templateName}#{language}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "TEMPLATE_EUM" |
| wabaId | S | AWS WABA ID |
| templateName | S | Template name |
| metaTemplateId | S | Meta template ID |
| templateStatus | S | APPROVED, PENDING, REJECTED, etc. |
| templateCategory | S | UTILITY, MARKETING, AUTHENTICATION |
| templateLanguage | S | Language code (en_US, etc.) |
| qualityScore | S | GREEN, YELLOW, RED |
| components | L | Template components |
| cachedAt / syncedAt | S | Cache timestamp |

### Business Profiles

```
PK: TENANT#{tenantId}#BIZPROFILE#{phoneNumberId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "BUSINESS_PROFILE" |
| tenantId | S | Tenant ID |
| phoneNumberId | S | Phone number ID |
| about | S | About text |
| address | S | Business address |
| description | S | Business description |
| email | S | Contact email |
| websites | L | Website URLs |
| vertical | S | Business vertical |
| profilePictureS3Key | S | Profile picture S3 key |
| appliedState | S | pending, applied, unknown |
| appliedAt | S | When applied to WhatsApp |
| appliedBy | S | Who applied |
| versionHistory | L | Change history |

### Welcome Config

```
PK: TENANT#{tenantId}#WELCOME#default
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "WELCOME_CONFIG" |
| tenantId | S | Tenant ID |
| welcomeText | S | Welcome message text |
| enabled | BOOL | Feature enabled |
| onlyOnFirstContact | BOOL | First contact only |
| cooldownHours | N | Cooldown period |
| outsideWindowTemplateName | S | Template for outside window |

### Menu Config

```
PK: TENANT#{tenantId}#MENU#main
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "MENU_CONFIG" |
| tenantId | S | Tenant ID |
| buttonText | S | Menu button text |
| bodyText | S | Menu body text |
| sections | L | Menu sections with rows |

### Payment Configurations

```
PK: TENANT#{tenantId}#PAYCFG#{wabaId}#{configName}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "PAYMENT_CONFIG" |
| tenantId | S | Tenant ID |
| wabaId | S | WABA ID |
| configName | S | Configuration name |
| gatewayMid | S | Payment gateway MID |
| upiId | S | UPI ID |
| mcc | S | Merchant Category Code |
| purposeCode | S | Purpose code |
| isDefault | BOOL | Default config |

### Idempotency Records

```
PK: EVENT#{idempotencyKey}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "IDEMPOTENCY" |
| eventType | S | Event type |
| processedAt | S | Processing timestamp |
| ttl | N | TTL for auto-deletion |

### Notification Records

```
PK: NOTIFICATION#{notificationId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "NOTIFICATION_SENT" |
| notificationType | S | inbound, outbound |
| recipient | S | Email recipient |
| messageId | S | Related message ID |
| sentAt | S | Send timestamp |
| ttl | N | TTL for auto-deletion |

### Bedrock Results

```
PK: BEDROCK#{conversationId}#{messageId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "BEDROCK_RESULT" |
| messageId | S | Message ID |
| tenantId | S | Tenant ID |
| conversationId | S | Conversation ID |
| contentType | S | text, image, document, etc. |
| summary | S | Content summary |
| extractedText | S | Extracted text |
| entities | M | Extracted entities |
| intent | S | Detected intent |
| replyDraft | S | Generated reply |
| processedAt | S | Processing timestamp |

### Phone Quality

```
PK: QUALITY#{phoneNumberId}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| pk | S | Primary key |
| itemType | S | "PHONE_QUALITY" |
| wabaId | S | WABA ID |
| phoneNumberId | S | Phone number ID |
| qualityRating | S | GREEN, YELLOW, RED |
| throughputStatus | S | Throughput eligibility |
| qualityHistory | L | Quality history |

## Global Secondary Indexes

### GSI1: Inbox View

- **Index Name:** `inboxPk-receivedAt-index`
- **Partition Key:** `inboxPk` (S)
- **Sort Key:** `receivedAt` (S)
- **Use Case:** List conversations for a phone number

### GSI2: Conversation Timeline

- **Index Name:** `conversationPk-receivedAt-index`
- **Partition Key:** `conversationPk` (S)
- **Sort Key:** `receivedAt` (S)
- **Use Case:** List messages in a conversation

### GSI3: Item Type Index

- **Index Name:** `itemType-receivedAt-index`
- **Partition Key:** `itemType` (S)
- **Sort Key:** `receivedAt` (S)
- **Use Case:** Query by item type (messages, templates, etc.)

### GSI4: Template Search

- **Index Name:** `wabaId-templateStatus-index`
- **Partition Key:** `wabaId` (S)
- **Sort Key:** `templateStatus` (S)
- **Use Case:** List templates by status

### GSI5: Delivery Status

- **Index Name:** `deliveryStatus-receivedAt-index`
- **Partition Key:** `deliveryStatus` (S)
- **Sort Key:** `receivedAt` (S)
- **Use Case:** Find failed messages for retry

## TTL Configuration

- **TTL Attribute:** `ttl`
- **Enabled:** Yes
- **Used By:** Idempotency records, notification records

## Access Patterns

1. **Get message by ID:** Query PK = `MSG#{messageId}`
2. **List conversations:** Query GSI1 with inboxPk
3. **Get conversation messages:** Query GSI2 with conversationPk
4. **List templates:** Query GSI4 with wabaId
5. **Find failed messages:** Query GSI5 with deliveryStatus = "failed"
6. **Get business profile:** Query PK = `TENANT#{tenantId}#BIZPROFILE#{phoneId}`
7. **Get welcome config:** Query PK = `TENANT#{tenantId}#WELCOME#default`
8. **Get menu config:** Query PK = `TENANT#{tenantId}#MENU#main`
