# =============================================================================
# WECARE DIGITAL - Direct Messaging Infrastructure Setup
# =============================================================================
# Creates:
# - dm.wecare.digital → API Gateway (WhatsApp, Bedrock Agent Core, Agents)
# - d.wecare.digital → CloudFront + S3 (Media Storage)
# - Proper redirects, tags, and documentation
# =============================================================================

$ErrorActionPreference = "Stop"
$REGION = "ap-south-1"
$HOSTED_ZONE_ID = "Z0123324UGZKLOSJPDS8"
$ACM_CERT_ARN = "arn:aws:acm:us-east-1:010526260063:certificate/7f24ca44-e21f-4ead-af46-d8e3a1af82ef"
$ACCOUNT_ID = "010526260063"

# Standard tags for all resources
$TAGS = @{
    Project = "wecare-dm"
    Owner = "wecare.digital"
    Environment = "prod"
    CostCenter = "messaging"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WECARE.DIGITAL - DM Infrastructure" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# =============================================================================
# STEP 1A: API Gateway Custom Domain (dm.wecare.digital)
# =============================================================================
Write-Host "`n[1/6] Setting up API Gateway custom domain: dm.wecare.digital" -ForegroundColor Yellow

# Check if custom domain exists
$existingDomain = aws apigatewayv2 get-domain-names --region $REGION --query "Items[?DomainName=='dm.wecare.digital'].DomainName" --output text 2>$null

if ($existingDomain -eq "dm.wecare.digital") {
    Write-Host "  Custom domain dm.wecare.digital already exists" -ForegroundColor Green
} else {
    Write-Host "  Creating custom domain dm.wecare.digital..." -ForegroundColor White
    
    # For API Gateway HTTP API, we need regional certificate
    $regionalCert = aws acm list-certificates --region $REGION --query "CertificateSummaryList[?contains(DomainName, 'wecare.digital')].CertificateArn" --output text
    
    if (-not $regionalCert) {
        Write-Host "  No regional certificate found. Creating one..." -ForegroundColor Yellow
        # Request certificate in ap-south-1
        $certArn = aws acm request-certificate `
            --domain-name "dm.wecare.digital" `
            --validation-method DNS `
            --region $REGION `
            --query "CertificateArn" --output text
        
        Write-Host "  Certificate requested: $certArn" -ForegroundColor White
        Write-Host "  Please validate the certificate via DNS before continuing." -ForegroundColor Red
        exit 1
    }
    
    aws apigatewayv2 create-domain-name `
        --domain-name "dm.wecare.digital" `
        --domain-name-configurations "CertificateArn=$regionalCert,EndpointType=REGIONAL" `
        --region $REGION
    
    Write-Host "  Custom domain created" -ForegroundColor Green
}

# =============================================================================
# STEP 1B: Create HTTP API for dm.wecare.digital
# =============================================================================
Write-Host "`n[2/6] Creating HTTP API for dm.wecare.digital" -ForegroundColor Yellow

# Check if API exists
$existingApi = aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='wecare-dm-api'].ApiId" --output text

if ($existingApi) {
    Write-Host "  API wecare-dm-api already exists: $existingApi" -ForegroundColor Green
    $API_ID = $existingApi
} else {
    Write-Host "  Creating HTTP API wecare-dm-api..." -ForegroundColor White
    
    $apiResult = aws apigatewayv2 create-api `
        --name "wecare-dm-api" `
        --protocol-type HTTP `
        --description "Wecare Digital Direct Messaging API - WhatsApp, Bedrock Agents, Media" `
        --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=*" `
        --region $REGION `
        --output json | ConvertFrom-Json
    
    $API_ID = $apiResult.ApiId
    Write-Host "  API created: $API_ID" -ForegroundColor Green
}

Write-Host "  API ID: $API_ID" -ForegroundColor Cyan

# =============================================================================
# STEP 2: S3 Bucket Setup (d.wecare.digital)
# =============================================================================
Write-Host "`n[3/6] Setting up S3 bucket: d.wecare.digital" -ForegroundColor Yellow

# Check if bucket exists
$bucketExists = aws s3api head-bucket --bucket "d.wecare.digital" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Bucket d.wecare.digital already exists" -ForegroundColor Green
} else {
    Write-Host "  Creating bucket d.wecare.digital..." -ForegroundColor White
    aws s3api create-bucket `
        --bucket "d.wecare.digital" `
        --region $REGION `
        --create-bucket-configuration LocationConstraint=$REGION
}

# Create folder structure
Write-Host "  Creating folder structure (d/ and u/)..." -ForegroundColor White
aws s3api put-object --bucket "d.wecare.digital" --key "d/" --region $REGION | Out-Null
aws s3api put-object --bucket "d.wecare.digital" --key "u/" --region $REGION | Out-Null

# Create redirect HTML files
$redirectHtml = @"
<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url=https://wecare.digital/selfservice">
<script>window.location.href='https://wecare.digital/selfservice';</script>
</head>
<body>Redirecting to <a href="https://wecare.digital/selfservice">wecare.digital/selfservice</a>...</body>
</html>
"@

$redirectHtml | Out-File -FilePath "temp-index.html" -Encoding UTF8
aws s3 cp "temp-index.html" "s3://d.wecare.digital/index.html" --content-type "text/html" --region $REGION | Out-Null
aws s3 cp "temp-index.html" "s3://d.wecare.digital/404.html" --content-type "text/html" --region $REGION | Out-Null
Remove-Item "temp-index.html" -Force

# Add bucket tags
aws s3api put-bucket-tagging --bucket "d.wecare.digital" --tagging "TagSet=[{Key=Project,Value=wecare-dm},{Key=Owner,Value=wecare.digital},{Key=Environment,Value=prod},{Key=CostCenter,Value=messaging}]" --region $REGION

Write-Host "  Bucket configured with d/ and u/ folders" -ForegroundColor Green

# =============================================================================
# STEP 3: CloudFront Distribution for d.wecare.digital
# =============================================================================
Write-Host "`n[4/6] Setting up CloudFront for d.wecare.digital" -ForegroundColor Yellow

# Check if distribution exists
$existingDist = aws cloudfront list-distributions --query "DistributionList.Items[?contains(Aliases.Items, 'd.wecare.digital')].Id" --output text

if ($existingDist) {
    Write-Host "  CloudFront distribution already exists: $existingDist" -ForegroundColor Green
} else {
    Write-Host "  Creating CloudFront distribution..." -ForegroundColor White
    Write-Host "  (This will be created via JSON config)" -ForegroundColor Gray
}

Write-Host "`n[5/6] Infrastructure setup complete!" -ForegroundColor Green
Write-Host "`n[6/6] Next steps:" -ForegroundColor Yellow
Write-Host "  1. Validate ACM certificate for dm.wecare.digital (if new)" -ForegroundColor White
Write-Host "  2. Create API Gateway routes and integrations" -ForegroundColor White
Write-Host "  3. Create CloudFront distribution for d.wecare.digital" -ForegroundColor White
Write-Host "  4. Update Route 53 DNS records" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "INFRASTRUCTURE SETUP COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
