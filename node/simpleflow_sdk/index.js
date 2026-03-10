"use strict";

const DEFAULT_TIMEOUT_MS = 10000;

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
class SimpleFlowLifecycleError extends SimpleFlowRequestError {}

function normalizePayload(payload) {
  if (payload == null) return {};
  if (typeof payload === "object" && !Array.isArray(payload)) return payload;
  throw new TypeError("simpleflow sdk payload error: payload must be an object or null");
}

function shouldSample(traceId, sampleRate) {
  if (sampleRate == null) return true;
  if (!Number.isFinite(sampleRate) || sampleRate < 0 || sampleRate > 1) {
    throw new Error("simpleflow sdk config error: telemetry sample_rate must be a finite value between 0.0 and 1.0");
  }
  if (sampleRate <= 0) return false;
  if (sampleRate >= 1) return true;
  let h = 2166136261;
  const text = String(traceId || "");
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const ratio = (h >>> 0) / 4294967295;
  return ratio <= sampleRate;
}

function countEventTypes(workflowResult) {
  const events = Array.isArray(workflowResult.events) ? workflowResult.events : [];
  const counts = {};
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    const eventType = String(event.event_type || "").trim();
    if (!eventType) continue;
    counts[eventType] = (counts[eventType] || 0) + 1;
  }
  return counts;
}

function extractNerdstats(workflowResult) {
  const direct = workflowResult?.metadata?.nerdstats;
  if (direct && typeof direct === "object" && !Array.isArray(direct)) return direct;
  const events = Array.isArray(workflowResult.events) ? workflowResult.events : [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    if (String(event.event_type || "").trim() !== "workflow_completed") continue;
    const stats = event?.metadata?.nerdstats;
    if (stats && typeof stats === "object" && !Array.isArray(stats)) return stats;
  }
  return null;
}

function usageSummary(nerdstats) {
  if (!nerdstats) {
    return {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      reasoning_tokens: 0,
      ttft_ms: 0,
      total_elapsed_ms: 0,
      tokens_per_second: 0,
    };
  }
  return {
    prompt_tokens: Number(nerdstats.total_input_tokens ?? nerdstats.prompt_tokens ?? 0),
    completion_tokens: Number(nerdstats.total_output_tokens ?? nerdstats.completion_tokens ?? 0),
    total_tokens: Number(nerdstats.total_tokens ?? 0),
    reasoning_tokens: Number(nerdstats.total_reasoning_tokens ?? nerdstats.reasoning_tokens ?? 0),
    ttft_ms: Number(nerdstats.ttft_ms ?? 0),
    total_elapsed_ms: Number(nerdstats.total_elapsed_ms ?? 0),
    tokens_per_second: Number(nerdstats.tokens_per_second ?? 0),
  };
}

function modelUsage(nerdstats) {
  if (!nerdstats || typeof nerdstats !== "object") return [];
  const totals = new Map();
  const steps = Array.isArray(nerdstats.step_details) ? nerdstats.step_details : [];
  for (const step of steps) {
    if (!step || typeof step !== "object") continue;
    const model = String(step.model_name || "").trim();
    if (!model) continue;
    if (!totals.has(model)) {
      totals.set(model, {
        request_count: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        reasoning_tokens: 0,
        elapsed_ms: 0,
      });
    }
    const bucket = totals.get(model);
    bucket.request_count += 1;
    bucket.prompt_tokens += Number(step.prompt_tokens || 0);
    bucket.completion_tokens += Number(step.completion_tokens || 0);
    bucket.total_tokens += Number(step.total_tokens || 0);
    bucket.reasoning_tokens += Number(step.reasoning_tokens || 0);
    bucket.elapsed_ms += Number(step.elapsed_ms || 0);
  }
  const nodeModels = nerdstats.llm_node_models;
  if (nodeModels && typeof nodeModels === "object") {
    for (const value of Object.values(nodeModels)) {
      const model = String(value || "").trim();
      if (!model) continue;
      if (!totals.has(model)) {
        totals.set(model, {
          request_count: 0,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
          reasoning_tokens: 0,
          elapsed_ms: 0,
        });
      }
    }
  }
  return Array.from(totals.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([model, bucket]) => ({ model, ...bucket }));
}

