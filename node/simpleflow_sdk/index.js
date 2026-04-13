"use strict";

const DEFAULT_TIMEOUT_MS = 10000;
const ALLOWED_CHAT_MESSAGE_KEYS = new Set([
  "agent_id",
  "user_id",
  "chat_id",
  "message_id",
  "role",
  "content",
  "telemetry_data",
]);

/**
 * @typedef {Object} ChatSession
 * @property {string} chat_id
 * @property {string=} status
 * @property {string=} agent_id
 * @property {string=} user_id
 * @property {Object<string, any>=} metadata
 */

/**
 * @typedef {Object} ChatSessionsPage
 * @property {ChatSession[]=} sessions
 * @property {number=} page
 * @property {number=} limit
 * @property {boolean=} has_more
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

function rolesIncludeAny(userRoles, required) {
  const have = new Set(
    (userRoles || []).map((r) => String(r || "").trim()).filter((r) => r !== "")
  );
  for (const r of required || []) {
    if (have.has(String(r || "").trim())) return true;
  }
  return false;
}

/**
 * Aligns with control-plane requireChatReadScope / requireChatUserScope.
 * @param {{ roles: string[], principalUserId: string, targetUserId?: string | null }} opts
 */
function canReadChatUserScope({ roles, principalUserId, targetUserId }) {
  const roleSet = new Set(
    (roles || []).map((r) => String(r || "").trim()).filter((r) => r !== "")
  );
  const privileged = roleSet.has("admin") || roleSet.has("super_admin");
  const target = String(targetUserId == null ? "" : targetUserId).trim();
  if (target === "") return privileged;
  if (privileged) return true;
  return String(principalUserId || "").trim() === target;
}

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
    chatSessionsPath = "/v1/chat/sessions",
    mePath = "/v1/me",
  }) {
    if (!String(baseUrl || "").trim()) {
      throw new Error("simpleflow sdk config error: base_url is required");
    }
    this.baseUrl = String(baseUrl).replace(/\/+$/, "");
    this.apiToken = String(apiToken || "").trim();
    this.timeoutMs = Number(timeoutMs || DEFAULT_TIMEOUT_MS);
    this.chatSessionsPath = chatSessionsPath;
    const mp = String(mePath || "/v1/me").trim() || "/v1/me";
    this.mePath = mp.startsWith("/") ? mp : `/${mp}`;
  }

  async listChatSessions({ agentId, userId = undefined, status = undefined, page = 1, limit = 20, authToken } = {}) {
    return this.listChatSessionsTyped({ agentId, userId, status, page, limit, authToken });
  }

  async listChatSessionsTyped({ agentId, userId = undefined, status = undefined, page = 1, limit = 20, authToken } = {}) {
    const response = await this.listChatSessionsPage({ agentId, userId, status, page, limit, authToken });
    if (!Array.isArray(response.sessions)) return [];
    return response.sessions.filter((x) => x && typeof x === "object").map((session) => normalizeChatSession(session));
  }

  async listChatSessionsPage({ agentId, userId = undefined, status = undefined, page = 1, limit = 20, authToken } = {}) {
    const path = this._pathWithQuery(this.chatSessionsPath, {
      agent_id: agentId,
      user_id: userId,
      status,
      page,
      limit,
    });
    return this._get(path, { authToken });
  }

  async listChatMessages({ agentId, chatId, userId = undefined, limit = 20, authToken } = {}) {
    const path = this._pathWithQuery(this.chatSessionsPath, {
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
    const required = ["agent_id", "user_id", "chat_id", "message_id", "role"];
    const missing = required.filter((key) => String(sanitized[key] || "").trim() === "");
    if (missing.length > 0) {
      throw new Error(`simpleflow sdk payload error: missing required keys: ${missing.join(", ")}`);
    }
    if (sanitized.content == null) sanitized.content = {};
    if (sanitized.telemetry_data == null) sanitized.telemetry_data = {};
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return this._post(this.chatSessionsPath, sanitized, { extraHeaders: headers, authToken });
  }

  async updateChatSession({ chatId, agentId, userId, title, status, authToken } = {}) {
    const cid = String(chatId || "").trim();
    if (!cid) throw new Error("simpleflow sdk config error: chatId is required");
    const body = {
      agent_id: agentId,
      user_id: userId,
    };
    if (title !== undefined) body.title = title;
    if (status !== undefined) body.status = status;
    return this._request({
      method: "PATCH",
      path: `${this.chatSessionsPath}/${encodeURIComponent(cid)}`,
      body,
      authToken,
    });
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

  async fetchCurrentUser({ authToken }) {
    const token = String(authToken || "").trim();
    if (!token) throw new Error("simpleflow sdk config error: authToken is required");
    return this._get(this.mePath, { authToken: token });
  }

  async fetchAgent({ agentId, authToken }) {
    const token = String(authToken || "").trim();
    if (!token) throw new Error("simpleflow sdk config error: authToken is required");
    const aid = String(agentId || "").trim();
    if (!aid) throw new Error("simpleflow sdk config error: agentId is required");
    return this._get(`/api/v1/agents/${encodeURIComponent(aid)}`, { authToken: token });
  }

  async authorizeChatRead({ authToken, agentId, chatUserId }) {
    const me = await this.fetchCurrentUser({ authToken });
    const roles = Array.isArray(me.roles) ? me.roles.map((x) => String(x)).filter((x) => x.trim() !== "") : [];
    const uid = String(me.user_id || "").trim();
    if (
      !canReadChatUserScope({
        roles,
        principalUserId: uid,
        targetUserId: chatUserId == null ? "" : chatUserId,
      })
    ) {
      throw new SimpleFlowAuthorizationError({
        statusCode: 403,
        detail: "chat read scope denied for this principal and target user_id",
        path: "/v1/chat/sessions",
      });
    }
    const agent = await this.fetchAgent({ agentId, authToken });
    return { me, agent };
  }
}

module.exports = {
  SimpleFlowClient,
  SimpleFlowRequestError,
  SimpleFlowAuthenticationError,
  SimpleFlowAuthorizationError,
  rolesIncludeAny,
  canReadChatUserScope,
};
