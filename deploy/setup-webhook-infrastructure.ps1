# =============================================================================
# WhatsApp Webhook Infrastructure Setup
# =============================================================================
# Creates SNS + SQS + EventBridge integration for WhatsApp webhooks
# Naming convention: base-wecare-digital-*
# Region: ap-south-1
# =============================================================================

$REGION = "ap-south-1"
$ACCOUNT_ID = "010526260063"
$PREFIX = "base-wecare-digital"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  WhatsApp Webhook Infrastructure Setup" -ForegroundColor Cyan
Write-Host "  Region: $REGION" -ForegroundColor Cyan
Write-Host "  Prefix: $PREFIX" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# Step 1: Check existing SNS Topic
# =============================================================================
Write-Host "`n=== Step 1: Checking SNS Topic ===" -ForegroundColor Yellow

$SNS_TOPIC_ARN = "arn:aws:sns:${REGION}:${ACCOUNT_ID}:${PREFIX}"
Write-Host "  SNS Topic: $SNS_TOPIC_ARN"

$topicExists = aws sns get-topic-attributes --topic-arn $SNS_TOPIC_ARN --region $REGION 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  SNS Topic exists" -ForegroundColor Green
} else {
    Write-Host "  Creating SNS Topic..." -ForegroundColor Yellow
    aws sns create-topic --name $PREFIX --region $REGION
}

# =============================================================================
# Step 2: Create SQS Queues (Main + DLQ)
# =============================================================================
Write-Host "`n=== Step 2: Creating SQS Queues ===" -ForegroundColor Yellow

# Dead Letter Queue
$DLQ_NAME = "${PREFIX}-whatsapp-dlq"
$DLQ_URL = aws sqs get-queue-url --queue-name $DLQ_NAME --region $REGION --query "QueueUrl" --output text 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Creating DLQ: $DLQ_NAME"
    $DLQ_URL = aws sqs create-queue --queue-name $DLQ_NAME --region $REGION --attributes "MessageRetentionPeriod=1209600" --query "QueueUrl" --output text
    Write-Host "  DLQ created: $DLQ_URL" -ForegroundColor Green
} else {
    Write-Host "  DLQ exists: $DLQ_URL" -ForegroundColor Green
}

$DLQ_ARN = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${DLQ_NAME}"

# Main Queue with DLQ
$QUEUE_NAME = "${PREFIX}-whatsapp-webhooks"
$QUEUE_URL = aws sqs get-queue-url --queue-name $QUEUE_NAME --region $REGION --query "QueueUrl" --output text 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Creating Main Queue: $QUEUE_NAME"
    
    # Create queue attributes JSON
    $queueAttrs = @{
        MessageRetentionPeriod = "345600"
        VisibilityTimeout = "300"
        RedrivePolicy = "{`"deadLetterTargetArn`":`"$DLQ_ARN`",`"maxReceiveCount`":`"3`"}"
    } | ConvertTo-Json -Compress
    
    # Write to temp file to avoid escaping issues
    $queueAttrs | Out-File -FilePath "temp-queue-attrs.json" -Encoding utf8
    
    $QUEUE_URL = aws sqs create-queue --queue-name $QUEUE_NAME --region $REGION --attributes file://temp-queue-attrs.json --query "QueueUrl" --output text
    Remove-Item "temp-queue-attrs.json" -Force
    Write-Host "  Queue created: $QUEUE_URL" -ForegroundColor Green
} else {
    Write-Host "  Queue exists: $QUEUE_URL" -ForegroundColor Green
}

$QUEUE_ARN = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${QUEUE_NAME}"

# =============================================================================
# Step 3: Set SQS Policy to allow SNS
# =============================================================================
Write-Host "`n=== Step 3: Setting SQS Policy ===" -ForegroundColor Yellow

$sqsPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSNSPublish",
      "Effect": "Allow",
      "Principal": {"Service": "sns.amazonaws.com"},
      "Action": "sqs:SendMessage",
      "Resource": "$QUEUE_ARN",
      "Condition": {
        "ArnEquals": {"aws:SourceArn": "$SNS_TOPIC_ARN"}
      }
    },
    {
      "Sid": "AllowEventBridgePublish",
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sqs:SendMessage",
      "Resource": "$QUEUE_ARN"
    }
  ]
}
"@

