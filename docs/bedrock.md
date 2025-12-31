# Bedrock Integration

Amazon Bedrock Agent integration for WhatsApp multimedia processing.

## Overview

The system uses Amazon Bedrock to provide AI-powered responses to WhatsApp messages. All resources are deployed in `ap-south-1` (Mumbai) region.

## Resource Naming Convention

All Bedrock resources follow the `base-wecare-digital-whatsapp` naming convention:

| Resource | Name | ID |
|----------|------|-----|
| Bedrock Agent | `base-wecare-digital-whatsapp` | `UFVSBWGCIU` |
| Knowledge Base | `base-wecare-wa-kb` | `NVF0OLULMG` |
| OpenSearch Collection | `base-wecare-wa-kb` | - |
| Service Role | `base-wecare-digital-whatsapp-full-access-role` | - |
| Agent Alias | `prod` | (to be created) |

**Agent ARN:** `arn:aws:bedrock:ap-south-1:010526260063:agent/UFVSBWGCIU`

## Agent Configuration

### Agent Details

- **Agent Name:** `base-wecare-digital-whatsapp`
- **Region:** `ap-south-1`
- **Foundation Model:** `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` (APAC inference profile)
- **Embedding Model:** `amazon.titan-embed-text-v2:0`
- **Session TTL:** 1800 seconds (30 minutes)

### Environment Variables

```bash
BEDROCK_REGION=ap-south-1
BEDROCK_AGENT_ID=UFVSBWGCIU
BEDROCK_AGENT_ALIAS_ID=IDEFJTWLLK
BEDROCK_KB_ID=NVF0OLULMG
AUTO_REPLY_BEDROCK_ENABLED=false
```

### DynamoDB Configuration

Bedrock config is stored in DynamoDB:
```
PK: CONFIG#BEDROCK
SK: SETTINGS
```

### System Prompt

```
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
```

## Knowledge Base

### Configuration

- **Name:** `base-wecare-digital-whatsapp-kb`
- **Data Source:** Web Crawler
- **Seed URL:** `https://wecare.digital`
- **Scope:** `HOST_ONLY`
- **Vector Store:** OpenSearch Serverless (`base-wecare-wa-kb`)
- **Embedding Model:** `amazon.titan-embed-text-v2:0`

### Crawl Settings

- Respects `robots.txt`
- Rate limit: 50 requests
- Scope: HOST_ONLY (only wecare.digital domain)
- Excludes admin/login pages
- Refreshes periodically

## Deployment

### Automated Setup

Run the deployment script:

```powershell
.\deploy\setup-bedrock-resources.ps1
```

This creates:
1. IAM roles for Agent and Knowledge Base
2. OpenSearch Serverless collection (vector store)
3. Bedrock Knowledge Base with web crawler
4. Bedrock Agent with Lambda action group
5. Updates Lambda environment variables
6. Stores config in DynamoDB

### Manual Setup (Console)

#### Create Bedrock Agent

1. Go to AWS Console → Bedrock → Agents (ap-south-1)
2. Create agent: `base-wecare-digital-whatsapp`
3. Select model: `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`
4. Add system prompt (see above)
5. Create alias: `prod`
6. Note Agent ID and Alias ID

#### Create Knowledge Base

1. Go to AWS Console → Bedrock → Knowledge Bases (ap-south-1)
2. Create: `base-wecare-digital-whatsapp-kb`
3. Select Web Crawler data source
4. Seed URL: `https://wecare.digital`
5. Scope: HOST_ONLY
6. Create OpenSearch Serverless collection
7. Sync data source
8. Note KB ID

### Post-Deployment

1. **Start KB Sync:**
```bash
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id <KB_ID> \
    --data-source-id <DS_ID> \
    --region ap-south-1
```

