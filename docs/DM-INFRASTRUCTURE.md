# Wecare Digital - Direct Messaging Infrastructure

## Overview

This document describes the AWS infrastructure for Wecare Digital Direct Messaging (DM) platform.

**Domains:**
- `dm.wecare.digital` - API Gateway (WhatsApp, Bedrock Agents, Core APIs)
- `d.wecare.digital` - Media Storage (CloudFront + S3)

**Tags (all resources):**
- `Project = wecare-dm`
- `Owner = wecare.digital`
- `Environment = prod`
- `CostCenter = messaging`

---

## 1. API Domain: dm.wecare.digital

### Purpose
Central API endpoint for all Direct Messaging services.

### Routes
| Path | Service | Description |
|------|---------|-------------|
| `/whatsapp/*` | WhatsApp API | Webhook, send messages, media |
| `/agent-core/*` | Bedrock Agent Core | Agent orchestration |
| `/agents/*` | Bedrock Agents | Individual agent endpoints |
| `/` (GET) | Redirect | → `https://wecare.digital/selfservice` |
| `/*` (404) | Redirect | → `https://wecare.digital/selfservice` |

### Configuration
- **Type:** HTTP API (API Gateway v2)
- **API ID:** o0wjog0nl4
- **Custom Domain:** dm.wecare.digital
- **Certificate:** Regional ACM (ap-south-1)
- **Region:** ap-south-1

### DNS
- **Record:** dm.wecare.digital → d-ci3wvxfyqf.execute-api.ap-south-1.amazonaws.com (A alias)

---

## 2. Files Domain: d.wecare.digital

### Purpose
Media storage for WhatsApp, SMS, Voice, Email attachments.

### Folder Structure
```
d.wecare.digital/
├── d/                    # Inbound media (received from users)
│   ├── wa-in-{uuid1}{uuid2}-file.jpg
│   ├── ses-in-{uuid1}{uuid2}-email.eml
│   └── ...
├── u/                    # Outbound media (sent to users)
│   ├── wa-out-{uuid1}{uuid2}-image.png
│   ├── voice-out-{uuid1}{uuid2}-audio.mp3
│   └── ...
├── index.html            # Redirect to selfservice
└── 404.html              # Redirect to selfservice
```

### Key Format
```
{direction}/{source}-{uuid1}{uuid2}-{filename}
```

**Direction:**
- `d/` = Inbound (received)
- `u/` = Outbound (sent)

**Source Prefixes:**
| Prefix | Description |
|--------|-------------|
| `wa-in` | WhatsApp inbound |
| `wa-out` | WhatsApp outbound |
| `ses-in` | SES email inbound |
| `ses-out` | SES email outbound |
| `sms-out` | SMS outbound |
| `voice-out` | Voice TTS audio |
| `unknown` | Unknown source |

### Configuration
- **Bucket:** `d.wecare.digital` (S3, ap-south-1)
- **CloudFront:** E286NX9B76RUBU (de9qaq1vkecrl.cloudfront.net)
- **Certificate:** `*.wecare.digital` (ACM us-east-1)
- **Error handling:** 403/404 → /404.html (redirect to selfservice)

### DNS
- **Record:** d.wecare.digital → de9qaq1vkecrl.cloudfront.net (A alias)

---

## 3. Lambda Functions

### base-wecare-digital-whatsapp
- **Purpose:** Main WhatsApp handler + Bedrock Agent action groups
- **Triggers:** API Gateway, Bedrock Agent
- **Environment:**
  - `REGION = ap-south-1`
  - `WABA_ID = 1347766229904230`
- **IAM Role:** `base-wecare-digital-whatsapp-full-access-role`

### Handlers
| Handler | Description |
|---------|-------------|
| `app.lambda_handler` | Main entry point |
| `handlers.bedrock_actions` | Bedrock Agent action groups |
| `handlers.media_storage` | Media storage operations |
| `handlers.shortlinks` | Short URL service |
| `handlers.razorpay_api` | Payment links |

