# AI Integration Guide

**Last Updated:** 2026-01-01

This document covers Bedrock integration, optional AgentCore patterns, and Amplify frontend compatibility.

> **Region:** ap-south-1 (Mumbai) is primary for all AI services.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Processing Pipeline                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Inbound Message                                                             │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐  │
│  │ IngestQueue │───▶│ EventBridge │───▶│ BedrockJobsQueue                │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────────────┘  │
│                                                │                             │
│                                                ▼                             │
│                                        ┌─────────────────┐                   │
│                                        │ BedrockWorker   │                   │
│                                        │ Lambda          │                   │
│                                        └────────┬────────┘                   │
│                                                 │                            │
│                          ┌──────────────────────┼──────────────────────┐     │
│                          ▼                      ▼                      ▼     │
│                   ┌────────────┐         ┌────────────┐         ┌──────────┐│
│                   │ Bedrock    │         │ Bedrock    │         │ Bedrock  ││
│                   │ Runtime    │         │ Agent      │         │ KB       ││
│                   │ (Claude)   │         │            │         │          ││
│                   └────────────┘         └────────────┘         └──────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Bedrock Implementation (Baseline)

### 2.1 Knowledge Base Configuration

**Constraint:** Knowledge Base uses ONLY `https://wecare.digital` as content source.

```python
# Knowledge Base Settings
KB_ID = "base-wecare-wa-kb"
KB_DATA_SOURCE = "https://wecare.digital"
KB_CRAWL_SCOPE = "HOST_ONLY"  # Only wecare.digital domain
KB_SYNC_SCHEDULE = "rate(1 day)"  # Daily sync via EventBridge
```

**Sync Process:**
1. EventBridge rule triggers daily at 02:00 UTC
2. Starts KB ingestion job
3. Crawls wecare.digital pages
4. Updates vector store (OpenSearch Serverless)

### 2.2 Worker Pipeline

```python
# Event flow
whatsapp.inbound.received → EventBridge → BedrockJobsQueue → BedrockWorkerLambda
```

**Processing by content type:**

| Type | Processing | Model |
|------|------------|-------|
| Text | Direct agent invocation | Claude 3.5 Sonnet |
| Image | Vision analysis | Claude 3.5 Sonnet (vision) |
| Document | Extract text → summarize | Claude 3.5 Sonnet |
| Audio | Transcribe → summarize | Transcribe + Claude |
| Video | Extract frames → analyze | Claude 3.5 Sonnet (vision) |

### 2.3 Result Storage

```
PK: TENANT#{tenantId}
SK: BEDROCK#{conversationId}#{messageId}

Fields:
- summary: Content summary
- extractedText: Full extracted text
- entities: {phones, emails, references, dates}
- intent: Detected intent
- actionSuggestions: Recommended actions
- replyDraft: Generated reply (if enabled)
- processedAt: ISO timestamp
```

### 2.4 Auto-Reply Policy

**Default:** Draft only (store result; do not send).

**Feature Flags:**
```python
AI_DRAFT_ENABLED = True          # Generate drafts
AUTO_REPLY_ENABLED = False       # Default: OFF
AUTO_REPLY_ALLOWLIST_INTENTS = [
    "greeting",
    "menu_request",
    "faq_question"
]
```

**Auto-reply rules:**
1. Only if `AUTO_REPLY_ENABLED=true`
2. Only for allowlisted intents
3. Enforce 24-hour window rules
4. Use template if outside window

---

## 3. AiProvider Abstraction

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class Draft:
    text: str
    confidence: float
    intent: str
    requires_template: bool = False

@dataclass
class Answer:
    text: str
    citations: list
    confidence: float

class AiProvider(ABC):
    """Abstract AI provider interface."""
    
    @abstractmethod
    def draft_reply(self, message_id: str, tenant_id: str) -> Draft:
        """Generate reply draft for a message."""
        pass
    
    @abstractmethod
    def answer(self, question: str, context: dict) -> Answer:
        """Answer a question with context."""
        pass

# Implementations
class BedrockRuntimeProvider(AiProvider):
    """Direct Bedrock Runtime (Claude) calls."""
    pass

