# AWS Resources - WECARE.DIGITAL WhatsApp Platform

**Account ID:** `010526260063`  
**Region:** `ap-south-1` (Mumbai)  
**Last Updated:** 2025-12-31

---

## 1. Lambda Functions

### 1.1 Main Lambda - `base-wecare-digital-whatsapp`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp` |
| Runtime | Python 3.12 |
| Function URL | `https://tovlswqncgn624kl6hxbyj65qe0hiizw.lambda-url.ap-south-1.on.aws/` |
| API Gateway | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com/api` |

**Environment Variables:**
| Variable | Value |
|----------|-------|
| MESSAGES_TABLE_NAME | `base-wecare-digital-whatsapp` |
| MESSAGES_PK_NAME | `base-wecare-digital-whatsapp` |
| MEDIA_BUCKET | `dev.wecare.digital` |
| MEDIA_PREFIX | `WhatsApp/` |
| META_API_VERSION | `v20.0` |
| AUTO_REPLY_ENABLED | `true` |
| AUTO_REPLY_TEXT | `Thanks! We received your message. This is an auto-reply from WECARE.DIGITAL` |
| AUTO_REPLY_BEDROCK_ENABLED | `true` |
| ECHO_MEDIA_BACK | `true` |
| MARK_AS_READ_ENABLED | `true` |
| REACT_EMOJI_ENABLED | `true` |
| FORWARD_ENABLED | `false` |
| EMAIL_NOTIFICATION_ENABLED | `true` |
| EMAIL_SNS_TOPIC_ARN | `arn:aws:sns:ap-south-1:010526260063:base-wecare-digital` |
| BEDROCK_REGION | `ap-south-1` |
| BEDROCK_MODEL_ID | `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` |
| BEDROCK_AGENT_ID | `UFVSBWGCIU` |
| BEDROCK_AGENT_ALIAS_ID | `IDEFJTWLLK` |
| BEDROCK_KB_ID | `NVF0OLULMG` |

### 1.2 Email Notifier - `base-wecare-digital-whatsapp-email-notifier`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp-email-notifier` |
| Runtime | Python 3.12 |
| Triggers | SQS (inbound-notify, outbound-notify) |

**Environment Variables:**
| Variable | Value |
|----------|-------|
| INBOUND_NOTIFY_TO | `selfcare@wecare.digital` |
| MEDIA_BUCKET | `s3://dev.wecare.digital/SES/` |
| MESSAGES_TABLE_NAME | `base-wecare-digital-whatsapp` |
| OUTBOUND_NOTIFY_TO | `selfcare@wecare.digital` |
| SES_REPLY_TO | `one@wecare.digital` |
| SES_SENDER_EMAIL | `one@wecare.digital` |
| SES_SENDER_NAME | `WECARE.DIGITAL for sms use +91 9330994400 with 130 chatrts short sms with option to disable if high charges are there` |

### 1.3 Bedrock Worker - `base-wecare-digital-whatsapp-bedrock-worker`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp-bedrock-worker` |
| Runtime | Python 3.12 |
| Triggers | SQS (bedrock-events) |

**Environment Variables:**
| Variable | Value |
|----------|-------|
| MESSAGES_TABLE_NAME | `base-wecare-digital-whatsapp` |
| MEDIA_BUCKET | `s3://dev.wecare.digital/Bedrock/` |
| BEDROCK_REGION | `ap-south-1` |
| BEDROCK_MODEL_ID | `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` |
| BEDROCK_AGENT_ID | `UFVSBWGCIU` |
| BEDROCK_AGENT_ALIAS_ID | `IDEFJTWLLK` |
| BEDROCK_KB_ID | `NVF0OLULMG` |
| AUTO_REPLY_BEDROCK_ENABLED | `false` |

---

## 2. DynamoDB

### Table: `base-wecare-digital-whatsapp`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:dynamodb:ap-south-1:010526260063:table/base-wecare-digital-whatsapp` |
| Partition Key | `base-wecare-digital-whatsapp` (pk) |
| Sort Key | `sk` |
| Billing | On-Demand |

