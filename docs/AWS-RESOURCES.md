# AWS Resources - WECARE.DIGITAL WhatsApp Platform

**Account:** 010526260063 | **Region:** ap-south-1 (Mumbai) | **Updated:** 2026-01-01

---

## Lambda Functions (4)

| Function | ARN | Purpose |
|----------|-----|---------|
| Main | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp` | 201+ handlers |
| Email Notifier | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp-email-notifier` | SES emails |
| Bedrock Worker | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp-bedrock-worker` | AI processing |
| Agent Core | `arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp-agent-core` | Amplify API |

**All Lambdas:**
- Runtime: Python 3.12
- Log Group: `/wecare-digital/all` (7-day retention)
- Timezone: `TZ=Asia/Kolkata`
- Role: `base-wecare-digital-whatsapp-full-access-role`

---

## API Endpoints (2)

| API | ID | Endpoint |
|-----|-----|----------|
| Main WhatsApp | `o0wjog0nl4` | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com/api` |
| Agent Core | `3gxxxzll3e` | `https://3gxxxzll3e.execute-api.ap-south-1.amazonaws.com` |

**Lambda Function URL:** `https://tovlswqncgn624kl6hxbyj65qe0hiizw.lambda-url.ap-south-1.on.aws/`

---

## DynamoDB

| Property | Value |
|----------|-------|
| Table | `base-wecare-digital-whatsapp` |
| ARN | `arn:aws:dynamodb:ap-south-1:010526260063:table/base-wecare-digital-whatsapp` |
| PK | `base-wecare-digital-whatsapp` |
| SK | `sk` |
| Billing | On-Demand |
| GSIs | 16 |

**GSI Names:** gsi_order, gsi_payment_status, gsi_template_name, gsi_group, gsi_tenant, gsi_waba_itemtype, gsi_webhook_event, gsi_customer_phone, gsi_direction, gsi_conversation, gsi_campaign, gsi_from, gsi_inbox, gsi_catalog, gsi_status, gsi_template_waba

---

## S3 Bucket

| Property | Value |
|----------|-------|
| Bucket | `dev.wecare.digital` |
| Region | ap-south-1 |

**Folder Structure:**
```
s3://dev.wecare.digital/
├── WhatsApp/
│   ├── download/wecare/     # Inbound media WABA 1
│   ├── download/manish/     # Inbound media WABA 2
│   ├── upload/wecare/       # Outbound media WABA 1
│   └── upload/manish/       # Outbound media WABA 2
├── SES/                     # Email attachments
└── Bedrock/
    ├── agent/               # Bedrock Worker
    ├── agent-core/          # AgentCore
    └── kb/                  # Knowledge Base
```

---

## SQS Queues (7)

| Queue | ARN |
|-------|-----|
| Webhooks | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-webhooks` |
| Inbound Notify | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-inbound-notify` |
| Outbound Notify | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-outbound-notify` |
| Bedrock Events | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-bedrock-events` |
| DLQ | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-dlq` |
| Notify DLQ | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-notify-dlq` |
| Bedrock DLQ | `arn:aws:sqs:ap-south-1:010526260063:base-wecare-digital-whatsapp-bedrock-dlq` |

---

## SNS Topic

| Property | Value |
|----------|-------|
| Topic | `base-wecare-digital` |
| ARN | `arn:aws:sns:ap-south-1:010526260063:base-wecare-digital` |

**Subscriptions:** Lambda (live), SQS (webhooks), API Gateway, Email (base@wecare.digital)

---

## WhatsApp Business Accounts (2)

### WABA 1: WECARE.DIGITAL
| Property | Value |
|----------|-------|
| WABA ID | `1347766229904230` |
| Phone | `+919330994400` |
| AWS WABA ARN | `arn:aws:social-messaging:ap-south-1:010526260063:waba/60e8e476c4714b9f9ec14d78f5162ee7` |
| Phone ARN | `arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/3f8934395ae24a4583a413087a3d3fb0` |
| Meta Phone ID | `831049713436137` |
| S3 Folder | `wecare` |

