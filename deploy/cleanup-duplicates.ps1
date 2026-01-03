# =============================================================================
# CLEANUP DUPLICATE AWS RESOURCES
# =============================================================================
# This script removes duplicate Lambda functions that are not in use
# Run with -WhatIf to preview changes without deleting
# =============================================================================

param(
    [switch]$WhatIf = $false,
    [switch]$Force = $false
)

$Region = "ap-south-1"

Write-Host "=== AWS RESOURCE CLEANUP ===" -ForegroundColor Cyan
Write-Host "Region: $Region"
Write-Host ""

# =============================================================================
# DUPLICATE LAMBDAS TO DELETE
# =============================================================================
$DuplicateLambdas = @(
    "wecare-shortlinks",              # Duplicate - wecare-digital-shortlinks is active
    "base-wecare-digital-shortlinks"  # Duplicate - wecare-digital-shortlinks is active
)

Write-Host "LAMBDA FUNCTIONS TO DELETE:" -ForegroundColor Yellow
foreach ($lambda in $DuplicateLambdas) {
    Write-Host "  - $lambda" -ForegroundColor Red
}

if (-not $Force -and -not $WhatIf) {
    Write-Host ""
    $confirm = Read-Host "Are you sure you want to delete these Lambda functions? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""

foreach ($lambda in $DuplicateLambdas) {
    Write-Host "Deleting Lambda: $lambda..." -ForegroundColor Yellow
    if ($WhatIf) {
        Write-Host "  [WhatIf] Would delete $lambda" -ForegroundColor Gray
    } else {
        try {
            aws lambda delete-function --function-name $lambda --region $Region 2>$null
            Write-Host "  Deleted: $lambda" -ForegroundColor Green
        } catch {
            Write-Host "  Failed or not found: $lambda" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "=== CLEANUP COMPLETE ===" -ForegroundColor Green

# =============================================================================
# ACTIVE RESOURCES (DO NOT DELETE)
# =============================================================================
Write-Host ""
Write-Host "ACTIVE RESOURCES (kept):" -ForegroundColor Cyan
Write-Host "  Lambda Functions:" -ForegroundColor Yellow
Write-Host "    - base-wecare-digital-whatsapp (Main WhatsApp API)"
Write-Host "    - wecare-digital-shortlinks (r.wecare.digital)"
Write-Host "    - wecare-digital-payments (p.wecare.digital)"
Write-Host "    - base-wecare-digital-whatsapp-agent-core (Bedrock Agent)"
Write-Host "    - base-wecare-digital-whatsapp-bedrock-worker"
Write-Host "    - base-wecare-digital-whatsapp-payment-worker"
Write-Host "    - base-wecare-digital-whatsapp-email-notifier"
Write-Host "    - id-wecare-digital-custom-message (Cognito)"
Write-Host "    - id-wecare-digital-post-auth (Cognito)"
Write-Host ""
Write-Host "  API Gateways:" -ForegroundColor Yellow
Write-Host "    - wecare-shortlinks-api (REST) -> r.wecare.digital"
Write-Host "    - wecare-payment-api (REST) -> p.wecare.digital"
Write-Host "    - base-wecare-digital-whatsapp-api (HTTP)"
Write-Host "    - base-wecare-digital-whatsapp-agent-core-api (HTTP)"
Write-Host ""
Write-Host "  DynamoDB Tables:" -ForegroundColor Yellow
Write-Host "    - base-wecare-digital-whatsapp"
Write-Host "    - wecare-digital-shortlinks"
Write-Host "    - wecare-digital-payments"
Write-Host "    - wecare-digital-flows"
Write-Host "    - wecare-digital-inbound"
Write-Host "    - wecare-digital-outbound"
Write-Host "    - wecare-digital-orders"
