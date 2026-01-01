# Cleanup DynamoDB - Remove oversized items and reset quality history
# Run this before deploying to fix "Item size exceeded" errors

$REGION = "ap-south-1"
$TABLE_NAME = "base-wecare-digital-whatsapp"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DynamoDB Cleanup Script" -ForegroundColor Cyan
Write-Host "  Table: $TABLE_NAME" -ForegroundColor Cyan
Write-Host "  Region: $REGION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Step 1: Delete oversized QUALITY items
Write-Host "`n=== Step 1: Deleting oversized QUALITY items ===" -ForegroundColor Yellow

$qualityItems = @(
    "QUALITY#0b0d77d6d54645d991db7aa9cf1b0eb2",
    "QUALITY#3f8934395ae24a4583a413087a3d3fb0"
)

foreach ($pk in $qualityItems) {
    Write-Host "  Deleting: $pk"
    
    $keyJson = @{
        "$TABLE_NAME" = @{ "S" = $pk }
    } | ConvertTo-Json -Compress
    
    aws dynamodb delete-item `
        --table-name $TABLE_NAME `
        --key $keyJson `
        --region $REGION 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Deleted successfully" -ForegroundColor Green
    } else {
        Write-Host "    Item may not exist or already deleted" -ForegroundColor Yellow
    }
}

# Step 2: Delete old CONFIG items that might be oversized
Write-Host "`n=== Step 2: Cleaning up CONFIG items ===" -ForegroundColor Yellow

$configItems = @(
    "CONFIG#INFRASTRUCTURE",
    "CONFIG#MEDIA_TYPES"
)

foreach ($pk in $configItems) {
    Write-Host "  Deleting: $pk"
    
    $keyJson = @{
        "$TABLE_NAME" = @{ "S" = $pk }
    } | ConvertTo-Json -Compress
    
    aws dynamodb delete-item `
        --table-name $TABLE_NAME `
        --key $keyJson `
        --region $REGION 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Deleted successfully" -ForegroundColor Green
    } else {
        Write-Host "    Item may not exist or already deleted" -ForegroundColor Yellow
    }
}

# Step 3: Scan for any other QUALITY items and delete them
Write-Host "`n=== Step 3: Scanning for other QUALITY items ===" -ForegroundColor Yellow

$scanResult = aws dynamodb scan `
    --table-name $TABLE_NAME `
    --filter-expression "begins_with(#pk, :prefix)" `
    --expression-attribute-names '{"#pk": "base-wecare-digital-whatsapp"}' `
    --expression-attribute-values '{":prefix": {"S": "QUALITY#"}}' `
    --projection-expression "#pk" `
    --region $REGION `
    --output json | ConvertFrom-Json

$qualityCount = $scanResult.Items.Count
Write-Host "  Found $qualityCount QUALITY items"

if ($qualityCount -gt 0) {
    foreach ($item in $scanResult.Items) {
        $pk = $item."base-wecare-digital-whatsapp".S
        Write-Host "  Deleting: $pk"
        
        $keyJson = @{
            "$TABLE_NAME" = @{ "S" = $pk }
        } | ConvertTo-Json -Compress
        
        aws dynamodb delete-item `
            --table-name $TABLE_NAME `
            --key $keyJson `
            --region $REGION 2>&1 | Out-Null
    }
    Write-Host "  Deleted $qualityCount QUALITY items" -ForegroundColor Green
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run: .\deploy-167-handlers.ps1"
Write-Host "  2. Test from your UK number"
Write-Host ""
