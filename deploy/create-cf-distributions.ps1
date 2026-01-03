# Create CloudFront Distributions for S3 buckets
# selfcare.wecare.digital and dev.wecare.digital

$ACM_CERT = "arn:aws:acm:us-east-1:010526260063:certificate/7f24ca44-e21f-4ead-af46-d8e3a1af82ef"

Write-Host "Creating CloudFront distributions..." -ForegroundColor Cyan

# First, create CloudFront Functions if they don't exist
Write-Host "`nChecking CloudFront Functions..." -ForegroundColor Yellow

# Check if redirect function exists
$redirectExists = aws cloudfront list-functions --query "FunctionList.Items[?Name=='wecare-redirect-to-selfservice'].Name" --output text 2>$null
if (-not $redirectExists) {
    Write-Host "Creating wecare-redirect-to-selfservice function..." -ForegroundColor Yellow
    aws cloudfront create-function `
        --name wecare-redirect-to-selfservice `
        --function-config Comment="Root redirect to selfservice",Runtime="cloudfront-js-2.0" `
        --function-code fileb://cf-redirect-function.js `
        --region us-east-1
    
    $func = aws cloudfront describe-function --name wecare-redirect-to-selfservice --region us-east-1 | ConvertFrom-Json
    aws cloudfront publish-function --name wecare-redirect-to-selfservice --if-match $func.ETag --region us-east-1
}

# Check if 404 function exists
$redirect404Exists = aws cloudfront list-functions --query "FunctionList.Items[?Name=='wecare-404-redirect'].Name" --output text 2>$null
if (-not $redirect404Exists) {
    Write-Host "Creating wecare-404-redirect function..." -ForegroundColor Yellow
    aws cloudfront create-function `
        --name wecare-404-redirect `
        --function-config Comment="404 redirect to selfservice",Runtime="cloudfront-js-2.0" `
        --function-code fileb://cf-404-redirect.js `
        --region us-east-1
    
    $func = aws cloudfront describe-function --name wecare-404-redirect --region us-east-1 | ConvertFrom-Json
    aws cloudfront publish-function --name wecare-404-redirect --if-match $func.ETag --region us-east-1
}

# Get function ARNs
$redirectFuncArn = aws cloudfront describe-function --name wecare-redirect-to-selfservice --region us-east-1 --query "FunctionSummary.FunctionMetadata.FunctionARN" --output text
$redirect404FuncArn = aws cloudfront describe-function --name wecare-404-redirect --region us-east-1 --query "FunctionSummary.FunctionMetadata.FunctionARN" --output text

Write-Host "Function ARNs:" -ForegroundColor Green
Write-Host "  Redirect: $redirectFuncArn"
Write-Host "  404: $redirect404FuncArn"

# Create selfcare distribution
Write-Host "`nCreating selfcare.wecare.digital distribution..." -ForegroundColor Yellow
aws cloudfront create-distribution --distribution-config file://selfcare-cf-config.json

# Create dev distribution
Write-Host "`nCreating dev.wecare.digital distribution..." -ForegroundColor Yellow
aws cloudfront create-distribution --distribution-config file://dev-cf-config.json

Write-Host "`nDone! Distributions created." -ForegroundColor Green
Write-Host "Note: It may take 5-15 minutes for distributions to deploy." -ForegroundColor Cyan
