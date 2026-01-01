# Operations Runbook

**Last Updated:** 2026-01-01

This document provides operational procedures for managing the WhatsApp Business API integration.

> **Region:** ap-south-1 (Mumbai) is primary for all services.

---

## 1. Business Profile Apply Flow

### Gap
AWS EUM Social does not expose Business Profile update APIs. Profile changes must be applied manually.

### Procedure

1. **Update profile via API** (stores in DynamoDB):
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"update_business_profile","tenantId":"wecare-digital","phoneNumberId":"<phone-id>","about":"Your about text","description":"Your description"}' \
  response.json
```

2. **Get apply instructions**:
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"get_business_profile_apply_instructions","tenantId":"wecare-digital","phoneNumberId":"<phone-id>"}' \
  response.json
```

3. **Apply in AWS Console**:
   - Go to AWS Console → End User Messaging → Social
   - Select your WABA
   - Navigate to Business Profile section
   - Update fields manually from DynamoDB values
   - Save changes

4. **Mark as applied**:
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"mark_business_profile_applied","tenantId":"wecare-digital","phoneNumberId":"<phone-id>"}' \
  response.json
```

---

## 2. Email Notifications

### Architecture
```
Inbound Message → EventBridge → InboundNotifyQueue → EmailNotifierLambda → SES
Outbound Message → EventBridge → OutboundNotifyQueue → EmailNotifierLambda → SES
```

### Idempotency
- Each notification has unique `eventId`
- Stored in DynamoDB: `PK=EMAIL#{eventId}` with 7-day TTL
- Duplicate events are skipped

### Email Format

**Inbound Email:**
- Subject: `[WECARE] Inbound from {sender_name} ({sender_number})`
- Body: Sender info, business info, message text/caption, media link (presigned S3)

**Outbound Email:**
- Subject: `[WECARE] Outbound to {receiver_number}`
- Body: Receiver info, message text/caption, media links, WABA + phoneNumberId + messageId

### Configuration
```bash
# Environment variables
SES_SENDER_EMAIL=notifications@wecare.digital
INBOUND_NOTIFY_TO=team@wecare.digital
OUTBOUND_NOTIFY_TO=team@wecare.digital
```

### Troubleshooting

**Emails not sending:**
1. Check SES identity verification
2. Check SES sending limits
3. Check CloudWatch logs for EmailNotifierLambda
4. Verify SQS queue has messages

**Duplicate emails:**
1. Check idempotency records in DynamoDB
2. Verify TTL is working (7 days)

---

## 3. Knowledge Base Sync

### Schedule
- Daily sync at 02:00 UTC via EventBridge
- Manual sync available via CLI

### Manual Sync
```bash
# Start ingestion job
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id base-wecare-wa-kb \
  --data-source-id <data-source-id> \
  --region ap-south-1

# Check status
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id base-wecare-wa-kb \
  --data-source-id <data-source-id> \
  --ingestion-job-id <job-id> \
  --region ap-south-1
```

### Data Source Configuration
```json
{
  "type": "WEB",
  "webConfiguration": {
    "sourceConfiguration": {
      "urlConfiguration": {
        "seedUrls": [
          {"url": "https://wecare.digital"}
        ]
      }
    },
    "crawlerConfiguration": {
      "crawlerLimits": {
        "rateLimit": 10
      },
      "scope": "HOST_ONLY"
    }
  }
}
```

### Troubleshooting

**Sync failures:**
1. Check CloudWatch logs for ingestion job
2. Verify wecare.digital is accessible
3. Check OpenSearch Serverless collection status

**Stale content:**
1. Force manual sync
2. Check crawl scope (HOST_ONLY)
3. Verify sitemap.xml exists

---

## 4. Template Management

### Sync Templates from AWS EUM
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"eum_sync_templates","metaWabaId":"1347766229904230"}' \
  response.json
