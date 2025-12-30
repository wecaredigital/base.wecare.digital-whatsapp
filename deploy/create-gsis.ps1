# Create GSIs for base-wecare-digital-whatsapp table
$TableName = "base-wecare-digital-whatsapp"
$Region = "ap-south-1"

Write-Host "Creating GSIs for $TableName..." -ForegroundColor Cyan

# Check existing GSIs
$existing = aws dynamodb describe-table --table-name $TableName --query "Table.GlobalSecondaryIndexes[*].IndexName" --region $Region | ConvertFrom-Json
Write-Host "Existing GSIs: $($existing -join ', ')" -ForegroundColor Yellow

# GSI 1: gsi_conversation (conversationPk + receivedAt)
if ($existing -notcontains "gsi_conversation") {
    Write-Host "Creating gsi_conversation..." -ForegroundColor Green
    aws dynamodb update-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=conversationPk,AttributeType=S AttributeName=receivedAt,AttributeType=S `
        --global-secondary-index-updates file://../archive/gsi-conversation.json `
        --region $Region
    
    Write-Host "Waiting for gsi_conversation to be active..." -ForegroundColor Yellow
    aws dynamodb wait table-exists --table-name $TableName --region $Region
    Start-Sleep -Seconds 30
} else {
    Write-Host "gsi_conversation already exists" -ForegroundColor Gray
}

# GSI 2: gsi_from (fromPk + receivedAt)
if ($existing -notcontains "gsi_from") {
    Write-Host "Creating gsi_from..." -ForegroundColor Green
    aws dynamodb update-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=fromPk,AttributeType=S AttributeName=receivedAt,AttributeType=S `
        --global-secondary-index-updates file://../archive/gsi-from.json `
        --region $Region
    
    Write-Host "Waiting for gsi_from to be active..." -ForegroundColor Yellow
    aws dynamodb wait table-exists --table-name $TableName --region $Region
    Start-Sleep -Seconds 30
} else {
    Write-Host "gsi_from already exists" -ForegroundColor Gray
}

# GSI 3: gsi_direction (direction + receivedAt)
if ($existing -notcontains "gsi_direction") {
    Write-Host "Creating gsi_direction..." -ForegroundColor Green
    aws dynamodb update-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=direction,AttributeType=S AttributeName=receivedAt,AttributeType=S `
        --global-secondary-index-updates file://../archive/gsi-direction.json `
        --region $Region
    
    Write-Host "Waiting for gsi_direction to be active..." -ForegroundColor Yellow
    aws dynamodb wait table-exists --table-name $TableName --region $Region
    Start-Sleep -Seconds 30
} else {
    Write-Host "gsi_direction already exists" -ForegroundColor Gray
}

# GSI 4: gsi_inbox (inboxPk + receivedAt)
if ($existing -notcontains "gsi_inbox") {
    Write-Host "Creating gsi_inbox..." -ForegroundColor Green
    aws dynamodb update-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=inboxPk,AttributeType=S AttributeName=receivedAt,AttributeType=S `
        --global-secondary-index-updates file://../archive/gsi-inbox.json `
        --region $Region
    
    Write-Host "Waiting for gsi_inbox to be active..." -ForegroundColor Yellow
    aws dynamodb wait table-exists --table-name $TableName --region $Region
} else {
    Write-Host "gsi_inbox already exists" -ForegroundColor Gray
}

Write-Host "`nDone! Final GSI status:" -ForegroundColor Cyan
aws dynamodb describe-table --table-name $TableName --query "Table.GlobalSecondaryIndexes[*].{Name:IndexName,Status:IndexStatus}" --region $Region
