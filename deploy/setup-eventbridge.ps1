# =============================================================================
# Setup EventBridge Rules for base-wecare-digital-whatsapp
# =============================================================================
# Creates EventBridge rules for WhatsApp event routing:
# - Inbound message received -> Notify + Bedrock queues
# - Outbound message sent -> Notify queue
# - Message status updates -> Lambda
# - Template status changes -> Lambda
# - Campaign events -> Lambda
# =============================================================================

$ErrorActionPreference = "Stop"

$REGION = "ap-south-1"
$PROJECT_NAME = "base-wecare-digital-whatsapp"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

# Resource names
$EVENT_BUS_NAME = "$PROJECT_NAME-events"
$LAMBDA_ARN = "arn:aws:lambda:$REGION`:$ACCOUNT_ID`:function:$PROJECT_NAME"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Setting up EventBridge Rules" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_NAME" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# =============================================================================
# Step 1: Create Event Bus
# =============================================================================
Write-Host "`n[1/6] Creating Event Bus..." -ForegroundColor Yellow

try {
    aws events create-event-bus --name $EVENT_BUS_NAME --region $REGION 2>$null | Out-Null
    Write-Host "  + Created event bus: $EVENT_BUS_NAME" -ForegroundColor Green
} catch {
    Write-Host "  ~ Event bus exists: $EVENT_BUS_NAME" -ForegroundColor Gray
}

# =============================================================================
# Step 2: Create SQS Queues
# =============================================================================
Write-Host "`n[2/6] Creating SQS Queues..." -ForegroundColor Yellow

$queues = @(
    @{Name="$PROJECT_NAME-inbound-notify"; Visibility=120},
    @{Name="$PROJECT_NAME-outbound-notify"; Visibility=120},
    @{Name="$PROJECT_NAME-bedrock-events"; Visibility=600},
    @{Name="$PROJECT_NAME-notify-dlq"; Visibility=120},
    @{Name="$PROJECT_NAME-bedrock-dlq"; Visibility=120}
)

$queueUrls = @{}
foreach ($q in $queues) {
    try {
        $result = aws sqs create-queue --queue-name $q.Name `
            --attributes "VisibilityTimeout=$($q.Visibility)" `
            --region $REGION 2>$null | ConvertFrom-Json
        $queueUrls[$q.Name] = $result.QueueUrl
        Write-Host "  + Created queue: $($q.Name)" -ForegroundColor Green
    } catch {
        $existing = aws sqs get-queue-url --queue-name $q.Name --region $REGION | ConvertFrom-Json
        $queueUrls[$q.Name] = $existing.QueueUrl
        Write-Host "  ~ Queue exists: $($q.Name)" -ForegroundColor Gray
    }
}

# Get queue ARNs
$INBOUND_NOTIFY_ARN = "arn:aws:sqs:$REGION`:$ACCOUNT_ID`:$PROJECT_NAME-inbound-notify"
$OUTBOUND_NOTIFY_ARN = "arn:aws:sqs:$REGION`:$ACCOUNT_ID`:$PROJECT_NAME-outbound-notify"
$BEDROCK_QUEUE_ARN = "arn:aws:sqs:$REGION`:$ACCOUNT_ID`:$PROJECT_NAME-bedrock-events"

# =============================================================================
# Step 3: Create EventBridge Rules
# =============================================================================
Write-Host "`n[3/6] Creating EventBridge Rules..." -ForegroundColor Yellow

# Rule 1: Inbound message received
$inboundPatternFile = "temp-inbound-pattern.json"
[System.IO.File]::WriteAllText($inboundPatternFile, '{"source":["custom.whatsapp"],"detail-type":["whatsapp.inbound.received"]}')

aws events put-rule --name "$PROJECT_NAME-inbound-received" `
    --event-bus-name $EVENT_BUS_NAME `
    --event-pattern file://$inboundPatternFile `
    --state ENABLED `
    --description "Route inbound WhatsApp messages" `
    --region $REGION | Out-Null