---

## 4. DynamoDB Tables

### wecare-shortlinks
- **Purpose:** Short URL mappings for r.wecare.digital
- **PK:** `code` (short code)
- **Attributes:** `target`, `title`, `clicks`, `created_at`

### wecare-payments
- **Purpose:** Payment link tracking
- **PK:** `payment_id`
- **Attributes:** `amount`, `status`, `razorpay_id`, `created_at`

---

## 5. S3 Buckets

### d.wecare.digital
- **Purpose:** Media storage (inbound/outbound)
- **Structure:** `d/` (inbound), `u/` (outbound)
- **Access:** CloudFront OAC, presigned URLs

### dev.wecare.digital
- **Purpose:** Development assets, voice audio
- **Structure:** `voice/` (TTS audio files)

---

## 6. CloudFront Distributions

### d.wecare.digital
- **Origin:** S3 `d.wecare.digital`
- **Behaviors:**
  - Default: Cache media files
  - Error 403/404: Redirect to selfservice
- **Certificate:** `*.wecare.digital`

### selfcare.wecare.digital
- **Origin:** S3 `selfcare.wecare.digital`
- **Purpose:** Self-service portal

---

## 7. Route 53 DNS

### Hosted Zone: wecare.digital
| Record | Type | Target |
|--------|------|--------|
| `dm.wecare.digital` | A/AAAA | API Gateway |
| `d.wecare.digital` | A/AAAA | CloudFront |
| `r.wecare.digital` | A/AAAA | API Gateway (shortlinks) |
| `p.wecare.digital` | A/AAAA | API Gateway (payments) |

---

## 8. IAM Roles

### base-wecare-digital-whatsapp-full-access-role
- **Assumed by:** Lambda
- **Permissions:**
  - S3: Read/Write to d.wecare.digital, dev.wecare.digital
  - DynamoDB: Full access to wecare-* tables
  - SES: Send email
  - Pinpoint SMS/Voice: Send messages
  - Social Messaging: WhatsApp operations
  - Polly: Text-to-speech
  - Bedrock: Agent invocation
  - CloudWatch Logs: Write logs

---

## 9. Bedrock Agents

### Agent ID: UFVSBWGCIU
- **Alias:** TSTALIASID
- **Purpose:** Omni-channel messaging orchestration

### Action Groups
| Group | Description |
|-------|-------------|
| PaymentsAPI | Razorpay payment links |
| ShortlinksAPI | Short URL creation |
| WhatsAppAPI | WhatsApp messaging |
| NotificationsAPI | SMS + Email |
| VoiceAPI | Polly TTS + SMS fallback |

---

## 10. India DLT Configuration

For SMS to India (+91), DLT registration is required:

| Parameter | Value |
|-----------|-------|
| Sender ID | `WDBEEP` |
| Entity ID | `1201161991108627443` |
| Template ID | Provided per message |

**Usage:** Pass `dlt_template_id` parameter to use registered sender.

---

## Acceptance Checklist

### API (dm.wecare.digital)
- [ ] `https://dm.wecare.digital/` → redirects to selfservice
- [ ] `https://dm.wecare.digital/unknown` → redirects to selfservice
- [ ] `/whatsapp/*` routes work
- [ ] `/agent-core/*` routes work
- [ ] `/agents/*` routes work

### Files (d.wecare.digital)
- [ ] `https://d.wecare.digital/` → redirects to selfservice
- [ ] `https://d.wecare.digital/unknown` → redirects to selfservice
- [ ] Media files accessible via CDN
- [ ] Presigned URLs work

### Media Storage
- [ ] Inbound media stored in `d/`
- [ ] Outbound media stored in `u/`
- [ ] Keys are flat (no subfolders)
- [ ] Keys include uuid+uuid
- [ ] Metadata stored correctly

### Tags
- [ ] All resources tagged with Project, Owner, Environment, CostCenter
