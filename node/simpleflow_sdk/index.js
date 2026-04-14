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
  "output_data",
]);

const VALID_CHAT_ROLES = new Set(["system", "user", "assistant", "tool"]);
const CONTENT_ALLOWED_KEYS = new Set(["text", "title", "message", "prompt", "parts", "messages"]);
const TELEMETRY_ALLOWED_KEYS = new Set([
  "source",
  "event_type",
  "client_timestamp",
  "latency_ms",
  "model",
  "tokens",
  "tags",
]);
const TELEMETRY_TOKEN_ALLOWED_KEYS = new Set(["prompt", "completion", "total"]);
const STRUCTURED_OUTPUT_ALLOWED_KEYS = new Set([
  "domain",
  "finance_subtype",
  "company_name",
  "label",
  "reason",
  "stakeholder_name",
  "subtype",
  "top_level_category",
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

function asNonNegativeInt(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    const rounded = Math.trunc(value);
    if (rounded >= 0 && rounded === value) return rounded;
  }
  return null;
}

function asNonNegativeFloat(value) {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
  return null;
}

function stringifyContent(value) {
  if (typeof value === "string" && value.trim()) return value.trim();
  try {
    return JSON.stringify(value);
  } catch (_error) {
    return String(value);
  }
}

function sanitizeContent(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  for (const key of CONTENT_ALLOWED_KEYS) {
    if (Object.prototype.hasOwnProperty.call(value, key)) out[key] = value[key];
  }
  return out;
}

function sanitizeTelemetryData(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  for (const key of TELEMETRY_ALLOWED_KEYS) {
    if (Object.prototype.hasOwnProperty.call(value, key)) out[key] = value[key];
  }

  const latency = asNonNegativeInt(out.latency_ms);
  if (latency == null) delete out.latency_ms;
  else out.latency_ms = latency;

  if (out.tokens && typeof out.tokens === "object" && !Array.isArray(out.tokens)) {
    const tokenOut = {};
    for (const key of TELEMETRY_TOKEN_ALLOWED_KEYS) {
      const parsed = asNonNegativeInt(out.tokens[key]);
      if (parsed != null) tokenOut[key] = parsed;
    }
    out.tokens = tokenOut;
  } else {
    delete out.tokens;
  }

  if (Array.isArray(out.tags)) {
    out.tags = out.tags.map((x) => String(x || "").trim()).filter((x) => x !== "");
  } else {
    delete out.tags;
  }

  return out;
}

function sanitizeStructuredOutput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const out = {};
  for (const key of STRUCTURED_OUTPUT_ALLOWED_KEYS) {
    const raw = value[key];
    if (typeof raw === "string" && raw.trim() !== "") out[key] = raw;
  }
  return Object.keys(out).length > 0 ? out : null;
}