Write-Host "  + Created rule: inbound-received" -ForegroundColor Green

# Rule 2: Outbound message sent
$outboundPatternFile = "temp-outbound-pattern.json"
[System.IO.File]::WriteAllText($outboundPatternFile, '{"source":["custom.whatsapp"],"detail-type":["whatsapp.outbound.sent"]}')

aws events put-rule --name "$PROJECT_NAME-outbound-sent" `
    --event-bus-name $EVENT_BUS_NAME `
    --event-pattern file://$outboundPatternFile `
    --state ENABLED `
    --description "Route outbound WhatsApp messages" `
    --region $REGION | Out-Null

Write-Host "  + Created rule: outbound-sent" -ForegroundColor Green

# Rule 3: Message status updates
$statusPatternFile = "temp-status-pattern.json"
[System.IO.File]::WriteAllText($statusPatternFile, '{"source":["custom.whatsapp"],"detail-type":["whatsapp.message.status"]}')

aws events put-rule --name "$PROJECT_NAME-status-update" `
    --event-bus-name $EVENT_BUS_NAME `
    --event-pattern file://$statusPatternFile `
    --state ENABLED `
    --description "Route message status updates" `
    --region $REGION | Out-Null

Write-Host "  + Created rule: status-update" -ForegroundColor Green

# Rule 4: Template status changes
$templatePatternFile = "temp-template-pattern.json"
[System.IO.File]::WriteAllText($templatePatternFile, '{"source":["custom.whatsapp"],"detail-type":["whatsapp.template.status"]}')

aws events put-rule --name "$PROJECT_NAME-template-status" `
    --event-bus-name $EVENT_BUS_NAME `
    --event-pattern file://$templatePatternFile `
    --state ENABLED `
    --description "Route template status changes" `
    --region $REGION | Out-Null

Write-Host "  + Created rule: template-status" -ForegroundColor Green

# Rule 5: Campaign events
$campaignPatternFile = "temp-campaign-pattern.json"
[System.IO.File]::WriteAllText($campaignPatternFile, '{"source":["custom.whatsapp"],"detail-type":[{"prefix":"campaign."}]}')

aws events put-rule --name "$PROJECT_NAME-campaign-events" `
    --event-bus-name $EVENT_BUS_NAME `
    --event-pattern file://$campaignPatternFile `
    --state ENABLED `
    --description "Route campaign events" `
    --region $REGION | Out-Null

Write-Host "  + Created rule: campaign-events" -ForegroundColor Green

# Cleanup pattern files
Remove-Item temp-*-pattern.json -ErrorAction SilentlyContinue

# =============================================================================
# Step 4: Add SQS Permissions for EventBridge
# =============================================================================
Write-Host "`n[4/6] Adding SQS Permissions..." -ForegroundColor Yellow

$sqsPolicyContent = @"
{"Version":"2012-10-17","Statement":[{"Sid":"AllowEventBridge","Effect":"Allow","Principal":{"Service":"events.amazonaws.com"},"Action":"sqs:SendMessage","Resource":"*","Condition":{"ArnLike":{"aws:SourceArn":"arn:aws:events:$REGION`:$ACCOUNT_ID`:rule/$EVENT_BUS_NAME/*"}}}]}
"@

foreach ($qName in @("$PROJECT_NAME-inbound-notify", "$PROJECT_NAME-outbound-notify", "$PROJECT_NAME-bedrock-events")) {
    $qUrl = $queueUrls[$qName]
    if ($qUrl) {
        # Create attributes JSON with Policy key
        $attrsContent = @{ Policy = $sqsPolicyContent } | ConvertTo-Json -Compress
        $attrsFile = "temp-sqs-attrs-$($qName -replace '-','').json"
        [System.IO.File]::WriteAllText($attrsFile, $attrsContent)
        aws sqs set-queue-attributes --queue-url $qUrl `
            --attributes file://$attrsFile `
            --region $REGION 2>$null | Out-Null
        Remove-Item $attrsFile -ErrorAction SilentlyContinue
        Write-Host "  + Set policy for: $qName" -ForegroundColor Green
    }
}

