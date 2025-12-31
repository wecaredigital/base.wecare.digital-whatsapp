# Repository Map

> Generated: 2025-12-31 | Spec: Kiro Final Prompt v7

## Overview

**Project:** base-wecare-digital-whatsapp  
**Type:** AWS Lambda-based WhatsApp Business API backend  
**Region:** ap-south-1 (Mumbai)  
**Integration:** AWS End User Messaging Social (EUM) — NO Meta Graph API runtime calls

## Architecture Principles

1. **AWS EUM Only** — All WhatsApp operations via `socialmessaging` SDK
2. **Single Dispatch** — One router for API GW, SNS/SQS, direct invoke, CLI
3. **Lazy Initialization** — Clients/env created on first access
4. **No PII Logging** — Phone numbers, message bodies redacted
5. **Capability Stubs** — Unsupported features have upgrade hooks

## Directory Structure

```
base.wecare.digital-whatsapp/
├── app.py                    # Lambda entry point (thin wrapper)
├── handlers/                 # 167+ action handlers (27 modules)
│   ├── __init__.py          # Package exports + unified_dispatch
│   ├── dispatcher.py        # Unified dispatcher with registry
│   ├── base.py              # Lazy clients, env, utilities
│   ├── messaging.py         # send_text, send_image, send_template, etc.
│   ├── templates_eum.py     # AWS EUM template CRUD
│   ├── templates_meta.py    # Template validation (Meta spec)
│   ├── template_library.py  # Template library management
│   ├── media_eum.py         # Media upload/download via EUM + S3
│   ├── queries.py           # DynamoDB query handlers
│   ├── marketing.py         # Campaign management
│   ├── payments.py          # Payment message handlers
│   ├── payment_config.py    # Payment config (India: WECARE-DIGITAL, ManishAgarwal)
│   ├── business_profile.py  # Business profile (local + manual apply)
│   ├── welcome_menu.py      # Welcome + Interactive List Menu
│   ├── notifications.py     # Email notification handlers
│   ├── webhooks.py          # Event processing
│   ├── event_destinations.py# AWS EUM event destinations
│   ├── analytics.py         # Analytics handlers
│   ├── catalogs.py          # Product catalog handlers
│   ├── groups.py            # Group messaging (stub)
│   ├── calling.py           # Voice calling (stub)
│   ├── flows_messaging.py   # WhatsApp Flows
│   ├── carousels.py         # Carousel messages
│   ├── address_messages.py  # Address collection
│   ├── throughput.py        # Rate limiting (token bucket)
│   ├── retry.py             # Retry failed messages
│   ├── config.py            # Configuration handlers
│   ├── extended.py          # Extended handler registry
│   ├── refunds.py           # Refund handlers
│   └── s3_paths.py          # S3 path utilities
├── src/
│   ├── runtime/             # Core dispatch layer (§4)
│   │   ├── envelope.py      # Envelope(kind, requestId, tenantId, source, payload)
│   │   ├── parse_event.py   # Detect: API GW, SNS, SQS, EventBridge, direct, CLI
│   │   ├── dispatch.py      # dispatch(envelope, deps) → response
│   │   └── deps.py          # Deps DI container (lazy clients)
│   ├── app/                 # Entry point adapters
│   │   ├── api_handler.py   # API Gateway HTTP API
│   │   ├── inbound_handler.py # SNS/SQS inbound events
│   │   └── direct_handler.py  # Direct Lambda invoke
│   ├── bedrock/             # Bedrock AI integration (§12)
│   │   ├── agent.py         # BedrockAgent client (Claude 3.5 Sonnet)
│   │   ├── strands_agent.py # Strands SDK agent
│   │   ├── processor.py     # Multimedia processor (BDA)
│   │   └── handlers.py      # Bedrock worker Lambda handler
│   └── notifications/       # Email notifications (§9)
│       └── email_notifier.py # SES HTML emails (idempotent)
├── tools/
│   └── cli.py               # Admin CLI tool
├── tests/
│   ├── test_all_handlers.py # Handler tests
│   ├── test_unified_handlers.py
│   ├── test_handlers_import.py
│   ├── test_eum_templates.py
│   ├── test_welcome_menu.py # Welcome/menu tests
│   └── test_runtime.py      # Runtime tests (47 tests)
├── deploy/                  # Deployment scripts
│   ├── deploy-167-handlers.ps1
│   ├── deploy-email-notifier.ps1
│   ├── deploy-bedrock-worker.ps1
│   ├── setup-eventbridge-sqs.ps1
│   ├── setup-bedrock-resources.ps1
│   ├── setup-dynamodb-complete.ps1
│   ├── setup-step-functions.ps1
│   ├── seed-menu-data.ps1
│   ├── menu-data/           # Menu JSON seed files
│   └── *.json               # IAM policies, configs
├── cdk/                     # CDK TypeScript IaC (source of truth)
│   ├── bin/app.ts
│   └── lib/
│       ├── base-wecare-whatsapp-stack.ts  # Main infra
│       ├── eventbridge-stack.ts           # EventBridge rules
│       ├── campaign-engine-stack.ts       # Step Functions
│       └── bedrock-stack.ts               # Bedrock + OpenSearch
├── docs/
│   ├── spec.md              # Canonical link index (Meta + AWS)
│   ├── bedrock.md           # Bedrock integration docs
│   ├── dynamodb-contract.md # DynamoDB schema (16 GSIs)
│   ├── gaps.md              # AWS EUM capability gaps + workarounds
│   ├── API.md               # API documentation
│   ├── DEVELOPMENT.md       # Development guide
│   ├── STATUS.md            # Implementation status
│   └── repo-map.md          # This file
└── .github/workflows/       # CI/CD
    ├── pr-check.yml         # Lint + pytest
    └── deploy.yml           # Auto-deploy on push
```

