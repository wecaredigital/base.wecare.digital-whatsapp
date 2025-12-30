# DynamoDB Extended Schema Setup for WhatsApp Business API
# This script adds GSIs for extended features (Business Profiles, Marketing, Webhooks, etc.)
# Run each GSI creation one at a time - wait for ACTIVE status before next

$REGION = "ap-south-1"
$MESSAGES_TABLE = "base-wecare-digital-whatsapp"

Write-Host "=== Extended DynamoDB Schema Setup ===" -ForegroundColor Green
Write-Host "Table: $MESSAGES_TABLE" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan
Write-Host ""

# Function to wait for GSI to be active
function Wait-ForGSI {
    param($IndexName)
    Write-Host "Waiting for GSI $IndexName to be active..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    do {
        Start-Sleep -Seconds 10
        $attempt++
        $status = aws dynamodb describe-table --table-name $MESSAGES_TABLE --region $REGION --query "Table.GlobalSecondaryIndexes[?IndexName=='$IndexName'].IndexStatus" --output text 2>$null
        Write-Host "  Attempt $attempt/$maxAttempts - Status: $status"
    } while ($status -ne "ACTIVE" -and $attempt -lt $maxAttempts)
    
    if ($status -eq "ACTIVE") {
        Write-Host "  GSI $IndexName is now ACTIVE" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: GSI $IndexName may not be ready" -ForegroundColor Red
    }
}

# GSI 1: Query by WABA ID and Item Type
Write-Host "`n=== Step 1: Adding GSI gsi_waba_itemtype ===" -ForegroundColor Yellow
Write-Host "Purpose: Query items by WABA ID and item type (profiles, templates, etc.)"

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=wabaMetaId,AttributeType=S `
        AttributeName=itemType,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_waba_itemtype",
                "KeySchema": [
                    {"AttributeName":"wabaMetaId","KeyType":"HASH"},
                    {"AttributeName":"itemType","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Wait-ForGSI "gsi_waba_itemtype"

# GSI 2: Query by Customer Phone
Write-Host "`n=== Step 2: Adding GSI gsi_customer_phone ===" -ForegroundColor Yellow
Write-Host "Purpose: Query payments, orders by customer phone"

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=customerPhone,AttributeType=S `
        AttributeName=createdAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_customer_phone",
                "KeySchema": [
                    {"AttributeName":"customerPhone","KeyType":"HASH"},
                    {"AttributeName":"createdAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Wait-ForGSI "gsi_customer_phone"

# GSI 3: Query by Group ID
Write-Host "`n=== Step 3: Adding GSI gsi_group ===" -ForegroundColor Yellow
Write-Host "Purpose: Query group messages and participants"

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=groupId,AttributeType=S `
        AttributeName=sentAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_group",
                "KeySchema": [
                    {"AttributeName":"groupId","KeyType":"HASH"},
                    {"AttributeName":"sentAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Wait-ForGSI "gsi_group"

# GSI 4: Query by Catalog ID
Write-Host "`n=== Step 4: Adding GSI gsi_catalog ===" -ForegroundColor Yellow
Write-Host "Purpose: Query products by catalog"

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=catalogId,AttributeType=S `
        AttributeName=retailerId,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_catalog",
                "KeySchema": [
                    {"AttributeName":"catalogId","KeyType":"HASH"},
                    {"AttributeName":"retailerId","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Wait-ForGSI "gsi_catalog"

# GSI 5: Query by Order ID
Write-Host "`n=== Step 5: Adding GSI gsi_order ===" -ForegroundColor Yellow
Write-Host "Purpose: Query payments by order ID"

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=orderId,AttributeType=S `
        AttributeName=createdAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_order",
                "KeySchema": [
                    {"AttributeName":"orderId","KeyType":"HASH"},
                    {"AttributeName":"createdAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Wait-ForGSI "gsi_order"

Write-Host "`n=== Extended DynamoDB Schema Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "New GSIs added:" -ForegroundColor Cyan
Write-Host "  - gsi_waba_itemtype: Query by WABA ID + item type"
Write-Host "  - gsi_customer_phone: Query by customer phone"
Write-Host "  - gsi_group: Query group messages"
Write-Host "  - gsi_catalog: Query catalog products"
Write-Host "  - gsi_order: Query by order ID"
Write-Host ""
Write-Host "Check status with:"
Write-Host "aws dynamodb describe-table --table-name $MESSAGES_TABLE --region $REGION --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]' --output table"
