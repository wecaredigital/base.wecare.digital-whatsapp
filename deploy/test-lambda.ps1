# Test Lambda Function Script

$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$ALIAS_NAME = "live"

Write-Host "=== Testing Lambda Function ===" -ForegroundColor Green

# Test with the alias
$FUNCTION_ARN = "arn:aws:lambda:ap-south-1:010526260063:function:${FUNCTION_NAME}:${ALIAS_NAME}"

Write-Host "Invoking: $FUNCTION_ARN"

aws lambda invoke `
    --region $REGION `
    --function-name $FUNCTION_ARN `
    --payload fileb://test-event.json `
    --cli-binary-format raw-in-base64-out `
    response.json

Write-Host "`n=== Response ===" -ForegroundColor Green
Get-Content response.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

Write-Host "`n=== CloudWatch Logs (last 5 minutes) ===" -ForegroundColor Green
$LOG_GROUP = "/aws/lambda/$FUNCTION_NAME"
$START_TIME = [int64]((Get-Date).AddMinutes(-5).ToUniversalTime() - (Get-Date "1970-01-01")).TotalMilliseconds

aws logs filter-log-events `
    --region $REGION `
    --log-group-name $LOG_GROUP `
    --start-time $START_TIME `
    --filter-pattern "RAW_EVENT" `
    --limit 5

# Cleanup
Remove-Item response.json -Force -ErrorAction SilentlyContinue
