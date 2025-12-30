# DynamoDB Setup Script for WhatsApp Webhook Handler
# Run each GSI creation one at a time (wait for ACTIVE status before next)

$REGION = "ap-south-1"
$MESSAGES_TABLE = "base-wecare-digital-whatsapp"
$CONVERSATIONS_TABLE = "base-wecare-digital-whatsapp-conversations"

Write-Host "=== Step 1: Create Conversations Table ===" -ForegroundColor Green

aws dynamodb create-table `
    --region $REGION `
    --table-name $CONVERSATIONS_TABLE `
    --billing-mode PAY_PER_REQUEST `
    --attribute-definitions `
        AttributeName=originationPhoneNumberId,AttributeType=S `
        AttributeName=from,AttributeType=S `
        AttributeName=lastReceivedAt,AttributeType=S `
    --key-schema `
        AttributeName=originationPhoneNumberId,KeyType=HASH `
        AttributeName=from,KeyType=RANGE `
    --global-secondary-indexes '[
        {
            "IndexName": "gsi_inbox_origin_lastReceivedAt",
            "KeySchema": [
                {"AttributeName":"originationPhoneNumberId","KeyType":"HASH"},
                {"AttributeName":"lastReceivedAt","KeyType":"RANGE"}
            ],
            "Projection": {"ProjectionType":"ALL"}
        }
    ]'

Write-Host "Waiting for conversations table to be active..."
aws dynamodb wait table-exists --table-name $CONVERSATIONS_TABLE --region $REGION

Write-Host "`n=== Step 2: Add GSI gsi_from_receivedAt to Messages Table ===" -ForegroundColor Green

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=from,AttributeType=S `
        AttributeName=receivedAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_from_receivedAt",
                "KeySchema": [
                    {"AttributeName":"from","KeyType":"HASH"},
                    {"AttributeName":"receivedAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Write-Host "Waiting for GSI gsi_from_receivedAt to be active (this may take a few minutes)..."
Start-Sleep -Seconds 30

Write-Host "`n=== Step 3: Add GSI gsi_origin_receivedAt to Messages Table ===" -ForegroundColor Green

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=originationPhoneNumberId,AttributeType=S `
        AttributeName=receivedAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_origin_receivedAt",
                "KeySchema": [
                    {"AttributeName":"originationPhoneNumberId","KeyType":"HASH"},
                    {"AttributeName":"receivedAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Write-Host "Waiting for GSI gsi_origin_receivedAt to be active..."
Start-Sleep -Seconds 30

Write-Host "`n=== Step 4: Add GSI gsi_conversation_receivedAt to Messages Table ===" -ForegroundColor Green

aws dynamodb update-table `
    --region $REGION `
    --table-name $MESSAGES_TABLE `
    --attribute-definitions `
        AttributeName=conversationId,AttributeType=S `
        AttributeName=receivedAt,AttributeType=S `
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "gsi_conversation_receivedAt",
                "KeySchema": [
                    {"AttributeName":"conversationId","KeyType":"HASH"},
                    {"AttributeName":"receivedAt","KeyType":"RANGE"}
                ],
                "Projection": {"ProjectionType":"ALL"}
            }
        }
    ]'

Write-Host "`n=== DynamoDB Setup Complete ===" -ForegroundColor Green
Write-Host "Note: GSI creation can take several minutes. Check status with:"
Write-Host "aws dynamodb describe-table --table-name $MESSAGES_TABLE --region $REGION --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]'"