**Global Secondary Indexes (16):**
| GSI Name | Purpose |
|----------|---------|
| gsi_order | Order lookups |
| gsi_payment_status | Payment status queries |
| gsi_template_name | Template by name |
| gsi_group | Group message queries |
| gsi_tenant | Multi-tenant queries |
| gsi_waba_itemtype | WABA + item type queries |
| gsi_webhook_event | Webhook event lookups |
| gsi_customer_phone | Customer phone lookups |
| gsi_direction | Inbound/outbound queries |
| gsi_conversation | Conversation threads |
| gsi_campaign | Campaign queries |
| gsi_from | Sender queries |
| gsi_inbox | Inbox queries |
| gsi_catalog | Catalog queries |
| gsi_status | Status queries |
| gsi_template_waba | Template + WABA queries |

---

## 3. S3 Bucket

### Bucket: `dev.wecare.digital`

**Folder Structure:**
```
s3://dev.wecare.digital/
├── WhatsApp/                    ← Main Lambda (WhatsApp media)
│   ├── download/                ← INBOUND media (received from customers)
│   │   ├── wecare/              ← WABA 1347766229904230
│   │   └── manish/              ← WABA 1390647332755815
│   └── upload/                  ← OUTBOUND media (sent to customers)
│       ├── wecare/
│       └── manish/
├── SES/                         ← Email Notifier Lambda
└── Bedrock/                     ← Bedrock Worker Lambda
    ├── AWSLogs/
    ├── agents/
    ├── kb/
    └── logs/
```

**Folder → Lambda Mapping:**
| S3 Path | Lambda | Purpose |
|---------|--------|---------|
| `s3://dev.wecare.digital/WhatsApp/` | Main Lambda | WhatsApp media storage |
| `s3://dev.wecare.digital/SES/` | Email Notifier | SES email attachments |
| `s3://dev.wecare.digital/Bedrock/` | Bedrock Worker | Bedrock agent/KB data |

---

## 4. SQS Queues

| Queue | ARN | Purpose |
|-------|-----|---------|
| `base-wecare-digital-whatsapp-webhooks` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-webhooks` | Webhook events from SNS |
| `base-wecare-digital-whatsapp-inbound-notify` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-inbound-notify` | Inbound email notifications |
| `base-wecare-digital-whatsapp-outbound-notify` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-outbound-notify` | Outbound email notifications |
| `base-wecare-digital-whatsapp-bedrock-events` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-bedrock-events` | Bedrock processing queue |
| `base-wecare-digital-whatsapp-dlq` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-dlq` | Main DLQ |
| `base-wecare-digital-whatsapp-notify-dlq` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-notify-dlq` | Notification DLQ |
| `base-wecare-digital-whatsapp-bedrock-dlq` | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-bedrock-dlq` | Bedrock DLQ |

---

## 5. SNS Topic

### Topic: `base-wecare-digital`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:sns:ap-south-1:010526260063:base-wecare-digital` |

**Subscriptions:**
| Protocol | Endpoint | Purpose |
|----------|----------|---------|
| lambda | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp:live` | Main Lambda (live alias) |
| sqs | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-webhooks` | Webhook queue |
| https | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com` | API Gateway |
| email-json | `base@wecare.digital` | Email notifications |

---

## 6. AWS End User Messaging (EUM) - WhatsApp

### Linked WABA Accounts

#### WABA 1: WECARE.DIGITAL
| Property | Value |
|----------|-------|
| WABA ID | `1347766229904230` |
| WABA Name | `WECARE.DIGITAL` |
| AWS WABA ARN | `arn:aws:social-messaging:ap-south-1:010526260063:waba/60e8e476c4714b9f9ec14d78f5162ee7` |
| Phone Number | `+919330994400` |
| Phone ARN | `arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/3f8934395ae24a4583a413087a3d3fb0` |
| Meta Phone Number ID | `831049713436137` |
| S3 Folder | `wecare` |
| Event Destination | `arn:aws:sns:ap-south-1:010526260063:base-wecare-digital` |

#### WABA 2: Manish Agarwal
| Property | Value |
|----------|-------|
| WABA ID | `1390647332755815` |
| WABA Name | `Manish Agarwal` |
| AWS WABA ARN | `arn:aws:social-messaging:ap-south-1:010526260063:waba/4a0270d5a59a46778b600931a63fc97b` |
| Phone Number | `+919903300044` |
| Phone ARN | `arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/0b0d77d6d54645d991db7aa9cf1b0eb2` |
| Meta Phone Number ID | `888782840987368` |
| S3 Folder | `manish` |
| Event Destination | `arn:aws:sns:ap-south-1:010526260063:base-wecare-digital` |

---

## 7. Amazon Bedrock

### Agent: `base-wecare-digital-whatsapp`
| Property | Value |
|----------|-------|
| Agent ID | `UFVSBWGCIU` |
| Agent Alias ID | `IDEFJTWLLK` |
| Status | `PREPARED` |
| Model | `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` |

### Knowledge Base: `base-wecare-wa-kb`
| Property | Value |
|----------|-------|
| KB ID | `NVF0OLULMG` |
| Status | `ACTIVE` |
| Data Source | `s3://dev.wecare.digital/Bedrock/kb/` |

