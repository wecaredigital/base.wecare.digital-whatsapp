# Deploy 167 Handlers - Complete Lambda Deployment
# This script packages and deploys the Modular Mono-Lambda with all 167 handlers

$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$ALIAS = "live"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Deploying Modular Mono-Lambda (167 Handlers)" -ForegroundColor Cyan
Write-Host "  Function: $FUNCTION_NAME" -ForegroundColor Cyan
Write-Host "  Region: $REGION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Step 1: Clean up old packages
Write-Host "`n=== Step 1: Cleaning up ===" -ForegroundColor Yellow
$packageName = "lambda-167-handlers.zip"
if (Test-Path $packageName) {
    Remove-Item $packageName -Force
    Write-Host "Removed old package"
}

# Step 2: Create deployment package
Write-Host "`n=== Step 2: Creating deployment package ===" -ForegroundColor Yellow

# Create a temp directory for packaging
$tempDir = "temp_package_167"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Copy app.py
Write-Host "  Adding app.py..."
Copy-Item "app.py" -Destination $tempDir

# Copy handlers module (excluding __pycache__)
Write-Host "  Adding handlers/ module (36 files)..."
New-Item -ItemType Directory -Path "$tempDir/handlers" | Out-Null
Get-ChildItem "handlers" -Filter "*.py" | ForEach-Object {
    Copy-Item $_.FullName -Destination "$tempDir/handlers/"
}

# Copy src module if it exists and is used
if (Test-Path "src") {
    Write-Host "  Adding src/ module..."
    Copy-Item "src" -Destination $tempDir -Recurse -Exclude "__pycache__"
}

# Create the zip package
Write-Host "  Creating zip package..."
Push-Location $tempDir
Compress-Archive -Path "*" -DestinationPath "../$packageName" -Force
Pop-Location

# Clean up temp directory
Remove-Item $tempDir -Recurse -Force

$packageSize = (Get-Item $packageName).Length / 1MB
Write-Host "  Package created: $packageName ($([math]::Round($packageSize, 2)) MB)" -ForegroundColor Green

# Step 3: Update Lambda function code
Write-Host "`n=== Step 3: Updating Lambda function code ===" -ForegroundColor Yellow

aws lambda update-function-code `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --zip-file "fileb://$packageName"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to update Lambda function code" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for update to complete..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

Write-Host "  Lambda code updated successfully" -ForegroundColor Green

# Step 4: Publish new version
Write-Host "`n=== Step 4: Publishing new version ===" -ForegroundColor Yellow

$versionOutput = aws lambda publish-version `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --description "167 handlers - Modular Mono-Lambda deployment" `
    --output json | ConvertFrom-Json

$VERSION = $versionOutput.Version
Write-Host "  Published version: $VERSION" -ForegroundColor Green

# Step 5: Update alias
Write-Host "`n=== Step 5: Updating alias '$ALIAS' ===" -ForegroundColor Yellow

aws lambda update-alias `
    --region $REGION `
    --function-name $FUNCTION_NAME `
    --name $ALIAS `
    --function-version $VERSION

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Alias doesn't exist, creating..." -ForegroundColor Yellow
    aws lambda create-alias `
        --region $REGION `
        --function-name $FUNCTION_NAME `
        --name $ALIAS `
        --function-version $VERSION
}

Write-Host "  Alias '$ALIAS' now points to version $VERSION" -ForegroundColor Green

# Step 6: Quick validation test
Write-Host "`n=== Step 6: Validation Tests ===" -ForegroundColor Yellow

# Test 1: List actions
Write-Host "  Test 1: Listing all actions..."
$testPayload1 = '{"action": "list_actions"}'

$response1 = aws lambda invoke `
    --region $REGION `
    --function-name "${FUNCTION_NAME}:${ALIAS}" `
    --payload $testPayload1 `
    --cli-binary-format raw-in-base64-out `
    test-response-1.json 2>&1

if (Test-Path test-response-1.json) {
    $result1 = Get-Content test-response-1.json | ConvertFrom-Json
    if ($result1.statusCode -eq 200) {
        $body1 = $result1.body | ConvertFrom-Json
        $actionCount = $body1.actions.Count
        Write-Host "    SUCCESS: $actionCount actions available" -ForegroundColor Green
    } else {
        Write-Host "    WARNING: list_actions returned status $($result1.statusCode)" -ForegroundColor Yellow
    }
} else {
    Write-Host "    SKIPPED: Could not invoke Lambda" -ForegroundColor Yellow
}

# Test 2: Handler count
Write-Host "  Test 2: Getting handler count..."
$testPayload2 = '{"action": "handler_count"}'

aws lambda invoke `
    --region $REGION `
    --function-name "${FUNCTION_NAME}:${ALIAS}" `
    --payload $testPayload2 `
    --cli-binary-format raw-in-base64-out `
    test-response-2.json 2>&1 | Out-Null

if (Test-Path test-response-2.json) {
    $result2 = Get-Content test-response-2.json | ConvertFrom-Json
    if ($result2.statusCode -eq 200) {
        $body2 = $result2.body | ConvertFrom-Json
        Write-Host "    SUCCESS: $($body2.count) handlers registered" -ForegroundColor Green
    } else {
        Write-Host "    WARNING: handler_count returned status $($result2.statusCode)" -ForegroundColor Yellow
    }
} else {
    Write-Host "    SKIPPED: Could not invoke Lambda" -ForegroundColor Yellow
}

# Test 3: EUM template handler (one of the new handlers)
Write-Host "  Test 3: Testing EUM handler..."
$testPayload3 = '{"action": "eum_get_supported_formats"}'

aws lambda invoke `
    --region $REGION `
    --function-name "${FUNCTION_NAME}:${ALIAS}" `
    --payload $testPayload3 `
    --cli-binary-format raw-in-base64-out `
    test-response-3.json 2>&1 | Out-Null

if (Test-Path test-response-3.json) {
    $result3 = Get-Content test-response-3.json | ConvertFrom-Json
    if ($result3.statusCode -eq 200) {
        Write-Host "    SUCCESS: EUM handlers working" -ForegroundColor Green
    } else {
        Write-Host "    WARNING: eum_get_supported_formats returned status $($result3.statusCode)" -ForegroundColor Yellow
    }
} else {
    Write-Host "    SKIPPED: Could not invoke Lambda" -ForegroundColor Yellow
}

# Cleanup test files
Remove-Item test-response-*.json -Force -ErrorAction SilentlyContinue

# Summary
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Function: $FUNCTION_NAME"
Write-Host "  Version:  $VERSION"
Write-Host "  Alias:    $ALIAS"
Write-Host "  Package:  $packageName ($([math]::Round($packageSize, 2)) MB)"
Write-Host ""
Write-Host "  Test with:" -ForegroundColor Yellow
Write-Host "  aws lambda invoke --function-name ${FUNCTION_NAME}:${ALIAS} --payload '{\"action\":\"list_actions\"}' --cli-binary-format raw-in-base64-out out.json --region $REGION"
Write-Host ""
