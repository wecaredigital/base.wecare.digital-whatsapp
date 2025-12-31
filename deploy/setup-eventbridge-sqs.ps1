# =============================================================================
# Setup EventBridge Rules + SQS Queues for Notifications & Bedrock
# =============================================================================
$REGION = "ap-south-1"
$PROJECT = "base-wecare-digital-whatsapp"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

Write-Host "Setting up EventBridge + SQS infrastructure..." -ForegroundColor Cyan

# =============================================================================
# 1. Create SQS Queues
# =============================================================================
Write-Host "`n[1/5] Creating SQS Queues..." -ForegroundColor Yellow

# DLQs
$dlqNames = @("$PROJECT-notify-dlq", "$PROJECT-bedrock-dlq")
foreach ($dlq in $dlqNames) {
    aws sqs create-queue --queue-name $dlq --region $REGION 2>$null | Out-Null
    Write-Host "  + $dlq" -ForegroundColor Green
}

# Main queues with DLQ
$notifyDlqArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-notify-dlq"
$bedrockDlqArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-bedrock-dlq"

$redriveNotify = "{`"deadLetterTargetArn`":`"$notifyDlqArn`",`"maxReceiveCount`":`"3`"}"
$redriveBedrock = "{`"deadLetterTargetArn`":`"$bedrockDlqArn`",`"maxReceiveCount`":`"3`"}"

aws sqs create-queue --queue-name "$PROJECT-inbound-notify" --attributes "RedrivePolicy=$redriveNotify,VisibilityTimeout=120" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-inbound-notify" -ForegroundColor Green

aws sqs create-queue --queue-name "$PROJECT-outbound-notify" --attributes "RedrivePolicy=$redriveNotify,VisibilityTimeout=120" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-outbound-notify" -ForegroundColor Green

aws sqs create-queue --queue-name "$PROJECT-bedrock-jobs" --attributes "RedrivePolicy=$redriveBedrock,VisibilityTimeout=600" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-bedrock-jobs" -ForegroundColor Green

# Get queue ARNs
$inboundNotifyArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-inbound-notify"
$outboundNotifyArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-outbound-notify"
$bedrockJobsArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-bedrock-jobs"

# =============================================================================
# 2. Create EventBridge Event Bus
# =============================================================================
Write-Host "`n[2/5] Creating EventBridge Event Bus..." -ForegroundColor Yellow

aws events create-event-bus --name "$PROJECT-events" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-events" -ForegroundColor Green

# =============================================================================
# 3. Add SQS Policies for EventBridge
# =============================================================================
Write-Host "`n[3/5] Setting SQS Policies..." -ForegroundColor Yellow

$sqsPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AllowEventBridge",
        "Effect": "Allow",
        "Principal": {"Service": "events.amazonaws.com"},
        "Action": "sqs:SendMessage",
        "Resource": "*",
        "Condition": {"ArnEquals": {"aws:SourceArn": "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/$PROJECT-events/*"}}
    }]
}
"@

$queues = @("$PROJECT-inbound-notify", "$PROJECT-outbound-notify", "$PROJECT-bedrock-jobs")
foreach ($q in $queues) {
    $qUrl = aws sqs get-queue-url --queue-name $q --region $REGION --query QueueUrl --output text
    aws sqs set-queue-attributes --queue-url $qUrl --attributes "Policy=$($sqsPolicy -replace '"','\"')" --region $REGION 2>$null
    Write-Host "  + Policy for $q" -ForegroundColor Green
}

# =============================================================================
# 4. Create EventBridge Rules
# =============================================================================
Write-Host "`n[4/5] Creating EventBridge Rules..." -ForegroundColor Yellow

# Rule: Inbound received -> Notify + Bedrock
$inboundPattern = '{"source":["custom.whatsapp"],"detail-type":["whatsapp.inbound.received"]}'
aws events put-rule --name "$PROJECT-inbound-received" --event-bus-name "$PROJECT-events" --event-pattern $inboundPattern --state ENABLED --region $REGION 2>$null | Out-Null

aws events put-targets --rule "$PROJECT-inbound-received" --event-bus-name "$PROJECT-events" --targets "Id=inbound-notify,Arn=$inboundNotifyArn" "Id=bedrock-jobs,Arn=$bedrockJobsArn" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-inbound-received -> notify + bedrock" -ForegroundColor Green

# Rule: Outbound sent -> Notify
$outboundPattern = '{"source":["custom.whatsapp"],"detail-type":["whatsapp.outbound.sent"]}'
aws events put-rule --name "$PROJECT-outbound-sent" --event-bus-name "$PROJECT-events" --event-pattern $outboundPattern --state ENABLED --region $REGION 2>$null | Out-Null

aws events put-targets --rule "$PROJECT-outbound-sent" --event-bus-name "$PROJECT-events" --targets "Id=outbound-notify,Arn=$outboundNotifyArn" --region $REGION 2>$null | Out-Null
Write-Host "  + $PROJECT-outbound-sent -> notify" -ForegroundColor Green

# =============================================================================
# 5. Create KB Sync Scheduler (every 6 hours)
# =============================================================================
Write-Host "`n[5/5] Creating KB Sync Scheduler..." -ForegroundColor Yellow

$kbSyncPattern = "rate(6 hours)"
aws events put-rule --name "$PROJECT-kb-sync" --schedule-expression "$kbSyncPattern" --state ENABLED --region $REGION 2>$null | Out-Null

# Target: Lambda to trigger KB ingestion
$lambdaArn = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:$PROJECT"
$kbSyncInput = '{"action":"sync_knowledge_base","knowledgeBaseId":"NVF0OLULMG"}'

aws events put-targets --rule "$PROJECT-kb-sync" --targets "Id=kb-sync-lambda,Arn=$lambdaArn,Input='$kbSyncInput'" --region $REGION 2>$null | Out-Null

# Add Lambda permission
aws lambda add-permission --function-name $PROJECT --statement-id "EventBridge-KB-Sync" --action "lambda:InvokeFunction" --principal "events.amazonaws.com" --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/$PROJECT-kb-sync" --region $REGION 2>$null | Out-Null

Write-Host "  + $PROJECT-kb-sync (every 6 hours)" -ForegroundColor Green

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  EventBridge + SQS Setup Complete" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Event Bus: $PROJECT-events"
Write-Host "  Queues: inbound-notify, outbound-notify, bedrock-jobs"
Write-Host "  Rules: inbound-received, outbound-sent, kb-sync"