2. **Test Agent:**
```bash
aws bedrock-agent-runtime invoke-agent \
    --agent-id <AGENT_ID> \
    --agent-alias-id <ALIAS_ID> \
    --session-id test-session \
    --input-text "What is WECARE.DIGITAL?" \
    --region ap-south-1
```

3. **Enable Auto-Reply:**
```bash
aws lambda update-function-configuration \
    --function-name base-wecare-digital-whatsapp \
    --environment "Variables={AUTO_REPLY_BEDROCK_ENABLED=true}" \
    --region ap-south-1
```

## Processing Pipeline

### 1. Message Ingestion

When an inbound message is stored:
1. Publish `whatsapp.inbound.received` to EventBridge
2. EventBridge routes to `BedrockJobsQueue` (SQS)
3. `BedrockWorkerLambda` consumes the queue

### 2. Content Processing

Based on message type:

| Type | Processing |
|------|------------|
| Text | Direct agent invocation |
| Image | Claude 3.5 Sonnet vision (APAC) |
| Document | Data Automation → agent |
| Audio | Data Automation transcript → agent |
| Video | Data Automation scenes/transcript → agent |

### 3. Result Storage

Results stored in DynamoDB:
```
PK: BEDROCK#{conversationId}#{messageId}
```

Fields:
- `summary`: Content summary
- `extractedText`: Full extracted text
- `entities`: Detected entities (phones, emails, refs)
- `intent`: Detected intent
- `replyDraft`: Generated reply

### 4. Reply Sending (Feature-Flagged)

If `AUTO_REPLY_BEDROCK_ENABLED=true`:
- Send reply via `SendWhatsAppMessage`
- Respect 24-hour service window
- Use template if outside window

## API Actions

### bedrock_process_message

Process a WhatsApp message with Bedrock.

```json
{
    "action": "bedrock_process_message",
    "messageId": "wamid.xxx",
    "tenantId": "1347766229904230",
    "generateReply": true
}
```

### bedrock_invoke_agent

Invoke agent directly with text.

```json
{
    "action": "bedrock_invoke_agent",
    "inputText": "What services does WECARE.DIGITAL offer?",
    "sessionId": "session-123"
}
```

### bedrock_get_reply_draft

Get stored reply draft.

```json
{
    "action": "bedrock_get_reply_draft",
    "messageId": "wamid.xxx"
}
```

### bedrock_send_reply

Send the generated reply.

```json
{
    "action": "bedrock_send_reply",
    "messageId": "wamid.xxx",
    "metaWabaId": "1347766229904230",
    "to": "+447447840003"
}
```

### bedrock_get_config

Get Bedrock configuration status.

```json
{
    "action": "bedrock_get_config"
}
```

## Intent Detection

Simple heuristic-based intent detection:

| Intent | Keywords |
|--------|----------|
| `support_request` | help, support, assist |
| `pricing_inquiry` | price, cost, how much |
| `booking_request` | book, schedule, appointment |
| `tracking_inquiry` | track, status, where |
| `cancellation_request` | cancel, refund |
| `menu_request` | menu, options, start |
| `greeting` | hi, hello, hey |
| `general_inquiry` | (default) |

## Entity Extraction

Extracted entities:
- Phone numbers
- Email addresses
- Order/reference numbers

## Safety & Compliance

1. **PII Redaction:** Message bodies not logged to CloudWatch
2. **Per-Tenant Control:** Bedrock processing can be disabled per tenant
3. **Data Retention:** Results stored with configurable TTL
4. **Audit Trail:** All processing logged with request IDs

## CDK Resources

