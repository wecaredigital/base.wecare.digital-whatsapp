# =============================================================================
# Create All GSIs for WhatsApp Business API (167 Handlers)
# =============================================================================
# This script creates all required GSIs one at a time with proper waits.
# DynamoDB only allows one GSI to be created at a time per table.
#
# Run: .\deploy\create-all-gsis.ps1
# =============================================================================

param(
    [string]$Region = "ap-south-1",
    [string]$TableName = "base-wecare-digital-whatsapp"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DynamoDB GSI Creation Script" -ForegroundColor Cyan
Write-Host "  Table: $TableName" -ForegroundColor Yellow
Write-Host "  Region: $Region" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------------
# GSI Definitions - All 16 GSIs needed for 167 handlers
# -----------------------------------------------------------------------------
$GSIs = @(
    # Core Message GSIs
    @{ Name = "gsi_direction"; HashKey = "direction"; RangeKey = "receivedAt"; Desc = "Query by INBOUND/OUTBOUND" },
    @{ Name = "gsi_from"; HashKey = "fromPk"; RangeKey = "receivedAt"; Desc = "Query by sender phone" },
    @{ Name = "gsi_inbox"; HashKey = "inboxPk"; RangeKey = "receivedAt"; Desc = "Inbox view" },
    @{ Name = "gsi_conversation"; HashKey = "conversationPk"; RangeKey = "receivedAt"; Desc = "Conversation timeline" },
    @{ Name = "gsi_status"; HashKey = "deliveryStatus"; RangeKey = "sentAt"; Desc = "Delivery status queries" },
    
    # Extended Feature GSIs
    @{ Name = "gsi_waba_itemtype"; HashKey = "wabaMetaId"; RangeKey = "itemType"; Desc = "WABA + item type" },
    @{ Name = "gsi_customer_phone"; HashKey = "customerPhone"; RangeKey = "createdAt"; Desc = "Customer queries" },
    @{ Name = "gsi_group"; HashKey = "groupId"; RangeKey = "sentAt"; Desc = "Group messages" },
    @{ Name = "gsi_catalog"; HashKey = "catalogId"; RangeKey = "retailerId"; Desc = "Catalog products" },
    @{ Name = "gsi_order"; HashKey = "orderId"; RangeKey = "createdAt"; Desc = "Order queries" },
    
    # Tenant and Payment GSIs
    @{ Name = "gsi_tenant"; HashKey = "tenantId"; RangeKey = "itemType"; Desc = "Tenant items" },
    @{ Name = "gsi_payment_status"; HashKey = "paymentStatus"; RangeKey = "createdAt"; Desc = "Payment status" },
    
    # Template GSIs
    @{ Name = "gsi_template_waba"; HashKey = "wabaId"; RangeKey = "templateStatus"; Desc = "Templates by WABA" },
    @{ Name = "gsi_template_name"; HashKey = "templateName"; RangeKey = "templateLanguage"; Desc = "Templates by name" },
    
    # Analytics and Webhook GSIs
    @{ Name = "gsi_campaign"; HashKey = "campaignId"; RangeKey = "sentAt"; Desc = "Campaign messages" },
    @{ Name = "gsi_webhook_event"; HashKey = "webhookEventType"; RangeKey = "receivedAt"; Desc = "Webhook events" }
)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

function Get-TableStatus {
    $result = aws dynamodb describe-table --table-name $TableName --region $Region --query "Table.TableStatus" --output text 2>$null
    return $result
}

function Get-GSIStatus {
    param([string]$IndexName)
    $result = aws dynamodb describe-table --table-name $TableName --region $Region --query "Table.GlobalSecondaryIndexes[?IndexName=='$IndexName'].IndexStatus" --output text 2>$null
    return $result
}

function Get-ExistingGSIs {
    $result = aws dynamodb describe-table --table-name $TableName --region $Region --query "Table.GlobalSecondaryIndexes[*].IndexName" --output text 2>$null
    if ($result) {
        return $result -split "`t"
    }
    return @()
}

function Wait-ForTableReady {
    Write-Host "  Waiting for table to be ready..." -NoNewline
    $maxAttempts = 120
    $attempt = 0
    
    do {
        Start-Sleep -Seconds 5
        $attempt++
        $status = Get-TableStatus
        
        if ($attempt % 12 -eq 0) {
            Write-Host "." -NoNewline
        }
    } while ($status -ne "ACTIVE" -and $attempt -lt $maxAttempts)
    
    if ($status -eq "ACTIVE") {
        Write-Host " Ready" -ForegroundColor Green
        return $true
    } else {
        Write-Host " Timeout" -ForegroundColor Red
        return $false
    }
}

function Wait-ForGSIActive {
    param([string]$IndexName)
    
    Write-Host "  Waiting for $IndexName to be ACTIVE..." -NoNewline
    $maxAttempts = 120
    $attempt = 0
    
    do {
        Start-Sleep -Seconds 5
        $attempt++
        $status = Get-GSIStatus -IndexName $IndexName
        
        if ($attempt % 12 -eq 0) {
            Write-Host "." -NoNewline
        }
    } while ($status -ne "ACTIVE" -and $attempt -lt $maxAttempts)
    
    if ($status -eq "ACTIVE") {
        Write-Host " ACTIVE" -ForegroundColor Green
        return $true
    } else {
        Write-Host " Timeout (status: $status)" -ForegroundColor Red
        return $false
    }
}

function Create-GSI {
    param(
        [string]$IndexName,
        [string]$HashKey,
        [string]$RangeKey,
        [string]$Description
    )
    
    Write-Host ""
    Write-Host "--- Creating $IndexName ---" -ForegroundColor Cyan
    Write-Host "    $Description"
    Write-Host "    Keys: $HashKey (HASH), $RangeKey (RANGE)"
    
    # Check if GSI already exists
    $existingGSIs = Get-ExistingGSIs
    if ($existingGSIs -contains $IndexName) {
        $status = Get-GSIStatus -IndexName $IndexName
        if ($status -eq "ACTIVE") {
            Write-Host "  Already exists and ACTIVE" -ForegroundColor Yellow
            return $true
        } elseif ($status -eq "CREATING") {
            Write-Host "  Already being created, waiting..." -ForegroundColor Yellow
            return Wait-ForGSIActive -IndexName $IndexName
        } else {
            Write-Host "  Exists with status: $status" -ForegroundColor Yellow
            return $false
        }
    }
    
    # Wait for table to be ready
    $tableStatus = Get-TableStatus
    if ($tableStatus -ne "ACTIVE") {
        if (-not (Wait-ForTableReady)) {
            Write-Host "  Table not ready, skipping" -ForegroundColor Red
            return $false
        }
    }
    
    # Create attribute definitions JSON file with proper encoding
    $attrDefsPath = Join-Path $env:TEMP "attr-defs-$IndexName.json"
    $attrDefsJson = "[{`"AttributeName`":`"$HashKey`",`"AttributeType`":`"S`"},{`"AttributeName`":`"$RangeKey`",`"AttributeType`":`"S`"}]"
    [System.IO.File]::WriteAllText($attrDefsPath, $attrDefsJson)
    
    # Create GSI update JSON file with proper encoding
    $gsiUpdatePath = Join-Path $env:TEMP "gsi-update-$IndexName.json"
    $gsiUpdateJson = "[{`"Create`":{`"IndexName`":`"$IndexName`",`"KeySchema`":[{`"AttributeName`":`"$HashKey`",`"KeyType`":`"HASH`"},{`"AttributeName`":`"$RangeKey`",`"KeyType`":`"RANGE`"}],`"Projection`":{`"ProjectionType`":`"ALL`"}}}]"
    [System.IO.File]::WriteAllText($gsiUpdatePath, $gsiUpdateJson)
    
    # Execute the update
    Write-Host "  Creating GSI..." -NoNewline
    
    $result = aws dynamodb update-table `
        --region $Region `
        --table-name $TableName `
        --attribute-definitions "file://$attrDefsPath" `
        --global-secondary-index-updates "file://$gsiUpdatePath" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " Submitted" -ForegroundColor Green
        
        # Wait for GSI to be active
        $success = Wait-ForGSIActive -IndexName $IndexName
        
        # Cleanup temp files
        Remove-Item -Path $attrDefsPath -ErrorAction SilentlyContinue
        Remove-Item -Path $gsiUpdatePath -ErrorAction SilentlyContinue
        
        return $success
    } else {
        Write-Host " Failed" -ForegroundColor Red
        Write-Host "  Error: $result" -ForegroundColor Red
        
        # Cleanup temp files
        Remove-Item -Path $attrDefsPath -ErrorAction SilentlyContinue
        Remove-Item -Path $gsiUpdatePath -ErrorAction SilentlyContinue
        
        return $false
    }
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