# =============================================================================
# Step 5: Add Targets to Rules
# =============================================================================
Write-Host "`n[5/6] Adding Targets to Rules..." -ForegroundColor Yellow

# Inbound received -> Notify + Bedrock queues
$inboundTargetsJson = "[{`"Id`":`"inbound-notify`",`"Arn`":`"$INBOUND_NOTIFY_ARN`"},{`"Id`":`"bedrock-queue`",`"Arn`":`"$BEDROCK_QUEUE_ARN`"}]"
[System.IO.File]::WriteAllText("temp-inbound-targets.json", $inboundTargetsJson)

aws events put-targets --rule "$PROJECT_NAME-inbound-received" `
    --event-bus-name $EVENT_BUS_NAME `
    --targets file://temp-inbound-targets.json `
    --region $REGION | Out-Null

Remove-Item temp-inbound-targets.json -ErrorAction SilentlyContinue
Write-Host "  + Added targets to inbound-received" -ForegroundColor Green

# Outbound sent -> Notify queue
$outboundTargetsJson = "[{`"Id`":`"outbound-notify`",`"Arn`":`"$OUTBOUND_NOTIFY_ARN`"}]"
[System.IO.File]::WriteAllText("temp-outbound-targets.json", $outboundTargetsJson)

aws events put-targets --rule "$PROJECT_NAME-outbound-sent" `
    --event-bus-name $EVENT_BUS_NAME `
    --targets file://temp-outbound-targets.json `
    --region $REGION | Out-Null

Remove-Item temp-outbound-targets.json -ErrorAction SilentlyContinue
Write-Host "  + Added targets to outbound-sent" -ForegroundColor Green