```

### Create Template
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{
    "action":"eum_create_template",
    "metaWabaId":"1347766229904230",
    "templateName":"order_confirmation",
    "category":"UTILITY",
    "language":"en_US",
    "components":[
      {"type":"BODY","text":"Your order {{1}} has been confirmed. Total: {{2}}"}
    ]
  }' \
  response.json
```

### Template Status Monitoring
- Templates are cached in DynamoDB
- Status updates via webhooks
- Query by status: `GSI: TemplatesByStatus`

---

## 5. Menu & Welcome Configuration

### Seed Default Menu Data
```powershell
# PowerShell
.\deploy\seed-menu-data.ps1
```

### Update Welcome Config
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{
    "action":"update_welcome_config",
    "tenantId":"1347766229904230",
    "welcomeText":"Welcome to WECARE.DIGITAL 👋",
    "enabled":true,
    "cooldownHours":72
  }' \
  response.json
```

### Update Menu
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{
    "action":"update_menu_config",
    "tenantId":"1347766229904230",
    "menuId":"main",
    "sections":[...]
  }' \
  response.json
```

---

## 6. Payment Configuration

### Pre-configured Tenants

**WECARE-DIGITAL:**
- WABA ID: 1347766229904230
- Phone: +91 9330994400
- Gateway MID: acc_HDfub6wOfQybuH
- UPI: 9330994400@sbi
- MCC: 4722 (Travel)
- Purpose: 03 (Travel)

**ManishAgarwal:**
- WABA ID: 1390647332755815
- Phone: +91 9903300044
- Gateway MID: acc_HDfub6wOfQybuH
- UPI: 9330994400@sbi
- MCC: 4722 (Travel)
- Purpose: 03 (Travel)

### Seed Payment Configs
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"seed_payment_configs"}' \
  response.json
```

### Validate Payment Config
```bash
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{
    "action":"validate_payment_configuration",
    "tenantId":"wecare-digital",
    "configName":"WECARE-DIGITAL"
  }' \
  response.json
```

---

## 7. Monitoring & Alerts

### CloudWatch Dashboards
- Lambda invocations, errors, duration
- SQS queue depth, age of oldest message
- DynamoDB consumed capacity
- EventBridge rule invocations

### Key Metrics
```
# Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=base-wecare-digital-whatsapp \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum

# SQS queue depth
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=base-wecare-digital-whatsapp-inbound \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average
```

### Alerts
- Lambda error rate > 5%
- SQS DLQ messages > 0
- Bedrock invocation failures
- SES bounce rate > 2%

---

## 8. Disaster Recovery

### Backup Strategy
- DynamoDB: Point-in-time recovery enabled
- S3: Versioning enabled, cross-region replication optional
- Lambda: Code in Git, deployed via CDK

### Recovery Procedures

**DynamoDB restore:**
```bash
aws dynamodb restore-table-to-point-in-time \
  --source-table-name base-wecare-digital-whatsapp \
  --target-table-name base-wecare-digital-whatsapp-restored \
  --restore-date-time <timestamp>
```

**Redeploy Lambda:**
```powershell
cd cdk
npm run cdk deploy
```

---

## 9. Common Issues

### Message not delivered
1. Check delivery status in DynamoDB
2. Check DLQ for failed messages
3. Verify phone number format (+91...)
4. Check 24-hour window rules

### Template rejected
1. Check rejection reason in webhook
2. Review Meta template guidelines
3. Resubmit with corrections

### Media upload failed
1. Check file size limits (5MB image, 16MB video)
2. Verify MIME type is supported
3. Check S3 bucket permissions

### Bedrock timeout
1. Check message size
2. Verify model availability in ap-south-1
3. Check Bedrock service quotas

---

## 10. Useful Commands

```bash
# List all handlers
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"list_actions"}' response.json

# Health check
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"ping"}' response.json

# Get conversations
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{"action":"get_conversations","metaWabaId":"1347766229904230"}' response.json

# Send test message
aws lambda invoke --function-name base-wecare-digital-whatsapp \
  --payload '{
    "action":"send_text",
    "metaWabaId":"1347766229904230",
    "to":"+919876543210",
    "text":"Test message"
  }' response.json
```