## Key Components

### 1. Handler Architecture (§3-4)
- **167+ handlers** across 27 modules
- Action-based routing: `{"action": "send_text", ...}`
- Single dispatcher with handler registry
- Shared dependency injection (Deps)
- Handler signature: `handle(payload: Dict, deps: Deps) -> Dict`

### 2. AWS Services Used
| Service | Purpose |
|---------|---------|
| Lambda | Main function + workers (email, bedrock) |
| DynamoDB | Single-table design (16 GSIs) |
| S3 | Media storage (KMS encrypted) |
| SQS | Event queues (inbound, notify, bedrock) |
| SNS | AWS EUM event destinations |
| EventBridge | Event routing (5 rules) |
| SES | Email notifications (HTML) |
| Bedrock | Agent + KB + BDA |
| Step Functions | Campaign engine |
| API Gateway | HTTP API |
| OpenSearch Serverless | KB vector store |

### 3. DynamoDB Schema (Single Table)
- **PK patterns:** `MSG#`, `CONV#`, `TENANT#`, `TEMPLATE#`, `ORDER#`, `MEDIA#`, `BEDROCK#`, `EMAIL#`, `MENU#`, `WELCOME#`, `PAYCFG#`, `QUALITY#`
- **16 GSIs** for query patterns
- TTL for idempotency records (7 days)

