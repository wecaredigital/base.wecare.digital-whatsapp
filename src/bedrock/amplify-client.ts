/**
 * =============================================================================
 * Bedrock Agent Core Client - TypeScript/JavaScript SDK for Amplify
 * =============================================================================
 * Use this client to connect to the Bedrock Agent Core API from Amplify apps.
 *
 * Installation:
 *   npm install axios
 *
 * Usage:
 *   import { AgentCoreClient } from './amplify-client';
 *   
 *   const client = new AgentCoreClient({
 *     apiEndpoint: 'https://xxx.execute-api.ap-south-1.amazonaws.com',
 *     tenantId: '1347766229904230'
 *   });
 *   
 *   const response = await client.chat('What services do you offer?');
 *   console.log(response.response);
 * =============================================================================
 */

export interface AgentCoreConfig {
  apiEndpoint: string;
  tenantId: string;
  userId?: string;
  timeout?: number;
}

export interface ChatResponse {
  success: boolean;
  sessionId: string;
  messageId?: string;
  response?: string;
  intent?: string;
  suggestedActions?: string[];
  citations?: any[];
  error?: string;
}

export interface KBQueryResponse {
  success: boolean;
  query: string;
  generatedResponse?: string;
  results?: any[];
  citations?: any[];
  error?: string;
}

export interface SessionInfo {
  sessionId: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  messageId: string;
}

export class AgentCoreClient {
  private config: Required<AgentCoreConfig>;
  private sessionId: string | null = null;

  constructor(config: AgentCoreConfig) {
    this.config = {
      apiEndpoint: config.apiEndpoint.replace(/\/$/, ''),
      tenantId: config.tenantId,
      userId: config.userId || 'anonymous',
      timeout: config.timeout || 60000,
    };
  }

  private get headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'X-Tenant-Id': this.config.tenantId,
      'X-User-Id': this.config.userId,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    data?: any,
    params?: Record<string, string>
  ): Promise<T> {
    const url = new URL(`${this.config.apiEndpoint}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }

    const response = await fetch(url.toString(), {
      method,
      headers: this.headers,
      body: data ? JSON.stringify(data) : undefined,
    });

    return response.json();
  }

  // =========================================================================
  // CHAT API
  // =========================================================================

  /**
   * Send a chat message and get AI response.
   */
  async chat(
    message: string,
    options?: { sessionId?: string; metadata?: Record<string, any> }
  ): Promise<ChatResponse> {
    const data = {
      message,
      tenantId: this.config.tenantId,
      userId: this.config.userId,
      sessionId: options?.sessionId || this.sessionId,
      metadata: options?.metadata || {},
    };

    const result = await this.request<ChatResponse>('POST', '/api/chat', data);

    if (result.success && result.sessionId) {
      this.sessionId = result.sessionId;
    }

    return result;
  }

  /**
   * Directly invoke Bedrock Agent.
   */
  async invokeAgent(
    inputText: string,
    options?: { sessionId?: string; enableTrace?: boolean }
  ): Promise<ChatResponse> {
    const data = {
      inputText,
      sessionId: options?.sessionId || this.sessionId || `sess-${Date.now()}`,
      tenantId: this.config.tenantId,
      enableTrace: options?.enableTrace || false,
    };

    const result = await this.request<ChatResponse>('POST', '/api/invoke-agent', data);

    if (result.success && result.sessionId) {
      this.sessionId = result.sessionId;
    }

    return result;
  }

  /**
   * Query the Knowledge Base.
   */
  async queryKB(
    query: string,
    options?: { maxResults?: number; generateResponse?: boolean }
  ): Promise<KBQueryResponse> {
    const data = {
      query,
      maxResults: options?.maxResults || 5,
      generateResponse: options?.generateResponse !== false,
    };

    return this.request<KBQueryResponse>('POST', '/api/query-kb', data);
  }

  // =========================================================================
  // SESSION API
  // =========================================================================

  /**
   * Get current session ID.
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Set session ID manually.
   */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId;
  }

  /**
   * Start a new session.
   */
  newSession(): void {
    this.sessionId = null;
  }

  /**
   * Get session details and history.
   */
  async getSession(sessionId?: string): Promise<{
    success: boolean;
    session?: SessionInfo;
    history?: ChatMessage[];
    error?: string;
  }> {
    const sid = sessionId || this.sessionId;
    if (!sid) {
      return { success: false, error: 'No session ID' };
    }
    return this.request('GET', `/api/sessions/${sid}`);
  }

  /**
   * Get chat history for a session.
   */
  async getHistory(
    sessionId?: string,
    limit: number = 20
  ): Promise<{
    success: boolean;
    sessionId?: string;
    history?: ChatMessage[];
    error?: string;
  }> {
    const sid = sessionId || this.sessionId;
    if (!sid) {
      return { success: false, error: 'No session ID' };
    }
    return this.request('GET', `/api/sessions/${sid}/history`, undefined, {
      limit: limit.toString(),
    });
  }

  /**
   * Delete/clear a session.
   */
  async deleteSession(sessionId?: string): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    const sid = sessionId || this.sessionId;
    if (!sid) {
      return { success: false, error: 'No session ID' };
    }

    const result = await this.request<{ success: boolean; message?: string }>(
      'DELETE',
      `/api/sessions/${sid}`
    );

    if (result.success && sid === this.sessionId) {
      this.sessionId = null;
    }

    return result;
  }

  /**
   * List sessions for the current tenant/user.
   */
  async listSessions(limit: number = 10): Promise<{
    success: boolean;
    sessions?: SessionInfo[];
    error?: string;
  }> {
    return this.request('GET', '/api/sessions', undefined, {
      tenantId: this.config.tenantId,
      userId: this.config.userId,
      limit: limit.toString(),
    });
  }

  // =========================================================================
  // UTILITY API
  // =========================================================================

  /**
   * Check API health.
   */
  async health(): Promise<{
    success: boolean;
    status?: string;
    service?: string;
    region?: string;
    agent_id?: string;
    kb_id?: string;
  }> {
    return this.request('GET', '/api/health');
  }

  /**
   * Upload a file to S3.
   */
  async uploadFile(
    file: File | Blob,
    filename: string
  ): Promise<{
    success: boolean;
    s3_key?: string;
    presigned_url?: string;
    error?: string;
  }> {
    const content = await this.fileToBase64(file);
    const contentType = file instanceof File ? file.type : 'application/octet-stream';

    return this.request('POST', '/api/upload', {
      filename,
      content,
      contentType,
      tenantId: this.config.tenantId,
    });
  }

  private async fileToBase64(file: File | Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]); // Remove data URL prefix
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
}

// =============================================================================
// REACT HOOK (Optional)
// =============================================================================

/**
 * React hook for Agent Core client.
 * 
 * Usage:
 *   const { client, chat, loading, error } = useAgentCore({
 *     apiEndpoint: 'https://xxx.execute-api.ap-south-1.amazonaws.com',
 *     tenantId: '1347766229904230'
 *   });
 */
export function createAgentCoreHook(config: AgentCoreConfig) {
  const client = new AgentCoreClient(config);
  
  return {
    client,
    chat: client.chat.bind(client),
    invokeAgent: client.invokeAgent.bind(client),
    queryKB: client.queryKB.bind(client),
    getSession: client.getSession.bind(client),
    getHistory: client.getHistory.bind(client),
    health: client.health.bind(client),
  };
}

export default AgentCoreClient;
