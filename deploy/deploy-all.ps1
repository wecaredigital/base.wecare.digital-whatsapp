# Complete Deployment Script for WhatsApp Webhook Handler
# This script runs all deployment steps in the correct order

$ErrorActionPreference = "Stop"
$REGION = "ap-south-1"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  WhatsApp Webhook Handler - Full Deploy   " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Setup S3 folder
Write-Host "[1/5] Setting up S3 folder structure..." -ForegroundColor Yellow
& .\setup-s3-folder.ps1
Write-Host ""

# Step 2: Setup DynamoDB (conversations table + GSIs)
Write-Host "[2/5] Setting up DynamoDB tables and GSIs..." -ForegroundColor Yellow
Write-Host "Note: GSI creation takes several minutes. Running in background..." -ForegroundColor Gray

# Create conversations table first
$CONVERSATIONS_TABLE = "base-wecare-digital-whatsapp-conversations"
$TABLE_EXISTS = $false

try {
    aws dynamodb describe-table --table-name $CONVERSATIONS_TABLE --region $REGION 2>$null | Out-Null
    $TABLE_EXISTS = $true
    Write-Host "Conversations table already exists"
} catch {
    Write-Host "Creating conversations table..."
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
        --global-secondary-indexes '[{"IndexName":"gsi_inbox_origin_lastReceivedAt","KeySchema":[{"AttributeName":"originationPhoneNumberId","KeyType":"HASH"},{"AttributeName":"lastReceivedAt","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]'
    
    Write-Host "Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name $CONVERSATIONS_TABLE --region $REGION
}
Write-Host ""

# Step 3: Update IAM role
Write-Host "[3/5] Updating IAM role permissions..." -ForegroundColor Yellow
& .\update-iam-role.ps1
Write-Host ""

# Step 4: Deploy Lambda
Write-Host "[4/5] Deploying Lambda function..." -ForegroundColor Yellow
& .\deploy-lambda.ps1
Write-Host ""

# Step 5: Test
Write-Host "[5/5] Running test invocation..." -ForegroundColor Yellow
& .\test-lambda.ps1
Write-Host ""

Write-Host "============================================" -ForegroundColor Green
Write-Host "  Deployment Complete!                     " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Resources deployed:"
Write-Host "  - Lambda: arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-whatsapp:live"
Write-Host "  - Messages Table: base-wecare-digital-whatsapp"
Write-Host "  - Conversations Table: base-wecare-digital-whatsapp-conversations"
Write-Host "  - S3 Media Path: s3://dev.wecare.digital/WhatsApp/"
Write-Host ""
Write-Host "Note: GSIs on messages table may still be creating. Check status with:"
Write-Host "aws dynamodb describe-table --table-name base-wecare-digital-whatsapp --region ap-south-1 --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]'"
