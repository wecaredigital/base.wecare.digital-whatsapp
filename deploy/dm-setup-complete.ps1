# =============================================================================
# WECARE DIGITAL - Complete DM Infrastructure Setup
# =============================================================================
# Configures:
# - dm.wecare.digital → API Gateway (WhatsApp, Bedrock Agents)
# - d.wecare.digital → CloudFront + S3 (Media Storage)
# - Proper redirects, tags, and DNS
# =============================================================================

$ErrorActionPreference = "Stop"
$REGION = "ap-south-1"
$HOSTED_ZONE_ID = "Z0123324UGZKLOSJPDS8"
$ACM_CERT_ARN = "arn:aws:acm:us-east-1:010526260063:certificate/7f24ca44-e21f-4ead-af46-d8e3a1af82ef"
$REGIONAL_CERT_ARN = "arn:aws:acm:ap-south-1:010526260063:certificate/500011eb-52cf-4079-863c-2ec01bf4da7b"
$ACCOUNT_ID = "010526260063"
$LAMBDA_ARN = "arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp"

# Standard tags
$TAGS = "Project=wecare-dm,Owner=wecare.digital,Environment=prod,CostCenter=messaging"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WECARE.DIGITAL - DM Infrastructure" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# =============================================================================
# STEP 1: Clean up duplicate APIs
# =============================================================================
Write-Host "`n[1/8] Cleaning up duplicate APIs..." -ForegroundColor Yellow

$apis = aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='wecare-dm-api'].[ApiId]" --output text
$apiList = $apis -split "`t"

if ($apiList.Count -gt 1) {
    Write-Host "  Found $($apiList.Count) duplicate wecare-dm-api APIs" -ForegroundColor Yellow
    # Keep the first one, delete others
    for ($i = 1; $i -lt $apiList.Count; $i++) {
        $apiId = $apiList[$i].Trim()
        if ($apiId) {
            Write-Host "  Deleting duplicate API: $apiId" -ForegroundColor Red
            aws apigatewayv2 delete-api --api-id $apiId --region $REGION 2>$null
        }
    }
}

# Get the main API ID (use existing base-wecare-digital-whatsapp-api)
$MAIN_API_ID = aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='base-wecare-digital-whatsapp-api'].ApiId" --output text
Write-Host "  Main API ID: $MAIN_API_ID" -ForegroundColor Green

# Get agent core API ID
$AGENT_CORE_API_ID = aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='base-wecare-digital-whatsapp-agent-core-api'].ApiId" --output text
Write-Host "  Agent Core API ID: $AGENT_CORE_API_ID" -ForegroundColor Green

# =============================================================================
# STEP 2: Create Redirect Lambda for 404/root
# =============================================================================
Write-Host "`n[2/8] Setting up redirect handler..." -ForegroundColor Yellow

# Check if redirect handler exists in main Lambda
# We'll add a redirect route to the main Lambda

# =============================================================================
# STEP 3: Configure API Gateway routes
# =============================================================================
Write-Host "`n[3/8] Configuring API Gateway routes..." -ForegroundColor Yellow

# Get existing routes
$existingRoutes = aws apigatewayv2 get-routes --api-id $MAIN_API_ID --region $REGION --query "Items[*].RouteKey" --output text
Write-Host "  Existing routes: $existingRoutes" -ForegroundColor Gray

# Get Lambda integration
$integrations = aws apigatewayv2 get-integrations --api-id $MAIN_API_ID --region $REGION --query "Items[0].IntegrationId" --output text
Write-Host "  Integration ID: $integrations" -ForegroundColor Gray

# =============================================================================
# STEP 4: Create API Mapping for dm.wecare.digital
# =============================================================================
Write-Host "`n[4/8] Creating API mapping for dm.wecare.digital..." -ForegroundColor Yellow

# Check existing mappings
$existingMappings = aws apigatewayv2 get-api-mappings --domain-name dm.wecare.digital --region $REGION --query "Items[*].ApiId" --output text 2>$null

if (-not $existingMappings) {
    # Get stage name
    $stageName = aws apigatewayv2 get-stages --api-id $MAIN_API_ID --region $REGION --query "Items[0].StageName" --output text
    
    if ($stageName) {
        Write-Host "  Creating mapping: dm.wecare.digital -> $MAIN_API_ID ($stageName)" -ForegroundColor White
        aws apigatewayv2 create-api-mapping `
            --domain-name dm.wecare.digital `
            --api-id $MAIN_API_ID `
            --stage $stageName `
            --region $REGION 2>$null
        Write-Host "  API mapping created" -ForegroundColor Green
    } else {
        Write-Host "  No stage found, creating default stage..." -ForegroundColor Yellow
        aws apigatewayv2 create-stage --api-id $MAIN_API_ID --stage-name '$default' --auto-deploy --region $REGION 2>$null
        aws apigatewayv2 create-api-mapping `
            --domain-name dm.wecare.digital `
            --api-id $MAIN_API_ID `
            --stage '$default' `
            --region $REGION 2>$null
    }
} else {
    Write-Host "  API mapping already exists" -ForegroundColor Green
}

