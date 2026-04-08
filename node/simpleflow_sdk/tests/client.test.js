"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");

const { SimpleFlowClient } = require("../index.js");

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

test("writeEvent emits event to runtime events endpoint", async () => {
  let captured = null;
  const { server, baseUrl } = await startServer((req, res) => {
    assert.equal(req.url, "/v1/runtime/events");
    assert.equal(req.headers["content-type"], "application/json");
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      captured = JSON.parse(body);
      res.statusCode = 204;
      res.end();
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeEvent({
      event_type: "chat.message.telemetry",
      agent_id: "agent_1",
      conversation_id: "session_123",
      user_id: "user_123",
      payload: {
        total_tokens: 150,
        ttfs: 250,
      },
    });

    assert.equal(captured.event_type, "chat.message.telemetry");
    assert.equal(captured.agent_id, "agent_1");
    assert.equal(captured.conversation_id, "session_123");
    assert.equal(captured.payload.total_tokens, 150);
    assert.equal(captured.payload.ttfs, 250);
  } finally {
    server.close();
  }
});

test("writeEvent accepts auth token for user authentication", async () => {
  let capturedAuth = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedAuth = req.headers.authorization || "";
    res.statusCode = 204;
    res.end();
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeEvent(
      {
        event_type: "test.event",
        agent_id: "agent_1",
      },
      { authToken: "user_jwt_token_123" }
    );

    assert.equal(capturedAuth, "Bearer user_jwt_token_123");
  } finally {
    server.close();
  }
});

test("writeChatMessage emits message to runtime chat endpoint", async () => {
  let captured = null;
  const { server, baseUrl } = await startServer((req, res) => {
    assert.equal(req.url, "/v1/runtime/chat/messages");
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      captured = JSON.parse(body);
      res.statusCode = 204;
      res.end();
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeChatMessage({
      agent_id: "agent_1",
      organization_id: "org_123",
      user_id: "user_123",
      chat_id: "session_123",
      role: "user",
      content: { text: "Hello!" },
      metadata: { source: "chat.app" },
    });

    assert.equal(captured.agent_id, "agent_1");
    assert.equal(captured.chat_id, "session_123");
    assert.equal(captured.role, "user");
    assert.equal(captured.direction, "outbound");
    assert.deepEqual(captured.content, { text: "Hello!" });
  } finally {
    server.close();
  }
});

test("writeChatMessage uses idempotency key when provided", async () => {
  let capturedKey = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedKey = req.headers["idempotency-key"] || "";
    res.statusCode = 204;
    res.end();
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeChatMessage({
      agent_id: "agent_1",
      organization_id: "org_123",
      user_id: "user_123",
      chat_id: "session_123",
      role: "user",
      content: { text: "Hello!" },
      idempotency_key: "unique-key-123",
    });

    assert.equal(capturedKey, "unique-key-123");
  } finally {
    server.close();
  }
});

test("listChatSessions fetches sessions with correct query params", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(
      JSON.stringify({
        sessions: [
          {
            chat_id: "session_123",
            status: "active",
            agent_id: "agent_1",
            user_id: "user_123",
            metadata: { title: "Chat Session" },
          },
        ],
      })
    );
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const sessions = await client.listChatSessions({
      agentId: "agent_1",
      userId: "user_123",
      status: "active",
      limit: 10,
      authToken: "user_token",
    });

    assert.equal(sessions.length, 1);
    assert.equal(sessions[0].chat_id, "session_123");
    assert.equal(sessions[0].status, "active");
    assert.match(capturedPath, /\/v1\/runtime\/chat\/sessions/);
    assert.match(capturedPath, /agent_id=agent_1/);
    assert.match(capturedPath, /user_id=user_123/);
    assert.match(capturedPath, /status=active/);
    assert.match(capturedPath, /limit=10/);
  } finally {
    server.close();
  }
});

test("listChatMessages fetches messages with correct query params", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(
      JSON.stringify({
        messages: [
          {
            message_id: "msg_1",
            chat_id: "session_123",
            role: "user",
            content: { text: "Hello" },
          },
        ],
      })
    );
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const messages = await client.listChatMessages({
      agentId: "agent_1",
      chatId: "session_123",
      userId: "user_123",
      limit: 20,
      authToken: "user_token",
    });

    assert.equal(messages.length, 1);
    assert.equal(messages[0].message_id, "msg_1");
    assert.match(capturedPath, /\/v1\/runtime\/chat\/messages\/list/);
    assert.match(capturedPath, /agent_id=agent_1/);
    assert.match(capturedPath, /chat_id=session_123/);
    assert.match(capturedPath, /user_id=user_123/);
    assert.match(capturedPath, /limit=20/);
  } finally {
    server.close();
  }
});

test("writeMessageTelemetry writes telemetry for a chat message", async () => {
  let captured = null;
  const { server, baseUrl } = await startServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      captured = JSON.parse(body);
      res.statusCode = 204;
      res.end();
    });
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await client.writeMessageTelemetry(
      "agent_1",
      "session_123",
      {
        total_tokens: 150,
        ttfs: 250,
        prompt_tokens: 50,
        completion_tokens: 100,
        user_id: "user_123",
        run_id: "run_456",
      },
      "user_jwt_token"
    );

    assert.equal(captured.event_type, "chat.message.telemetry");
    assert.equal(captured.agent_id, "agent_1");
    assert.equal(captured.conversation_id, "session_123");
    assert.equal(captured.user_id, "user_123");
    assert.equal(captured.run_id, "run_456");
    assert.equal(captured.payload.total_tokens, 150);
    assert.equal(captured.payload.ttfs, 250);
    assert.equal(captured.payload.prompt_tokens, 50);
    assert.equal(captured.payload.completion_tokens, 100);
    assert.equal(typeof captured.payload.timestamp_ms, "number");
  } finally {
    server.close();
  }
});

test("authentication error throws SimpleFlowAuthenticationError", async () => {
  const { server, baseUrl } = await startServer((req, res) => {
    res.statusCode = 401;
    res.end("Unauthorized");
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await assert.rejects(
      async () => {
        await client.listChatSessions({ agentId: "agent_1", userId: "user_1" });
      },
      (err) => {
        assert.equal(err.statusCode, 401);
        assert.ok(err.message.includes("status=401"));
        return true;
      }
    );
  } finally {
    server.close();
  }
});

test("authorization error throws SimpleFlowAuthorizationError", async () => {
  const { server, baseUrl } = await startServer((req, res) => {
    res.statusCode = 403;
    res.end("Forbidden");
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    await assert.rejects(
      async () => {
        await client.listChatSessions({ agentId: "agent_1", userId: "user_1" });
      },
      (err) => {
        assert.equal(err.statusCode, 403);
        assert.ok(err.message.includes("status=403"));
        return true;
      }
    );
  } finally {
    server.close();
  }
});
