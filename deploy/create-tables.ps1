# =============================================================================
# CREATE DYNAMODB TABLES - Separate tables for each service
# =============================================================================
# Run: .\deploy\create-tables.ps1
# =============================================================================

$Region = "ap-south-1"

$Tables = @(
    @{
        Name = "wecare-digital-shortlinks"
        Description = "Short links - r.wecare.digital"
    },
    @{
        Name = "wecare-digital-payments"
        Description = "Razorpay payments - p.wecare.digital"
    },
    @{
        Name = "wecare-digital-flows"
        Description = "WhatsApp Flows data"
    },
    @{
        Name = "wecare-digital-inbound"
        Description = "Inbound WhatsApp messages"
    },
    @{
        Name = "wecare-digital-outbound"
        Description = "Outbound WhatsApp messages"
    },
    @{
        Name = "wecare-digital-orders"
        Description = "WhatsApp order payments"
    }
)

foreach ($table in $Tables) {
    Write-Host "Creating table: $($table.Name)..." -ForegroundColor Cyan
    
    try {
        aws dynamodb create-table `
            --table-name $table.Name `
            --attribute-definitions AttributeName=pk,AttributeType=S `
            --key-schema AttributeName=pk,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST `
            --region $Region `
            --tags Key=Project,Value=wecare-digital Key=Description,Value="$($table.Description)" `
            2>$null
        
        Write-Host "  Created: $($table.Name)" -ForegroundColor Green
    }
    catch {
        Write-Host "  Already exists or error: $($table.Name)" -ForegroundColor Yellow
    }
}

Write-Host "`nAll tables processed!" -ForegroundColor Green
