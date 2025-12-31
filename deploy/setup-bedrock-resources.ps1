# =============================================================================
# Setup Bedrock Agent + Knowledge Base for base-wecare-digital-whatsapp
# =============================================================================
# Region: ap-south-1 (Mumbai) - ALL RESOURCES
#
# Creates:
# 1. Bedrock Agent: base-wecare-digital-whatsapp
# 2. Knowledge Base: base-wecare-digital-whatsapp-kb (web crawler for wecare.digital)
# 3. OpenSearch Serverless Collection (vector store)
# 4. Agent Action Group (Lambda integration)
# 5. IAM Roles and Policies
# 6. Lambda environment variable updates
# 7. DynamoDB items for Bedrock session tracking
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - Lambda function: base-wecare-digital-whatsapp (must exist)
# - DynamoDB table: base-wecare-digital-whatsapp (must exist)
# =============================================================================

$ErrorActionPreference = "Continue"

# =============================================================================
# CONFIGURATION
# =============================================================================
$REGION = "ap-south-1"
$PROJECT_NAME = "base-wecare-digital-whatsapp"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

# Resource names
$AGENT_NAME = "base-wecare-digital-whatsapp"
$AGENT_ALIAS_NAME = "prod"
$KB_NAME = "base-wecare-digital-whatsapp-kb"
$OSS_COLLECTION_NAME = "base-wecare-wa-kb"  # Max 32 chars for OpenSearch
$AGENT_ROLE_NAME = "base-wecare-digital-whatsapp-bedrock-agent-role"
$KB_ROLE_NAME = "base-wecare-digital-whatsapp-bedrock-kb-role"

# Existing resources
$LAMBDA_FUNCTION_NAME = "base-wecare-digital-whatsapp"
$DYNAMODB_TABLE_NAME = "base-wecare-digital-whatsapp"

# Model configuration (ap-south-1 via APAC inference profile)
$FOUNDATION_MODEL = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
$EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

# Knowledge Base - Web Crawler config
$KB_SEED_URL = "https://wecare.digital"
$KB_CRAWL_SCOPE = "HOST_ONLY"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BEDROCK AGENT + KB SETUP: $PROJECT_NAME" -ForegroundColor Cyan
Write-Host "  Region: $REGION (ap-south-1 Mumbai)" -ForegroundColor Cyan
Write-Host "  Account: $ACCOUNT_ID" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# STEP 0: Enable Bedrock Model Invocation Logging
# =============================================================================
Write-Host "`n[0/10] Enabling Bedrock Model Invocation Logging..." -ForegroundColor Yellow

$S3_LOGGING_BUCKET = "base-wecare-digital-whatsapp-bedrock-logs"
$S3_LOGGING_PREFIX = "bedrock-logs"

# Check if S3 bucket exists, create if not
$bucketExists = aws s3api head-bucket --bucket $S3_LOGGING_BUCKET 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Creating S3 bucket for Bedrock logs..." -ForegroundColor Gray
    if ($REGION -eq "us-east-1") {
        aws s3api create-bucket --bucket $S3_LOGGING_BUCKET --region $REGION | Out-Null
    } else {
        aws s3api create-bucket --bucket $S3_LOGGING_BUCKET --region $REGION `
            --create-bucket-configuration LocationConstraint=$REGION | Out-Null
    }
    Write-Host "  + Created bucket: $S3_LOGGING_BUCKET" -ForegroundColor Green
} else {
    Write-Host "  ~ Bucket exists: $S3_LOGGING_BUCKET" -ForegroundColor Gray
}

# Add bucket policy to allow Bedrock to write logs
$loggingBucketPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowBedrockLogging",
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::$S3_LOGGING_BUCKET/$S3_LOGGING_PREFIX/*",
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": "$ACCOUNT_ID"
                },
                "ArnLike": {
                    "aws:SourceArn": "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:*"
                }
            }
        }
    ]
}
"@
$loggingBucketPolicy | Out-File -FilePath "temp-logging-bucket-policy.json" -Encoding UTF8 -NoNewline

aws s3api put-bucket-policy --bucket $S3_LOGGING_BUCKET `
    --policy file://temp-logging-bucket-policy.json 2>$null
Write-Host "  + Applied bucket policy for Bedrock logging" -ForegroundColor Green

# Enable Model Invocation Logging
$loggingConfig = @"
{
    "loggingConfig": {
        "s3Config": {
            "bucketName": "$S3_LOGGING_BUCKET",
            "keyPrefix": "$S3_LOGGING_PREFIX"
        },
        "textDataDeliveryEnabled": true,
        "imageDataDeliveryEnabled": true,
        "embeddingDataDeliveryEnabled": true
    }
}
"@
$loggingConfig | Out-File -FilePath "temp-bedrock-logging.json" -Encoding UTF8 -NoNewline

aws bedrock put-model-invocation-logging-configuration `
    --logging-config file://temp-bedrock-logging.json `
    --region $REGION 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  + Enabled Model Invocation Logging" -ForegroundColor Green
    Write-Host "    S3: s3://$S3_LOGGING_BUCKET/$S3_LOGGING_PREFIX" -ForegroundColor Gray
    Write-Host "    Text: Enabled | Image: Enabled | Embedding: Enabled" -ForegroundColor Gray
} else {
    Write-Host "  ! Failed to enable logging - check permissions" -ForegroundColor Red
}

