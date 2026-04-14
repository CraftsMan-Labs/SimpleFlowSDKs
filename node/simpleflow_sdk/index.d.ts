export interface ChatSession {
  chat_id?: string;
  status?: string;
  agent_id?: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatSessionsPage {
  sessions?: ChatSession[];
  page?: number;
  limit?: number;
  has_more?: boolean;
}

export interface ChatMessageWrite {
  agent_id: string;
  user_id: string;
  chat_id: string;
  message_id: string;
  role: "system" | "user" | "assistant" | "tool";
  content?: Record<string, unknown>;
  telemetry_data?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  idempotency_key?: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user?: Record<string, unknown>;
}

export interface Principal {
  user_id: string;
  organization_id: string;
  role?: string;
  roles?: string[];
  provider?: string;
}

export interface MessageOutputResponse {
  output?: Record<string, unknown>;
}

export interface SimpleFlowClientOptions {
  baseUrl: string;
  apiToken?: string;
  timeoutMs?: number;
  chatSessionsPath?: string;
  mePath?: string;
  authSessionsPath?: string;
  authRefreshPath?: string;
  csrfHeaderName?: string;
  csrfCookieName?: string;
}

export interface AuthTokenOption {
  authToken?: string;
}

export class SimpleFlowRequestError extends Error {
  statusCode: number;
  detail: string;
  path: string;
}

export class SimpleFlowAuthenticationError extends SimpleFlowRequestError {}

export class SimpleFlowAuthorizationError extends SimpleFlowRequestError {}

export class SimpleFlowClient {
  constructor(options: SimpleFlowClientOptions);

  listChatSessions(input: {
    agentId: string;
    userId?: string;
    status?: string;
    page?: number;
    limit?: number;
    authToken?: string;
  }): Promise<ChatSession[]>;

  listChatSessionsTyped(input: {
    agentId: string;
    userId?: string;
    status?: string;
    page?: number;
    limit?: number;
    authToken?: string;
  }): Promise<ChatSession[]>;

  listChatSessionsPage(input: {
    agentId: string;
    userId?: string;
    status?: string;
    page?: number;
    limit?: number;
    authToken?: string;
  }): Promise<ChatSessionsPage>;

  listChatMessages(input: {
    agentId: string;
    chatId: string;
    userId?: string;
    limit?: number;
    authToken?: string;
  }): Promise<Record<string, unknown>[]>;

  writeChatMessage(message: ChatMessageWrite, opts?: AuthTokenOption): Promise<Record<string, unknown>>;

  buildChatMessageFromSimpleAgentsResult(input: {
    agentId: string;
    userId: string;
    chatId: string;
    messageId: string;
    workflowResult: Record<string, unknown>;
    telemetryData?: Record<string, unknown>;
  }): ChatMessageWrite;

  writeChatMessageFromSimpleAgentsResult(input: {
    agentId: string;
    userId: string;
    chatId: string;
    messageId: string;
    workflowResult: Record<string, unknown>;
    telemetryData?: Record<string, unknown>;
    authToken?: string;
  }): Promise<Record<string, unknown>>;

  getChatMessageOutput(input: {
    messageId: string;
    agentId: string;
    chatId: string;
    userId?: string;
    authToken?: string;
  }): Promise<MessageOutputResponse>;

  upsertChatMessageOutput(input: {
    messageId: string;
    agentId: string;
    chatId: string;
    userId: string;
    outputData: Record<string, unknown>;
    authToken?: string;
  }): Promise<Record<string, unknown>>;

  updateChatSession(input: {
    chatId: string;
    agentId: string;
    userId: string;
    title?: string;
    status?: string;
    authToken?: string;
  }): Promise<Record<string, unknown>>;

  createAuthSession(input: {
    email: string;
    password: string;
    setAsDefaultToken?: boolean;
  }): Promise<AuthTokenResponse>;

  refreshAuthSession(input?: {
    csrfToken?: string;
    setAsDefaultToken?: boolean;
  }): Promise<AuthTokenResponse>;

  validateAccessToken(input?: {
    authToken?: string;
  }): Promise<Principal>;

  fetchCurrentUser(input: {
    authToken: string;
  }): Promise<Principal>;

  fetchAgent(input: {
    agentId: string;
    authToken: string;
  }): Promise<Record<string, unknown>>;

  authorizeChatRead(input: {
    authToken: string;
    agentId: string;
    chatUserId?: string;
  }): Promise<{ me: Principal; agent: Record<string, unknown> }>;
}

export function rolesIncludeAny(userRoles: string[], required: string[]): boolean;

export function canReadChatUserScope(input: {
  roles: string[];
  principalUserId: string;
  targetUserId?: string | null;
}): boolean;
