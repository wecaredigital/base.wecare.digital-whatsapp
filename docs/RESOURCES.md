# WECARE.DIGITAL - AWS Resources Documentation

> Last Updated: 2026-01-02
> Region: ap-south-1 (Mumbai)
> Account: 010526260063

---

## 🔐 IAM - Unified Role

All Lambda functions use a single full-access role.

| Resource | Value |
|----------|-------|
| **Role Name** | `base-wecare-digital-whatsapp-full-access-role` |
| **Role ARN** | `arn:aws:iam::010526260063:role/base-wecare-digital-whatsapp-full-access-role` |

---

## 📊 CloudWatch - Unified Log Group

| Resource | Value |
|----------|-------|
| **Log Group** | `/wecare-digital/all` |
| **Retention** | 30 days |

---

## ⚡ Lambda Functions

| Function | Handler | Domain | Purpose |
|----------|---------|--------|---------|
| `base-wecare-digital-whatsapp` | `app.lambda_handler` | Main API | WhatsApp messaging |
| `wecare-digital-shortlinks` | `handlers.shortlinks.lambda_handler` | r.wecare.digital | Short links |
| `wecare-digital-payments` | `handlers.razorpay_api.lambda_handler` | p.wecare.digital | Razorpay payments |

---

## 🗄️ DynamoDB Tables

| Table | Purpose |
|-------|---------|
| `base-wecare-digital-whatsapp` | Main WhatsApp data |
| `wecare-digital-shortlinks` | Short links (r.wecare.digital) |
| `wecare-digital-payments` | Razorpay payments (p.wecare.digital) |
| `wecare-digital-flows` | WhatsApp Flows |
| `wecare-digital-inbound` | Inbound messages |
| `wecare-digital-outbound` | Outbound messages |
| `wecare-digital-orders` | Order payments |

---

## 🌐 API Gateway & Domains

| Domain | API ID | Lambda |
|--------|--------|--------|
| `r.wecare.digital` | `w19x9gi045` | `wecare-digital-shortlinks` |
| `p.wecare.digital` | `z8raub1eth` | `wecare-digital-payments` |

---

## 💳 Razorpay Configuration

| Setting | Value |
|---------|-------|
| **Merchant ID** | `acc_HDfub6wOfQybuH` |
| **Key ID** | `rzp_live_CLnEhAF46T9eQm` |
| **Key Secret** | `4MIFXNF5pIW6LnqpFMNrlvFT` |
| **Webhook Secret** | `b@c4mk9t9Z8qLq3` |
| **Webhook URL 1** | `https://p.wecare.digital/razorpay-webhook` |
| **Webhook URL 2** | `https://z8raub1eth.execute-api.ap-south-1.amazonaws.com/prod/razorpay-webhook` |
| **Secret ARN** | `arn:aws:secretsmanager:ap-south-1:010526260063:secret:wecare-digital/razorpay-6rCxYB` |

---

## 🔗 Short Links Service (r.wecare.digital)

**Independent microservice - can be attached to any project**

### Routes
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Home page → redirect to selfservice |
| `/r/{code}` | GET | Short link redirect (PUBLIC) |
| `/r/create` | POST | Create short link API |
| `/r/stats/{code}` | GET | Get link statistics |
| `/*` | ANY | 404 → redirect to selfservice |

### Features
- UUID-based codes (12 chars, non-guessable)
- Click tracking with referrer, user-agent, IP
- Expiration support
- Custom codes (optional)
- Full CORS support

### Test URLs
```
https://r.wecare.digital/                    → Home page
https://r.wecare.digital/r/{uuid}            → Redirect to target
https://r.wecare.digital/anything            → 404 page
```

### Create Link API
```bash
POST https://r.wecare.digital/r/create
Content-Type: application/json

{
  "targetUrl": "https://example.com",
  "title": "My Link",
  "customCode": "mycode",      # optional
  "expiresAt": "2026-12-31"    # optional
}
```

---

## 💰 Payment Service (p.wecare.digital)

**Independent microservice - can be attached to any project**

### Routes
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Service info page |
| `/p/test` | GET | Create Rs.1 test payment link |
| `/p/pay/{id}` | GET | Payment checkout page |
| `/p/success` | GET | Payment success page |
| `/p/{id}` | GET | Payment link redirect |
| `/p/create-link` | POST | Create payment link API |
| `/razorpay-webhook` | POST | Razorpay webhook handler |
| `/*` | ANY | 404 → redirect to selfservice |

### Features
- Razorpay integration (live credentials)
- Webhook signature verification
- Payment tracking in DynamoDB
- Full CORS support
- Professional branded pages

### Test URLs
```
https://p.wecare.digital/                    → Service info
https://p.wecare.digital/p/test              → Rs.1 test link
https://p.wecare.digital/p/success           → Success page
https://p.wecare.digital/anything            → 404 page
```

### Create Payment Link API
```bash
POST https://p.wecare.digital/p/create-link
Content-Type: application/json

{
  "amount": 100,
  "currency": "INR",
  "description": "Order Payment",
  "customerName": "John Doe",
  "customerEmail": "john@example.com",
  "customerPhone": "+919876543210",
  "referenceId": "ORDER-123",
  "callbackUrl": "https://yoursite.com/callback"
}
```

---

## 🚀 Deployment

### Quick Deploy
```powershell
.\deploy\quick-deploy.ps1
```

### Manual Deploy
```powershell
# Package
Compress-Archive -Path "app.py","handlers" -DestinationPath lambda-package.zip -Force

# Deploy
aws lambda update-function-code --function-name wecare-digital-shortlinks --zip-file fileb://lambda-package.zip --region ap-south-1
aws lambda update-function-code --function-name wecare-digital-payments --zip-file fileb://lambda-package.zip --region ap-south-1
```

---

## ✅ Test Results (2026-01-02)

### Short Links Lambda
| Test | Status |
|------|--------|
| Root path (/) | ✅ 200 - Home page |
| Create link (/r/create) | ✅ 200 - UUID code generated |
| 404 page | ✅ 404 - Branded page |

### Payments Lambda
| Test | Status |
|------|--------|
| Root path (/) | ✅ 200 - Service info |
| Test link (/p/test) | ✅ 200 - Rs.1 link created |
| 404 page | ✅ 404 - Branded page |

---

## 📋 Environment Variables

### wecare-digital-shortlinks
```
SHORTLINKS_TABLE=wecare-digital-shortlinks
SHORT_LINK_BASE_URL=https://r.wecare.digital
DEFAULT_REDIRECT=https://wecare.digital/selfservice
FAVICON=https://selfcare.wecare.digital/wecare-digital.ico
```

### wecare-digital-payments
```
PAYMENTS_TABLE=wecare-digital-payments
RAZORPAY_KEY_ID=rzp_live_CLnEhAF46T9eQm
RAZORPAY_KEY_SECRET=4MIFXNF5pIW6LnqpFMNrlvFT
RAZORPAY_WEBHOOK_SECRET=b@c4mk9t9Z8qLq3
RAZORPAY_MERCHANT_ID=acc_HDfub6wOfQybuH
RAZORPAY_SECRET_ARN=arn:aws:secretsmanager:ap-south-1:010526260063:secret:wecare-digital/razorpay-6rCxYB
DEFAULT_REDIRECT=https://wecare.digital/selfservice
FAVICON=https://selfcare.wecare.digital/wecare-digital.ico
```
