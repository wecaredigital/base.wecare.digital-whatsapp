# WECARE.DIGITAL WhatsApp Platform - Architecture

**Last Updated:** 2026-01-01  
**Region:** ap-south-1 (Mumbai)  
**Account:** 010526260063

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        WECARE.DIGITAL WhatsApp Platform                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │  WhatsApp   │     │   Amplify   │     │  External   │     │    Admin    │       │
│  │    Users    │     │  Dashboard  │     │    APIs     │     │     CLI     │       │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│         │                   │                   │                   │              │
│         ▼                   ▼                   ▼                   ▼              │
│  ┌─────────────────────────────────────────────────────────────────────────┐       │
│  │                         AWS End User Messaging                           │       │
│  │                    (Social Messaging - WhatsApp)                         │       │
│  │  WABA 1: +919330994400 (WECARE.DIGITAL)                                 │       │
│  │  WABA 2: +919903300044 (Manish Agarwal)                                 │       │
│  └──────────────────────────────┬──────────────────────────────────────────┘       │
│                                 │                                                   │
│                                 ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐       │
│  │                           SNS Topic                                      │       │
│  │                    base-wecare-digital                                   │       │
│  └───────┬─────────────────┬─────────────────┬─────────────────┬───────────┘       │
│          │                 │                 │                 │                    │
│          ▼                 ▼                 ▼                 ▼                    │
│  ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐              │
│  │  Lambda   │     │    SQS    │     │    API    │     │   Email   │              │
│  │  (Main)   │     │ Webhooks  │     │  Gateway  │     │  (base@)  │              │
│  └─────┬─────┘     └───────────┘     └───────────┘     └───────────┘              │
│        │                                                                            │
│        ├────────────────────────────────────────────────────────────┐              │
│        ▼                                                            ▼              │
│  ┌─────────────┐                                           ┌─────────────┐         │
│  │  DynamoDB   │                                           │     S3      │         │
│  │  (16 GSIs)  │                                           │   Media     │         │
│  └──────┬──────┘                                           └─────────────┘         │
│         │                                                                           │
│         ├──────────────────┬──────────────────┬──────────────────┐                 │
│         ▼                  ▼                  ▼                  ▼                 │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐      ┌───────────┐           │
│  │    SQS    │      │    SQS    │      │    SQS    │      │ EventBridge│           │
│  │  Inbound  │      │ Outbound  │      │  Bedrock  │      │  (5 rules) │           │
│  │  Notify   │      │  Notify   │      │  Events   │      └───────────┘           │
│  └─────┬─────┘      └─────┬─────┘      └─────┬─────┘                              │
│        │                  │                  │                                      │
│        ▼                  ▼                  ▼                                      │
│  ┌─────────────────────────────┐      ┌─────────────┐                              │
│  │      Email Notifier         │      │   Bedrock   │                              │
│  │         Lambda              │      │   Worker    │                              │
│  └──────────────┬──────────────┘      └──────┬──────┘                              │
│                 │                            │                                      │
│                 ▼                            ▼                                      │
│  ┌─────────────────────────────┐      ┌─────────────────────────────┐              │
│  │           SES               │      │         Bedrock             │              │
│  │     (HTML Emails)           │      │  Agent + KB + Nova Lite     │              │
│  └─────────────────────────────┘      └─────────────────────────────┘              │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐       │
│  │                      Agent Core API (Amplify)                            │       │
│  │  API: https://3gxxxzll3e.execute-api.ap-south-1.amazonaws.com           │       │
│  │  Lambda: base-wecare-digital-whatsapp-agent-core                        │       │
│  │  Routes: /api/chat, /api/sessions, /api/invoke-agent, /api/query-kb     │       │
│  └─────────────────────────────────────────────────────────────────────────┘       │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐       │
│  │                         Unified Logging                                  │       │
│  │  Log Group: /wecare-digital/all (7-day retention, IST timezone)         │       │
│  └─────────────────────────────────────────────────────────────────────────┘       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Lambda Functions (4)

| Function | Purpose | Trigger | Log Group |
|----------|---------|---------|-----------|
| `base-wecare-digital-whatsapp` | Main handler (201+ actions) | SNS, API GW, Direct | `/wecare-digital/all` |
| `base-wecare-digital-whatsapp-email-notifier` | Email notifications | SQS | `/wecare-digital/all` |
| `base-wecare-digital-whatsapp-bedrock-worker` | AI processing | SQS | `/wecare-digital/all` |
| `base-wecare-digital-whatsapp-agent-core` | Amplify frontend API | API GW | `/wecare-digital/all` |

### 2. API Endpoints (2)

| API | Endpoint | Purpose |
|-----|----------|---------|
| Main API | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com/api` | WhatsApp handlers |
| Agent Core | `https://3gxxxzll3e.execute-api.ap-south-1.amazonaws.com` | Amplify dashboard |

### 3. DynamoDB (1 Table, 16 GSIs)

**Table:** `base-wecare-digital-whatsapp`  
**PK:** `base-wecare-digital-whatsapp` | **SK:** `sk`