function toolUsage(eventCounts) {
  const started = Number(eventCounts.node_tool_start || 0);
  const completed = Number(eventCounts.node_tool_completed || 0);
  const errored = Number(eventCounts.node_tool_error || 0);
  if (started === 0 && completed === 0 && errored === 0) return [];
  return [
    {
      tool: "workflow_tools",
      started_count: started,
      completed_count: completed,
      error_count: errored,
    },
  ];
}

function buildCanonicalTelemetryEnvelope({
  workflowResult,
  agentId,
  organizationId,
  userId,
  runId,
  traceId,
  conversationId,
  requestId,
  sampled,
  includeRaw,
}) {
  const metadata = workflowResult.metadata && typeof workflowResult.metadata === "object" ? workflowResult.metadata : {};
  const traceMeta = metadata.trace && typeof metadata.trace === "object" ? metadata.trace : {};
  const eventCounts = countEventTypes(workflowResult);
  const nerdstats = extractNerdstats(workflowResult);
  const usage = usageSummary(nerdstats);
  const payload = {
    schema_version: "telemetry-envelope.v1",
    identity: {
      organization_id: String(organizationId || "").trim(),
      agent_id: String(agentId || "").trim(),
      user_id: String(userId || "").trim(),
    },
    trace: {
      trace_id: String(traceId || "").trim(),
      span_id: String(traceMeta.span_id || "").trim(),
      tenant_id: String(traceMeta.tenant_id || "").trim(),
      conversation_id: String(conversationId || "").trim(),
      request_id: String(requestId || "").trim(),
      run_id: String(runId || "").trim(),
      sampled: Boolean(sampled),
    },
    workflow: {
      workflow_id: String(workflowResult.workflow_id || "").trim(),
      terminal_node: String(workflowResult.terminal_node || "").trim(),
      status: String(workflowResult.status || "").trim() || "completed",
      total_elapsed_ms: Number(workflowResult.total_elapsed_ms || 0),
      ttft_ms: Number(usage.ttft_ms || 0),
    },
    usage,
    model_usage: modelUsage(nerdstats),
    tool_usage: toolUsage(eventCounts),
    event_counts: eventCounts,
  };
  if (nerdstats) payload.nerdstats = nerdstats;
  if (includeRaw) payload.raw = workflowResult;
  return payload;
}

class SimpleFlowClient {
  constructor({
    baseUrl,
    apiToken = "",
    oauthClientId = "",
    oauthClientSecret = "",
    oauthTokenPath = "/v1/oauth/token",
    oauthTokenLeewaySeconds = 30,
    runtimeRegisterPath = "/v1/runtime/registrations",
    runtimeInvokePath = "/v1/runtime/invoke",
    runtimeEventsPath = "/v1/runtime/events",
    runtimeActivatePath = "/v1/runtime/registrations/{registration_id}/activate",
    runtimeDeactivatePath = "/v1/runtime/registrations/{registration_id}/deactivate",
    runtimeValidatePath = "/v1/runtime/registrations/{registration_id}/validate",
    chatMessagesPath = "/v1/runtime/chat/messages",
    queueContractsPath = "/v1/runtime/queue/contracts",
    chatSessionsPath = "/v1/chat/history/sessions",
    chatHistoryPath = "/v1/chat/history/messages",
    timeoutMs = DEFAULT_TIMEOUT_MS,
  }) {
    if (!String(baseUrl || "").trim()) {
      throw new Error("simpleflow sdk config error: base_url is required");
    }
    this.baseUrl = String(baseUrl).replace(/\/+$/, "");
    this.apiToken = String(apiToken || "").trim();
    this.oauthClientId = String(oauthClientId || "").trim();
    this.oauthClientSecret = String(oauthClientSecret || "").trim();
    this.oauthTokenPath = oauthTokenPath;
    this.oauthTokenLeewaySeconds = Math.max(0, Number(oauthTokenLeewaySeconds || 0));
    this.oauthAccessToken = "";
    this.oauthAccessTokenExpiresAtUnix = 0;
    this.runtimeRegisterPath = runtimeRegisterPath;
    this.runtimeInvokePath = runtimeInvokePath;
    this.runtimeEventsPath = runtimeEventsPath;
    this.runtimeActivatePath = runtimeActivatePath;
    this.runtimeDeactivatePath = runtimeDeactivatePath;
    this.runtimeValidatePath = runtimeValidatePath;
    this.chatMessagesPath = chatMessagesPath;
    this.queueContractsPath = queueContractsPath;
    this.chatSessionsPath = chatSessionsPath;
    this.chatHistoryPath = chatHistoryPath;
    this.timeoutMs = Number(timeoutMs || DEFAULT_TIMEOUT_MS);
  }