### WABA 2: Manish Agarwal
| Property | Value |
|----------|-------|
| WABA ID | `1390647332755815` |
| Phone | `+919903300044` |
| AWS WABA ARN | `arn:aws:social-messaging:ap-south-1:010526260063:waba/4a0270d5a59a46778b600931a63fc97b` |
| Phone ARN | `arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/0b0d77d6d54645d991db7aa9cf1b0eb2` |
| Meta Phone ID | `888782840987368` |
| S3 Folder | `manish` |

---

## Bedrock AI

| Resource | ID | Model |
|----------|-----|-------|
| Agent | `UFVSBWGCIU` | amazon.nova-2-lite-v1:0 |
| Agent Alias | `IDEFJTWLLK` | - |
| Knowledge Base | `NVF0OLULMG` | - |
| AgentCore | `wecareinternalagent_Agent-9bq7z65aEP` | amazon.nova-2-lite-v1:0 |

---

## IAM Role

| Property | Value |
|----------|-------|
| Role | `base-wecare-digital-whatsapp-full-access-role` |
| ARN | `arn:aws:iam::010526260063:role/base-wecare-digital-whatsapp-full-access-role` |

**Permissions:** Full access to DynamoDB, S3, SNS, SES, SQS, Lambda, API Gateway, EventBridge, Bedrock, CloudWatch, IAM, KMS, Secrets Manager

**Trust:** lambda, bedrock, bedrock-agentcore, states, events, apigateway, sqs, sns, s3

---

## CloudWatch Logging

| Property | Value |
|----------|-------|
| Log Group | `/wecare-digital/all` |
| Retention | 7 days |
| Format | JSON |
| Timezone | IST (Asia/Kolkata) |

---

## Payment Config

| Business | Gateway MID | UPI ID |
|----------|-------------|--------|
| WECARE.DIGITAL | `acc_HDfub6wOfQybuH` | `9330994400@sbi` |
| Manish Agarwal | `acc_HDfub6wOfQybuH` | `9330994400@sbi` |

---

## Environment Variables (Main Lambda)

```json
{
  "MESSAGES_TABLE_NAME": "base-wecare-digital-whatsapp",
  "MESSAGES_PK_NAME": "base-wecare-digital-whatsapp",
  "MEDIA_BUCKET": "dev.wecare.digital",
  "MEDIA_PREFIX": "WhatsApp/",
  "META_API_VERSION": "v20.0",
  "AUTO_REPLY_ENABLED": "true",
  "AUTO_REPLY_BEDROCK_ENABLED": "true",
  "MARK_AS_READ_ENABLED": "true",
  "REACT_EMOJI_ENABLED": "true",
  "EMAIL_NOTIFICATION_ENABLED": "true",
  "EMAIL_SNS_TOPIC_ARN": "arn:aws:sns:ap-south-1:010526260063:base-wecare-digital",
  "BEDROCK_REGION": "ap-south-1",
  "BEDROCK_MODEL_ID": "amazon.nova-2-lite-v1:0",
  "BEDROCK_AGENT_ID": "UFVSBWGCIU",
  "BEDROCK_AGENT_ALIAS_ID": "IDEFJTWLLK",
  "BEDROCK_KB_ID": "NVF0OLULMG",
  "TZ": "Asia/Kolkata"
}
```

---

## Quick Commands

```powershell
# Deploy
.\deploy\quick-deploy.ps1

# Test
aws lambda invoke --function-name base-wecare-digital-whatsapp --payload '{"action":"ping"}' out.json --region ap-south-1

# Logs
aws logs tail /wecare-digital/all --follow --region ap-south-1

# Send message
aws lambda invoke --function-name base-wecare-digital-whatsapp --payload '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919876543210","text":"Hello!"}' out.json --region ap-south-1
```
