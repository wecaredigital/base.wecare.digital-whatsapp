# =============================================================================
# Setup Bedrock Agent Core for Frontend (Amplify) Integration
# =============================================================================
# Region: ap-south-1 (Mumbai)
#
# Creates:
# 1. Lambda function: base-wecare-digital-whatsapp-agent-core
# 2. HTTP API Gateway with CORS for Amplify
# 3. IAM Role with full Bedrock + S3 access
# 4. Environment configuration
#
# Prerequisites:
# - AWS CLI configured
# - Existing S3 bucket: dev.wecare.digital
# - Existing DynamoDB table: base-wecare-digital-whatsapp
# - Bedrock Agent + KB already created (run setup-bedrock-resources.ps1 first)
# =============================================================================

$ErrorActionPreference = "Continue"

# =============================================================================
# CONFIGURATION
# =============================================================================
$REGION = "ap-south-1"
$PROJECT_NAME = "base-wecare-digital-whatsapp"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

# Resource names
$LAMBDA_NAME = "$PROJECT_NAME-agent-core"
$API_NAME = "$PROJECT_NAME-agent-core-api"
$ROLE_NAME = "$PROJECT_NAME-agent-core-role"

# Existing resources
$S3_BUCKET = "dev.wecare.digital"
$DDB_TABLE = "base-wecare-digital-whatsapp"

# Bedrock config (from setup-bedrock-resources.ps1)
$BEDROCK_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

# Get existing Bedrock Agent/KB IDs
$AGENT_ID = ""
$KB_ID = ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BEDROCK AGENT CORE SETUP" -ForegroundColor Cyan
Write-Host "  Region: $REGION (ap-south-1 Mumbai)" -ForegroundColor Cyan
Write-Host "  Account: $ACCOUNT_ID" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# STEP 1: Get Existing Bedrock Resources
# =============================================================================
Write-Host "`n[1/7] Getting existing Bedrock resources..." -ForegroundColor Yellow

# Get Agent ID
$agentList = aws bedrock-agent list-agents --region $REGION 2>$null | ConvertFrom-Json
$existingAgent = $agentList.agentSummaries | Where-Object { $_.agentName -eq $PROJECT_NAME }
if ($existingAgent) {
    $AGENT_ID = $existingAgent.agentId
    Write-Host "  + Found Agent: $AGENT_ID" -ForegroundColor Green
    
    # Get Agent Alias
    $aliasList = aws bedrock-agent list-agent-aliases --agent-id $AGENT_ID --region $REGION 2>$null | ConvertFrom-Json
    $prodAlias = $aliasList.agentAliasSummaries | Where-Object { $_.agentAliasName -eq "prod" }
    if ($prodAlias) {
        $AGENT_ALIAS_ID = $prodAlias.agentAliasId
        Write-Host "  + Found Alias: $AGENT_ALIAS_ID" -ForegroundColor Green
    }
} else {
    Write-Host "  ! Agent not found - run setup-bedrock-resources.ps1 first" -ForegroundColor Yellow
}

# Get KB ID
$kbList = aws bedrock-agent list-knowledge-bases --region $REGION 2>$null | ConvertFrom-Json
$existingKb = $kbList.knowledgeBaseSummaries | Where-Object { $_.name -eq "$PROJECT_NAME-kb" }
if ($existingKb) {
    $KB_ID = $existingKb.knowledgeBaseId
    Write-Host "  + Found KB: $KB_ID" -ForegroundColor Green
} else {
    Write-Host "  ! KB not found - run setup-bedrock-resources.ps1 first" -ForegroundColor Yellow
}

# =============================================================================
# STEP 2: Create IAM Role for Agent Core Lambda
# =============================================================================
Write-Host "`n[2/7] Creating IAM Role..." -ForegroundColor Yellow

$trustPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }
    ]
}
"@
[System.IO.File]::WriteAllText("temp-trust.json", $trustPolicy)

