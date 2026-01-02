# =============================================================================
# QUICK DEPLOY - Deploy updated Lambda code to AWS
# =============================================================================
# Usage: .\deploy\quick-deploy.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WECARE.DIGITAL - Quick Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Configuration
$REGION = "ap-south-1"
$LAMBDA_MAIN = "base-wecare-digital-whatsapp"
$ZIP_FILE = "lambda-package.zip"

Write-Host "`n[1/4] Creating deployment package..." -ForegroundColor Yellow

# Remove old zip if exists
if (Test-Path $ZIP_FILE) { Remove-Item $ZIP_FILE -Force }

# Create zip with all Python files
$filesToInclude = @(
    "app.py",
    "requirements.txt"
)

# Add handlers folder
$handlersFiles = Get-ChildItem -Path "handlers" -Filter "*.py" -Recurse
$srcFiles = Get-ChildItem -Path "src" -Filter "*.py" -Recurse -ErrorAction SilentlyContinue

# Create zip
Compress-Archive -Path "app.py" -DestinationPath $ZIP_FILE -Force
Compress-Archive -Path "handlers" -Update -DestinationPath $ZIP_FILE
if (Test-Path "src") {
    Compress-Archive -Path "src" -Update -DestinationPath $ZIP_FILE
}

Write-Host "[2/4] Package created: $ZIP_FILE" -ForegroundColor Green

Write-Host "`n[3/4] Deploying to Lambda: $LAMBDA_MAIN..." -ForegroundColor Yellow

try {
    aws lambda update-function-code `
        --function-name $LAMBDA_MAIN `
        --zip-file "fileb://$ZIP_FILE" `
        --region $REGION `
        --output json | Out-Null
    
    Write-Host "[3/4] Lambda updated successfully!" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to update Lambda: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n[4/4] Verifying deployment..." -ForegroundColor Yellow

# Wait for update to complete
Start-Sleep -Seconds 3

$status = aws lambda get-function --function-name $LAMBDA_MAIN --region $REGION --query "Configuration.LastUpdateStatus" --output text
Write-Host "Lambda Status: $status" -ForegroundColor $(if ($status -eq "Successful") { "Green" } else { "Yellow" })

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nTest URLs:" -ForegroundColor White
Write-Host "  Short Links:  https://r.wecare.digital/" -ForegroundColor Gray
Write-Host "  Payments:     https://p.wecare.digital/" -ForegroundColor Gray
Write-Host "  Rs.1 Test:    https://p.wecare.digital/p/test" -ForegroundColor Gray

Write-Host "`nAPI Gateway: z8raub1eth.execute-api.ap-south-1.amazonaws.com/prod" -ForegroundColor Gray

# Cleanup
if (Test-Path $ZIP_FILE) { Remove-Item $ZIP_FILE -Force }
Write-Host "`nCleanup complete." -ForegroundColor Gray
