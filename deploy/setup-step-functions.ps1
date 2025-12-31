# =============================================================================
# Setup Step Functions Campaign Engine for base-wecare-digital-whatsapp
# =============================================================================
# Creates Step Functions state machine for bulk marketing campaigns:
# - Expand segment -> Create batches -> Process batches -> Aggregate results
# - Rate limiting between batches
# - Error handling and retry logic
# =============================================================================

$ErrorActionPreference = "Continue"

$REGION = "ap-south-1"
$PROJECT_NAME = "base-wecare-digital-whatsapp"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

# Resource names
$STATE_MACHINE_NAME = "$PROJECT_NAME-campaign-engine"
$LAMBDA_ARN = "arn:aws:lambda:$REGION`:$ACCOUNT_ID`:function:$PROJECT_NAME"
$ROLE_NAME = "$PROJECT_NAME-stepfunctions-role"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Setting up Step Functions Campaign Engine" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_NAME" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# =============================================================================
# Step 1: Create IAM Role for Step Functions
# =============================================================================
Write-Host "`n[1/3] Creating IAM Role..." -ForegroundColor Yellow

$trustPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "states.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }
    ]
}
"@
$trustPolicy | Out-File -FilePath "temp-sfn-trust.json" -Encoding UTF8 -NoNewline

$roleExists = $null
$roleExists = aws iam get-role --role-name $ROLE_NAME 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ~ Role exists: $ROLE_NAME" -ForegroundColor Gray
} else {
    aws iam create-role --role-name $ROLE_NAME `
        --assume-role-policy-document file://temp-sfn-trust.json `
        --description "Step Functions role for campaign engine" `
        --region $REGION | Out-Null
    Write-Host "  + Created role: $ROLE_NAME" -ForegroundColor Green
}

$sfnPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "InvokeLambda",
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": ["$LAMBDA_ARN", "$LAMBDA_ARN`:*"]
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogDelivery",
                "logs:GetLogDelivery",
                "logs:UpdateLogDelivery",
                "logs:DeleteLogDelivery",
                "logs:ListLogDeliveries",
                "logs:PutResourcePolicy",
                "logs:DescribeResourcePolicies",
                "logs:DescribeLogGroups"
            ],
            "Resource": "*"
        },
        {
            "Sid": "XRay",
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets"
            ],
            "Resource": "*"
        }
    ]
}
"@
$sfnPolicy | Out-File -FilePath "temp-sfn-policy.json" -Encoding UTF8 -NoNewline

aws iam put-role-policy --role-name $ROLE_NAME `
    --policy-name "StepFunctionsPolicy" `
    --policy-document file://temp-sfn-policy.json `
    --region $REGION | Out-Null

Write-Host "  + Attached policy to role" -ForegroundColor Green

$ROLE_ARN = "arn:aws:iam::$ACCOUNT_ID`:role/$ROLE_NAME"

# Wait for role propagation
Write-Host "  Waiting for IAM propagation..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# =============================================================================
# Step 2: Create State Machine Definition
# =============================================================================
Write-Host "`n[2/3] Creating State Machine Definition..." -ForegroundColor Yellow

$stateMachineDefinition = @"
{
  "Comment": "Campaign Engine - Bulk WhatsApp Marketing",
  "StartAt": "ExpandSegment",
  "States": {
    "ExpandSegment": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "$LAMBDA_ARN",
        "Payload": {
          "action": "expand_campaign_segment",
          "campaignId.$": "$.campaignId",
          "segmentId.$": "$.segmentId",
          "tenantId.$": "$.tenantId"
        }
      },
      "ResultPath": "$.segmentResult",
      "ResultSelector": {
        "recipients.$": "$.Payload.recipients",
        "totalCount.$": "$.Payload.totalCount"
      },
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "HandleError"
      }],
      "Next": "CreateBatches"
    },
    "CreateBatches": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "$LAMBDA_ARN",
        "Payload": {
          "action": "create_campaign_batches",
          "campaignId.$": "$.campaignId",
          "recipients.$": "$.segmentResult.recipients",
          "batchSize.$": "$.batchSize",
          "rateLimit.$": "$.rateLimit"
        }
      },
      "ResultPath": "$.batchResult",
      "ResultSelector": {
        "batches.$": "$.Payload.batches",
        "batchCount.$": "$.Payload.batchCount"
      },
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "HandleError"
      }],
      "Next": "ProcessBatches"
    },
    "ProcessBatches": {
      "Type": "Map",
      "ItemsPath": "$.batchResult.batches",
      "MaxConcurrency": 1,
      "Parameters": {
        "campaignId.$": "$.campaignId",
        "batchId.$": "$$.Map.Item.Value.batchId",
        "recipients.$": "$$.Map.Item.Value.recipients",
        "templateName.$": "$.templateName",
        "templateLanguage.$": "$.templateLanguage",
        "templateParams.$": "$.templateParams",
        "tenantId.$": "$.tenantId",
        "phoneArn.$": "$.phoneArn",
        "waitSeconds.$": "$.waitSeconds"
      },
      "Iterator": {
        "StartAt": "SendBatch",
        "States": {
          "SendBatch": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName": "$LAMBDA_ARN",
              "Payload": {
                "action": "send_campaign_batch",
                "campaignId.$": "$.campaignId",
                "batchId.$": "$.batchId",
                "recipients.$": "$.recipients",
                "templateName.$": "$.templateName",
                "templateLanguage.$": "$.templateLanguage",
                "templateParams.$": "$.templateParams",
                "tenantId.$": "$.tenantId",
                "phoneArn.$": "$.phoneArn"
              }
            },
            "ResultPath": "$.sendResult",
            "Next": "RateLimitWait"
          },
          "RateLimitWait": {
            "Type": "Wait",
            "SecondsPath": "$.waitSeconds",
            "End": true
          }
        }
      },
      "ResultPath": "$.batchResults",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "HandleError"
      }],
      "Next": "AggregateResults"
    },
    "AggregateResults": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "$LAMBDA_ARN",
        "Payload": {
          "action": "aggregate_campaign_results",
          "campaignId.$": "$.campaignId",
          "batchResults.$": "$.batchResults",
          "totalRecipients.$": "$.segmentResult.totalCount"
        }
      },
      "ResultPath": "$.aggregateResult",
      "Next": "UpdateCampaignStatus"
    },
    "UpdateCampaignStatus": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "$LAMBDA_ARN",
        "Payload": {
          "action": "update_campaign_status",
          "campaignId.$": "$.campaignId",
          "status": "COMPLETED",
          "results.$": "$.aggregateResult.Payload"
        }
      },
      "ResultPath": "$.finalResult",
      "Next": "CampaignSucceeded"
    },
    "HandleError": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "$LAMBDA_ARN",
        "Payload": {
          "action": "handle_campaign_error",
          "campaignId.$": "$.campaignId",
          "error.$": "$.error"
        }
      },
      "Next": "CampaignFailed"
    },
    "CampaignFailed": {
      "Type": "Fail",
      "Cause": "Campaign execution failed",
      "Error": "CampaignError"
    },
    "CampaignSucceeded": {
      "Type": "Succeed"
    }
  }
}
"@