# =============================================================================
# STEP 1: Create IAM Role for Bedrock Agent
# =============================================================================
Write-Host "`n[1/10] Creating Bedrock Agent IAM Role..." -ForegroundColor Yellow

$roleExists = aws iam get-role --role-name $AGENT_ROLE_NAME 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Role exists: $AGENT_ROLE_NAME" -ForegroundColor Gray
} else {
    aws iam create-role --role-name $AGENT_ROLE_NAME `
        --assume-role-policy-document file://deploy/bedrock-agent-trust.json `
        --description "Bedrock Agent role for $PROJECT_NAME" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  + Created role: $AGENT_ROLE_NAME" -ForegroundColor Green
    } else {
        Write-Host "  ! Failed to create role" -ForegroundColor Red
    }
}

# Wait for role to propagate
Start-Sleep -Seconds 3

# Attach inline full access policy
aws iam put-role-policy --role-name $AGENT_ROLE_NAME `
    --policy-name "FullAccessPolicy" `
    --policy-document file://deploy/bedrock-full-access-policy.json

# Attach AWS managed full access policies
aws iam attach-role-policy --role-name $AGENT_ROLE_NAME `
    --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" 2>$null
aws iam attach-role-policy --role-name $AGENT_ROLE_NAME `
    --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess" 2>$null

Write-Host "  + Attached agent permissions (full access)" -ForegroundColor Green
$AGENT_ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$AGENT_ROLE_NAME"

# =============================================================================
# STEP 2: Create IAM Role for Knowledge Base
# =============================================================================
Write-Host "`n[2/10] Creating Knowledge Base IAM Role..." -ForegroundColor Yellow

$roleExists = aws iam get-role --role-name $KB_ROLE_NAME 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Role exists: $KB_ROLE_NAME" -ForegroundColor Gray
} else {
    aws iam create-role --role-name $KB_ROLE_NAME `
        --assume-role-policy-document file://deploy/bedrock-kb-trust.json `
        --description "Bedrock KB role for $PROJECT_NAME" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  + Created role: $KB_ROLE_NAME" -ForegroundColor Green
    } else {
        Write-Host "  ! Failed to create role" -ForegroundColor Red
    }
}

# Wait for role to propagate
Start-Sleep -Seconds 3

# Attach inline full access policy
aws iam put-role-policy --role-name $KB_ROLE_NAME `
    --policy-name "FullAccessPolicy" `
    --policy-document file://deploy/bedrock-full-access-policy.json

# Attach AWS managed full access policies
aws iam attach-role-policy --role-name $KB_ROLE_NAME `
    --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" 2>$null
aws iam attach-role-policy --role-name $KB_ROLE_NAME `
    --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess" 2>$null

Write-Host "  + Attached KB permissions (full access)" -ForegroundColor Green
$KB_ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$KB_ROLE_NAME"

Write-Host "  Waiting 10s for IAM propagation..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# =============================================================================
# STEP 3: Create OpenSearch Serverless Collection (Vector Store)
# =============================================================================
Write-Host "`n[3/10] Creating OpenSearch Serverless Collection..." -ForegroundColor Yellow

# Encryption policy
$encPolicy = "[{`"Rules`":[{`"ResourceType`":`"collection`",`"Resource`":[`"collection/$OSS_COLLECTION_NAME`"]}],`"AWSOwnedKey`":true}]"