Write-Host "Checking table exists..." -NoNewline
$tableStatus = Get-TableStatus
if (-not $tableStatus) {
    Write-Host " NOT FOUND" -ForegroundColor Red
    Write-Host "Please create the table first using setup-dynamodb.ps1"
    exit 1
}
Write-Host " $tableStatus" -ForegroundColor Green

Write-Host ""
Write-Host "Existing GSIs:" -ForegroundColor Yellow
$existingGSIs = Get-ExistingGSIs
if ($existingGSIs.Count -gt 0) {
    foreach ($gsi in $existingGSIs) {
        $status = Get-GSIStatus -IndexName $gsi
        Write-Host "  - $gsi : $status"
    }
} else {
    Write-Host "  (none)"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Creating $($GSIs.Count) GSIs (this may take 30-60 minutes)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$created = 0
$skipped = 0
$failed = 0
$startTime = Get-Date

foreach ($gsi in $GSIs) {
    $result = Create-GSI -IndexName $gsi.Name -HashKey $gsi.HashKey -RangeKey $gsi.RangeKey -Description $gsi.Desc
    
    if ($result) {
        if ($existingGSIs -contains $gsi.Name) {
            $skipped++
        } else {
            $created++
        }
    } else {
        $failed++
    }
}

$endTime = Get-Date
$duration = $endTime - $startTime

# -----------------------------------------------------------------------------
# Enable TTL
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "--- Enabling TTL ---" -ForegroundColor Cyan
aws dynamodb update-time-to-live `
    --region $Region `
    --table-name $TableName `
    --time-to-live-specification Enabled=true,AttributeName=ttl 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  TTL enabled on 'ttl' attribute" -ForegroundColor Green
} else {
    Write-Host "  TTL may already be enabled" -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Duration: $($duration.ToString('hh\:mm\:ss'))"
Write-Host "  Created:  $created" -ForegroundColor Green
Write-Host "  Skipped:  $skipped (already existed)" -ForegroundColor Yellow
Write-Host "  Failed:   $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host ""

Write-Host "Final GSI Status:" -ForegroundColor Yellow
$finalGSIs = Get-ExistingGSIs
foreach ($gsi in $finalGSIs) {
    $status = Get-GSIStatus -IndexName $gsi
    $color = if ($status -eq "ACTIVE") { "Green" } elseif ($status -eq "CREATING") { "Yellow" } else { "Red" }
    Write-Host "  - $gsi : $status" -ForegroundColor $color
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
if ($failed -eq 0) {
    Write-Host "  All GSIs created successfully!" -ForegroundColor Green
} else {
    Write-Host "  Some GSIs failed - run script again to retry" -ForegroundColor Yellow
}
Write-Host "============================================================" -ForegroundColor Cyan