### 4. Bedrock Integration (§12)
- **Agent:** base-wecare-digital-whatsapp (ap-south-1)
- **Model:** apac.anthropic.claude-3-5-sonnet-20241022-v2:0
- **KB:** base-wecare-wa-kb (OpenSearch Serverless)
- **Data Source:** Web crawler (https://wecare.digital, HOST_ONLY)
- **BDA:** Document/audio/video processing
- **Feature Flags:** BEDROCK_ENABLED, AUTO_REPLY_ENABLED

### 5. Event Flow
```
WhatsApp → AWS EUM → SNS → SQS → Lambda (inbound)
                                    ↓
                              EventBridge
                              ↓         ↓
                    Notify Queue    Bedrock Queue
                         ↓              ↓
                  Email Lambda    Bedrock Worker
```

### 6. Welcome + Menu System (§13)
- **Main Menu** + 3 Submenus (services, self_service, support)
- Interactive List Messages
- Keyword triggers: menu, help, start, hi, hello
- Cooldown: 72 hours default
- Crisp Q/A responses before links

### 7. Payment Configs (§8)
| Business | WABA ID | Phone | Gateway MID | UPI ID |
|----------|---------|-------|-------------|--------|
| WECARE-DIGITAL | 1347766229904230 | +91 9330994400 | acc_HDfub6wOfQybuH | 9330994400@sbi |
| ManishAgarwal | 1390647332755815 | +91 9903300044 | acc_HDfub6wOfQybuH | 9330994400@sbi |

## API Contract

```json
// Request (all triggers)
{
    "action": "send_text",
    "metaWabaId": "1347766229904230",
    "phoneNumberId": "831049713436137",
    "to": "+91...",
    "text": "Hello!"
}

// Response
{
    "statusCode": 200,
    "messageId": "wamid.xxx",
    "timestamp": "2025-01-01T00:00:00Z"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| MESSAGES_TABLE_NAME | DynamoDB table | base-wecare-digital-whatsapp |
| MEDIA_BUCKET | S3 bucket for media | dev.wecare.digital |
| MEDIA_PREFIX | S3 key prefix | WhatsApp/ |
| BEDROCK_REGION | Bedrock region | ap-south-1 |
| BEDROCK_AGENT_ID | Bedrock Agent ID | (from setup) |
| BEDROCK_KB_ID | Knowledge Base ID | (from setup) |
| BEDROCK_MODEL_ID | Model inference profile | apac.anthropic.claude-3-5-sonnet-20241022-v2:0 |
| AUTO_REPLY_ENABLED | Enable auto-reply | false |
| AUTO_REPLY_BEDROCK_ENABLED | Enable AI auto-reply | false |
| AUTO_WELCOME_ENABLED | Enable auto-welcome | false |
| AUTO_MENU_ON_KEYWORDS | Send menu on keywords | true |
| WELCOME_COOLDOWN_HOURS | Welcome cooldown | 72 |
| SES_SENDER_EMAIL | Email sender address | noreply@wecare.digital |
| INBOUND_NOTIFY_TO | Inbound email recipients | ops@wecare.digital |
| OUTBOUND_NOTIFY_TO | Outbound email recipients | ops@wecare.digital |
| EVENT_BUS_NAME | EventBridge bus | base-wecare-digital-whatsapp-events |

## Deployment

### Option A: CDK (Recommended)
```bash
cd cdk
npm install
npm run build
cdk bootstrap  # First time only
cdk deploy --all
```

### Option B: PowerShell Scripts
```powershell
# Run in order from project root:
.\deploy\setup-dynamodb-complete.ps1
.\deploy\create-all-gsis.ps1
.\deploy\update-iam-role.ps1
.\deploy\deploy-167-handlers.ps1
.\deploy\setup-eventbridge-sqs.ps1
.\deploy\setup-step-functions.ps1
.\deploy\setup-bedrock-resources.ps1
.\deploy\seed-menu-data.ps1
```

### Post-Deployment
```powershell
# Start Bedrock KB sync
aws bedrock-agent start-ingestion-job --knowledge-base-id $KB_ID --data-source-id $DS_ID

# Test Lambda
.\deploy\test-lambda.ps1

# Seed menu for WABA
aws lambda invoke --function-name base-wecare-digital-whatsapp `
  --payload '{"action":"seed_default_menu","tenantId":"1347766229904230"}' out.json
```

## Testing

```powershell
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_welcome_menu.py -v

# Test Lambda directly
aws lambda invoke --function-name base-wecare-digital-whatsapp `
  --payload '{"action":"ping"}' out.json
```

## Quick Reference

### Common Actions
| Action | Description |
|--------|-------------|
| `ping` | Health check |
| `help` | List all actions |
| `send_text` | Send text message |
| `send_template` | Send template message |
| `send_menu` | Send interactive menu |
| `send_welcome` | Send welcome message |
| `get_welcome_config` | Get welcome config |
| `get_menu_config` | Get menu config |
| `list_templates` | List templates |
| `get_business_profile` | Get business profile |
| `list_payment_configs` | List payment configs |

### WABAs
| Business | Meta WABA ID | Phone |
|----------|--------------|-------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 |