$sqsPolicy | Out-File -FilePath "temp-sqs-policy.json" -Encoding utf8
aws sqs set-queue-attributes --queue-url $QUEUE_URL --attributes "Policy=$(Get-Content temp-sqs-policy.json -Raw)" --region $REGION
Remove-Item "temp-sqs-policy.json" -Force
Write-Host "  SQS Policy set" -ForegroundColor Green

# =============================================================================
# Step 4: Subscribe SQS to SNS
# =============================================================================
Write-Host "`n=== Step 4: Subscribing SQS to SNS ===" -ForegroundColor Yellow

$existingSub = aws sns list-subscriptions-by-topic --topic-arn $SNS_TOPIC_ARN --region $REGION --query "Subscriptions[?Protocol=='sqs' && Endpoint=='$QUEUE_ARN'].SubscriptionArn" --output text

if ([string]::IsNullOrEmpty($existingSub)) {
    Write-Host "  Creating SNS -> SQS subscription..."
    aws sns subscribe --topic-arn $SNS_TOPIC_ARN --protocol sqs --notification-endpoint $QUEUE_ARN --region $REGION
    Write-Host "  Subscribed SQS to SNS" -ForegroundColor Green
} else {
    Write-Host "  SQS already subscribed to SNS" -ForegroundColor Green
}

# =============================================================================
# Step 5: Create EventBridge Event Bus (use default)
# =============================================================================
Write-Host "`n=== Step 5: Setting up EventBridge ===" -ForegroundColor Yellow

# Create custom event bus for WhatsApp events
$EVENT_BUS_NAME = "${PREFIX}-whatsapp"
$busExists = aws events describe-event-bus --name $EVENT_BUS_NAME --region $REGION 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Creating Event Bus: $EVENT_BUS_NAME"
    aws events create-event-bus --name $EVENT_BUS_NAME --region $REGION
    Write-Host "  Event Bus created" -ForegroundColor Green
} else {
    Write-Host "  Event Bus exists" -ForegroundColor Green
}

# =============================================================================
# Step 6: Create EventBridge Rules
# =============================================================================
Write-Host "`n=== Step 6: Creating EventBridge Rules ===" -ForegroundColor Yellow

# Rule 1: All WhatsApp messages -> SQS
$RULE_NAME_MESSAGES = "${PREFIX}-whatsapp-messages"
Write-Host "  Creating rule: $RULE_NAME_MESSAGES"

$messagePattern = @{
    source = @("whatsapp.webhook")
    "detail-type" = @("message.received", "message.sent", "message.delivered", "message.read")
} | ConvertTo-Json -Compress

aws events put-rule --name $RULE_NAME_MESSAGES --event-bus-name $EVENT_BUS_NAME --event-pattern $messagePattern --state ENABLED --region $REGION --description "Route WhatsApp messages to SQS"

# Add SQS target
aws events put-targets --rule $RULE_NAME_MESSAGES --event-bus-name $EVENT_BUS_NAME --targets "Id=sqs-target,Arn=$QUEUE_ARN" --region $REGION

Write-Host "  Rule created: messages -> SQS" -ForegroundColor Green

# Rule 2: Status updates -> Lambda
$RULE_NAME_STATUS = "${PREFIX}-whatsapp-status"
Write-Host "  Creating rule: $RULE_NAME_STATUS"

$statusPattern = @{
    source = @("whatsapp.webhook")
    "detail-type" = @("status.sent", "status.delivered", "status.read", "status.failed")
} | ConvertTo-Json -Compress

