# Bedrock Agent Core - Frontend API

Production-ready API for connecting Bedrock Agent to frontend apps (Amplify, React, etc.).

## Features

- Session-based conversations with history
- S3 integration for media/documents
- Bedrock Agent invocation
- Knowledge Base queries
- Multi-tenant support
- Rate limiting
- CORS-enabled for Amplify

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Amplify App    │────▶│  HTTP API GW     │────▶│  Agent Core     │
│  (React/Next)   │     │  (CORS enabled)  │     │  Lambda         │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────┼─────────────────────────────────┐
                        │                                 │                                 │
                        ▼                                 ▼                                 ▼
               ┌─────────────────┐             ┌─────────────────┐             ┌─────────────────┐
               │  Bedrock Agent  │             │  Knowledge Base │             │  DynamoDB       │
               │  (Claude 3.5)   │             │  (Web Crawler)  │             │  (Sessions)     │
               └─────────────────┘             └─────────────────┘             └─────────────────┘
```

## Deployment

### Option 1: PowerShell Script (Recommended)

```powershell
# Prerequisites: Run setup-bedrock-resources.ps1 first
.\deploy\setup-agent-core.ps1
```

### Option 2: CDK

```bash
cd cdk
npm install
npx cdk deploy AgentCoreStack
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message, get AI response |
| POST | `/api/invoke-agent` | Direct Bedrock Agent invocation |
| POST | `/api/query-kb` | Query Knowledge Base |
| POST | `/api/upload` | Upload file to S3 |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Get session details |
| GET | `/api/sessions/{id}/history` | Get chat history |
| DELETE | `/api/sessions/{id}` | Delete session |
| GET | `/api/health` | Health check |

## Usage from Amplify

### TypeScript/JavaScript

```typescript
import { AgentCoreClient } from './amplify-client';

const client = new AgentCoreClient({
  apiEndpoint: 'https://xxx.execute-api.ap-south-1.amazonaws.com',
  tenantId: '1347766229904230',
  userId: 'user@example.com'
});

// Chat with AI
const response = await client.chat('What services do you offer?');
console.log(response.response);
console.log(response.suggestedActions);

// Query Knowledge Base
const kbResult = await client.queryKB('What is BNB CLUB?');
console.log(kbResult.generatedResponse);

// Direct Agent invocation
const agentResult = await client.invokeAgent('Help me book a travel package');
console.log(agentResult.response);
```

### Python

```python
from src.bedrock.client import AgentCoreClient

client = AgentCoreClient(
    api_endpoint='https://xxx.execute-api.ap-south-1.amazonaws.com',
    tenant_id='1347766229904230',
    user_id='user@example.com'
)

# Chat
response = client.chat('What services do you offer?')
print(response['response'])

# Query KB
kb_result = client.query_kb('What is BNB CLUB?')
print(kb_result['generatedResponse'])
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_REGION` | AWS region | `ap-south-1` |
| `BEDROCK_MODEL_ID` | Claude model ID | `anthropic.claude-3-haiku-20240307-v1:0` |
| `BEDROCK_AGENT_ID` | Bedrock Agent ID | - |
| `BEDROCK_AGENT_ALIAS_ID` | Agent alias ID | - |
| `BEDROCK_KB_ID` | Knowledge Base ID | - |
| `MESSAGES_TABLE_NAME` | DynamoDB table | `base-wecare-digital-whatsapp` |
| `MEDIA_BUCKET` | S3 bucket | `dev.wecare.digital` |
| `ALLOWED_ORIGINS` | CORS origins | `*.amplifyapp.com,wecare.digital` |

## CORS Configuration

Pre-configured for:
- `http://localhost:3000` (development)
- `https://*.amplifyapp.com` (Amplify apps)
- `https://wecare.digital`
- `https://www.wecare.digital`

## Rate Limiting

- 60 requests per minute per user
- Configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW`

## Session Management

- Sessions auto-expire after 24 hours (TTL)
- Max 20 messages per session in history
- Sessions stored in DynamoDB with `AGENT_SESSION#` prefix

## Files

- `src/bedrock/agent_core.py` - Core Agent class
- `src/bedrock/api_lambda.py` - Lambda entry point
- `src/bedrock/api_handlers.py` - API handlers
- `src/bedrock/client.py` - Python SDK
- `src/bedrock/amplify-client.ts` - TypeScript SDK
- `cdk/lib/agent-core-stack.ts` - CDK stack
- `deploy/setup-agent-core.ps1` - Deployment script