| GSI | Purpose |
|-----|---------|
| gsi_order | Order lookups |
| gsi_payment_status | Payment queries |
| gsi_template_name | Template by name |
| gsi_group | Group messages |
| gsi_tenant | Multi-tenant |
| gsi_waba_itemtype | WABA + type |
| gsi_webhook_event | Webhook events |
| gsi_customer_phone | Customer lookup |
| gsi_direction | In/outbound |
| gsi_conversation | Threads |
| gsi_campaign | Campaigns |
| gsi_from | Sender |
| gsi_inbox | Inbox |
| gsi_catalog | Catalogs |
| gsi_status | Status |
| gsi_template_waba | Template + WABA |

### 4. SQS Queues (7)

| Queue | Purpose |
|-------|---------|
| `webhooks` | Webhook events |
| `inbound-notify` | Inbound email alerts |
| `outbound-notify` | Outbound email alerts |
| `bedrock-events` | AI processing |
| `dlq` | Main dead letter |
| `notify-dlq` | Notification DLQ |
| `bedrock-dlq` | Bedrock DLQ |

### 5. S3 Bucket

**Bucket:** `dev.wecare.digital`

```
s3://dev.wecare.digital/
├── WhatsApp/
│   ├── download/wecare/     ← Inbound media (WABA 1)
│   ├── download/manish/     ← Inbound media (WABA 2)
│   ├── upload/wecare/       ← Outbound media (WABA 1)
│   └── upload/manish/       ← Outbound media (WABA 2)
├── SES/                     ← Email attachments
└── Bedrock/
    ├── agent/               ← Bedrock Worker data
    ├── agent-core/          ← AgentCore deployments
    └── kb/                  ← Knowledge Base docs
```

### 6. Bedrock AI

| Resource | ID | Model |
|----------|-----|-------|
| Agent | `UFVSBWGCIU` | amazon.nova-2-lite-v1:0 |
| Agent Alias | `IDEFJTWLLK` | - |
| Knowledge Base | `NVF0OLULMG` | - |
| AgentCore | `wecareinternalagent_Agent-9bq7z65aEP` | amazon.nova-2-lite-v1:0 |

### 7. WhatsApp Business Accounts (2)

| Business | WABA ID | Phone | S3 Folder |
|----------|---------|-------|-----------|
| WECARE.DIGITAL | `1347766229904230` | +919330994400 | `wecare` |
| Manish Agarwal | `1390647332755815` | +919903300044 | `manish` |

---

## Message Flows

### Inbound (Customer → System)
```
WhatsApp User → AWS EUM → SNS → Main Lambda → DynamoDB
                                     ↓
                              ┌──────┴──────┐
                              ▼             ▼
                        SQS Notify    SQS Bedrock
                              ↓             ↓
                        Email Lambda  Bedrock Worker
                              ↓             ↓
                           SES Email   AI Response → AWS EUM → User
```

### Outbound (System → Customer)
```
API Request → API Gateway → Main Lambda → AWS EUM → WhatsApp User
                                 ↓
                           DynamoDB (log)
                                 ↓
                           SQS Notify → Email Lambda → SES
```

---

## Handler Categories (201+ handlers in 31 modules)

| Category | Module | Handlers |
|----------|--------|----------|
| Messaging | `messaging.py` | 16 |
| Queries | `queries.py` | 11 |
| Config | `config.py` | 11 |
| Welcome/Menu | `welcome_menu.py` | 13 |
| Templates | `templates_eum.py`, `templates_meta.py`, `template_library.py` | 21 |
| Media | `media_eum.py` | 8 |
| Payments | `payments.py`, `payment_config.py`, `refunds.py` | 27 |
| Webhooks | `webhooks.py`, `webhook_security.py` | 12 |
| Business | `business_profile.py` | 5 |
| Marketing | `marketing.py` | 12 |
| Analytics | `analytics.py` | 5 |
| Catalogs | `catalogs.py` | 3 |
| Groups | `groups.py` | 7 |
| Calling | `calling.py` | 6 |
| Flows | `flows_messaging.py` | 10 |
| Carousels | `carousels.py` | 3 |
| Address | `address_messages.py` | 7 |
| Throughput | `throughput.py` | 4 |
| Retry | `retry.py` | 6 |
| Events | `event_destinations.py` | 5 |
| Notifications | `notifications.py` | 5 |
| Bedrock | `src/bedrock/handlers.py`, `api_handlers.py` | 16 |

---

## IAM Role

**Role:** `base-wecare-digital-whatsapp-full-access-role`

Used by ALL resources with full access to:
- DynamoDB, S3, SNS, SES, SQS
- Lambda, API Gateway, EventBridge
- Bedrock, OpenSearch Serverless
- CloudWatch, IAM, KMS, Secrets Manager

---

## Quick Commands

```powershell
# Deploy main Lambda
.\deploy\deploy-167-handlers.ps1

# Test ping
aws lambda invoke --function-name base-wecare-digital-whatsapp --payload '{"action":"ping"}' out.json --region ap-south-1

# View logs
aws logs tail /wecare-digital/all --follow --region ap-south-1

# Send test message
aws lambda invoke --function-name base-wecare-digital-whatsapp --payload '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919876543210","text":"Hello!"}' out.json --region ap-south-1
```