aws events put-rule --name $RULE_NAME_STATUS --event-bus-name $EVENT_BUS_NAME --event-pattern $statusPattern --state ENABLED --region $REGION --description "Route WhatsApp status updates to Lambda"

$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${PREFIX}-whatsapp:live"
aws events put-targets --rule $RULE_NAME_STATUS --event-bus-name $EVENT_BUS_NAME --targets "Id=lambda-target,Arn=$LAMBDA_ARN" --region $REGION

Write-Host "  Rule created: status -> Lambda" -ForegroundColor Green

# Rule 3: All events -> CloudWatch Logs (for debugging)
$RULE_NAME_LOGS = "${PREFIX}-whatsapp-logs"
Write-Host "  Creating rule: $RULE_NAME_LOGS"

$allPattern = @{
    source = @("whatsapp.webhook")
} | ConvertTo-Json -Compress

aws events put-rule --name $RULE_NAME_LOGS --event-bus-name $EVENT_BUS_NAME --event-pattern $allPattern --state ENABLED --region $REGION --description "Log all WhatsApp events to CloudWatch"

# Create CloudWatch Log Group
$LOG_GROUP = "/aws/events/${PREFIX}-whatsapp"
aws logs create-log-group --log-group-name $LOG_GROUP --region $REGION 2>$null

# Set log group policy for EventBridge
$logPolicy = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Sid = "EventBridgeToCloudWatchLogs"
            Effect = "Allow"
            Principal = @{ Service = "events.amazonaws.com" }
            Action = @("logs:CreateLogStream", "logs:PutLogEvents")
            Resource = "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:${LOG_GROUP}:*"
        }
    )
} | ConvertTo-Json -Depth 5 -Compress

aws logs put-resource-policy --policy-name "${PREFIX}-whatsapp-events" --policy-document $logPolicy --region $REGION 2>$null

$LOG_GROUP_ARN = "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:${LOG_GROUP}"
aws events put-targets --rule $RULE_NAME_LOGS --event-bus-name $EVENT_BUS_NAME --targets "Id=logs-target,Arn=$LOG_GROUP_ARN" --region $REGION

Write-Host "  Rule created: all events -> CloudWatch Logs" -ForegroundColor Green

# =============================================================================
# Step 7: Add Lambda permission for EventBridge
# =============================================================================
Write-Host "`n=== Step 7: Adding Lambda Permissions ===" -ForegroundColor Yellow

aws lambda add-permission --function-name "${PREFIX}-whatsapp:live" --statement-id "eventbridge-status-invoke" --action "lambda:InvokeFunction" --principal events.amazonaws.com --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${EVENT_BUS_NAME}/${RULE_NAME_STATUS}" --region $REGION 2>$null

Write-Host "  Lambda permission added for EventBridge" -ForegroundColor Green

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  WEBHOOK INFRASTRUCTURE COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  SNS Topic:" -ForegroundColor Yellow
Write-Host "    $SNS_TOPIC_ARN"
Write-Host ""
Write-Host "  SQS Queues:" -ForegroundColor Yellow
Write-Host "    Main:  $QUEUE_URL"
Write-Host "    DLQ:   arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${DLQ_NAME}"
Write-Host ""
Write-Host "  EventBridge:" -ForegroundColor Yellow
Write-Host "    Bus:   $EVENT_BUS_NAME"
Write-Host "    Rules: $RULE_NAME_MESSAGES (-> SQS)"
Write-Host "           $RULE_NAME_STATUS (-> Lambda)"
Write-Host "           $RULE_NAME_LOGS (-> CloudWatch)"
Write-Host ""
Write-Host "  CloudWatch Logs:" -ForegroundColor Yellow
Write-Host "    $LOG_GROUP"
Write-Host ""
Write-Host "  Flow:" -ForegroundColor Yellow
Write-Host "    WhatsApp -> AWS EUM -> SNS -> Lambda (existing)"
Write-Host "                              -> SQS (new - for async processing)"
Write-Host "                              -> EventBridge -> SQS/Lambda/Logs"
Write-Host ""
