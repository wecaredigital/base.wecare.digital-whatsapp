# WhatsApp Business API

Production-ready WhatsApp Business API built on AWS End User Messaging (EUM) Social.

![Deploy](https://github.com/wecaredigital/base.wecare.digital-whatsapp/actions/workflows/deploy.yml/badge.svg)

## Features

- **167 Handlers** - Complete WhatsApp Business API coverage
- **AWS Native** - Uses AWS EUM Social (no Meta Graph API)
- **Modular Architecture** - Hexagonal/Clean architecture pattern
- **Production Ready** - CloudWatch alarms, DLQ, monitoring

## Quick Start

```bash
# Health check
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -d '{"action":"ping"}'

# Send message
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -H "Content-Type: application/json" \
  -d '{
    "action": "send_text",
    "metaWabaId": "1347766229904230",
    "to": "+919903300044",
    "text": "Hello from WhatsApp API!"
  }'
```

## Documentation

- [API Reference](docs/API.md) - Complete API documentation
- [Quick Reference](docs/QUICK_REFERENCE.md) - Common actions cheat sheet
- [Architecture](docs/ARCHITECTURE.md) - System design
- [DynamoDB Schema](docs/dynamodb-contract.md) - Database schema

## Infrastructure

| Component | Resource |
|-----------|----------|
| Lambda | `base-wecare-digital-whatsapp` (167 handlers) |
| DynamoDB | `base-wecare-digital-whatsapp` (16 GSIs) |
| API Gateway | `https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com` |
| SNS | `base-wecare-digital` |
| SQS | `base-wecare-digital-whatsapp-webhooks` |
| EventBridge | `base-wecare-digital-whatsapp` |
| Region | `ap-south-1` |

## WABAs

| Business | Meta WABA ID | Phone |
|----------|--------------|-------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 |

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Deploy (via GitHub Actions on push to main)
git push origin main

# Manual deploy
powershell -File deploy/deploy-167-handlers.ps1
```

## Project Structure

```
├── app.py                 # Lambda entry point
├── handlers/              # 167 handler modules
│   ├── messaging.py       # Send messages
│   ├── queries.py         # Query data
│   ├── config.py          # Configuration
│   ├── templates_eum.py   # AWS EUM templates
│   ├── payments.py        # Payments
│   └── ...
├── deploy/                # Deployment scripts
├── tests/                 # Unit tests
└── docs/                  # Documentation
```

## CI/CD

GitHub Actions automatically:
1. Runs tests on PR
2. Deploys to Lambda on merge to main
3. Publishes new version
4. Updates `live` alias
5. Runs smoke test

## Monitoring

CloudWatch Alarms:
- Lambda errors > 5 in 5 min
- Lambda throttles > 0
- Lambda duration > 10s avg
- SQS DLQ messages > 0

All alarms notify via SNS → email.

## License

Proprietary - WECARE.DIGITAL
