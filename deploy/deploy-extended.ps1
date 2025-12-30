# Deploy Extended Handlers
# This script packages and deploys the Lambda with extended handlers

$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$ALIAS = "live"

Write-Host "=== Deploying Extended Handlers ===" -ForegroundColor Green

# Step 1: Create deployment package
Write-Host "`n=== Step 1: Creating deployment package ===" -ForegroundColor Yellow

# Clean up old package
if (Test-Path "lambda-package-extended.zip") {
    Remove-Item "lambda-package-extended.zip"
}

# Create package with handlers
Write-Host "Adding app.py..."
Compress-Archive -Path "..\app.py" -DestinationPath "lambda-package-extended.zip"

Write-Host "Adding handlers module..."
Compress-Archive -Path "..\handlers" -Update -DestinationPath "lambda-package-extended.zip"

Write-Host "Package created: lambda-package-extended.zip"

# Step 2: Update Lambda function
Write-Host "`n=== Step 2: Updating Lambda function ===" -ForegroundColor Yellow

aws lambda update-function-code `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --zip-file fileb://lambda-package-extended.zip

Write-Host "Waiting for update to complete..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

# Step 3: Publish new version
Write-Host "`n=== Step 3: Publishing new version ===" -ForegroundColor Yellow

$VERSION = aws lambda publish-version `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --description "Extended handlers deployment" `
    --query 'Version' `
    --output text

Write-Host "Published version: $VERSION"

# Step 4: Update alias
Write-Host "`n=== Step 4: Updating alias '$ALIAS' ===" -ForegroundColor Yellow

aws lambda update-alias `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --name $ALIAS `
    --function-version $VERSION

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Function: $FUNCTION_NAME"
Write-Host "Version: $VERSION"
Write-Host "Alias: $ALIAS"

# Step 5: Test
Write-Host "`n=== Step 5: Quick Test ===" -ForegroundColor Yellow

$testPayload = '{"action": "eum_get_supported_formats"}'
$testPayloadBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($testPayload))

aws lambda invoke `
    --region $REGION `
    --function-name "${FUNCTION_NAME}:${ALIAS}" `
    --payload $testPayload `
    --cli-binary-format raw-in-base64-out `
    test-response.json

Write-Host "Test response:"
Get-Content test-response.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
