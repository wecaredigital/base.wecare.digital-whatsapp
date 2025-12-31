# =============================================================================
# Deploy Email Notifier Lambda
# =============================================================================
$REGION = "ap-south-1"
$PROJECT = "base-wecare-digital-whatsapp"
$FUNCTION_NAME = "$PROJECT-email-notifier"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

Write-Host "Deploying Email Notifier Lambda..." -ForegroundColor Cyan

# Create deployment package
Write-Host "`n[1/4] Creating deployment package..." -ForegroundColor Yellow
Remove-Item lambda-email-notifier.zip -ErrorAction SilentlyContinue

# Create temp directory
$tempDir = "temp-email-notifier"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy source files
Copy-Item -Path "src/notifications/*" -Destination $tempDir -Recurse
Copy-Item -Path "src/__init__.py" -Destination $tempDir -ErrorAction SilentlyContinue

# Create zip
Compress-Archive -Path "$tempDir/*" -DestinationPath "lambda-email-notifier.zip" -Force
Remove-Item -Recurse -Force $tempDir

Write-Host "  + Package created" -ForegroundColor Green

# Check if function exists
Write-Host "`n[2/4] Checking Lambda function..." -ForegroundColor Yellow
$functionExists = aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>&1
if ($LASTEXITCODE -ne 0) {
    # Create function
    Write-Host "  Creating new function..." -ForegroundColor Gray
    
    # Get role ARN
    $roleArn = "arn:aws:iam::${ACCOUNT_ID}:role/$PROJECT-full-access-role"
    
    aws lambda create-function `
        --function-name $FUNCTION_NAME `
        --runtime python3.12 `
        --handler email_notifier.lambda_handler `
        --role $roleArn `
        --zip-file fileb://lambda-email-notifier.zip `
        --timeout 120 `
        --memory-size 256 `
        --environment "Variables={MESSAGES_TABLE_NAME=$PROJECT,MEDIA_BUCKET=dev.wecare.digital,SES_SENDER_EMAIL=noreply@wecare.digital,INBOUND_NOTIFY_TO=ops@wecare.digital,OUTBOUND_NOTIFY_TO=ops@wecare.digital}" `
        --region $REGION | Out-Null
    
    Write-Host "  + Function created" -ForegroundColor Green
} else {
    # Update function
    Write-Host "  Updating existing function..." -ForegroundColor Gray
    aws lambda update-function-code `
        --function-name $FUNCTION_NAME `
        --zip-file fileb://lambda-email-notifier.zip `
        --region $REGION | Out-Null
    
    Write-Host "  + Function updated" -ForegroundColor Green
}

# Add SQS triggers
Write-Host "`n[3/4] Adding SQS triggers..." -ForegroundColor Yellow

$inboundQueueArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-inbound-notify"
$outboundQueueArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-outbound-notify"

# Check and create event source mappings
$existingMappings = aws lambda list-event-source-mappings --function-name $FUNCTION_NAME --region $REGION | ConvertFrom-Json

$hasInbound = $existingMappings.EventSourceMappings | Where-Object { $_.EventSourceArn -like "*inbound-notify*" }
$hasOutbound = $existingMappings.EventSourceMappings | Where-Object { $_.EventSourceArn -like "*outbound-notify*" }

if (-not $hasInbound) {
    aws lambda create-event-source-mapping `
        --function-name $FUNCTION_NAME `
        --event-source-arn $inboundQueueArn `
        --batch-size 5 `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Inbound notify trigger" -ForegroundColor Green
} else {
    Write-Host "  ~ Inbound trigger exists" -ForegroundColor Gray
}

if (-not $hasOutbound) {
    aws lambda create-event-source-mapping `
        --function-name $FUNCTION_NAME `
        --event-source-arn $outboundQueueArn `
        --batch-size 5 `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Outbound notify trigger" -ForegroundColor Green
} else {
    Write-Host "  ~ Outbound trigger exists" -ForegroundColor Gray
}

Write-Host "`n[4/4] Verification..." -ForegroundColor Yellow
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query "Configuration.[FunctionName,Runtime,LastModified]" --output table

Write-Host "`nEmail Notifier deployed!" -ForegroundColor Green