  async createSession(email, password) {
    return this._post("/v1/auth/sessions", { email, password }, { authToken: "" });
  }

  async deleteCurrentSession({ authToken } = {}) {
    await this._delete("/v1/auth/sessions/current", { authToken });
  }

  async getMe({ authToken } = {}) {
    return this._get("/v1/me", { authToken });
  }

  async registerRuntime(registration, { authToken } = {}) {
    return this._post(this.runtimeRegisterPath, registration, { authToken });
  }

  async listRuntimeRegistrations({ agentId, agentVersion, authToken } = {}) {
    const path = this._pathWithQuery(this.runtimeRegisterPath, {
      agent_id: agentId,
      agent_version: agentVersion,
    });
    const response = await this._get(path, { authToken });
    return Array.isArray(response.registrations) ? response.registrations.filter((x) => x && typeof x === "object") : [];
  }

  async activateRuntimeRegistration(registrationId, { authToken } = {}) {
    const path = this._runtimeRegistrationActionPath(this.runtimeActivatePath, registrationId);
    await this._post(path, {}, { authToken });
  }

  async deactivateRuntimeRegistration(registrationId, { authToken } = {}) {
    const path = this._runtimeRegistrationActionPath(this.runtimeDeactivatePath, registrationId);
    await this._post(path, {}, { authToken });
  }

  async validateRuntimeRegistration(registrationId, { authToken } = {}) {
    const path = this._runtimeRegistrationActionPath(this.runtimeValidatePath, registrationId);
    return this._post(path, {}, { authToken });
  }

  async ensureRuntimeRegistrationActive({ registration, authToken } = {}) {
    const payload = normalizePayload(registration);
    const requestedAgentId = String(payload.agent_id || "").trim();
    const requestedAgentVersion = String(payload.agent_version || "").trim();
    if (!requestedAgentId || !requestedAgentVersion) {
      throw new Error("simpleflow sdk payload error: registration agent_id and agent_version are required");
    }
    const existing = await this.listRuntimeRegistrations({
      agentId: requestedAgentId,
      agentVersion: requestedAgentVersion,
      authToken,
    });
    for (const item of existing) {
      if (String(item.status || "").trim().toLowerCase() === "active") {
        return {
          status: "active",
          registration: item,
          registration_id: String(item.id || item.registration_id || "").trim(),
          created: false,
          validated: false,
          activated: false,
        };
      }
    }
    let target = existing[0] || null;
    let created = false;
    if (!target) {
      target = await this.registerRuntime(payload, { authToken });
      created = true;
    }
    const registrationId = String(target.id || target.registration_id || "").trim();
    if (!registrationId) {
      throw new SimpleFlowLifecycleError({ statusCode: 502, detail: "registration response did not include registration id", path: this.runtimeRegisterPath });
    }
    const validation = await this.validateRuntimeRegistration(registrationId, { authToken });
    await this.activateRuntimeRegistration(registrationId, { authToken });
    return {
      status: "active",
      registration: target,
      registration_id: registrationId,
      validation,
      created,
      validated: true,
      activated: true,
    };
  }