$roleExists = aws iam get-role --role-name $ROLE_NAME 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Role exists: $ROLE_NAME" -ForegroundColor Gray
} else {
    aws iam create-role --role-name $ROLE_NAME `
        --assume-role-policy-document file://temp-trust.json `
        --description "Agent Core Lambda role with full Bedrock access" | Out-Null
    Write-Host "  + Created role: $ROLE_NAME" -ForegroundColor Green
}

$ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME"

# Full access policy
$fullAccessPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        },
        {
            "Sid": "BedrockFullAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:*",
                "bedrock-agent:*",
                "bedrock-agent-runtime:*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3Access",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::$S3_BUCKET",
                "arn:aws:s3:::$S3_BUCKET/*"
            ]
        },
        {
            "Sid": "DynamoDBAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": [
                "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/$DDB_TABLE",
                "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/$DDB_TABLE/index/*"
            ]
        }
    ]
}
"@
$fullAccessPolicy | Out-File -FilePath "temp-policy.json" -Encoding ASCII -NoNewline

aws iam put-role-policy --role-name $ROLE_NAME `
    --policy-name "AgentCoreFullAccess" `
    --policy-document file://temp-policy.json

Write-Host "  + Attached full access policy" -ForegroundColor Green

# Wait for IAM propagation
Write-Host "  Waiting 10s for IAM propagation..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# =============================================================================
# STEP 3: Package Lambda Code
# =============================================================================
Write-Host "`n[3/7] Packaging Lambda code..." -ForegroundColor Yellow

$zipFile = "agent-core-lambda.zip"

# Remove old zip
if (Test-Path $zipFile) { Remove-Item $zipFile }

# Create temp directory structure
$tempDir = "temp-lambda-package"
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
New-Item -ItemType Directory -Path $tempDir | Out-Null
New-Item -ItemType Directory -Path "$tempDir/src/bedrock" -Force | Out-Null
New-Item -ItemType Directory -Path "$tempDir/handlers" -Force | Out-Null

# Copy ONLY the files needed for Agent Core API (no other bedrock modules)
Copy-Item "src/bedrock/agent_core.py" "$tempDir/src/bedrock/"
Copy-Item "src/bedrock/api_lambda.py" "$tempDir/src/bedrock/"
Copy-Item "src/bedrock/api_handlers.py" "$tempDir/src/bedrock/"
Copy-Item "handlers/base.py" "$tempDir/handlers/"

# Create empty __init__.py files (no imports to avoid dependency issues)
"" | Set-Content "$tempDir/src/__init__.py"
"" | Set-Content "$tempDir/src/bedrock/__init__.py"
"" | Set-Content "$tempDir/handlers/__init__.py"

# Create zip
Compress-Archive -Path "$tempDir/*" -DestinationPath $zipFile -Force

Write-Host "  + Created $zipFile" -ForegroundColor Green

# Cleanup temp
Remove-Item -Recurse -Force $tempDir

# =============================================================================
# STEP 4: Create/Update Lambda Function
# =============================================================================
Write-Host "`n[4/7] Creating Lambda function..." -ForegroundColor Yellow

$envVars = @{
    BEDROCK_REGION = $REGION
    MESSAGES_TABLE_NAME = $DDB_TABLE
    MESSAGES_PK_NAME = "pk"
    MEDIA_BUCKET = $S3_BUCKET
    BEDROCK_MODEL_ID = $BEDROCK_MODEL
    BEDROCK_AGENT_ID = if ($AGENT_ID) { $AGENT_ID } else { "" }
    BEDROCK_AGENT_ALIAS_ID = if ($AGENT_ALIAS_ID) { $AGENT_ALIAS_ID } else { "" }
    BEDROCK_KB_ID = if ($KB_ID) { $KB_ID } else { "" }
    ALLOWED_ORIGINS = "http://localhost:3000,https://localhost:3000,https://*.amplifyapp.com,https://wecare.digital,https://www.wecare.digital"
    LOG_LEVEL = "INFO"
}
$envJson = @{ Variables = $envVars } | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText("temp-env.json", $envJson)

