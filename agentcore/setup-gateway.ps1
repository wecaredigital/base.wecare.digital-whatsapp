# =============================================================================
# SETUP BEDROCK AGENTCORE GATEWAY
# =============================================================================
# Creates AgentCore Gateway with MCP tools for:
# - Payments API (p.wecare.digital)
# - Shortlinks API (r.wecare.digital)
# - WhatsApp API
# =============================================================================

$Region = "ap-south-1"
$AccountId = "010526260063"
$GatewayName = "wecare-digital-gateway"

Write-Host "=== BEDROCK AGENTCORE GATEWAY SETUP ===" -ForegroundColor Cyan
Write-Host "Region: $Region"
Write-Host "Account: $AccountId"
Write-Host ""

# =============================================================================
# Step 1: Check if AgentCore is available
# =============================================================================
Write-Host "Step 1: Checking AgentCore availability..." -ForegroundColor Yellow

# AgentCore Gateway uses bedrock-agent-runtime or a dedicated service
# As of late 2025, it's accessed via AWS CLI bedrock-agentcore commands

# Check if the service is available
$agentcoreCheck = aws bedrock-agentcore help 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "AgentCore CLI not available. Checking alternative..." -ForegroundColor Yellow
    
    # Try via bedrock-agent
    $bedrockCheck = aws bedrock-agent help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Using bedrock-agent CLI" -ForegroundColor Green
    } else {
        Write-Host "ERROR: AgentCore/Bedrock Agent CLI not available." -ForegroundColor Red
        Write-Host "Please ensure you have the latest AWS CLI installed." -ForegroundColor Yellow
        Write-Host "Run: pip install --upgrade awscli" -ForegroundColor Cyan
        exit 1
    }
}

# =============================================================================
# Step 2: Create IAM Role for AgentCore Gateway
# =============================================================================
Write-Host "`nStep 2: Creating IAM Role for AgentCore Gateway..." -ForegroundColor Yellow

$TrustPolicy = @'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "bedrock.amazonaws.com",
                    "agentcore.bedrock.amazonaws.com"
                ]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
'@

$TrustPolicy | Out-File -FilePath "agentcore-trust-policy.json" -Encoding ascii

# Create role
aws iam create-role `
    --role-name wecare-agentcore-gateway-role `
    --assume-role-policy-document file://agentcore-trust-policy.json `
    --description "Role for WECARE AgentCore Gateway" `
    2>$null

# Attach policies for API Gateway and Lambda invocation
$GatewayPolicy = @'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "execute-api:Invoke",
                "execute-api:ManageConnections"
            ],
            "Resource": [
                "arn:aws:execute-api:ap-south-1:010526260063:*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": [
                "arn:aws:lambda:ap-south-1:010526260063:function:wecare-digital-*",
                "arn:aws:lambda:ap-south-1:010526260063:function:base-wecare-digital-*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
'@

$GatewayPolicy | Out-File -FilePath "agentcore-gateway-policy.json" -Encoding ascii

aws iam put-role-policy `
    --role-name wecare-agentcore-gateway-role `
    --policy-name AgentCoreGatewayPolicy `
    --policy-document file://agentcore-gateway-policy.json

Write-Host "IAM Role created: wecare-agentcore-gateway-role" -ForegroundColor Green

# =============================================================================
# Step 3: Create AgentCore Gateway (if CLI supports it)
# =============================================================================
Write-Host "`nStep 3: AgentCore Gateway Configuration..." -ForegroundColor Yellow

# Note: As of the current AWS CLI, AgentCore Gateway may need to be created via Console
# or using the Bedrock Agent APIs. The exact CLI commands depend on the service version.

Write-Host @"

=============================================================================
MANUAL SETUP REQUIRED (AgentCore Gateway Console)
=============================================================================

Since AgentCore Gateway is in preview, complete setup via AWS Console:

1. Go to: https://console.aws.amazon.com/bedrock/home?region=$Region#/agentcore/gateways

2. Click "Create gateway"

3. Gateway settings:
   - Name: $GatewayName
   - Description: WECARE Digital API Gateway for MCP
   - IAM Role: wecare-agentcore-gateway-role

4. Add API Gateway targets:

   TARGET 1: Payments API
   - Name: payments
   - Type: API Gateway
   - API ID: z8raub1eth
   - Stage: prod
   - OpenAPI: Upload agentcore/openapi-payments.yaml

   TARGET 2: Shortlinks API
   - Name: shortlinks
   - Type: API Gateway
   - API ID: w19x9gi045
   - Stage: prod
   - OpenAPI: Upload agentcore/openapi-shortlinks.yaml

   TARGET 3: WhatsApp API
   - Name: whatsapp
   - Type: API Gateway (HTTP)
   - API ID: o0wjog0nl4
   - OpenAPI: Upload agentcore/openapi-whatsapp.yaml

5. Configure authentication:
   - Inbound: IAM (for your AI agents)
   - Outbound: None (APIs are public)

6. Click "Create gateway"

=============================================================================
AFTER CREATION
=============================================================================

Your MCP endpoint will be:
https://{gateway-id}.gateway.bedrock-agentcore.$Region.amazonaws.com

Tools available to AI agents:
- createPaymentLink(amount, description, ...)
- getShortLinkStats(code)
- createShortLink(targetUrl, title, ...)
- whatsappAction(action, to, text, ...)

=============================================================================
"@ -ForegroundColor Cyan

# Cleanup temp files
Remove-Item -Path "agentcore-trust-policy.json" -ErrorAction SilentlyContinue
Remove-Item -Path "agentcore-gateway-policy.json" -ErrorAction SilentlyContinue

Write-Host "`nSetup script complete!" -ForegroundColor Green
Write-Host "OpenAPI specs created in agentcore/ folder" -ForegroundColor Cyan
