# WhatsApp Business API

Production-ready WhatsApp Business API on AWS End User Messaging Social.

![Deploy](https://github.com/wecaredigital/base.wecare.digital-whatsapp/actions/workflows/deploy.yml/badge.svg)

## Architecture

```
┌──────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐
│   WhatsApp   │───▶│  AWS EUM    │───▶│         Lambda (167 handlers)   │
│   (Meta)     │    │   Social    │    │                                 │
└──────────────┘    └─────────────┘    └───────────────┬─────────────────┘
                                                       │
                    ┌──────────────────────────────────┼──────────────────────────────────┐
                    ▼                                  ▼                                  ▼
            ┌───────────────┐                 ┌───────────────┐                 ┌───────────────┐
            │   DynamoDB    │                 │      S3       │                 │  EventBridge  │
            │   (16 GSIs)   │                 │   (Media)     │                 │  SNS + SQS    │
            └───────────────┘                 └───────────────┘                 └───────────────┘
```

## Quick Start

```bash
curl -X POST https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com \
  -H "Content-Type: application/json" \
  -d '{"action":"send_text","metaWabaId":"1347766229904230","to":"+919903300044","text":"Hello!"}'
```

## Documentation

- [API Reference](docs/API.md) - All 167 handlers
- [Development Guide](docs/DEVELOPMENT.md) - Architecture & adding handlers

## Project Structure

```
├── app.py              # Lambda entry point
├── handlers/           # 34 handler modules
├── deploy/             # Deployment scripts
├── tests/              # Unit tests
└── docs/               # Documentation
```

## Deploy

```bash
git push origin main  # Auto-deploy via GitHub Actions
```

## WABAs

| Business | Meta WABA ID | Phone |
|----------|--------------|-------|
| WECARE.DIGITAL | `1347766229904230` | +91 93309 94400 |
| Manish Agarwal | `1390647332755815` | +91 99033 00044 |

## License

Proprietary - WECARE.DIGITAL
