# WECARE.DIGITAL WhatsApp Platform - Architecture

**Account:** 010526260063 | **Region:** ap-south-1 | **Updated:** 2026-01-01

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CUSTOMERS                                       │
│   WhatsApp Users    │    Amplify Dashboard    │    External APIs            │
└──────────┬──────────────────────┬─────────────────────────┬─────────────────┘
           │                      │                         │
           ▼                      ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AWS END USER MESSAGING                                │
│  WABA 1: WECARE.DIGITAL (+919330994400)                                     │
│  WABA 2: Manish Agarwal (+919903300044)                                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SNS: base-wecare-digital                             │
│  Subscriptions: Lambda │ SQS │ API Gateway │ Email                          │
└────────┬────────────────────────┬────────────────────────┬──────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐
│   MAIN LAMBDA   │    │  API GATEWAY    │    │      AGENT CORE LAMBDA      │
│   201+ handlers │    │  o0wjog0nl4     │    │  3gxxxzll3e                 │
│   31 modules    │    │  /api endpoint  │    │  /api/chat, /api/sessions   │
└────────┬────────┘    └─────────────────┘    └─────────────────────────────┘
         │
         ├──────────────────────────────────────────────────┐
         ▼                                                  ▼
┌─────────────────────────────────┐    ┌─────────────────────────────────────┐
│           DYNAMODB              │    │              S3                      │
│  Table: base-wecare-digital-    │    │  Bucket: dev.wecare.digital         │
│         whatsapp                │    │  /WhatsApp/download/                │
│  PK: base-wecare-digital-       │    │  /WhatsApp/upload/                  │
│      whatsapp                   │    │  /SES/, /Bedrock/                   │
│  GSIs: 16                       │    └─────────────────────────────────────┘
└────────┬────────────────────────┘
         │
    ┌────┴────┬─────────────┐
    ▼         ▼             ▼
┌───────┐ ┌───────┐ ┌─────────────┐
│  SQS  │ │  SQS  │ │     SQS     │
│Inbound│ │Outbnd │ │   Bedrock   │
│Notify │ │Notify │ │   Events    │
└───┬───┘ └───┬───┘ └──────┬──────┘
    └────┬────┘            │
         ▼                 ▼
┌─────────────────┐ ┌─────────────────┐
│ EMAIL NOTIFIER  │ │ BEDROCK WORKER  │
│     LAMBDA      │ │     LAMBDA      │
│  SES emails     │ │  Agent/KB AI    │
└─────────────────┘ └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          UNIFIED LOGGING                                     │
│  Log Group: /wecare-digital/all | Retention: 7 days | TZ: Asia/Kolkata      │
│  Sources: All 4 Lambdas + Bedrock + API Gateway                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Message Flows

### Inbound (Customer → System)
```
WhatsApp → AWS EUM → SNS → Main Lambda → DynamoDB + S3
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
             SQS Notify            SQS Bedrock
                   │                     │
                   ▼                     ▼
             Email Lambda          Bedrock Worker → AI Response → User
```

### Outbound (System → Customer)
```
API Request → API Gateway → Main Lambda → AWS EUM → WhatsApp
                                │
                          DynamoDB (log) → SQS Notify → Email Lambda → SES
```

## Repository Structure

```
base.wecare.digital-whatsapp/
├── app.py                    # Lambda entry point
├── requirements.txt          # Python dependencies
├── .gitignore
├── handlers/                 # 201+ handlers (31 modules)
│   ├── __init__.py          # Package + unified_dispatch
│   ├── dispatcher.py        # Router with registry
│   ├── base.py              # Lazy clients, env, utils
│   ├── messaging.py         # send_text, send_image, send_template
│   ├── queries.py           # DynamoDB queries
│   ├── config.py            # Configuration
│   ├── templates_*.py       # Template CRUD (3 files)
│   ├── media_eum.py         # Media upload/download
│   ├── payments.py          # Payment messages
│   ├── payment_config.py    # Payment config
│   ├── refunds.py           # Refunds
│   ├── webhooks.py          # Event processing
│   ├── webhook_security.py  # Security
│   ├── notifications.py     # Email notifications
│   ├── welcome_menu.py      # Welcome + menus
│   ├── business_profile.py  # Business profile
│   ├── marketing.py         # Campaigns
│   ├── analytics.py         # Analytics
│   ├── catalogs.py          # Product catalogs
│   ├── groups.py            # Group messaging
│   ├── calling.py           # Voice calling
│   ├── flows_messaging.py   # WhatsApp Flows
│   ├── carousels.py         # Carousels
│   ├── address_messages.py  # Address collection
│   ├── throughput.py        # Rate limiting
│   ├── retry.py             # Retry logic
│   ├── event_destinations.py# AWS EUM events
│   ├── extended.py          # Extended registry
│   └── s3_paths.py          # S3 utilities
├── src/
│   ├── __init__.py
│   ├── runtime/             # Core dispatch (5 files)
│   ├── app/                 # Entry adapters (3 files)
│   ├── bedrock/             # AI integration (9 files)
│   └── notifications/       # Email (2 files)
├── deploy/                  # Deployment (4 files)
│   ├── quick-deploy.ps1     # Main deploy script
│   ├── create-full-access-role.ps1
│   ├── full-access-policy.json
│   └── env-vars.json
└── docs/                    # Documentation (2 files)
    ├── ARCHITECTURE.md      # This file
    └── RESOURCES.md         # All ARNs + configs
```

## Handler Categories (201+ handlers)

| Category | Module | Handlers | Key Actions |
|----------|--------|----------|-------------|
| Messaging | messaging.py | 16 | send_text, send_image, send_template |
| Queries | queries.py | 11 | get_messages, list_conversations |
| Config | config.py | 11 | get_config, set_config |
| Welcome/Menu | welcome_menu.py | 13 | send_welcome, send_menu |
| Templates | templates_*.py | 21 | create_template, list_templates |
| Media | media_eum.py | 8 | upload_media, download_media |
| Payments | payments.py, payment_config.py | 19 | send_payment |
| Refunds | refunds.py | 8 | process_refund |
| Webhooks | webhooks.py | 12 | process_webhook |
| Business | business_profile.py | 5 | get_business_profile |
| Marketing | marketing.py | 12 | create_campaign |
| Analytics | analytics.py | 5 | get_analytics |
| Catalogs | catalogs.py | 3 | list_products |
| Groups | groups.py | 7 | create_group |
| Calling | calling.py | 6 | initiate_call |
| Flows | flows_messaging.py | 10 | send_flow |
| Carousels | carousels.py | 3 | send_carousel |
| Address | address_messages.py | 7 | request_address |
| Throughput | throughput.py | 4 | check_rate_limit |
| Retry | retry.py | 6 | retry_message |
| Events | event_destinations.py | 5 | configure_events |
| Notifications | notifications.py | 5 | send_notification |
| Bedrock | src/bedrock/*.py | 16 | invoke_agent, query_kb |

## Quick Commands

```powershell
# Deploy
.\deploy\quick-deploy.ps1

# Test
aws lambda invoke --function-name base-wecare-digital-whatsapp:live --payload '{"action":"ping"}' out.json --region ap-south-1

# Logs
aws logs tail /wecare-digital/all --follow --region ap-south-1
```
