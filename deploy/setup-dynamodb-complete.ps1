# DynamoDB Complete Schema Setup for WhatsApp Business API
$REGION = "ap-south-1"
$MESSAGES_TABLE = "base-wecare-digital-whatsapp"

Write-Host "DynamoDB Setup - Table: $MESSAGES_TABLE"

function Wait-ForGSI($IndexName) {
    Write-Host "  Waiting for $IndexName..." -NoNewline
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 5
        $status = aws dynamodb describe-table --table-name $MESSAGES_TABLE --region $REGION --query "Table.GlobalSecondaryIndexes[?IndexName==``$IndexName``].IndexStatus" --output text 2>$null
        if ($status -eq "ACTIVE") { Write-Host " ACTIVE" -ForegroundColor Green; return }
    }
    Write-Host " TIMEOUT" -ForegroundColor Red
}

function Add-GSI($IndexName, $HashKey, $RangeKey) {
    Write-Host "Creating $IndexName..." -NoNewline
    $exists = aws dynamodb describe-table --table-name $MESSAGES_TABLE --region $REGION --query "Table.GlobalSecondaryIndexes[?IndexName==``$IndexName``].IndexName" --output text 2>$null
    if ($exists -eq $IndexName) { Write-Host " EXISTS" -ForegroundColor Yellow; return }
    
    $attrDefs = "[{`"AttributeName`":`"$HashKey`",`"AttributeType`":`"S`"},{`"AttributeName`":`"$RangeKey`",`"AttributeType`":`"S`"}]"
    $keySchema = "[{`"AttributeName`":`"$HashKey`",`"KeyType`":`"HASH`"},{`"AttributeName`":`"$RangeKey`",`"KeyType`":`"RANGE`"}]"
    $gsiUpdate = "[{`"Create`":{`"IndexName`":`"$IndexName`",`"KeySchema`":$keySchema,`"Projection`":{`"ProjectionType`":`"ALL`"}}}]"
    
    aws dynamodb update-table --region $REGION --table-name $MESSAGES_TABLE --attribute-definitions $attrDefs --global-secondary-index-updates $gsiUpdate 2>$null
    if ($LASTEXITCODE -eq 0) { Wait-ForGSI $IndexName } else { Write-Host " ERROR" -ForegroundColor Red }
}

# Core GSIs
Add-GSI "gsi_direction" "direction" "receivedAt"
Add-GSI "gsi_from" "fromPk" "receivedAt"
Add-GSI "gsi_inbox" "inboxPk" "receivedAt"
Add-GSI "gsi_conversation" "conversationPk" "receivedAt"
Add-GSI "gsi_status" "deliveryStatus" "sentAt"

# Extended GSIs
Add-GSI "gsi_waba_itemtype" "wabaMetaId" "itemType"
Add-GSI "gsi_customer_phone" "customerPhone" "createdAt"
Add-GSI "gsi_group" "groupId" "sentAt"
Add-GSI "gsi_catalog" "catalogId" "retailerId"
Add-GSI "gsi_order" "orderId" "createdAt"

# Tenant GSIs
Add-GSI "gsi_tenant" "tenantId" "itemType"
Add-GSI "gsi_payment_status" "paymentStatus" "createdAt"

# Template GSIs
Add-GSI "gsi_template_waba" "wabaId" "templateStatus"
Add-GSI "gsi_template_name" "templateName" "templateLanguage"

# Analytics GSIs
Add-GSI "gsi_campaign" "campaignId" "sentAt"
Add-GSI "gsi_webhook_event" "webhookEventType" "receivedAt"

Write-Host "`nSetup Complete!" -ForegroundColor Green
