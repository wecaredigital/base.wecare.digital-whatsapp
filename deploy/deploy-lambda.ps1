# Lambda Deployment Script for WhatsApp Webhook Handler

$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$FUNCTION_ARN = "arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp"
$SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:010526260063:base-wecare-digital"
$ALIAS_NAME = "live"

Write-Host "=== Step 1: Create deployment package ===" -ForegroundColor Green

# Create zip file with app.py
Compress-Archive -Path ..\app.py -DestinationPath lambda-package.zip -Force

Write-Host "=== Step 2: Update Lambda function code ===" -ForegroundColor Green

aws lambda update-function-code `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --zip-file fileb://lambda-package.zip

Write-Host "Waiting for function update to complete..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

Write-Host "=== Step 3: Update environment variables ===" -ForegroundColor Green

aws lambda update-function-configuration `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --environment file://env-vars.json `
    --timeout 300 `
    --memory-size 512

Write-Host "Waiting for configuration update..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

Write-Host "=== Step 4: Publish new version ===" -ForegroundColor Green

$VERSION_OUTPUT = aws lambda publish-version `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --description "WhatsApp webhook handler with media download and DynamoDB" | ConvertFrom-Json

$VERSION = $VERSION_OUTPUT.Version
Write-Host "Published version: $VERSION"

Write-Host "=== Step 5: Create/Update alias '$ALIAS_NAME' ===" -ForegroundColor Green

# Try to update alias, create if doesn't exist
try {
    aws lambda update-alias `
        --region $REGION `
        --function-name $FUNCTION_NAME `
        --name $ALIAS_NAME `
        --function-version $VERSION
    Write-Host "Updated alias '$ALIAS_NAME' to version $VERSION"
} catch {
    aws lambda create-alias `
        --region $REGION `
        --function-name $FUNCTION_NAME `
        --name $ALIAS_NAME `
        --function-version $VERSION
    Write-Host "Created alias '$ALIAS_NAME' pointing to version $VERSION"
}

$ALIAS_ARN = "${FUNCTION_ARN}:${ALIAS_NAME}"

Write-Host "=== Step 6: Add SNS invoke permission to alias ===" -ForegroundColor Green

# Remove existing permission if any, then add new one
try {
    aws lambda remove-permission `
        --region $REGION `
        --function-name $ALIAS_ARN `
        --statement-id sns-invoke-live 2>$null
} catch {}

aws lambda add-permission `
    --region $REGION `
    --function-name $ALIAS_ARN `
    --statement-id sns-invoke-live `
    --action "lambda:InvokeFunction" `
    --principal sns.amazonaws.com `
    --source-arn $SNS_TOPIC_ARN

Write-Host "=== Step 7: Subscribe SNS to Lambda alias ===" -ForegroundColor Green

# Check existing subscriptions
$EXISTING_SUBS = aws sns list-subscriptions-by-topic `
    --region $REGION `
    --topic-arn $SNS_TOPIC_ARN | ConvertFrom-Json

$ALIAS_SUBSCRIBED = $false
foreach ($sub in $EXISTING_SUBS.Subscriptions) {
    if ($sub.Endpoint -eq $ALIAS_ARN) {
        $ALIAS_SUBSCRIBED = $true
        Write-Host "SNS already subscribed to alias"
        break
    }
}

if (-not $ALIAS_SUBSCRIBED) {
    aws sns subscribe `
        --region $REGION `
        --topic-arn $SNS_TOPIC_ARN `
        --protocol lambda `
        --notification-endpoint $ALIAS_ARN
    Write-Host "Subscribed SNS to Lambda alias"
}

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Lambda ARN: $FUNCTION_ARN"
Write-Host "Alias ARN: $ALIAS_ARN"
Write-Host "Version: $VERSION"

# Cleanup
Remove-Item lambda-package.zip -Force