---

## 8. IAM Role

### Role: `base-wecare-digital-whatsapp-full-access-role`
| Property | Value |
|----------|-------|
| ARN | `arn:aws:iam::010526260063:role/base-wecare-digital-whatsapp-full-access-role` |

**Permissions:**
- DynamoDB full access to `base-wecare-digital-whatsapp` table
- S3 full access to `dev.wecare.digital` bucket
- SQS full access to all project queues
- SNS publish to `base-wecare-digital` topic
- SES send email
- Bedrock invoke agent/model
- Social Messaging (EUM) send/receive
- CloudWatch Logs

---

## 9. API Endpoints

| Endpoint | URL |
|----------|-----|
| API Gateway | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com/api` |
| Lambda Function URL | `https://tovlswqncgn624kl6hxbyj65qe0hiizw.lambda-url.ap-south-1.on.aws/` |

---

## 10. Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INBOUND MESSAGE FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WhatsApp User                                                               │
│       │                                                                      │
│       ▼                                                                      │
│  AWS EUM (Social Messaging)                                                  │
│       │                                                                      │
│       ▼                                                                      │
│  SNS Topic (base-wecare-digital)                                             │
│       │                                                                      │
│       ├──────────────────┬──────────────────┬──────────────────┐            │
│       ▼                  ▼                  ▼                  ▼            │
│  Main Lambda        SQS Webhooks      API Gateway        Email (base@)      │
│       │                                                                      │
│       ├─────────────────────────────────────────────────────────┐           │
│       ▼                                                         ▼           │
│  DynamoDB                                              S3 (WhatsApp/download)│
│       │                                                                      │
│       ├──────────────────┬──────────────────┐                               │
│       ▼                  ▼                  ▼                               │
│  SQS Inbound-Notify  SQS Bedrock-Events  Auto-Reply                         │
│       │                  │                                                   │
│       ▼                  ▼                                                   │
│  Email Notifier      Bedrock Worker                                          │
│       │                  │                                                   │
│       ▼                  ▼                                                   │
│  SES Email           AI Response                                             │
│                          │                                                   │
│                          ▼                                                   │
│                     AWS EUM → WhatsApp User                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           OUTBOUND MESSAGE FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  API Request (send_text, send_template, etc.)                                │
│       │                                                                      │
│       ▼                                                                      │
│  API Gateway / Lambda Function URL                                           │
│       │                                                                      │
│       ▼                                                                      │
│  Main Lambda                                                                 │
│       │                                                                      │
│       ├─────────────────────────────────────────────────────────┐           │
│       ▼                                                         ▼           │
│  AWS EUM (send_whatsapp_message)                        DynamoDB (log)      │
│       │                                                         │           │
│       ▼                                                         ▼           │
│  WhatsApp User                                          SQS Outbound-Notify │
│                                                                 │           │
│                                                                 ▼           │
│                                                         Email Notifier      │
│                                                                 │           │
│                                                                 ▼           │
│                                                         SES Email           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Test Numbers

| Number | Type | Notes |
|--------|------|-------|
| `+447447840003` | UK Test Number | No 24-hour rule, instant delivery |

---

## 12. Payment Configuration

### WABA 1347766229904230 (WECARE.DIGITAL)
| Provider | Config |
|----------|--------|
| Razorpay | MID: `acc_HDfub6wOfQybuH`, MCC: 4722 |
| UPI | ID: `9330994400@sbi` |

### WABA 1390647332755815 (Manish Agarwal)
| Provider | Config |
|----------|--------|
| Razorpay | MID: `acc_HDfub6wOfQybuH`, MCC: 4722 |
| UPI | ID: `9330994400@sbi` |