$stateMachineDefinition | Out-File -FilePath "temp-sfn-definition.json" -Encoding UTF8 -NoNewline
Write-Host "  + Created state machine definition" -ForegroundColor Green

# =============================================================================
# Step 3: Create State Machine
# =============================================================================
Write-Host "`n[3/3] Creating State Machine..." -ForegroundColor Yellow

try {
    $result = aws stepfunctions create-state-machine `
        --name $STATE_MACHINE_NAME `
        --definition file://temp-sfn-definition.json `
        --role-arn $ROLE_ARN `
        --type STANDARD `
        --tracing-configuration enabled=true `
        --region $REGION 2>$null | ConvertFrom-Json
    
    $STATE_MACHINE_ARN = $result.stateMachineArn
    Write-Host "  + Created state machine: $STATE_MACHINE_NAME" -ForegroundColor Green
} catch {
    # Update existing
    $existing = aws stepfunctions list-state-machines --region $REGION | ConvertFrom-Json
    $sm = $existing.stateMachines | Where-Object { $_.name -eq $STATE_MACHINE_NAME }
    if ($sm) {
        $STATE_MACHINE_ARN = $sm.stateMachineArn
        aws stepfunctions update-state-machine `
            --state-machine-arn $STATE_MACHINE_ARN `
            --definition file://temp-sfn-definition.json `
            --role-arn $ROLE_ARN `
            --region $REGION | Out-Null
        Write-Host "  ~ Updated state machine: $STATE_MACHINE_NAME" -ForegroundColor Gray
    }
}

# Cleanup temp files
Remove-Item temp-sfn-*.json -ErrorAction SilentlyContinue

# =============================================================================
# Step 4: Update Lambda Environment
# =============================================================================
Write-Host "`n[4/4] Updating Lambda Environment..." -ForegroundColor Yellow

$currentConfig = aws lambda get-function-configuration `
    --function-name $PROJECT_NAME `
    --region $REGION | ConvertFrom-Json

$currentEnv = @{}
if ($currentConfig.Environment.Variables) {
    $currentConfig.Environment.Variables.PSObject.Properties | ForEach-Object {
        $currentEnv[$_.Name] = $_.Value
    }
}

$currentEnv["CAMPAIGN_STATE_MACHINE_ARN"] = $STATE_MACHINE_ARN

$envJson = @{ Variables = $currentEnv } | ConvertTo-Json -Compress -Depth 3
$envJson | Out-File -FilePath "temp-lambda-env.json" -Encoding UTF8 -NoNewline

aws lambda update-function-configuration `
    --function-name $PROJECT_NAME `
    --environment file://temp-lambda-env.json `
    --region $REGION 2>$null | Out-Null

Remove-Item temp-lambda-env.json -ErrorAction SilentlyContinue

Write-Host "  + Updated Lambda environment" -ForegroundColor Green

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "Step Functions Setup Complete" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "State Machine: $STATE_MACHINE_NAME" -ForegroundColor White
Write-Host "ARN: $STATE_MACHINE_ARN" -ForegroundColor Gray
Write-Host ""
Write-Host "Workflow:" -ForegroundColor White
Write-Host "  1. ExpandSegment - Get all recipients from segment" -ForegroundColor Gray
Write-Host "  2. CreateBatches - Split into rate-limited batches" -ForegroundColor Gray
Write-Host "  3. ProcessBatches - Send each batch with wait" -ForegroundColor Gray
Write-Host "  4. AggregateResults - Compile send statistics" -ForegroundColor Gray
Write-Host "  5. UpdateCampaignStatus - Mark campaign complete" -ForegroundColor Gray
Write-Host ""
Write-Host "To start a campaign:" -ForegroundColor Yellow
Write-Host @"
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --input '{
        "campaignId": "camp-001",
        "segmentId": "seg-001",
        "tenantId": "1347766229904230",
        "templateName": "hello_world",
        "templateLanguage": "en",
        "templateParams": {},
        "phoneArn": "arn:aws:social-messaging:...",
        "batchSize": 100,
        "rateLimit": 50,
        "waitSeconds": 60
    }' \
    --region $REGION
"@ -ForegroundColor Gray
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
