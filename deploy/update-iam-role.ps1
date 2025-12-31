# Update IAM Role for Lambda
# This script attaches the required policy to the Lambda execution role

$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$POLICY_NAME = "WhatsAppWebhookHandlerPolicy"

Write-Host "=== Getting Lambda execution role ===" -ForegroundColor Green

$FUNCTION_CONFIG = aws lambda get-function-configuration `
    --region $REGION `
    --function-name $FUNCTION_NAME | ConvertFrom-Json

$ROLE_ARN = $FUNCTION_CONFIG.Role
$ROLE_NAME = $ROLE_ARN.Split("/")[-1]

Write-Host "Lambda Role: $ROLE_NAME"

Write-Host "=== Creating/Updating inline policy ===" -ForegroundColor Green

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$policyFile = Join-Path $scriptDir "iam-policy.json"

aws iam put-role-policy `
    --role-name $ROLE_NAME `
    --policy-name $POLICY_NAME `
    --policy-document "file://$policyFile"

Write-Host "Policy '$POLICY_NAME' attached to role '$ROLE_NAME'"

Write-Host "`n=== Verifying policy ===" -ForegroundColor Green
aws iam get-role-policy --role-name $ROLE_NAME --policy-name $POLICY_NAME
