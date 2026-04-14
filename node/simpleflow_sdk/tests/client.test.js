"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");

const {
  SimpleFlowClient,
  SimpleFlowAuthorizationError,
  canReadChatUserScope,
  rolesIncludeAny,
} = require("../index.js");

function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${address.port}`,
      });
    });
  });
}

test("writeChatMessage posts to /v1/chat/sessions with telemetry_data", async () => {
  let captured = null;
  const { server, baseUrl } = await startServer((req, res) => {
    assert.equal(req.url, "/v1/chat/sessions");
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      captured = JSON.parse(body);
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ message_id: "m1" }));
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeChatMessage({
      agent_id: "agent_1",
      user_id: "user_1",
      chat_id: "chat_1",
      message_id: "m1",
      role: "user",
      content: { text: "hello" },
      telemetry_data: { source: "web" },
    });
    assert.equal(captured.agent_id, "agent_1");
    assert.deepEqual(captured.telemetry_data, { source: "web" });
    assert.equal(captured.metadata, undefined);
  } finally {
    server.close();
  }
});

test("writeChatMessage rejects unknown top-level keys", async () => {
  const { server, baseUrl } = await startServer((_req, res) => {
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ ok: true }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await assert.rejects(
      async () => {
        await client.writeChatMessage({
          agent_id: "agent_1",
          user_id: "user_1",
          chat_id: "chat_1",
          message_id: "m1",
          role: "assistant",
          content: { text: "hello" },
          telemetry_data: { source: "web" },
          unexpected: true,
        });
      },
      /unknown keys/
    );
  } finally {
    server.close();
  }
});

test("writeChatMessage rejects output_data for non-assistant role", async () => {
  const { server, baseUrl } = await startServer((_req, res) => {
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ ok: true }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await assert.rejects(
      async () => {
        await client.writeChatMessage({
          agent_id: "agent_1",
          user_id: "user_1",
          chat_id: "chat_1",
          message_id: "m1",
          role: "user",
          content: { text: "hello" },
          telemetry_data: { source: "web" },
          output_data: { workflow_id: "wf_1" },
        });
      },
      /only allowed when role is assistant/
    );
  } finally {
    server.close();
  }
});

test("createAuthSession and refreshAuthSession set default access token", async () => {
  let refreshCookieSeen = false;
  const { server, baseUrl } = await startServer((req, res) => {
    if (req.url === "/v1/auth/sessions" && req.method === "POST") {
      res.setHeader("set-cookie", [
        "sf_refresh_token=refresh_1; Path=/v1/auth/sessions; HttpOnly",
        "sf_csrf_token=csrf_1; Path=/",
      ]);
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ access_token: "issued_token", token_type: "Bearer", expires_at: "2026-01-01T00:00:00Z" }));
      return;
    }
    if (req.url === "/v1/auth/sessions/refresh" && req.method === "POST") {
      const csrfHeader = req.headers["x-csrf-token"];
      const cookieHeader = req.headers.cookie || "";
      refreshCookieSeen = String(cookieHeader).includes("sf_refresh_token=refresh_1");
      assert.equal(csrfHeader, "csrf_1");
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ access_token: "refreshed_token", token_type: "Bearer", expires_at: "2026-01-01T01:00:00Z" }));
      return;
    }
    res.statusCode = 404;
    res.end(JSON.stringify({ error: "not found" }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const login = await client.createAuthSession({ email: "person@example.com", password: "secret" });
    assert.equal(login.access_token, "issued_token");
    assert.equal(client.apiToken, "issued_token");

    const refreshed = await client.refreshAuthSession();
    assert.equal(refreshed.access_token, "refreshed_token");
    assert.equal(client.apiToken, "refreshed_token");
    assert.equal(refreshCookieSeen, true);
  } finally {
    server.close();
  }
});

test("validateAccessToken calls /v1/me", async () => {
  const { server, baseUrl } = await startServer((req, res) => {
    assert.equal(req.url, "/v1/me");
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ user_id: "u_me", role: "member", organization_id: "org", provider: "self_hosted" }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl, apiToken: "issued_token" });
    const me = await client.validateAccessToken();
    assert.equal(me.user_id, "u_me");
  } finally {
    server.close();
  }
});

test("build/write chat message from simple agents result", async () => {
  let captured = null;
  const { server, baseUrl } = await startServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      captured = JSON.parse(body);
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ message_id: "m_assistant" }));
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const built = client.buildChatMessageFromSimpleAgentsResult({
      agentId: "agent_1",
      userId: "user_1",
      chatId: "chat_1",
      messageId: "m_assistant",
      workflowResult: {
        workflow_id: "wf_1",
        terminal_output: { label: "finance/invoice", reason: "ok", unknown: "drop" },
        outputs: {
          n1: { output: { label: "finance/invoice", reason: "ok", unknown: "drop" } },
        },
      },
    });
    assert.equal(built.role, "assistant");
    assert.equal(built.output_data.workflow_id, "wf_1");
    assert.equal(built.output_data.terminal_output.unknown, undefined);

    await client.writeChatMessageFromSimpleAgentsResult({
      agentId: "agent_1",
      userId: "user_1",
      chatId: "chat_1",
      messageId: "m_assistant",
      workflowResult: { workflow_id: "wf_1", terminal_output: "done" },
    });
    assert.equal(captured.role, "assistant");
    assert.ok(captured.output_data);
  } finally {
    server.close();
  }
});

test("getChatMessageOutput and upsertChatMessageOutput", async () => {
  let capturedPost = null;
  const { server, baseUrl } = await startServer((req, res) => {
    const path = (req.url || "").split("?")[0];
    if (path === "/v1/chat/messages/m1/output" && req.method === "GET") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ output: { workflow_id: "wf_1" } }));
      return;
    }
    if (path === "/v1/chat/messages/m1/output" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => {
        body += chunk;
      });
      req.on("end", () => {
        capturedPost = JSON.parse(body);
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify({ message_id: "m1", chat_id: "chat_1", output_data: { workflow_id: "wf_1" } }));
      });
      return;
    }
    res.statusCode = 404;
    res.end(JSON.stringify({ error: "not found" }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const out = await client.getChatMessageOutput({
      messageId: "m1",
      agentId: "agent_1",
      chatId: "chat_1",
      userId: "user_1",
      authToken: "jwt",
    });
    assert.equal(out.output.workflow_id, "wf_1");

    const upserted = await client.upsertChatMessageOutput({
      messageId: "m1",
      agentId: "agent_1",
      chatId: "chat_1",
      userId: "user_1",
      outputData: { workflow_id: "wf_1", events: [{ drop: true }] },
      authToken: "jwt",
    });
    assert.equal(upserted.chat_id, "chat_1");
    assert.equal(capturedPost.output_data.events, undefined);
  } finally {
    server.close();
  }
});

test("listChatSessions uses /v1/chat/sessions", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ sessions: [{ chat_id: "chat_1", status: "active" }], page: 2, limit: 10, has_more: true }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const sessions = await client.listChatSessions({
      agentId: "agent_1",
      userId: "user_1",
      page: 2,
      limit: 10,
      authToken: "jwt",
    });
    assert.equal(sessions.length, 1);
    assert.match(capturedPath, /\/v1\/chat\/sessions/);
    assert.match(capturedPath, /page=2/);
    assert.match(capturedPath, /limit=10/);
  } finally {
    server.close();
  }
});

test("listChatSessionsPage returns pagination metadata", async () => {
  const { server, baseUrl } = await startServer((_req, res) => {
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ sessions: [{ chat_id: "chat_1", status: "active" }], page: 3, limit: 20, has_more: true }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const page = await client.listChatSessionsPage({
      agentId: "agent_1",
      userId: "user_1",
      page: 3,
      limit: 20,
      authToken: "jwt",
    });
    assert.equal(page.page, 3);
    assert.equal(page.limit, 20);
    assert.equal(page.has_more, true);
  } finally {
    server.close();
  }
});

test("listChatSessions omits user_id when not provided", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ sessions: [{ chat_id: "chat_1", status: "active" }] }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const sessions = await client.listChatSessions({
      agentId: "agent_1",
      authToken: "jwt",
    });
    assert.equal(sessions.length, 1);
    assert.doesNotMatch(capturedPath, /user_id=/);
  } finally {
    server.close();
  }
});

test("listChatMessages uses /v1/chat/sessions with chat_id query", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ messages: [{ message_id: "m1" }] }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const messages = await client.listChatMessages({
      agentId: "agent_1",
      chatId: "chat_1",
      userId: "user_1",
      authToken: "jwt",
    });
    assert.equal(messages.length, 1);
    assert.match(capturedPath, /\/v1\/chat\/sessions/);
    assert.match(capturedPath, /chat_id=chat_1/);
  } finally {
    server.close();
  }
});

test("updateChatSession calls PATCH /v1/chat/sessions/{chat_id}", async () => {
  let capturedPath = "";
  let capturedBody = null;
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      capturedBody = JSON.parse(body);
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ chat_id: "chat_1", status: "archived" }));
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const updated = await client.updateChatSession({
      chatId: "chat_1",
      agentId: "agent_1",
      userId: "user_1",
      status: "archived",
      authToken: "jwt",
    });
    assert.equal(updated.status, "archived");
    assert.equal(capturedPath, "/v1/chat/sessions/chat_1");
    assert.equal(capturedBody.status, "archived");
  } finally {
    server.close();
  }
});

test("authorizeChatRead denies member when target user differs", async () => {
  const { server, baseUrl } = await startServer((req, res) => {
    res.setHeader("content-type", "application/json");
    const path = (req.url || "").split("?")[0];
    if (path === "/v1/me") {
      res.end(JSON.stringify({ user_id: "u_me", role: "member" }));
      return;
    }
    res.end(JSON.stringify({ ID: "agent_1" }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await assert.rejects(
      async () => {
        await client.authorizeChatRead({
          authToken: "jwt",
          agentId: "agent_1",
          chatUserId: "other_user",
        });
      },
      (err) => {
        assert.ok(err instanceof SimpleFlowAuthorizationError);
        assert.equal(err.statusCode, 403);
        return true;
      }
    );
  } finally {
    server.close();
  }
});

test("rolesIncludeAny and canReadChatUserScope helper parity", () => {
  assert.equal(rolesIncludeAny(["member", "admin"], ["admin"]), true);
  assert.equal(rolesIncludeAny(["member"], ["admin"]), false);
  assert.equal(
    canReadChatUserScope({
      roles: ["member"],
      principalUserId: "u1",
      targetUserId: "u1",
    }),
    true
  );
  assert.equal(
    canReadChatUserScope({
      roles: ["member"],
      principalUserId: "u1",
      targetUserId: "",
    }),
    false
  );
  assert.equal(
    canReadChatUserScope({
      roles: ["super_admin"],
      principalUserId: "u1",
      targetUserId: "",
    }),
    true
  );
});
