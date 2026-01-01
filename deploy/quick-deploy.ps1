# Quick deploy script
$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"

Write-Host "Creating deployment package..."

# Clean
Remove-Item deploy_pkg -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item deploy.zip -Force -ErrorAction SilentlyContinue

# Create structure
New-Item -ItemType Directory -Path deploy_pkg -Force | Out-Null
New-Item -ItemType Directory -Path deploy_pkg/handlers -Force | Out-Null

# Copy files
Copy-Item ../app.py -Destination deploy_pkg/ -Force
Copy-Item ../handlers/*.py -Destination deploy_pkg/handlers/ -Force
if (Test-Path ../src) { Copy-Item ../src -Destination deploy_pkg/ -Recurse -Force }

# Create zip
Push-Location deploy_pkg
Compress-Archive -Path * -DestinationPath ../deploy.zip -Force
Pop-Location

Write-Host "Package: $([math]::Round((Get-Item deploy.zip).Length / 1MB, 2)) MB"

# Deploy
Write-Host "Deploying to Lambda..."
aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file "fileb://deploy.zip" --region $REGION --query "LastModified" --output text
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

# Publish
$ver = aws lambda publish-version --function-name $FUNCTION_NAME --region $REGION --query "Version" --output text
aws lambda update-alias --function-name $FUNCTION_NAME --name live --function-version $ver --region $REGION | Out-Null

Write-Host "Deployed version: $ver"

# Cleanup
Remove-Item deploy_pkg -Recurse -Force
Remove-Item deploy.zip -Force

# Test
Write-Host "Testing..."
aws lambda invoke --function-name "${FUNCTION_NAME}:live" --region $REGION --payload '{"action":"get_config"}' --cli-binary-format raw-in-base64-out test_out.json 2>$null
$result = Get-Content test_out.json | ConvertFrom-Json
if ($result.config.welcomeEnabled -ne $null) {
    Write-Host "SUCCESS: welcomeEnabled = $($result.config.welcomeEnabled)"
} else {
    Write-Host "WARNING: welcomeEnabled not found in config"
}
Remove-Item test_out.json -Force