$lambdaExists = aws lambda get-function --function-name $LAMBDA_NAME --region $REGION 2>&1
if ($LASTEXITCODE -eq 0) {
    # Update existing
    aws lambda update-function-code `
        --function-name $LAMBDA_NAME `
        --zip-file fileb://$zipFile `
        --region $REGION | Out-Null
    
    Start-Sleep -Seconds 3
    
    aws lambda update-function-configuration `
        --function-name $LAMBDA_NAME `
        --environment file://temp-env.json `
        --timeout 60 `
        --memory-size 512 `
        --region $REGION | Out-Null
    
    Write-Host "  + Updated Lambda: $LAMBDA_NAME" -ForegroundColor Green
} else {
    # Create new
    aws lambda create-function `
        --function-name $LAMBDA_NAME `
        --runtime python3.12 `
        --role $ROLE_ARN `
        --handler "src.bedrock.api_lambda.lambda_handler" `
        --zip-file fileb://$zipFile `
        --timeout 60 `
        --memory-size 512 `
        --environment file://temp-env.json `
        --description "Bedrock Agent Core API for Amplify/frontend" `
        --region $REGION | Out-Null
    
    Write-Host "  + Created Lambda: $LAMBDA_NAME" -ForegroundColor Green
}

$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:$LAMBDA_NAME"

# =============================================================================
# STEP 5: Create HTTP API Gateway
# =============================================================================
Write-Host "`n[5/7] Creating HTTP API Gateway..." -ForegroundColor Yellow

# Check if API exists
$apiList = aws apigatewayv2 get-apis --region $REGION | ConvertFrom-Json
$existingApi = $apiList.Items | Where-Object { $_.Name -eq $API_NAME }

if ($existingApi) {
    $API_ID = $existingApi.ApiId
    $API_ENDPOINT = $existingApi.ApiEndpoint
    Write-Host "  ~ API exists: $API_ID" -ForegroundColor Gray
    
    # Update CORS to allow all origins
    Write-Host "  Updating CORS to allow all origins..." -ForegroundColor Gray
    aws apigatewayv2 update-api `
        --api-id $API_ID `
        --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,DELETE,OPTIONS,AllowHeaders=Content-Type,Authorization,X-Tenant-Id,X-User-Id,MaxAge=86400' `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Updated CORS: AllowOrigins=*" -ForegroundColor Green
} else {
    # Create HTTP API with CORS - allow all origins
    $apiResult = aws apigatewayv2 create-api `
        --name $API_NAME `
        --protocol-type HTTP `
        --description "Bedrock Agent Core API for Amplify" `
        --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,DELETE,OPTIONS,AllowHeaders=Content-Type,Authorization,X-Tenant-Id,X-User-Id,MaxAge=86400' `
        --region $REGION | ConvertFrom-Json
    
    $API_ID = $apiResult.ApiId
    $API_ENDPOINT = $apiResult.ApiEndpoint
    Write-Host "  + Created API: $API_ID" -ForegroundColor Green
}

# Create Lambda integration
$integrationResult = aws apigatewayv2 create-integration `
    --api-id $API_ID `
    --integration-type AWS_PROXY `
    --integration-uri $LAMBDA_ARN `
    --payload-format-version "2.0" `
    --region $REGION 2>$null | ConvertFrom-Json

$INTEGRATION_ID = $integrationResult.IntegrationId
Write-Host "  + Created integration: $INTEGRATION_ID" -ForegroundColor Green

# Add routes
$routes = @(
    @{ Method = "POST"; Path = "/api/chat" },
    @{ Method = "GET"; Path = "/api/sessions" },
    @{ Method = "GET"; Path = "/api/sessions/{sessionId}" },
    @{ Method = "DELETE"; Path = "/api/sessions/{sessionId}" },
    @{ Method = "GET"; Path = "/api/sessions/{sessionId}/history" },
    @{ Method = "GET"; Path = "/api/health" },
    @{ Method = "POST"; Path = "/api/invoke-agent" },
    @{ Method = "POST"; Path = "/api/query-kb" }
)

foreach ($route in $routes) {
    $routeKey = "$($route.Method) $($route.Path)"
    try {
        aws apigatewayv2 create-route `
            --api-id $API_ID `
            --route-key $routeKey `
            --target "integrations/$INTEGRATION_ID" `
            --region $REGION 2>$null | Out-Null
        Write-Host "    + Route: $routeKey" -ForegroundColor Gray
    } catch {
        Write-Host "    ~ Route exists: $routeKey" -ForegroundColor Gray
    }
}

# Create/update default stage
try {
    aws apigatewayv2 create-stage `
        --api-id $API_ID `
        --stage-name '$default' `
        --auto-deploy `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Created default stage" -ForegroundColor Green
} catch {
    Write-Host "  ~ Default stage exists" -ForegroundColor Gray
}

# =============================================================================
# STEP 6: Add Lambda Permission for API Gateway
# =============================================================================
Write-Host "`n[6/7] Adding Lambda permissions..." -ForegroundColor Yellow

try {
    aws lambda add-permission `
        --function-name $LAMBDA_NAME `
        --statement-id "AllowAPIGateway-$API_ID" `
        --action "lambda:InvokeFunction" `
        --principal "apigateway.amazonaws.com" `
        --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*" `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Added API Gateway permission" -ForegroundColor Green
} catch {
    Write-Host "  ~ Permission exists" -ForegroundColor Gray
}

# =============================================================================
# STEP 7: Save Configuration to DynamoDB
# =============================================================================
Write-Host "`n[7/7] Saving configuration..." -ForegroundColor Yellow

$configItem = @"
{
    "pk": {"S": "CONFIG#AGENT_CORE"},
    "sk": {"S": "SETTINGS"},
    "itemType": {"S": "AGENT_CORE_CONFIG"},
    "lambdaArn": {"S": "$LAMBDA_ARN"},
    "apiEndpoint": {"S": "$API_ENDPOINT"},
    "apiId": {"S": "$API_ID"},
    "agentId": {"S": "$AGENT_ID"},
    "agentAliasId": {"S": "$AGENT_ALIAS_ID"},
    "kbId": {"S": "$KB_ID"},
    "s3Bucket": {"S": "$S3_BUCKET"},
    "region": {"S": "$REGION"},
    "createdAt": {"S": "$(Get-Date -Format 'o')"},
    "updatedAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
[System.IO.File]::WriteAllText("temp-config.json", $configItem)

aws dynamodb put-item `
    --table-name $DDB_TABLE `
    --item file://temp-config.json `
    --region $REGION 2>$null | Out-Null

Write-Host "  + Saved config to DynamoDB" -ForegroundColor Green

# Cleanup
Remove-Item temp-*.json -ErrorAction SilentlyContinue
Remove-Item $zipFile -ErrorAction SilentlyContinue

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  AGENT CORE SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Region:         $REGION" -ForegroundColor White
Write-Host "  Lambda:         $LAMBDA_NAME" -ForegroundColor Green
Write-Host "  API Endpoint:   $API_ENDPOINT" -ForegroundColor Green
Write-Host "  API ID:         $API_ID" -ForegroundColor White
Write-Host "  S3 Bucket:      $S3_BUCKET" -ForegroundColor White
Write-Host "  DynamoDB:       $DDB_TABLE" -ForegroundColor White
Write-Host ""
Write-Host "  Bedrock Agent:  $AGENT_ID" -ForegroundColor White
Write-Host "  Agent Alias:    $AGENT_ALIAS_ID" -ForegroundColor White
Write-Host "  Knowledge Base: $KB_ID" -ForegroundColor White
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AMPLIFY INTEGRATION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Add to your Amplify app:" -ForegroundColor White
Write-Host ""
Write-Host "  const API_ENDPOINT = `"$API_ENDPOINT`";" -ForegroundColor Yellow
Write-Host ""
Write-Host "  // See docs/agent-core.md for full integration guide" -ForegroundColor Gray
Write-Host "  // POST /api/chat with X-Tenant-Id header" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nTest the API:" -ForegroundColor White
Write-Host "  curl $API_ENDPOINT/api/health" -ForegroundColor Yellow
