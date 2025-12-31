# =============================================================================
# Create Full Access IAM Role for base-wecare-digital-whatsapp
# =============================================================================
# Creates a new IAM role with full access to all AWS services used:
# - DynamoDB, S3, Social Messaging (EUM), SNS, SES, SQS
# - EventBridge, Step Functions, Lambda, Bedrock, OpenSearch Serverless
# - CloudWatch, IAM, KMS, Secrets Manager, API Gateway, X-Ray
# =============================================================================

$ErrorActionPreference = "Continue"

$REGION = "ap-south-1"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ROLE_NAME = "base-wecare-digital-whatsapp-full-access-role"
$POLICY_NAME = "base-wecare-digital-whatsapp-full-access-policy"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Creating Full Access IAM Role" -ForegroundColor Cyan
Write-Host "  Role: $ROLE_NAME" -ForegroundColor Yellow
Write-Host "  Account: $ACCOUNT_ID" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# Step 1: Create Trust Policy
# =============================================================================
Write-Host "`n[1/5] Creating Trust Policy..." -ForegroundColor Yellow

$trustPolicy = @'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "lambda.amazonaws.com",
                    "states.amazonaws.com",
                    "events.amazonaws.com",
                    "bedrock.amazonaws.com",
                    "apigateway.amazonaws.com"
                ]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
'@

$trustPolicy | Out-File -FilePath "temp-trust-policy.json" -Encoding UTF8 -NoNewline
Write-Host "  + Trust policy created" -ForegroundColor Green

# =============================================================================
# Step 2: Create IAM Role
# =============================================================================
Write-Host "`n[2/5] Creating IAM Role..." -ForegroundColor Yellow

# Check if role exists
$roleExists = aws iam get-role --role-name $ROLE_NAME 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Role already exists: $ROLE_NAME" -ForegroundColor Gray
} else {
    aws iam create-role `
        --role-name $ROLE_NAME `
        --assume-role-policy-document file://temp-trust-policy.json `
        --description "Full access role for base-wecare-digital-whatsapp Lambda and services" `
        | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  + Created role: $ROLE_NAME" -ForegroundColor Green
    } else {
        Write-Host "  ! Failed to create role" -ForegroundColor Red
    }
}

# =============================================================================
# Step 3: Create and Attach Policy
# =============================================================================
Write-Host "`n[3/5] Attaching Full Access Policy..." -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$policyFile = Join-Path $scriptDir "full-access-policy.json"

# Check if policy exists
$policyArn = "arn:aws:iam::$ACCOUNT_ID`:policy/$POLICY_NAME"
$policyExists = aws iam get-policy --policy-arn $policyArn 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Policy exists, creating new version..." -ForegroundColor Gray
    
    # Delete oldest version if we have 5 versions
    $versions = aws iam list-policy-versions --policy-arn $policyArn | ConvertFrom-Json
    $nonDefaultVersions = $versions.Versions | Where-Object { -not $_.IsDefaultVersion }
    if ($nonDefaultVersions.Count -ge 4) {
        $oldest = $nonDefaultVersions | Sort-Object CreateDate | Select-Object -First 1
        aws iam delete-policy-version --policy-arn $policyArn --version-id $oldest.VersionId | Out-Null
    }
    
    # Create new version
    aws iam create-policy-version `
        --policy-arn $policyArn `
        --policy-document file://$policyFile `
        --set-as-default | Out-Null
    Write-Host "  + Updated policy to new version" -ForegroundColor Green
} else {
    # Create new policy
    aws iam create-policy `
        --policy-name $POLICY_NAME `
        --policy-document file://$policyFile `
        --description "Full access policy for base-wecare-digital-whatsapp" | Out-Null
    Write-Host "  + Created policy: $POLICY_NAME" -ForegroundColor Green
}

# Attach policy to role
aws iam attach-role-policy `
    --role-name $ROLE_NAME `
    --policy-arn $policyArn 2>&1 | Out-Null
Write-Host "  + Attached policy to role" -ForegroundColor Green

# =============================================================================
# Step 4: Attach AWS Managed Policies for additional coverage
# =============================================================================
Write-Host "`n[4/5] Attaching AWS Managed Policies..." -ForegroundColor Yellow

$managedPolicies = @(
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess",
    "arn:aws:iam::aws:policy/AmazonSNSFullAccess",
    "arn:aws:iam::aws:policy/AmazonSESFullAccess",
    "arn:aws:iam::aws:policy/AmazonSQSFullAccess",
    "arn:aws:iam::aws:policy/AmazonEventBridgeFullAccess",
    "arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess",
    "arn:aws:iam::aws:policy/AWSLambda_FullAccess",
    "arn:aws:iam::aws:policy/CloudWatchFullAccess",
    "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
)

foreach ($policy in $managedPolicies) {
    $policyName = $policy.Split("/")[-1]
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn $policy 2>&1 | Out-Null
    Write-Host "  + Attached: $policyName" -ForegroundColor Green
}

# =============================================================================
# Step 5: Update Lambda to use new role
# =============================================================================
Write-Host "`n[5/5] Updating Lambda Function Role..." -ForegroundColor Yellow

$ROLE_ARN = "arn:aws:iam::$ACCOUNT_ID`:role/$ROLE_NAME"

# Wait for role to propagate
Write-Host "  Waiting 10s for IAM propagation..." -ForegroundColor Gray
Start-Sleep -Seconds 10

aws lambda update-function-configuration `
    --function-name "base-wecare-digital-whatsapp" `
    --role $ROLE_ARN `
    --region $REGION 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  + Updated Lambda to use new role" -ForegroundColor Green
} else {
    Write-Host "  ! Failed to update Lambda role (may need manual update)" -ForegroundColor Yellow
}

# Cleanup
Remove-Item temp-trust-policy.json -ErrorAction SilentlyContinue

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  IAM Role Setup Complete" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Role Name: $ROLE_NAME" -ForegroundColor White
Write-Host "  Role ARN:  $ROLE_ARN" -ForegroundColor White
Write-Host ""
Write-Host "  Full Access To:" -ForegroundColor Yellow
Write-Host "    - DynamoDB (tables, indexes, streams)" -ForegroundColor Gray
Write-Host "    - S3 (buckets, objects)" -ForegroundColor Gray
Write-Host "    - Social Messaging / EUM (WhatsApp API)" -ForegroundColor Gray
Write-Host "    - SNS (topics, subscriptions)" -ForegroundColor Gray
Write-Host "    - SES (email sending)" -ForegroundColor Gray
Write-Host "    - SQS (queues)" -ForegroundColor Gray
Write-Host "    - EventBridge (event buses, rules)" -ForegroundColor Gray
Write-Host "    - Step Functions (state machines)" -ForegroundColor Gray
Write-Host "    - Lambda (functions, layers)" -ForegroundColor Gray
Write-Host "    - Bedrock (agents, knowledge bases, models)" -ForegroundColor Gray
Write-Host "    - OpenSearch Serverless (collections)" -ForegroundColor Gray
Write-Host "    - CloudWatch (logs, metrics, alarms)" -ForegroundColor Gray
Write-Host "    - IAM (roles, policies)" -ForegroundColor Gray
Write-Host "    - KMS (encryption keys)" -ForegroundColor Gray
Write-Host "    - Secrets Manager" -ForegroundColor Gray
Write-Host "    - API Gateway" -ForegroundColor Gray
Write-Host "    - X-Ray (tracing)" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
