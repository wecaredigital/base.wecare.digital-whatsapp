# WECARE.DIGITAL WhatsApp Platform

**Last Updated:** 2026-01-01 | **Region:** ap-south-1 | **Account:** 010526260063

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    CUSTOMERS                                         │
│                                                                                      │
│     ┌──────────────┐          ┌──────────────┐          ┌──────────────┐            │
│     │   WhatsApp   │          │   Amplify    │          │   External   │            │
│     │    Users     │          │  Dashboard   │          │    APIs      │            │
│     └──────┬───────┘          └──────┬───────┘          └──────┬───────┘            │
│            │                         │                         │                    │
└────────────┼─────────────────────────┼─────────────────────────┼────────────────────┘
             │                         │                         │
             ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS END USER MESSAGING                                  │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  WABA 1: WECARE.DIGITAL (+919330994400)                                     │   │
│  │  WABA 2: Manish Agarwal (+919903300044)                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                              │
└──────────────────────────────────────┼──────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  SNS TOPIC                                           │
│                           base-wecare-digital                                        │
│                                                                                      │
│  Subscriptions: Lambda (live) │ SQS (webhooks) │ API Gateway │ Email (base@)       │
└───────────┬──────────────────────────┬──────────────────────────┬───────────────────┘
            │                          │                          │
            ▼                          ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│   MAIN LAMBDA     │      │   API GATEWAY     │      │   AGENT CORE      │
│                   │      │                   │      │   LAMBDA          │
│ 201+ handlers     │      │ o0wjog0nl4        │      │                   │
│ 31 modules        │      │ /api endpoint     │      │ 3gxxxzll3e        │
└─────────┬─────────┘      └───────────────────┘      │ /api/chat         │
          │                                           │ /api/sessions     │
          │                                           └───────────────────┘
          │
          ├────────────────────────────────────────────────────────────────┐
          │                                                                │
          ▼                                                                ▼
┌───────────────────────────────────────┐              ┌───────────────────────────┐
│              DYNAMODB                  │              │            S3             │
│                                        │              │                           │
│  Table: base-wecare-digital-whatsapp   │              │  Bucket: dev.wecare.digital│
│  PK: base-wecare-digital-whatsapp      │              │                           │
│  SK: sk                                │              │  /WhatsApp/download/      │
│  GSIs: 16                              │              │  /WhatsApp/upload/        │
│                                        │              │  /SES/                    │
│  Patterns:                             │              │  /Bedrock/                │
│  MSG#, CONV#, TENANT#, TEMPLATE#       │              │                           │
│  ORDER#, MEDIA#, BEDROCK#, EMAIL#      │              └───────────────────────────┘
│  MENU#, WELCOME#, PAYCFG#, QUALITY#    │
└────────────────────┬───────────────────┘
                     │
     ┌───────────────┼───────────────┬───────────────┐
     │               │               │               │
     ▼               ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐
│   SQS   │   │   SQS   │   │   SQS   │   │ EVENTBRIDGE │
│ Inbound │   │Outbound │   │ Bedrock │   │  (5 rules)  │
│ Notify  │   │ Notify  │   │ Events  │   └─────────────┘
└────┬────┘   └────┬────┘   └────┬────┘
     │             │             │
     └──────┬──────┘             │
            ▼                    ▼
┌───────────────────┐   ┌───────────────────┐
│  EMAIL NOTIFIER   │   │  BEDROCK WORKER   │
│     LAMBDA        │   │     LAMBDA        │
│                   │   │                   │
│  SES HTML emails  │   │  Agent: UFVSBWGCIU│
│  to: selfcare@    │   │  KB: NVF0OLULMG   │
│  from: one@       │   │  Model: Nova Lite │
└───────────────────┘   └───────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              UNIFIED LOGGING                                         │
│                                                                                      │
│  Log Group: /wecare-digital/all                                                     │
│  Retention: 7 days                                                                  │
│  Timezone: IST (Asia/Kolkata)                                                       │
│  Format: JSON                                                                       │
│                                                                                      │
│  Sources: All 4 Lambdas + Bedrock + API Gateway + SNS                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Message Flows

### Inbound (Customer → System)
```
WhatsApp → AWS EUM → SNS → Main Lambda → DynamoDB + S3
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
              SQS Notify              SQS Bedrock
                    │                       │
                    ▼                       ▼
              Email Lambda           Bedrock Worker
                    │                       │
                    ▼                       ▼
                SES Email            AI Response → EUM → User
```

