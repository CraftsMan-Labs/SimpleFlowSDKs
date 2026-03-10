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

test("writeEventFromWorkflowResult emits telemetry-envelope.v1 payload", async () => {
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
    await client.writeEventFromWorkflowResult({
      agentId: "agent_support_v1",
      workflowResult: {
        workflow_id: "email-chat-draft-or-clarify",
        terminal_node: "ask_for_scenario",
        run_id: "run_123",
        metadata: {
          telemetry: { trace_id: "trace_123", sampled: true },
          trace: {
            tenant: {
              conversation_id: "chat_123",
              request_id: "req_123",
              user_id: "user_123",
            },
          },
        },
        events: [
          { event_type: "workflow_started" },
          {
            event_type: "workflow_completed",
            metadata: {
              nerdstats: {
                total_input_tokens: 10,
                total_output_tokens: 5,
                total_tokens: 15,
                step_details: [
                  {
                    model_name: "gpt-5-mini",
                    prompt_tokens: 10,
                    completion_tokens: 5,
                    total_tokens: 15,
                  },
                ],
              },
            },
          },
        ],
      },
    });

    assert.equal(captured.event_type, "runtime.workflow.completed");
    assert.equal(captured.trace_id, "trace_123");
    assert.equal(captured.conversation_id, "chat_123");
    assert.equal(captured.user_id, "user_123");
    assert.equal(captured.payload.schema_version, "telemetry-envelope.v1");
    assert.equal(captured.payload.usage.total_tokens, 15);
    assert.equal(captured.payload.model_usage[0].model, "gpt-5-mini");
  } finally {
    server.close();
  }
});

test("withTelemetry simpleflow emits runtime.telemetry.span", async () => {
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
    const telemetry = client.withTelemetry({ mode: "simpleflow", sampleRate: 1.0 });
    await telemetry.emitSpan({
      span: { name: "llm.call", start_time_ms: 10, end_time_ms: 12 },
      agentId: "agent_1",
      runId: "run_1",
      traceId: "trace_1",
    });

    assert.equal(captured.event_type, "runtime.telemetry.span");
    assert.equal(captured.trace_id, "trace_1");
    assert.deepEqual(captured.payload.span.name, "llm.call");
  } finally {
    server.close();
  }
});

test("listChatHistoryMessages uses expected query params", async () => {
  let capturedPath = "";
  const { server, baseUrl } = await startServer((req, res) => {
    capturedPath = req.url || "";
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ messages: [{ message_id: "m1" }] }));
  });

  try {
    const client = new SimpleFlowClient({ baseUrl });
    const messages = await client.listChatHistoryMessages({
      agentId: "agent_1",
      chatId: "chat_1",
      userId: "user_1",
      limit: 10,
    });
    assert.equal(messages[0].message_id, "m1");
    assert.match(capturedPath, /agent_id=agent_1/);
    assert.match(capturedPath, /chat_id=chat_1/);
    assert.match(capturedPath, /user_id=user_1/);
    assert.match(capturedPath, /limit=10/);
  } finally {
    server.close();
  }
});