function sanitizeMessageOutputData(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};

  for (const key of ["workflow_id", "trace_id", "entry_node", "terminal_node"]) {
    if (typeof value[key] === "string" && value[key].trim() !== "") out[key] = value[key];
  }

  if (Array.isArray(value.trace)) {
    out.trace = value.trace.map((x) => (typeof x === "string" ? x : "")).filter((x) => x.trim() !== "");
  }

  if (Array.isArray(value.step_timings)) {
    out.step_timings = value.step_timings
      .filter((x) => x && typeof x === "object" && !Array.isArray(x))
      .map((timing) => {
        const nodeId = String(timing.node_id || "").trim();
        if (!nodeId) return null;
        const item = { node_id: nodeId };
        if (typeof timing.node_kind === "string" && timing.node_kind.trim()) item.node_kind = timing.node_kind;
        if (typeof timing.model_name === "string" && timing.model_name.trim()) item.model_name = timing.model_name;
        for (const key of ["completion_tokens", "elapsed_ms", "prompt_tokens", "reasoning_tokens", "total_tokens"]) {
          const parsed = asNonNegativeInt(timing[key]);
          if (parsed != null) item[key] = parsed;
        }
        const tps = asNonNegativeFloat(timing.tokens_per_second);
        if (tps != null) item.tokens_per_second = tps;
        return item;
      })
      .filter((x) => x !== null);
  }

  if (value.llm_node_metrics && typeof value.llm_node_metrics === "object" && !Array.isArray(value.llm_node_metrics)) {
    const metrics = {};
    for (const [nodeId, metricRaw] of Object.entries(value.llm_node_metrics)) {
      const key = String(nodeId || "").trim();
      if (!key || !metricRaw || typeof metricRaw !== "object" || Array.isArray(metricRaw)) continue;
      const metric = {};
      for (const metricKey of ["completion_tokens", "elapsed_ms", "prompt_tokens", "reasoning_tokens", "total_tokens"]) {
        const parsed = asNonNegativeInt(metricRaw[metricKey]);
        if (parsed != null) metric[metricKey] = parsed;
      }
      const tps = asNonNegativeFloat(metricRaw.tokens_per_second);
      if (tps != null) metric.tokens_per_second = tps;
      metrics[key] = metric;
    }
    out.llm_node_metrics = metrics;
  }

  if (value.llm_node_models && typeof value.llm_node_models === "object" && !Array.isArray(value.llm_node_models)) {
    const models = {};
    for (const [nodeId, model] of Object.entries(value.llm_node_models)) {
      const key = String(nodeId || "").trim();
      if (key && typeof model === "string" && model.trim()) models[key] = model;
    }
    out.llm_node_models = models;
  }

  if (value.outputs && typeof value.outputs === "object" && !Array.isArray(value.outputs)) {
    const outputs = {};
    for (const [nodeId, outputRaw] of Object.entries(value.outputs)) {
      const key = String(nodeId || "").trim();
      if (!key) continue;
      const source = outputRaw && typeof outputRaw === "object" && !Array.isArray(outputRaw) && Object.prototype.hasOwnProperty.call(outputRaw, "output")
        ? outputRaw.output
        : outputRaw;
      if (typeof source === "string") {
        outputs[key] = { output: source };
        continue;
      }
      const structured = sanitizeStructuredOutput(source);
      if (structured) {
        outputs[key] = { output: structured };
        continue;
      }
      if (source != null) {
        outputs[key] = { output: stringifyContent(source) };
      }
    }
    out.outputs = outputs;
  }

  if (value.metadata && typeof value.metadata === "object" && !Array.isArray(value.metadata)) {
    const metadata = {};
    if (value.metadata.telemetry && typeof value.metadata.telemetry === "object" && !Array.isArray(value.metadata.telemetry)) {
      const telemetry = {};
      for (const key of ["enabled", "multi_tenant", "nerdstats", "sampled"]) {
        if (typeof value.metadata.telemetry[key] === "boolean") telemetry[key] = value.metadata.telemetry[key];
      }
      for (const key of ["payload_mode", "tool_trace_mode", "trace_id", "trace_id_source"]) {
        if (typeof value.metadata.telemetry[key] === "string" && value.metadata.telemetry[key].trim()) telemetry[key] = value.metadata.telemetry[key];
      }
      const retentionDays = asNonNegativeInt(value.metadata.telemetry.retention_days);
      if (retentionDays != null) telemetry.retention_days = retentionDays;
      const sampleRate = asNonNegativeFloat(value.metadata.telemetry.sample_rate);
      if (sampleRate != null) telemetry.sample_rate = sampleRate;
      metadata.telemetry = telemetry;
    }
    if (value.metadata.trace && typeof value.metadata.trace === "object" && !Array.isArray(value.metadata.trace)) {
      const trace = {};
      if (value.metadata.trace.tenant && typeof value.metadata.trace.tenant === "object" && !Array.isArray(value.metadata.trace.tenant)) {
        const tenant = {};
        for (const key of ["conversation_id", "request_id", "run_id", "user_id", "workspace_id"]) {
          const raw = value.metadata.trace.tenant[key];
          if (raw === null || typeof raw === "string") tenant[key] = raw;
        }
        trace.tenant = tenant;
      }
      metadata.trace = trace;
    }
    out.metadata = metadata;
  }

  const terminalOutput = sanitizeStructuredOutput(value.terminal_output);
  if (terminalOutput) out.terminal_output = terminalOutput;

  for (const key of ["total_elapsed_ms", "total_input_tokens", "total_output_tokens", "total_reasoning_tokens", "total_tokens", "ttft_ms"]) {
    const parsed = asNonNegativeInt(value[key]);
    if (parsed != null) out[key] = parsed;
  }
  const tps = asNonNegativeFloat(value.tokens_per_second);
  if (tps != null) out.tokens_per_second = tps;

  return out;
}

