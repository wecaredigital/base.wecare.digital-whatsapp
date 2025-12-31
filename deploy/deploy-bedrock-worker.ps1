# =============================================================================
# Deploy Bedrock Worker Lambda
# =============================================================================
$REGION = "ap-south-1"
$PROJECT = "base-wecare-digital-whatsapp"
$FUNCTION_NAME = "$PROJECT-bedrock-worker"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

Write-Host "Deploying Bedrock Worker Lambda..." -ForegroundColor Cyan

# Create deployment package
Write-Host "`n[1/4] Creating deployment package..." -ForegroundColor Yellow
Remove-Item lambda-bedrock-worker.zip -ErrorAction SilentlyContinue

# Create temp directory
$tempDir = "temp-bedrock-worker"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy source files
Copy-Item -Path "src/bedrock/*" -Destination $tempDir -Recurse
Copy-Item -Path "src/__init__.py" -Destination $tempDir -ErrorAction SilentlyContinue

# Create zip
Compress-Archive -Path "$tempDir/*" -DestinationPath "lambda-bedrock-worker.zip" -Force
Remove-Item -Recurse -Force $tempDir

Write-Host "  + Package created" -ForegroundColor Green

# Check if function exists
Write-Host "`n[2/4] Checking Lambda function..." -ForegroundColor Yellow
$functionExists = aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>&1
if ($LASTEXITCODE -ne 0) {
    # Create function
    Write-Host "  Creating new function..." -ForegroundColor Gray
    
    $roleArn = "arn:aws:iam::${ACCOUNT_ID}:role/$PROJECT-full-access-role"
    
    aws lambda create-function `
        --function-name $FUNCTION_NAME `
        --runtime python3.12 `
        --handler handlers.lambda_handler `
        --role $roleArn `
        --zip-file fileb://lambda-bedrock-worker.zip `
        --timeout 600 `
        --memory-size 1024 `
        --environment "Variables={MESSAGES_TABLE_NAME=$PROJECT,MEDIA_BUCKET=dev.wecare.digital,BEDROCK_REGION=ap-south-1,BEDROCK_AGENT_ID=UFVSBWGCIU,BEDROCK_AGENT_ALIAS_ID=IDEFJTWLLK,BEDROCK_KB_ID=NVF0OLULMG,BEDROCK_MODEL_ID=apac.anthropic.claude-3-5-sonnet-20241022-v2:0,AUTO_REPLY_BEDROCK_ENABLED=false}" `
        --region $REGION | Out-Null
    
    Write-Host "  + Function created" -ForegroundColor Green
} else {
    # Update function
    Write-Host "  Updating existing function..." -ForegroundColor Gray
    aws lambda update-function-code `
        --function-name $FUNCTION_NAME `
        --zip-file fileb://lambda-bedrock-worker.zip `
        --region $REGION | Out-Null
    
    Write-Host "  + Function updated" -ForegroundColor Green
}

# Add SQS trigger
Write-Host "`n[3/4] Adding SQS trigger..." -ForegroundColor Yellow

$bedrockQueueArn = "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:$PROJECT-bedrock-jobs"

$existingMappings = aws lambda list-event-source-mappings --function-name $FUNCTION_NAME --region $REGION | ConvertFrom-Json
$hasBedrockQueue = $existingMappings.EventSourceMappings | Where-Object { $_.EventSourceArn -like "*bedrock-jobs*" }

if (-not $hasBedrockQueue) {
    aws lambda create-event-source-mapping `
        --function-name $FUNCTION_NAME `
        --event-source-arn $bedrockQueueArn `
        --batch-size 1 `
        --region $REGION 2>$null | Out-Null
    Write-Host "  + Bedrock jobs trigger" -ForegroundColor Green
} else {
    Write-Host "  ~ Bedrock trigger exists" -ForegroundColor Gray
}

Write-Host "`n[4/4] Verification..." -ForegroundColor Yellow
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query "Configuration.[FunctionName,Runtime,LastModified]" --output table

Write-Host "`nBedrock Worker deployed!" -ForegroundColor Green