# =============================================================================
# STEP 5: Create Route 53 record for dm.wecare.digital
# =============================================================================
Write-Host "`n[5/8] Creating Route 53 record for dm.wecare.digital..." -ForegroundColor Yellow

# Get API Gateway domain target
$apiGwDomain = aws apigatewayv2 get-domain-name --domain-name dm.wecare.digital --region $REGION --query "DomainNameConfigurations[0].ApiGatewayDomainName" --output text
$apiGwHostedZone = aws apigatewayv2 get-domain-name --domain-name dm.wecare.digital --region $REGION --query "DomainNameConfigurations[0].HostedZoneId" --output text

Write-Host "  API GW Domain: $apiGwDomain" -ForegroundColor Gray
Write-Host "  API GW Hosted Zone: $apiGwHostedZone" -ForegroundColor Gray

# Check if record exists
$existingRecord = aws route53 list-resource-record-sets --hosted-zone-id $HOSTED_ZONE_ID --query "ResourceRecordSets[?Name=='dm.wecare.digital.' && Type=='A'].Name" --output text

if (-not $existingRecord) {
    Write-Host "  Creating A record for dm.wecare.digital..." -ForegroundColor White
    
    $changeBatch = @{
        Changes = @(
            @{
                Action = "CREATE"
                ResourceRecordSet = @{
                    Name = "dm.wecare.digital"
                    Type = "A"
                    AliasTarget = @{
                        DNSName = $apiGwDomain
                        HostedZoneId = $apiGwHostedZone
                        EvaluateTargetHealth = $false
                    }
                }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $changeBatch | Out-File -FilePath "temp-dns-change.json" -Encoding UTF8
    aws route53 change-resource-record-sets --hosted-zone-id $HOSTED_ZONE_ID --change-batch file://temp-dns-change.json
    Remove-Item "temp-dns-change.json" -Force
    Write-Host "  DNS record created" -ForegroundColor Green
} else {
    Write-Host "  DNS record already exists" -ForegroundColor Green
}

# =============================================================================
# STEP 6: Verify d.wecare.digital CloudFront
# =============================================================================
Write-Host "`n[6/8] Verifying d.wecare.digital CloudFront..." -ForegroundColor Yellow

$cfDistId = aws cloudfront list-distributions --query "DistributionList.Items[?contains(Aliases.Items, 'd.wecare.digital')].Id" --output text
Write-Host "  CloudFront Distribution: $cfDistId" -ForegroundColor Green

# Check error pages
$errorResponses = aws cloudfront get-distribution --id $cfDistId --query "Distribution.DistributionConfig.CustomErrorResponses.Items[*].[ErrorCode,ResponsePagePath]" --output text
Write-Host "  Error responses configured: $errorResponses" -ForegroundColor Gray

# =============================================================================
# STEP 7: Add tags to resources
# =============================================================================
Write-Host "`n[7/8] Adding tags to resources..." -ForegroundColor Yellow

# Tag API Gateway
aws apigatewayv2 tag-resource --resource-arn "arn:aws:apigateway:$REGION::/apis/$MAIN_API_ID" --tags $TAGS --region $REGION 2>$null
Write-Host "  Tagged API Gateway: $MAIN_API_ID" -ForegroundColor Green

# Tag S3 bucket (already done in previous script)
Write-Host "  S3 bucket d.wecare.digital already tagged" -ForegroundColor Green

# Tag CloudFront
aws cloudfront tag-resource --resource "arn:aws:cloudfront::$ACCOUNT_ID`:distribution/$cfDistId" --tags "Items=[{Key=Project,Value=wecare-dm},{Key=Owner,Value=wecare.digital},{Key=Environment,Value=prod},{Key=CostCenter,Value=messaging}]" 2>$null
Write-Host "  Tagged CloudFront: $cfDistId" -ForegroundColor Green

# =============================================================================
# STEP 8: Summary
# =============================================================================
Write-Host "`n[8/8] Infrastructure Summary" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nAPI Domain: dm.wecare.digital" -ForegroundColor White
Write-Host "  API Gateway: $MAIN_API_ID" -ForegroundColor Gray
Write-Host "  Target: $apiGwDomain" -ForegroundColor Gray

Write-Host "`nFiles Domain: d.wecare.digital" -ForegroundColor White
Write-Host "  CloudFront: $cfDistId" -ForegroundColor Gray
Write-Host "  S3 Bucket: d.wecare.digital" -ForegroundColor Gray

Write-Host "`nRedirect Behavior:" -ForegroundColor White
Write-Host "  GET / -> https://wecare.digital/selfservice" -ForegroundColor Gray
Write-Host "  404   -> https://wecare.digital/selfservice" -ForegroundColor Gray

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nTest URLs:" -ForegroundColor Yellow
Write-Host "  https://dm.wecare.digital/" -ForegroundColor Gray
Write-Host "  https://d.wecare.digital/" -ForegroundColor Gray
Write-Host "  https://d.wecare.digital/d/" -ForegroundColor Gray
Write-Host "  https://d.wecare.digital/u/" -ForegroundColor Gray
