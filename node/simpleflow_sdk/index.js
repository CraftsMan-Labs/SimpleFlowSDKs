"use strict";

const DEFAULT_TIMEOUT_MS = 10000;
const ALLOWED_EVENT_KEYS = new Set([
  "agent_id",
  "organization_id",
  "user_id",
  "run_id",
  "event_type",
  "trace_id",
  "conversation_id",
  "request_id",
  "sampled",
  "payload",
]);
const ALLOWED_CHAT_MESSAGE_KEYS = new Set([
  "agent_id",
  "organization_id",
  "run_id",
  "chat_id",
  "message_id",
  "role",
  "direction",
  "content",
  "metadata",
]);

/**
 * @typedef {Object} ChatSession
 * @property {string} chat_id
 * @property {string=} status
 * @property {string=} agent_id
 * @property {string=} user_id
 * @property {Object<string, any>=} metadata
 */

class SimpleFlowRequestError extends Error {
  constructor({ statusCode, detail, path }) {
    super(`simpleflow sdk request error: status=${statusCode} path=${path} detail=${detail}`);
    this.statusCode = statusCode;
    this.detail = detail;
    this.path = path;
  }
}

class SimpleFlowAuthenticationError extends SimpleFlowRequestError {}
class SimpleFlowAuthorizationError extends SimpleFlowRequestError {}

function normalizePayload(payload) {
  if (payload == null) return {};
  if (typeof payload === "object" && !Array.isArray(payload)) return payload;
  throw new TypeError("simpleflow sdk payload error: payload must be an object or null");
}

function normalizeChatSession(value) {
  const source = value && typeof value === "object" ? value : {};
  const session = {};
  if (typeof source.chat_id === "string") session.chat_id = source.chat_id;
  if (typeof source.status === "string") session.status = source.status;
  if (typeof source.agent_id === "string") session.agent_id = source.agent_id;
  if (typeof source.user_id === "string") session.user_id = source.user_id;
  if (source.metadata && typeof source.metadata === "object" && !Array.isArray(source.metadata)) {
    session.metadata = source.metadata;
  }
  return session;
}

class SimpleFlowClient {
  constructor({
    baseUrl,
    apiToken = "",
    timeoutMs = DEFAULT_TIMEOUT_MS,
    runtimeEventsPath = "/v1/runtime/events",
    runtimeChatMessagesPath = "/v1/runtime/chat/messages",
    runtimeChatSessionsPath = "/v1/runtime/chat/sessions",
    runtimeChatMessagesListPath = "/v1/runtime/chat/messages/list",
  }) {
    if (!String(baseUrl || "").trim()) {
      throw new Error("simpleflow sdk config error: base_url is required");
    }
    this.baseUrl = String(baseUrl).replace(/\/+$/, "");
    this.apiToken = String(apiToken || "").trim();
    this.timeoutMs = Number(timeoutMs || DEFAULT_TIMEOUT_MS);
    this.runtimeEventsPath = runtimeEventsPath;
    this.runtimeChatMessagesPath = runtimeChatMessagesPath;
    this.runtimeChatSessionsPath = runtimeChatSessionsPath;
    this.runtimeChatMessagesListPath = runtimeChatMessagesListPath;
  }

  async listChatSessions({ agentId, userId, status = "active", limit = 50, authToken } = {}) {
    return this.listChatSessionsTyped({ agentId, userId, status, limit, authToken });
  }

  async listChatSessionsTyped({ agentId, userId, status = "active", limit = 50, authToken } = {}) {
    const path = this._pathWithQuery(this.runtimeChatSessionsPath, {
      agent_id: agentId,
      user_id: userId,
      status,
      limit,
    });
    const response = await this._get(path, { authToken });
    if (!Array.isArray(response.sessions)) return [];
    return response.sessions.filter((x) => x && typeof x === "object").map((session) => normalizeChatSession(session));
  }

  async listChatMessages({ agentId, chatId, userId, limit = 50, authToken } = {}) {
    const path = this._pathWithQuery(this.runtimeChatMessagesListPath, {
      agent_id: agentId,
      chat_id: chatId,
      user_id: userId,
      limit,
    });
    const response = await this._get(path, { authToken });
    return Array.isArray(response.messages) ? response.messages.filter((x) => x && typeof x === "object") : [];
  }