  async invoke(request, { authToken } = {}) {
    return this._post(this.runtimeInvokePath, request, { authToken });
  }

  async writeEvent(event) {
    const body = normalizePayload(event);
    const eventType = String(body.event_type || body.type || "").trim();
    const idempotencyKey = String(body.idempotency_key || "").trim();
    const allowedKeys = new Set([
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
    const sanitized = { event_type: eventType };
    for (const [key, value] of Object.entries(body)) {
      if (allowedKeys.has(key)) sanitized[key] = value;
    }
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    await this._post(this.runtimeEventsPath, sanitized, { extraHeaders: headers });
  }

  async reportRuntimeEvent(event) {
    await this.writeEvent(event);
  }

  async writeChatMessage(message) {
    const body = normalizePayload(message);
    const idempotencyKey = String(body.idempotency_key || "").trim();
    const allowedKeys = new Set([
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
    const sanitized = {};
    for (const [key, value] of Object.entries(body)) {
      if (allowedKeys.has(key)) sanitized[key] = value;
    }
    if (!sanitized.direction) sanitized.direction = "outbound";
    if (sanitized.content == null) sanitized.content = {};
    if (sanitized.metadata == null) sanitized.metadata = {};
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    await this._post(this.chatMessagesPath, sanitized, { extraHeaders: headers });
  }

  async publishQueueContract(contract) {
    const body = normalizePayload(contract);
    if (!String(body.contract_name || "").trim()) {
      body.contract_name = String(body.message_id || "").trim() || "runtime.queue.contract";
    }
    if (!String(body.contract_version || "").trim()) body.contract_version = "v1";
    if (!String(body.status || "").trim()) body.status = "draft";
    if (body.schema == null) body.schema = body.payload || {};
    if (body.transport == null) body.transport = {};
    const idempotencyKey = String(body.idempotency_key || "").trim();
    const headers = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    await this._post(this.queueContractsPath, body, { extraHeaders: headers });
  }

  async listChatHistoryMessages({ agentId, chatId, userId, limit = 50, authToken } = {}) {
    const path = this._pathWithQuery(this.chatHistoryPath, {
      agent_id: agentId,
      chat_id: chatId,
      user_id: userId,
      limit,
    });
    const response = await this._get(path, { authToken });
    return Array.isArray(response.messages) ? response.messages.filter((x) => x && typeof x === "object") : [];
  }

  async listChatSessions({ agentId, userId, status = "active", limit = 50, authToken } = {}) {
    const path = this._pathWithQuery(this.chatSessionsPath, {
      agent_id: agentId,
      user_id: userId,
      status,
      limit,
    });
    const response = await this._get(path, { authToken });
    return Array.isArray(response.sessions) ? response.sessions.filter((x) => x && typeof x === "object") : [];
  }

  async createChatHistoryMessage(message, { authToken } = {}) {
    return this._post(this.chatHistoryPath, message, { authToken });
  }

  async updateChatHistoryMessage({ messageId, agentId, chatId, userId, content, metadata, authToken } = {}) {
    const payload = { agent_id: agentId, chat_id: chatId, user_id: userId, content: normalizePayload(content), metadata: normalizePayload(metadata) };
    return this._patch(`${this.chatHistoryPath}/${messageId}`, payload, { authToken });
  }

  async writeEventFromWorkflowResult({
    agentId,
    workflowResult,
    eventType = "runtime.workflow.completed",
    organizationId = "",
    userId = "",
    includeRaw = false,
  }) {
    const normalizedResult = normalizePayload(workflowResult);
    const metadata = normalizedResult.metadata && typeof normalizedResult.metadata === "object" ? normalizedResult.metadata : {};
    const telemetry = metadata.telemetry && typeof metadata.telemetry === "object" ? metadata.telemetry : {};
    const trace = metadata.trace && typeof metadata.trace === "object" ? metadata.trace : {};
    const tenant = trace.tenant && typeof trace.tenant === "object" ? trace.tenant : {};

    const conversationId = String(tenant.conversation_id || trace.conversation_id || "").trim();
    const requestId = String(tenant.request_id || trace.request_id || "").trim();
    const runId = String(tenant.run_id || normalizedResult.run_id || "").trim();
    const resolvedOrganizationId = String(organizationId || tenant.organization_id || trace.organization_id || normalizedResult.organization_id || "").trim();
    const resolvedUserId = String(userId || tenant.user_id || trace.user_id || normalizedResult.user_id || "").trim();
    const traceId = String(telemetry.trace_id || "").trim();
    const sampled = typeof telemetry.sampled === "boolean" ? telemetry.sampled : true;

    const payload = buildCanonicalTelemetryEnvelope({
      workflowResult: normalizedResult,
      agentId,
      organizationId: resolvedOrganizationId,
      userId: resolvedUserId,
      runId,
      traceId,
      conversationId,
      requestId,
      sampled,
      includeRaw,
    });

    await this.writeEvent({
      event_type: eventType,
      agent_id: String(agentId || "").trim(),
      organization_id: resolvedOrganizationId,
      user_id: resolvedUserId,
      run_id: runId,
      conversation_id: conversationId,
      request_id: requestId,
      trace_id: traceId,
      sampled,
      payload,
    });
  }

  async writeChatMessageFromWorkflowResult({
    agentId,
    organizationId,
    runId,
    role,
    workflowResult,
    traceId = "",
    spanId = "",
    tenantId = "",
    traceUiBaseUrl = "http://localhost:16686",
    chatId,
    messageId,
    direction,
    idempotencyKey,
  }) {
    const normalizedResult = normalizePayload(workflowResult);
    const eventCounts = countEventTypes(normalizedResult);
    const nerdstats = extractNerdstats(normalizedResult);
    const content = {
      reply: normalizedResult.terminal_output,
      terminal_output: normalizedResult.terminal_output,
      workflow: {
        workflow_id: normalizedResult.workflow_id,
        terminal_node: normalizedResult.terminal_node,
      },
    };
    const normalizedTraceId = String(traceId || "").trim();
    const traceBase = String(traceUiBaseUrl || "").replace(/\/+$/, "") || "http://localhost:16686";
    const metadata = {
      source: "runtime.workflow.invoke",
      workflow_id: normalizedResult.workflow_id,
      terminal_node: normalizedResult.terminal_node,
      trace: Array.isArray(normalizedResult.trace) ? normalizedResult.trace : [],
      step_timings: Array.isArray(normalizedResult.step_timings) ? normalizedResult.step_timings : [],
      event_counts: eventCounts,
      nerdstats,
      llm_node_metrics: normalizedResult.llm_node_metrics || {},
      total_elapsed_ms: normalizedResult.total_elapsed_ms,
      trace_context: {
        trace_id: normalizedTraceId,
        span_id: String(spanId || "").trim(),
        tenant_id: String(tenantId || "").trim(),
        trace_url: normalizedTraceId ? `${traceBase}/trace/${normalizedTraceId}` : "",
      },
    };
    if (Array.isArray(normalizedResult.events)) metadata.events = normalizedResult.events;
    await this.writeChatMessage({
      agent_id: agentId,
      organization_id: organizationId,
      run_id: runId,
      role,
      chat_id: chatId,
      message_id: messageId,
      direction,
      content,
      metadata,
      idempotency_key: idempotencyKey,
    });
  }

  withTelemetry({ mode = "simpleflow", sampleRate = null, otlpSink = null, defaultTrace = {} } = {}) {
    return new TelemetryBridge({ client: this, mode, sampleRate, otlpSink, defaultTrace });
  }

  _runtimeRegistrationActionPath(pathTemplate, registrationId) {
    const trimmedId = String(registrationId || "").trim();
    if (!trimmedId) throw new Error("simpleflow sdk payload error: registration_id is required");
    if (pathTemplate.includes("{registration_id}")) {
      return pathTemplate.replaceAll("{registration_id}", trimmedId);
    }
    return pathTemplate.endsWith("/") ? `${pathTemplate}${trimmedId}` : `${pathTemplate}/${trimmedId}`;
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
      if (!token && this.oauthClientId && this.oauthClientSecret) {
        token = await this._ensureOauthAccessToken();
      }
    }
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async _ensureOauthAccessToken() {
    const now = Date.now() / 1000;
    if (this.oauthAccessToken && now + this.oauthTokenLeewaySeconds < this.oauthAccessTokenExpiresAtUnix) {
      return this.oauthAccessToken;
    }
    const response = await this._request({
      method: "POST",
      path: this.oauthTokenPath,
      body: {
        grant_type: "client_credentials",
        client_id: this.oauthClientId,
        client_secret: this.oauthClientSecret,
      },
      authToken: "",
    });
    const accessToken = String(response.access_token || "").trim();
    if (!accessToken) throw new Error("simpleflow sdk oauth error: token response missing access_token");
    const expiresIn = Number(response.expires_in || 60);
    this.oauthAccessToken = accessToken;
    this.oauthAccessTokenExpiresAtUnix = now + (Number.isFinite(expiresIn) && expiresIn > 0 ? expiresIn : 60);
    return this.oauthAccessToken;
  }

  async _post(path, payload, { extraHeaders, authToken } = {}) {
    return this._request({ method: "POST", path, body: payload, extraHeaders, authToken });
  }

  async _patch(path, payload, { authToken } = {}) {
    return this._request({ method: "PATCH", path, body: payload, authToken });
  }

  async _get(path, { authToken } = {}) {
    return this._request({ method: "GET", path, authToken });
  }

  async _delete(path, { authToken } = {}) {
    await this._request({ method: "DELETE", path, authToken });
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
    if (path.startsWith(this.runtimeRegisterPath.replace(/\/+$/, ""))) {
      throw new SimpleFlowLifecycleError({ statusCode, detail, path });
    }
    throw new SimpleFlowRequestError({ statusCode, detail, path });
  }
}

class TelemetryBridge {
  constructor({ client, mode, sampleRate, otlpSink, defaultTrace }) {
    const normalizedMode = String(mode || "").trim().toLowerCase();
    if (!["simpleflow", "otlp"].includes(normalizedMode)) {
      throw new Error("simpleflow sdk config error: telemetry mode must be one of simpleflow or otlp");
    }
    if (sampleRate != null && (!Number.isFinite(sampleRate) || sampleRate < 0 || sampleRate > 1)) {
      throw new Error("simpleflow sdk config error: telemetry sample_rate must be a finite value between 0.0 and 1.0");
    }
    this.client = client;
    this.mode = normalizedMode;
    this.sampleRate = sampleRate;
    this.otlpSink = otlpSink;
    this.defaultTrace = defaultTrace && typeof defaultTrace === "object" ? defaultTrace : {};
  }

  async emitSpan({ span, agentId = "", runId = "", traceId = "", requestId = "", conversationId = "" }) {
    const normalizedSpan = normalizePayload(span);
    if (String(traceId || "").trim() && !shouldSample(traceId, this.sampleRate)) return;
    if (this.mode === "otlp") {
      if (typeof this.otlpSink === "function") await this.otlpSink(normalizedSpan);
      return;
    }
    await this.client.writeEvent({
      type: "runtime.telemetry.span",
      agent_id: String(agentId || this.defaultTrace.agent_id || "").trim(),
      run_id: String(runId || this.defaultTrace.run_id || "").trim(),
      request_id: String(requestId || this.defaultTrace.request_id || "").trim(),
      conversation_id: String(conversationId || this.defaultTrace.conversation_id || "").trim(),
      trace_id: String(traceId || "").trim(),
      sampled: true,
      payload: { span: normalizedSpan },
    });
  }
}

module.exports = {
  SimpleFlowClient,
  TelemetryBridge,
  SimpleFlowRequestError,
  SimpleFlowAuthenticationError,
  SimpleFlowAuthorizationError,
  SimpleFlowLifecycleError,
};
