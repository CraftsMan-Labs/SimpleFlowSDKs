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
      res.end(JSON.stringify({ user_id: "u_me", roles: ["member"] }));
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