# Status update -> Lambda
aws lambda add-permission --function-name $PROJECT_NAME `
    --statement-id "EventBridge-status-update" `
    --action "lambda:InvokeFunction" `
    --principal "events.amazonaws.com" `
    --source-arn "arn:aws:events:$REGION`:$ACCOUNT_ID`:rule/$EVENT_BUS_NAME/$PROJECT_NAME-status-update" `
    --region $REGION 2>$null | Out-Null

$statusTargetsJson = "[{`"Id`":`"lambda`",`"Arn`":`"$LAMBDA_ARN`",`"Input`":`"{\\\`"action\\\`":\\\`"process_status_update\\\`"}`"}]"
[System.IO.File]::WriteAllText("temp-status-targets.json", $statusTargetsJson)

aws events put-targets --rule "$PROJECT_NAME-status-update" `
    --event-bus-name $EVENT_BUS_NAME `
    --targets file://temp-status-targets.json `
    --region $REGION | Out-Null

Remove-Item temp-status-targets.json -ErrorAction SilentlyContinue
Write-Host "  + Added targets to status-update" -ForegroundColor Green

# Template status -> Lambda
aws lambda add-permission --function-name $PROJECT_NAME `
    --statement-id "EventBridge-template-status" `
    --action "lambda:InvokeFunction" `
    --principal "events.amazonaws.com" `
    --source-arn "arn:aws:events:$REGION`:$ACCOUNT_ID`:rule/$EVENT_BUS_NAME/$PROJECT_NAME-template-status" `
    --region $REGION 2>$null | Out-Null

$templateTargetsJson = "[{`"Id`":`"lambda`",`"Arn`":`"$LAMBDA_ARN`",`"Input`":`"{\\\`"action\\\`":\\\`"process_template_status\\\`"}`"}]"
[System.IO.File]::WriteAllText("temp-template-targets.json", $templateTargetsJson)

aws events put-targets --rule "$PROJECT_NAME-template-status" `
    --event-bus-name $EVENT_BUS_NAME `
    --targets file://temp-template-targets.json `
    --region $REGION | Out-Null

Remove-Item temp-template-targets.json -ErrorAction SilentlyContinue
Write-Host "  + Added targets to template-status" -ForegroundColor Green

# Campaign events -> Lambda
aws lambda add-permission --function-name $PROJECT_NAME `
    --statement-id "EventBridge-campaign-events" `
    --action "lambda:InvokeFunction" `
    --principal "events.amazonaws.com" `
    --source-arn "arn:aws:events:$REGION`:$ACCOUNT_ID`:rule/$EVENT_BUS_NAME/$PROJECT_NAME-campaign-events" `
    --region $REGION 2>$null | Out-Null

$campaignTargetsJson = "[{`"Id`":`"lambda`",`"Arn`":`"$LAMBDA_ARN`",`"Input`":`"{\\\`"action\\\`":\\\`"process_campaign_event\\\`"}`"}]"
[System.IO.File]::WriteAllText("temp-campaign-targets.json", $campaignTargetsJson)

aws events put-targets --rule "$PROJECT_NAME-campaign-events" `
    --event-bus-name $EVENT_BUS_NAME `
    --targets $campaignTargets `
    --region $REGION | Out-Null

Write-Host "  + Added targets to campaign-events" -ForegroundColor Green

# =============================================================================
# Step 6: Update Lambda Environment
# =============================================================================
Write-Host "`n[6/6] Updating Lambda Environment..." -ForegroundColor Yellow

# Get current env vars
$currentConfig = aws lambda get-function-configuration `
    --function-name $PROJECT_NAME `
    --region $REGION | ConvertFrom-Json

$currentEnv = @{}
if ($currentConfig.Environment.Variables) {
    $currentConfig.Environment.Variables.PSObject.Properties | ForEach-Object {
        $currentEnv[$_.Name] = $_.Value
    }
}

# Add EventBridge config
$currentEnv["EVENT_BUS_NAME"] = $EVENT_BUS_NAME
$currentEnv["INBOUND_NOTIFY_QUEUE_URL"] = $queueUrls["$PROJECT_NAME-inbound-notify"]
$currentEnv["OUTBOUND_NOTIFY_QUEUE_URL"] = $queueUrls["$PROJECT_NAME-outbound-notify"]
$currentEnv["BEDROCK_QUEUE_URL"] = $queueUrls["$PROJECT_NAME-bedrock-events"]

$envJson = @{ Variables = $currentEnv } | ConvertTo-Json -Compress -Depth 3
$envJson | Out-File -FilePath "temp-lambda-env.json" -Encoding UTF8 -NoNewline

aws lambda update-function-configuration `
    --function-name $PROJECT_NAME `
    --environment file://temp-lambda-env.json `
    --region $REGION 2>$null | Out-Null

Remove-Item temp-lambda-env.json -ErrorAction SilentlyContinue

Write-Host "  + Updated Lambda environment" -ForegroundColor Green

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "EventBridge Setup Complete" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Event Bus: $EVENT_BUS_NAME" -ForegroundColor White
Write-Host ""
Write-Host "Rules Created:" -ForegroundColor White
Write-Host "  - $PROJECT_NAME-inbound-received -> SQS (notify + bedrock)" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-outbound-sent -> SQS (notify)" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-status-update -> Lambda" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-template-status -> Lambda" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-campaign-events -> Lambda" -ForegroundColor Gray
Write-Host ""
Write-Host "Queues:" -ForegroundColor White
Write-Host "  - $PROJECT_NAME-inbound-notify" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-outbound-notify" -ForegroundColor Gray
Write-Host "  - $PROJECT_NAME-bedrock-events" -ForegroundColor Gray
Write-Host ""
Write-Host "To publish events:" -ForegroundColor Yellow
Write-Host '  aws events put-events --entries "[{\"Source\":\"custom.whatsapp\",\"DetailType\":\"whatsapp.inbound.received\",\"Detail\":\"{\\\"messageId\\\":\\\"test\\\"}\",\"EventBusName\":\"' + $EVENT_BUS_NAME + '\"}]" --region ' + $REGION -ForegroundColor Gray
Write-Host "=============================================" -ForegroundColor Cyan