function buildTelemetryDataFromWorkflowResult(workflowResult, telemetryData) {
  const merged = { source: "simple-agents", event_type: "assistant.reply" };
  const latency = asNonNegativeInt(workflowResult.total_elapsed_ms);
  if (latency != null) merged.latency_ms = latency;

  if (workflowResult.llm_node_models && typeof workflowResult.llm_node_models === "object") {
    for (const value of Object.values(workflowResult.llm_node_models)) {
      if (typeof value === "string" && value.trim()) {
        merged.model = value;
        break;
      }
    }
  }

  const tokens = {};
  const prompt = asNonNegativeInt(workflowResult.total_input_tokens);
  const completion = asNonNegativeInt(workflowResult.total_output_tokens);
  const total = asNonNegativeInt(workflowResult.total_tokens);
  if (prompt != null) tokens.prompt = prompt;
  if (completion != null) tokens.completion = completion;
  if (total != null) tokens.total = total;
  if (Object.keys(tokens).length > 0) merged.tokens = tokens;

  if (telemetryData && typeof telemetryData === "object" && !Array.isArray(telemetryData)) {
    Object.assign(merged, sanitizeTelemetryData(telemetryData));
  }
  return sanitizeTelemetryData(merged);
}

function splitSetCookieHeader(value) {
  if (!value) return [];
  return String(value)
    .split(/, (?=[^;]+?=)/g)
    .map((x) => x.trim())
    .filter((x) => x !== "");
}

function parseCookiePair(setCookieValue) {
  const first = String(setCookieValue || "").split(";", 1)[0] || "";
  const index = first.indexOf("=");
  if (index <= 0) return null;
  const name = first.slice(0, index).trim();
  const value = first.slice(index + 1).trim();
  if (!name) return null;
  return { name, value };
}