### Outbound (System → Customer)
```
API Request → API Gateway → Main Lambda → AWS EUM → WhatsApp
                                │
                          DynamoDB (log)
                                │
                          SQS Notify → Email Lambda → SES
```

---

## Repository Structure

```
base.wecare.digital-whatsapp/
├── app.py                    # Lambda entry point
├── requirements.txt          # Python dependencies
├── .gitignore
│
├── handlers/                 # 201+ action handlers (31 modules)
│   ├── __init__.py          # Package + unified_dispatch
│   ├── dispatcher.py        # Router with registry
│   ├── base.py              # Lazy clients, env, utils
│   ├── messaging.py         # send_text, send_image, send_template
│   ├── queries.py           # DynamoDB queries
│   ├── config.py            # Configuration
│   ├── templates_eum.py     # AWS EUM template CRUD
│   ├── templates_meta.py    # Template validation
│   ├── template_library.py  # Template library
│   ├── media_eum.py         # Media upload/download
│   ├── marketing.py         # Campaigns
│   ├── payments.py          # Payment messages
│   ├── payment_config.py    # Payment config
│   ├── refunds.py           # Refunds
│   ├── business_profile.py  # Business profile
│   ├── welcome_menu.py      # Welcome + menus
│   ├── notifications.py     # Email notifications
│   ├── webhooks.py          # Event processing
│   ├── webhook_security.py  # Security
│   ├── event_destinations.py# AWS EUM events
│   ├── analytics.py         # Analytics
│   ├── catalogs.py          # Product catalogs
│   ├── groups.py            # Group messaging
│   ├── calling.py           # Voice calling
│   ├── flows_messaging.py   # WhatsApp Flows
│   ├── carousels.py         # Carousels
│   ├── address_messages.py  # Address collection
│   ├── throughput.py        # Rate limiting
│   ├── retry.py             # Retry logic
│   ├── extended.py          # Extended registry
│   └── s3_paths.py          # S3 utilities
│
├── src/
│   ├── __init__.py
│   ├── cli.py               # Admin CLI
│   ├── runtime/             # Core dispatch
│   │   ├── envelope.py      # Request envelope
│   │   ├── parse_event.py   # Event detection
│   │   ├── dispatch.py      # Dispatcher
│   │   └── deps.py          # DI container
│   ├── app/                 # Entry adapters
│   │   ├── api_handler.py   # API Gateway
│   │   ├── inbound_handler.py # SNS/SQS
│   │   └── direct_handler.py  # Direct invoke
│   ├── bedrock/             # AI integration
│   │   ├── agent.py         # Bedrock Agent
│   │   ├── strands_agent.py # Strands SDK
│   │   ├── processor.py     # Multimedia
│   │   ├── handlers.py      # Worker handler
│   │   ├── api_handlers.py  # Agent Core API
│   │   ├── api_lambda.py    # API Lambda
│   │   ├── agent_core.py    # Core logic
│   │   └── client.py        # Client
│   └── notifications/
│       └── email_notifier.py # SES emails
│
├── tests/                   # Test suite
│   ├── test_all_handlers.py
│   ├── test_runtime.py
│   └── ...
│
├── deploy/                  # Deployment scripts
│   ├── deploy-167-handlers.ps1
│   ├── quick-deploy.ps1
│   ├── setup-*.ps1
│   ├── *.json               # IAM policies
│   └── menu-data/           # Menu configs
│
├── cdk/                     # CDK IaC
│   ├── bin/app.ts
│   └── lib/*.ts
│
├── docs/
│   ├── ARCHITECTURE.md      # This file
│   └── AWS-RESOURCES.md     # All ARNs + configs
│
└── .github/workflows/       # CI/CD
    ├── pr-check.yml
    └── deploy.yml
```

---

## Handler Categories (201+ handlers)

| Category | Module | Count | Key Actions |
|----------|--------|-------|-------------|
| Messaging | messaging.py | 16 | send_text, send_image, send_template |
| Queries | queries.py | 11 | get_messages, list_conversations |
| Config | config.py | 11 | get_config, set_config |
| Welcome/Menu | welcome_menu.py | 13 | send_welcome, send_menu |
| Templates | templates_*.py | 21 | create_template, list_templates |
| Media | media_eum.py | 8 | upload_media, download_media |
| Payments | payments.py, payment_config.py | 19 | send_payment, get_payment_config |
| Refunds | refunds.py | 8 | process_refund |
| Webhooks | webhooks.py, webhook_security.py | 12 | process_webhook |
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
aws lambda invoke --function-name base-wecare-digital-whatsapp --payload '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919876543210","text":"Hello!"}' out.json
```