```typescript
// OpenSearch Serverless Collection
const ossCollection = new opensearchserverless.CfnCollection(this, 'BedrockKBCollection', {
    name: 'base-wecare-wa-kb',
    type: 'VECTORSEARCH',
    description: 'Vector store for base-wecare-digital-whatsapp-kb',
});

// Bedrock Agent
const agent = new bedrock.CfnAgent(this, 'WhatsAppAgent', {
    agentName: 'base-wecare-digital-whatsapp',
    agentResourceRoleArn: agentRole.roleArn,
    foundationModel: 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0',
    instruction: SYSTEM_PROMPT,
    idleSessionTtlInSeconds: 1800,
});

// Knowledge Base
const kb = new bedrock.CfnKnowledgeBase(this, 'WecareKB', {
    name: 'base-wecare-digital-whatsapp-kb',
    roleArn: kbRole.roleArn,
    knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
            embeddingModelArn: `arn:aws:bedrock:ap-south-1::foundation-model/amazon.titan-embed-text-v2:0`,
        },
    },
    storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
            collectionArn: ossCollection.attrArn,
            vectorIndexName: 'bedrock-kb-default-index',
            fieldMapping: {
                vectorField: 'bedrock-knowledge-base-default-vector',
                textField: 'AMAZON_BEDROCK_TEXT_CHUNK',
                metadataField: 'AMAZON_BEDROCK_METADATA',
            },
        },
    },
});

// SQS Queue for Bedrock jobs
const bedrockQueue = new sqs.Queue(this, 'BedrockJobsQueue', {
    queueName: 'base-wecare-digital-whatsapp-bedrock-jobs',
    visibilityTimeout: Duration.minutes(5),
    deadLetterQueue: {
        queue: bedrockDlq,
        maxReceiveCount: 3,
    },
});

// Lambda worker
const bedrockWorker = new lambda.Function(this, 'BedrockWorker', {
    functionName: 'base-wecare-digital-whatsapp-bedrock-worker',
    runtime: lambda.Runtime.PYTHON_3_11,
    handler: 'src.bedrock.worker.handler',
    timeout: Duration.minutes(5),
    environment: {
        BEDROCK_REGION: 'ap-south-1',
        BEDROCK_AGENT_ID: agent.attrAgentId,
        BEDROCK_KB_ID: kb.attrKnowledgeBaseId,
    },
});
```

## Runbooks

### Deploy Bedrock Resources

```powershell
# Run from project root
.\deploy\setup-bedrock-resources.ps1
```

### Sync Knowledge Base

```bash
# List data sources
aws bedrock-agent list-data-sources \
    --knowledge-base-id <KB_ID> \
    --region ap-south-1

# Start sync
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id <KB_ID> \
    --data-source-id <DS_ID> \
    --region ap-south-1

# Check sync status
aws bedrock-agent get-ingestion-job \
    --knowledge-base-id <KB_ID> \
    --data-source-id <DS_ID> \
    --ingestion-job-id <JOB_ID> \
    --region ap-south-1
```

### Test Agent

```bash
# Invoke agent
aws bedrock-agent-runtime invoke-agent \
    --agent-id <AGENT_ID> \
    --agent-alias-id <ALIAS_ID> \
    --session-id "test-$(date +%s)" \
    --input-text "Tell me about BNB CLUB" \
    --region ap-south-1
```

### Enable Auto-Reply

1. Set `AUTO_REPLY_BEDROCK_ENABLED=true` in Lambda
2. Ensure agent is configured and tested
3. Monitor CloudWatch for errors
4. Review reply quality before production

### Disable Bedrock for Tenant

1. Update tenant config in DynamoDB:
```json
{
    "pk": "TENANT#<tenantId>",
    "sk": "CONFIG",
    "bedrockEnabled": false
}
```
2. Messages will skip Bedrock processing

### Update Agent Instructions

```bash
aws bedrock-agent update-agent \
    --agent-id <AGENT_ID> \
    --agent-name base-wecare-digital-whatsapp \
    --instruction "New instructions..." \
    --foundation-model apac.anthropic.claude-3-5-sonnet-20241022-v2:0 \
    --agent-resource-role-arn <ROLE_ARN> \
    --region ap-south-1

# Prepare agent after update
aws bedrock-agent prepare-agent \
    --agent-id <AGENT_ID> \
    --region ap-south-1
```
