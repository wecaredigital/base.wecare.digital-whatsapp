# Update CloudFront Functions
# Functions: wecare-redirect-to-selfservice, wecare-404-redirect

Write-Host "Updating CloudFront Functions..." -ForegroundColor Cyan

# Get current ETags
$redirectFunc = aws cloudfront describe-function --name wecare-redirect-to-selfservice --region us-east-1 | ConvertFrom-Json
$redirect404Func = aws cloudfront describe-function --name wecare-404-redirect --region us-east-1 | ConvertFrom-Json

$redirectETag = $redirectFunc.ETag
$redirect404ETag = $redirect404Func.ETag

Write-Host "Current ETags:" -ForegroundColor Yellow
Write-Host "  wecare-redirect-to-selfservice: $redirectETag"
Write-Host "  wecare-404-redirect: $redirect404ETag"

# Update viewer-request function
Write-Host "`nUpdating wecare-redirect-to-selfservice..." -ForegroundColor Yellow
aws cloudfront update-function `
    --name wecare-redirect-to-selfservice `
    --function-config Comment="Root redirect to selfservice",Runtime="cloudfront-js-2.0" `
    --function-code fileb://cf-redirect-function.js `
    --if-match $redirectETag `
    --region us-east-1

# Get new ETag and publish
$redirectFunc2 = aws cloudfront describe-function --name wecare-redirect-to-selfservice --region us-east-1 | ConvertFrom-Json
aws cloudfront publish-function --name wecare-redirect-to-selfservice --if-match $redirectFunc2.ETag --region us-east-1

# Update viewer-response function  
Write-Host "`nUpdating wecare-404-redirect..." -ForegroundColor Yellow
aws cloudfront update-function `
    --name wecare-404-redirect `
    --function-config Comment="404 redirect to selfservice",Runtime="cloudfront-js-2.0" `
    --function-code fileb://cf-404-redirect.js `
    --if-match $redirect404ETag `
    --region us-east-1

# Get new ETag and publish
$redirect404Func2 = aws cloudfront describe-function --name wecare-404-redirect --region us-east-1 | ConvertFrom-Json
aws cloudfront publish-function --name wecare-404-redirect --if-match $redirect404Func2.ETag --region us-east-1

Write-Host "`nDone! Functions updated and published." -ForegroundColor Green
Write-Host "Changes will take effect on next CloudFront request." -ForegroundColor Cyan