  async writeChatMessage(message, { authToken } = {}) {
    const body = normalizePayload(message);
    const idempotencyKey = String(body.idempotency_key || "").trim();
    const sanitized = {};
    for (const [key, value] of Object.entries(body)) {
      if (ALLOWED_CHAT_MESSAGE_KEYS.has(key)) sanitized[key] = value;
    }
    if (!sanitized.direction) sanitized.direction = "outbound";
    if (sanitized.content == null) sanitized.content = {};
    if (sanitized.metadata == null) sanitized.metadata = {};
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    await this._post(this.runtimeChatMessagesPath, sanitized, { extraHeaders: headers, authToken });
  }

  async writeEvent(event, { authToken } = {}) {
    const body = normalizePayload(event);
    const eventType = String(body.event_type || body.type || "").trim();
    const idempotencyKey = String(body.idempotency_key || "").trim();
    const sanitized = { event_type: eventType };
    for (const [key, value] of Object.entries(body)) {
      if (ALLOWED_EVENT_KEYS.has(key)) sanitized[key] = value;
    }
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    await this._post(this.runtimeEventsPath, sanitized, { extraHeaders: headers, authToken });
  }

  /**
   * Write telemetry metrics for a chat message.
   * @param {string} agentId - Agent identifier
   * @param {string} sessionId - Chat session ID
   * @param {Object} metrics - Telemetry metrics
   * @param {number} metrics.total_tokens - Total tokens used
   * @param {number} metrics.ttfs - Time to first token (ms)
   * @param {number} [metrics.prompt_tokens] - Input tokens (optional)
   * @param {number} [metrics.completion_tokens] - Output tokens (optional)
   * @param {string} [metrics.user_id] - User identifier (optional)
   * @param {string} [metrics.run_id] - Run identifier (optional)
   * @param {string} authToken - User's JWT bearer token
   */
  async writeMessageTelemetry(agentId, sessionId, metrics, authToken) {
    await this.writeEvent(
      {
        event_type: "chat.message.telemetry",
        agent_id: agentId,
        conversation_id: sessionId,
        user_id: metrics.user_id || "",
        run_id: metrics.run_id || "",
        payload: {
          total_tokens: metrics.total_tokens,
          ttfs: metrics.ttfs,
          prompt_tokens: metrics.prompt_tokens || null,
          completion_tokens: metrics.completion_tokens || null,
          timestamp_ms: Date.now(),
        },
      },
      { authToken }
    );
  }

  _pathWithQuery(path, query) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(query || {})) {
      if (value == null) continue;
      const text = String(value).trim();
      if (!text) continue;
      search.set(key, text);
    }
    const encoded = search.toString();
    return encoded ? `${path}?${encoded}` : path;
  }

  async _authorizationHeaders(authToken) {
    let token = "";
    if (typeof authToken === "string") {
      token = authToken.trim();
    } else {
      token = this.apiToken;
    }
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async _post(path, payload, { extraHeaders = {}, authToken } = {}) {
    return this._request({ method: "POST", path, body: payload, extraHeaders, authToken });
  }

  async _get(path, { authToken } = {}) {
    return this._request({ method: "GET", path, authToken });
  }

  async _request({ method, path, body, extraHeaders = {}, authToken }) {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${this.baseUrl}${normalizedPath}`;
    const headers = { ...(await this._authorizationHeaders(authToken)), ...extraHeaders };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(normalizePayload(body)),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }
    const text = await response.text();
    if (response.status < 200 || response.status >= 300) {
      this._raiseRequestError({ path: normalizedPath, statusCode: response.status, body: text });
    }
    if (!text.trim()) return {};
    try {
      const decoded = JSON.parse(text);
      if (decoded && typeof decoded === "object" && !Array.isArray(decoded)) return decoded;
      throw new Error("simpleflow sdk request error: expected JSON object response body");
    } catch (error) {
      if (error instanceof SimpleFlowRequestError) throw error;
      throw new Error("simpleflow sdk request error: expected JSON response body");
    }
  }

  _raiseRequestError({ path, statusCode, body }) {
    const detail = String(body || "").trim() || "request failed";
    if (statusCode === 401) throw new SimpleFlowAuthenticationError({ statusCode, detail, path });
    if (statusCode === 403) throw new SimpleFlowAuthorizationError({ statusCode, detail, path });
    throw new SimpleFlowRequestError({ statusCode, detail, path });
  }
}

module.exports = {
  SimpleFlowClient,
  SimpleFlowRequestError,
  SimpleFlowAuthenticationError,
  SimpleFlowAuthorizationError,
};