try {
    aws opensearchserverless create-security-policy `
        --name "$OSS_COLLECTION_NAME-enc" --type encryption `
        --policy $encPolicy --region $REGION 2>$null | Out-Null
    Write-Host "  + Created encryption policy" -ForegroundColor Green
} catch { Write-Host "  ~ Encryption policy exists" -ForegroundColor Gray }

# Network policy (public for Bedrock access)
$netPolicy = "[{`"Rules`":[{`"ResourceType`":`"collection`",`"Resource`":[`"collection/$OSS_COLLECTION_NAME`"]},{`"ResourceType`":`"dashboard`",`"Resource`":[`"collection/$OSS_COLLECTION_NAME`"]}],`"AllowFromPublic`":true}]"

try {
    aws opensearchserverless create-security-policy `
        --name "$OSS_COLLECTION_NAME-net" --type network `
        --policy $netPolicy --region $REGION 2>$null | Out-Null
    Write-Host "  + Created network policy" -ForegroundColor Green
} catch { Write-Host "  ~ Network policy exists" -ForegroundColor Gray }

# Data access policy
$dataPolicy = "[{`"Rules`":[{`"ResourceType`":`"index`",`"Resource`":[`"index/$OSS_COLLECTION_NAME/*`"],`"Permission`":[`"aoss:CreateIndex`",`"aoss:DeleteIndex`",`"aoss:UpdateIndex`",`"aoss:DescribeIndex`",`"aoss:ReadDocument`",`"aoss:WriteDocument`"]},{`"ResourceType`":`"collection`",`"Resource`":[`"collection/$OSS_COLLECTION_NAME`"],`"Permission`":[`"aoss:CreateCollectionItems`",`"aoss:DescribeCollectionItems`",`"aoss:UpdateCollectionItems`"]}],`"Principal`":[`"$KB_ROLE_ARN`",`"arn:aws:iam::${ACCOUNT_ID}:root`"]}]"

try {
    aws opensearchserverless create-access-policy `
        --name "$OSS_COLLECTION_NAME-data" --type data `
        --policy $dataPolicy --region $REGION 2>$null | Out-Null
    Write-Host "  + Created data access policy" -ForegroundColor Green
} catch { Write-Host "  ~ Data access policy exists" -ForegroundColor Gray }

# Create collection
try {
    $collResult = aws opensearchserverless create-collection `
        --name $OSS_COLLECTION_NAME --type VECTORSEARCH `
        --description "Vector store for $KB_NAME" `
        --region $REGION 2>$null | ConvertFrom-Json
    $OSS_COLLECTION_ARN = $collResult.createCollectionDetail.arn
    $OSS_COLLECTION_ID = $collResult.createCollectionDetail.id
    Write-Host "  + Created collection: $OSS_COLLECTION_NAME" -ForegroundColor Green
} catch {
    $existing = aws opensearchserverless batch-get-collection `
        --names $OSS_COLLECTION_NAME --region $REGION | ConvertFrom-Json
    $OSS_COLLECTION_ARN = $existing.collectionDetails[0].arn
    $OSS_COLLECTION_ID = $existing.collectionDetails[0].id
    Write-Host "  ~ Collection exists: $OSS_COLLECTION_NAME" -ForegroundColor Gray
}

# Wait for collection to be ACTIVE
Write-Host "  Waiting for collection to become ACTIVE (2-5 min)..." -ForegroundColor Gray
$maxWait = 300; $waited = 0
while ($waited -lt $maxWait) {
    $status = aws opensearchserverless batch-get-collection `
        --names $OSS_COLLECTION_NAME --region $REGION | ConvertFrom-Json
    $collStatus = $status.collectionDetails[0].status
    if ($collStatus -eq "ACTIVE") {
        $OSS_ENDPOINT = $status.collectionDetails[0].collectionEndpoint
        Write-Host "  + Collection ACTIVE: $OSS_ENDPOINT" -ForegroundColor Green
        break
    }
    Write-Host "    Status: $collStatus..." -ForegroundColor Gray
    Start-Sleep -Seconds 15; $waited += 15
}

# =============================================================================
# STEP 4: Create Bedrock Knowledge Base
# =============================================================================
Write-Host "`n[4/10] Creating Bedrock Knowledge Base..." -ForegroundColor Yellow

$kbConfigJson = @"
{
    "name": "$KB_NAME",
    "description": "Knowledge Base for WECARE.DIGITAL WhatsApp - crawls https://wecare.digital",
    "roleArn": "$KB_ROLE_ARN",
    "knowledgeBaseConfiguration": {
        "type": "VECTOR",
        "vectorKnowledgeBaseConfiguration": {
            "embeddingModelArn": "arn:aws:bedrock:${REGION}::foundation-model/$EMBEDDING_MODEL"
        }
    },
    "storageConfiguration": {
        "type": "OPENSEARCH_SERVERLESS",
        "opensearchServerlessConfiguration": {
            "collectionArn": "$OSS_COLLECTION_ARN",
            "vectorIndexName": "bedrock-kb-default-index",
            "fieldMapping": {
                "vectorField": "bedrock-knowledge-base-default-vector",
                "textField": "AMAZON_BEDROCK_TEXT_CHUNK",
                "metadataField": "AMAZON_BEDROCK_METADATA"
            }
        }
    }
}
"@
$kbConfigJson | Out-File -FilePath "temp-kb-config.json" -Encoding UTF8 -NoNewline

try {
    $kbResult = aws bedrock-agent create-knowledge-base `
        --cli-input-json file://temp-kb-config.json `
        --region $REGION 2>$null | ConvertFrom-Json
    $KB_ID = $kbResult.knowledgeBase.knowledgeBaseId
    $KB_ARN = $kbResult.knowledgeBase.knowledgeBaseArn
    Write-Host "  + Created KB: $KB_NAME" -ForegroundColor Green
    Write-Host "    KB ID: $KB_ID" -ForegroundColor Gray
} catch {
    # Try to get existing KB
    $kbList = aws bedrock-agent list-knowledge-bases --region $REGION | ConvertFrom-Json
    $existingKb = $kbList.knowledgeBaseSummaries | Where-Object { $_.name -eq $KB_NAME }
    if ($existingKb) {
        $KB_ID = $existingKb.knowledgeBaseId
        $KB_ARN = "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:knowledge-base/$KB_ID"
        Write-Host "  ~ KB exists: $KB_ID" -ForegroundColor Gray
    } else {
        Write-Host "  ! KB creation failed - create manually in console" -ForegroundColor Red
        $KB_ID = "MANUAL"
    }
}

# =============================================================================
# STEP 5: Add Web Crawler Data Source to KB
# =============================================================================
Write-Host "`n[5/10] Adding Web Crawler Data Source..." -ForegroundColor Yellow

if ($KB_ID -ne "MANUAL") {
    $dsConfig = @"
{
    "name": "wecare-digital-website",
    "description": "Web crawler for https://wecare.digital",
    "dataSourceConfiguration": {
        "type": "WEB",
        "webConfiguration": {
            "sourceConfiguration": {
                "urlConfiguration": {
                    "seedUrls": [{"url": "$KB_SEED_URL"}]
                }
            },
            "crawlerConfiguration": {
                "crawlerLimits": {
                    "rateLimit": 50
                },
                "scope": "$KB_CRAWL_SCOPE"
            }
        }
    }
}
"@
    $dsConfig | Out-File -FilePath "temp-ds-config.json" -Encoding UTF8 -NoNewline

    try {
        $dsResult = aws bedrock-agent create-data-source `
            --knowledge-base-id $KB_ID `
            --cli-input-json file://temp-ds-config.json `
            --region $REGION 2>$null | ConvertFrom-Json
        $DS_ID = $dsResult.dataSource.dataSourceId
        Write-Host "  + Created data source: $DS_ID" -ForegroundColor Green
    } catch {
        Write-Host "  ~ Data source may already exist" -ForegroundColor Gray
    }
}

# =============================================================================
# STEP 6: Create Bedrock Agent
# =============================================================================
Write-Host "`n[6/10] Creating Bedrock Agent..." -ForegroundColor Yellow

$agentInstruction = @"
You are the WhatsApp assistant for WECARE.DIGITAL.

CAPABILITIES:
- Answer questions about WECARE.DIGITAL services using the knowledge base
- Help users navigate to the right service or brand
- Process user requests and route to appropriate actions

WECARE.DIGITAL BRANDS:
- BNB CLUB: Travel services
- NO FAULT: Online Dispute Resolution (ODR)
- EXPO WEEK: Digital events
- RITUAL GURU: Cultural services
- LEGAL CHAMP: Documentation services
- SWDHYA: Samvad (communication)

SELF-SERVICE OPTIONS:
- Submit Request, Request Amendment, Request Tracking
- RX Slot, Drop Docs, Enterprise Assist
- Leave Review, FAQ, Gift Card, Download App

RULES:
1. Use ONLY knowledge base content for WECARE.DIGITAL info
2. If unsure, ask clarifying questions
3. Keep responses concise for WhatsApp (mobile-friendly)
4. Use emojis sparingly
5. For actions outside your scope, explain what you can help with
"@

$agentConfig = @"
{
    "agentName": "$AGENT_NAME",
    "description": "WhatsApp assistant for WECARE.DIGITAL - handles customer queries via AWS EUM Social",
    "agentResourceRoleArn": "$AGENT_ROLE_ARN",
    "foundationModel": "$FOUNDATION_MODEL",
    "idleSessionTTLInSeconds": 1800,
    "instruction": "$($agentInstruction -replace '"', '\"' -replace "`n", '\n')"
}
"@
$agentConfig | Out-File -FilePath "temp-agent-config.json" -Encoding UTF8 -NoNewline

try {
    $agentResult = aws bedrock-agent create-agent `
        --cli-input-json file://temp-agent-config.json `
        --region $REGION 2>$null | ConvertFrom-Json
    $AGENT_ID = $agentResult.agent.agentId
    $AGENT_ARN = $agentResult.agent.agentArn
    Write-Host "  + Created Agent: $AGENT_NAME" -ForegroundColor Green
    Write-Host "    Agent ID: $AGENT_ID" -ForegroundColor Gray
} catch {
    # Get existing agent
    $agentList = aws bedrock-agent list-agents --region $REGION | ConvertFrom-Json
    $existingAgent = $agentList.agentSummaries | Where-Object { $_.agentName -eq $AGENT_NAME }
    if ($existingAgent) {
        $AGENT_ID = $existingAgent.agentId
        $AGENT_ARN = "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent/$AGENT_ID"
        Write-Host "  ~ Agent exists: $AGENT_ID" -ForegroundColor Gray
    } else {
        Write-Host "  ! Agent creation failed" -ForegroundColor Red
        $AGENT_ID = "MANUAL"
    }
}

# =============================================================================
# STEP 7: Associate Knowledge Base with Agent
# =============================================================================
Write-Host "`n[7/10] Associating Knowledge Base with Agent..." -ForegroundColor Yellow

if ($AGENT_ID -ne "MANUAL" -and $KB_ID -ne "MANUAL") {
    try {
        aws bedrock-agent associate-agent-knowledge-base `
            --agent-id $AGENT_ID `
            --agent-version "DRAFT" `
            --knowledge-base-id $KB_ID `
            --description "WECARE.DIGITAL website knowledge" `
            --knowledge-base-state "ENABLED" `
            --region $REGION 2>$null | Out-Null
        Write-Host "  + Associated KB with Agent" -ForegroundColor Green
    } catch {
        Write-Host "  ~ KB already associated or error" -ForegroundColor Gray
    }
}

# =============================================================================
# STEP 8: Create Agent Action Group (Lambda Integration)
# =============================================================================
Write-Host "`n[8/10] Creating Agent Action Group (Lambda)..." -ForegroundColor Yellow

# Add Lambda permission for Bedrock to invoke
$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:$LAMBDA_FUNCTION_NAME"

try {
    aws lambda add-permission `
        --function-name $LAMBDA_FUNCTION_NAME `
        --statement-id "AllowBedrockAgent-$AGENT_ID" `
        --action "lambda:InvokeFunction" `
        --principal "bedrock.amazonaws.com" `
        --source-arn "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent/$AGENT_ID" `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Added Lambda permission for Bedrock" -ForegroundColor Green
} catch {
    Write-Host "  ~ Lambda permission exists" -ForegroundColor Gray
}

# Create Action Group with OpenAPI schema
$actionGroupSchema = @"
{
    "openapi": "3.0.0",
    "info": {"title": "WECARE WhatsApp Actions", "version": "1.0.0"},
    "paths": {
        "/send_message": {
            "post": {
                "operationId": "sendWhatsAppMessage",
                "description": "Send a WhatsApp message to a user",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "to": {"type": "string", "description": "Recipient phone number"},
                                    "text": {"type": "string", "description": "Message text"}
                                },
                                "required": ["to", "text"]
                            }
                        }
                    }
                }
            }
        },
        "/get_menu": {
            "get": {
                "operationId": "getMainMenu",
                "description": "Get the main menu options for WECARE.DIGITAL"
            }
        },
        "/submit_request": {
            "post": {
                "operationId": "submitServiceRequest",
                "description": "Submit a service request",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "requestType": {"type": "string"},
                                    "details": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"@
$actionGroupSchema | Out-File -FilePath "temp-action-schema.json" -Encoding UTF8 -NoNewline

if ($AGENT_ID -ne "MANUAL") {
    try {
        aws bedrock-agent create-agent-action-group `
            --agent-id $AGENT_ID `
            --agent-version "DRAFT" `
            --action-group-name "wecare-whatsapp-actions" `
            --description "WhatsApp actions via Lambda" `
            --action-group-executor "lambda={lambdaArn=$LAMBDA_ARN}" `
            --api-schema "payload=$(Get-Content temp-action-schema.json -Raw)" `
            --region $REGION 2>$null | Out-Null
        Write-Host "  + Created Action Group" -ForegroundColor Green
    } catch {
        Write-Host "  ~ Action Group exists or error" -ForegroundColor Gray
    }

    # Prepare and create agent alias
    Write-Host "  Preparing agent..." -ForegroundColor Gray
    aws bedrock-agent prepare-agent --agent-id $AGENT_ID --region $REGION 2>$null | Out-Null
    Start-Sleep -Seconds 5

    try {
        $aliasResult = aws bedrock-agent create-agent-alias `
            --agent-id $AGENT_ID `
            --agent-alias-name $AGENT_ALIAS_NAME `
            --description "Production alias" `
            --region $REGION 2>$null | ConvertFrom-Json
        $AGENT_ALIAS_ID = $aliasResult.agentAlias.agentAliasId
        Write-Host "  + Created Agent Alias: $AGENT_ALIAS_ID" -ForegroundColor Green
    } catch {
        # Get existing alias
        $aliasList = aws bedrock-agent list-agent-aliases --agent-id $AGENT_ID --region $REGION | ConvertFrom-Json
        $existingAlias = $aliasList.agentAliasSummaries | Where-Object { $_.agentAliasName -eq $AGENT_ALIAS_NAME }
        if ($existingAlias) {
            $AGENT_ALIAS_ID = $existingAlias.agentAliasId
            Write-Host "  ~ Alias exists: $AGENT_ALIAS_ID" -ForegroundColor Gray
        }
    }
}

# =============================================================================
# STEP 9: Update Lambda Environment Variables + DynamoDB Config
# =============================================================================
Write-Host "`n[9/10] Updating Lambda + DynamoDB Configuration..." -ForegroundColor Yellow

# Update Lambda environment variables
$envVars = @{
    BEDROCK_REGION = $REGION
    BEDROCK_AGENT_ID = $AGENT_ID
    BEDROCK_AGENT_ALIAS_ID = if ($AGENT_ALIAS_ID) { $AGENT_ALIAS_ID } else { "TSTALIASID" }
    BEDROCK_KB_ID = $KB_ID
    AUTO_REPLY_BEDROCK_ENABLED = "false"
}

$envJson = $envVars | ConvertTo-Json -Compress
Write-Host "  Updating Lambda env vars..." -ForegroundColor Gray

# Get current env vars and merge
$currentConfig = aws lambda get-function-configuration `
    --function-name $LAMBDA_FUNCTION_NAME `
    --region $REGION | ConvertFrom-Json

$currentEnv = @{}
if ($currentConfig.Environment.Variables) {
    $currentConfig.Environment.Variables.PSObject.Properties | ForEach-Object {
        $currentEnv[$_.Name] = $_.Value
    }
}

# Merge new vars
$envVars.GetEnumerator() | ForEach-Object {
    $currentEnv[$_.Key] = $_.Value
}

$mergedEnvJson = @{ Variables = $currentEnv } | ConvertTo-Json -Compress -Depth 3
$mergedEnvJson | Out-File -FilePath "temp-lambda-env.json" -Encoding UTF8 -NoNewline

aws lambda update-function-configuration `
    --function-name $LAMBDA_FUNCTION_NAME `
    --environment file://temp-lambda-env.json `
    --region $REGION 2>$null | Out-Null

Write-Host "  + Updated Lambda environment" -ForegroundColor Green

# Add Bedrock config to DynamoDB
$bedrockConfigItem = @"
{
    "pk": {"S": "CONFIG#BEDROCK"},
    "sk": {"S": "SETTINGS"},
    "itemType": {"S": "BEDROCK_CONFIG"},
    "agentId": {"S": "$AGENT_ID"},
    "agentAliasId": {"S": "$AGENT_ALIAS_ID"},
    "knowledgeBaseId": {"S": "$KB_ID"},
    "region": {"S": "$REGION"},
    "foundationModel": {"S": "$FOUNDATION_MODEL"},
    "embeddingModel": {"S": "$EMBEDDING_MODEL"},
    "kbSeedUrl": {"S": "$KB_SEED_URL"},
    "autoReplyEnabled": {"BOOL": false},
    "createdAt": {"S": "$(Get-Date -Format 'o')"},
    "updatedAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
$bedrockConfigItem | Out-File -FilePath "temp-ddb-bedrock-config.json" -Encoding UTF8 -NoNewline

aws dynamodb put-item `
    --table-name $DYNAMODB_TABLE_NAME `
    --item file://temp-ddb-bedrock-config.json `
    --region $REGION 2>$null | Out-Null

Write-Host "  + Saved Bedrock config to DynamoDB" -ForegroundColor Green

# =============================================================================
# STEP 10: Start Knowledge Base Ingestion
# =============================================================================
Write-Host "`n[10/10] Starting Knowledge Base Ingestion..." -ForegroundColor Yellow

if ($KB_ID -ne "MANUAL") {
    # Get data source ID
    $dsList = aws bedrock-agent list-data-sources --knowledge-base-id $KB_ID --region $REGION 2>$null | ConvertFrom-Json
    if ($dsList.dataSourceSummaries.Count -gt 0) {
        $DS_ID = $dsList.dataSourceSummaries[0].dataSourceId
        
        try {
            $ingestionResult = aws bedrock-agent start-ingestion-job `
                --knowledge-base-id $KB_ID `
                --data-source-id $DS_ID `
                --region $REGION 2>$null | ConvertFrom-Json
            $INGESTION_JOB_ID = $ingestionResult.ingestionJob.ingestionJobId
            Write-Host "  + Started ingestion job: $INGESTION_JOB_ID" -ForegroundColor Green
            Write-Host "    This will crawl https://wecare.digital and index content" -ForegroundColor Gray
        } catch {
            Write-Host "  ! Could not start ingestion - start manually" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ~ No data source found - create web crawler first" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ~ Skipping - KB not created" -ForegroundColor Gray
}

# Cleanup temp files
Remove-Item temp-*.json -ErrorAction SilentlyContinue

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  BEDROCK SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Region:           $REGION" -ForegroundColor White
Write-Host "  Logging Bucket:   s3://$S3_LOGGING_BUCKET/$S3_LOGGING_PREFIX" -ForegroundColor White
Write-Host "  Agent Name:       $AGENT_NAME" -ForegroundColor White
Write-Host "  Agent ID:         $AGENT_ID" -ForegroundColor Green
Write-Host "  Agent Alias ID:   $AGENT_ALIAS_ID" -ForegroundColor Green
Write-Host "  KB Name:          $KB_NAME" -ForegroundColor White
Write-Host "  KB ID:            $KB_ID" -ForegroundColor Green
Write-Host "  OSS Collection:   $OSS_COLLECTION_NAME" -ForegroundColor White
Write-Host "  Lambda:           $LAMBDA_FUNCTION_NAME" -ForegroundColor White
Write-Host "  DynamoDB:         $DYNAMODB_TABLE_NAME" -ForegroundColor White
Write-Host ""
Write-Host "  MODEL INVOCATION LOGGING:" -ForegroundColor Yellow
Write-Host "    Text:      Enabled" -ForegroundColor Gray
Write-Host "    Image:     Enabled" -ForegroundColor Gray
Write-Host "    Embedding: Enabled" -ForegroundColor Gray
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Check ingestion status: aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID --region $REGION" -ForegroundColor Gray
Write-Host "  2. Test agent: aws bedrock-agent-runtime invoke-agent --agent-id $AGENT_ID --agent-alias-id $AGENT_ALIAS_ID --session-id test --input-text 'Hello' --region $REGION" -ForegroundColor Gray
Write-Host "  3. Enable auto-reply: Set AUTO_REPLY_BEDROCK_ENABLED=true in Lambda" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