class SimpleFlowClient {
  constructor({
    baseUrl,
    apiToken = "",
    timeoutMs = DEFAULT_TIMEOUT_MS,
    chatSessionsPath = "/v1/chat/sessions",
    mePath = "/v1/me",
    authSessionsPath = "/v1/auth/sessions",
    authRefreshPath = "/v1/auth/sessions/refresh",
    csrfHeaderName = "X-CSRF-Token",
    csrfCookieName = "sf_csrf_token",
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
    const asp = String(authSessionsPath || "/v1/auth/sessions").trim() || "/v1/auth/sessions";
    const arp = String(authRefreshPath || "/v1/auth/sessions/refresh").trim() || "/v1/auth/sessions/refresh";
    this.authSessionsPath = asp.startsWith("/") ? asp : `/${asp}`;
    this.authRefreshPath = arp.startsWith("/") ? arp : `/${arp}`;
    this.csrfHeaderName = String(csrfHeaderName || "X-CSRF-Token").trim() || "X-CSRF-Token";
    this.csrfCookieName = String(csrfCookieName || "sf_csrf_token").trim() || "sf_csrf_token";
    this._cookieJar = {};
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
    const unknownKeys = Object.keys(body).filter(
      (key) => key !== "idempotency_key" && !ALLOWED_CHAT_MESSAGE_KEYS.has(key)
    );
    if (unknownKeys.length > 0) {
      throw new Error(
        `simpleflow sdk payload error: unknown keys in chat message payload: ${unknownKeys.join(", ")}`
      );
    }
    const sanitized = { ...body };
    const required = ["agent_id", "user_id", "chat_id", "message_id", "role"];
    const missing = required.filter((key) => String(sanitized[key] || "").trim() === "");
    if (missing.length > 0) {
      throw new Error(`simpleflow sdk payload error: missing required keys: ${missing.join(", ")}`);
    }

    const role = String(sanitized.role || "").trim().toLowerCase();
    if (!VALID_CHAT_ROLES.has(role)) {
      throw new Error("simpleflow sdk payload error: role must be one of: system, user, assistant, tool");
    }
    sanitized.role = role;

    if (sanitized.output_data != null && role !== "assistant") {
      throw new Error("simpleflow sdk payload error: output_data is only allowed when role is assistant");
    }

    sanitized.content = sanitizeContent(sanitized.content);
    sanitized.telemetry_data = sanitizeTelemetryData(sanitized.telemetry_data);
    if (sanitized.output_data != null) sanitized.output_data = sanitizeMessageOutputData(sanitized.output_data);

    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return this._post(this.chatSessionsPath, sanitized, { extraHeaders: headers, authToken });
  }

  buildChatMessageFromSimpleAgentsResult({
    agentId,
    userId,
    chatId,
    messageId,
    workflowResult,
    telemetryData,
  } = {}) {
    const payload = normalizePayload(workflowResult);
    return {
      agent_id: String(agentId || "").trim(),
      user_id: String(userId || "").trim(),
      chat_id: String(chatId || "").trim(),
      message_id: String(messageId || "").trim(),
      role: "assistant",
      content: { text: stringifyContent(payload.terminal_output) },
      telemetry_data: buildTelemetryDataFromWorkflowResult(payload, telemetryData),
      output_data: sanitizeMessageOutputData(payload),
    };
  }

  async writeChatMessageFromSimpleAgentsResult({
    agentId,
    userId,
    chatId,
    messageId,
    workflowResult,
    telemetryData,
    authToken,
  } = {}) {
    const message = this.buildChatMessageFromSimpleAgentsResult({
      agentId,
      userId,
      chatId,
      messageId,
      workflowResult,
      telemetryData,
    });
    return this.writeChatMessage(message, { authToken });
  }

  async getChatMessageOutput({ messageId, agentId, chatId, userId, authToken } = {}) {
    const mid = String(messageId || "").trim();
    if (!mid) throw new Error("simpleflow sdk config error: messageId is required");
    const path = this._pathWithQuery(`/v1/chat/messages/${encodeURIComponent(mid)}/output`, {
      agent_id: agentId,
      chat_id: chatId,
      user_id: userId,
    });
    return this._get(path, { authToken });
  }

  async upsertChatMessageOutput({ messageId, agentId, chatId, userId, outputData, authToken } = {}) {
    const mid = String(messageId || "").trim();
    if (!mid) throw new Error("simpleflow sdk config error: messageId is required");
    const uid = String(userId || "").trim();
    if (!uid) throw new Error("simpleflow sdk payload error: userId is required");
    const payload = {
      agent_id: String(agentId || "").trim(),
      chat_id: String(chatId || "").trim(),
      user_id: uid,
      output_data: sanitizeMessageOutputData(outputData),
    };
    return this._post(`/v1/chat/messages/${encodeURIComponent(mid)}/output`, payload, { authToken });
  }

  async createAuthSession({ email, password, setAsDefaultToken = true } = {}) {
    const emailValue = String(email || "").trim();
    const passwordValue = String(password || "");
    if (!emailValue || !passwordValue) {
      throw new Error("simpleflow sdk payload error: email and password are required");
    }
    const response = await this._request({
      method: "POST",
      path: this.authSessionsPath,
      body: { email: emailValue, password: passwordValue },
      useAuth: false,
    });
    const token = String(response.access_token || "").trim();
    if (setAsDefaultToken && token) this.apiToken = token;
    return response;
  }

  async refreshAuthSession({ csrfToken, setAsDefaultToken = true } = {}) {
    const token = String(csrfToken || "").trim() || this._cookieJar[this.csrfCookieName] || this._cookieJar.csrf_cookie || "";
    if (!token) {
      throw new Error(
        "simpleflow sdk auth error: csrf token is required; call createAuthSession first or pass csrfToken"
      );
    }
    const response = await this._request({
      method: "POST",
      path: this.authRefreshPath,
      extraHeaders: { [this.csrfHeaderName]: token },
      useAuth: false,
    });
    const accessToken = String(response.access_token || "").trim();
    if (setAsDefaultToken && accessToken) this.apiToken = accessToken;
    return response;
  }

  async validateAccessToken({ authToken } = {}) {
    const token = String(authToken || "").trim() || this.apiToken;
    if (!token) throw new Error("simpleflow sdk config error: authToken is required");
    return this.fetchCurrentUser({ authToken: token });
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

  async _request({ method, path, body, extraHeaders = {}, authToken, useAuth = true }) {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${this.baseUrl}${normalizedPath}`;
    const authHeaders = useAuth ? await this._authorizationHeaders(authToken) : {};
    const headers = { ...authHeaders, ...extraHeaders };
    const cookieHeader = this._cookieHeader();
    if (cookieHeader && !headers.Cookie && !headers.cookie) headers.Cookie = cookieHeader;
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
    this._storeResponseCookies(response);
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

  _cookieHeader() {
    const pairs = [];
    for (const [key, value] of Object.entries(this._cookieJar || {})) {
      const name = String(key || "").trim();
      const cookieValue = String(value || "").trim();
      if (!name || !cookieValue) continue;
      pairs.push(`${name}=${cookieValue}`);
    }
    return pairs.join("; ");
  }

  _storeResponseCookies(response) {
    if (!response || !response.headers) return;
    const setCookieValues = this._extractSetCookieHeaders(response.headers);
    for (const entry of setCookieValues) {
      const parsed = parseCookiePair(entry);
      if (!parsed) continue;
      if (!parsed.value) {
        delete this._cookieJar[parsed.name];
        continue;
      }
      this._cookieJar[parsed.name] = parsed.value;
    }
  }

  _extractSetCookieHeaders(headers) {
    if (typeof headers.getSetCookie === "function") {
      const values = headers.getSetCookie();
      if (Array.isArray(values)) return values;
    }
    const joined = headers.get("set-cookie");
    return splitSetCookieHeader(joined);
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
    if (roles.length === 0 && typeof me.role === "string" && me.role.trim() !== "") {
      roles.push(me.role.trim());
    }
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