class BedrockAgentsProvider(AiProvider):
    """Bedrock Agents with KB integration."""
    pass

class AgentCoreProvider(AiProvider):
    """Optional: Bedrock AgentCore for Amplify."""
    pass
```

---

## 4. OPTIONAL: Bedrock AgentCore

> **Note:** AgentCore is optional. Use it for Amplify web app chat assistant with tool orchestration.

### 4.1 Why AgentCore?

Use AgentCore if you want:
- Amplify web app chat assistant that can call backend tools safely
- Persistent memory per user/tenant
- Tool routing with governed access (gateway/policies)
- Production observability for agent behavior

**Reference:** [AgentCore Overview](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html)

### 4.2 Key Features

| Feature | Description |
|---------|-------------|
| Gateway | Convert APIs/Lambdas into MCP tools |
| Memory | Persistent conversation memory |
| Identity | User/tenant isolation |
| Observability | Agent behavior monitoring |

**Reference:** [AgentCore Gateway](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore-gateway.html)

### 4.3 Integration Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentCore Integration                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Amplify Frontend                                                │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────┐                                             │
│  │ AgentCore Agent │                                             │
│  └────────┬────────┘                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐ │
│  │ AgentCore       │───▶│ This Repo's API Gateway             │ │
│  │ Gateway (MCP)   │    │ (lookup_order, send_message, etc.)  │ │
│  └─────────────────┘    └─────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Tool Examples:**
- `lookup_order_status` - Query order by reference
- `create_request` - Submit new request
- `get_menu` - Get menu options
- `send_whatsapp_message` - Send message (guard-railed)

**Important:** WhatsApp sending stays in this repo via AWS EUM. AgentCore just orchestrates.

---

## 5. Amplify Frontend Compatibility

### 5.1 Preferred Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                    Amplify + Backend                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Amplify Gen 2                                                   │
│  ├── Frontend (React/Next.js)                                    │
│  ├── Cognito (Auth)                                              │
│  └── API Gateway ──────────────────┐                             │
│                                    │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                     │
│                          │ This Repo's     │                     │
│                          │ ApiHandlerLambda│                     │
│                          └─────────────────┘                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Reference:** [Amplify Gen 2 REST API](https://docs.amplify.aws/react/build-a-backend/add-aws-services/rest-api/set-up-rest-api/)

### 5.2 Authentication

Use Cognito JWT to authorize API calls:

```typescript
// Amplify frontend
import { fetchAuthSession } from 'aws-amplify/auth';

const session = await fetchAuthSession();
const token = session.tokens?.idToken?.toString();

const response = await fetch(`${API_URL}/action`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ action: 'list_conversations' })
});
```

### 5.3 AgentCore with Amplify

Two options:

**Option A:** Separate paths
- Frontend → API Gateway → This repo (business ops)
- Frontend → AgentCore (AI chat/automation)
- AgentCore uses Gateway tools to call this repo

**Option B:** Single path
- Frontend → This repo only
- This repo calls Bedrock runtime/agents for drafts

---

## 6. Environment Variables

```bash
# Bedrock
BEDROCK_REGION=ap-south-1
BEDROCK_AGENT_ID=<agent-id>
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
BEDROCK_KB_ID=base-wecare-wa-kb
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# AI Features
AI_DRAFT_ENABLED=true
AUTO_REPLY_ENABLED=false
AUTO_REPLY_ALLOWLIST_INTENTS=greeting,menu_request,faq_question

# AgentCore (optional)
AGENTCORE_AGENT_ID=<agentcore-agent-id>
AGENTCORE_ENABLED=false
```

---

## 7. References

- [AWS EUM Social WhatsApp Automation](https://docs.aws.amazon.com/social-messaging/latest/userguide/whatsapp-automation.html)
- [Bedrock AgentCore Overview](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html)
- [AgentCore Gateway (MCP Tools)](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore-gateway.html)
- [Amplify Gen 2 REST API](https://docs.amplify.aws/react/build-a-backend/add-aws-services/rest-api/set-up-rest-api/)
- [Durable Lambda Functions](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html)
