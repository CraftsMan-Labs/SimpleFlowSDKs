"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

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

function loadFixture(...parts) {
  const fixturePath = path.resolve(__dirname, "../../..", ...parts);
  return JSON.parse(fs.readFileSync(fixturePath, "utf-8"));
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
                total_reasoning_tokens: 2,
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
    assert.equal(captured.payload.usage.reasoning_tokens, 2);
    assert.equal(captured.payload.model_usage[0].model, "gpt-5-mini");
  } finally {
    server.close();
  }
});

test("writeEventFromWorkflowResult extracts top-level nerdstats and keeps unavailable token usage nullable", async () => {
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
        nerdstats: {
          total_input_tokens: 999,
          total_output_tokens: 888,
          total_tokens: 777,
          token_metrics_available: false,
          token_metrics_source: "provider_stream_usage_unavailable",
          llm_nodes_without_usage: ["detect_scenario_context"],
          total_elapsed_ms: 321,
        },
      },
    });

    assert.equal(captured.payload.usage.prompt_tokens, null);
    assert.equal(captured.payload.usage.completion_tokens, null);
    assert.equal(captured.payload.usage.total_tokens, null);
    assert.equal(captured.payload.usage.reasoning_tokens, null);
    assert.equal(captured.payload.usage.total_elapsed_ms, 321);
    assert.equal(captured.payload.usage.token_metrics_available, false);
    assert.equal(captured.payload.usage.token_metrics_source, "provider_stream_usage_unavailable");
    assert.deepEqual(captured.payload.usage.llm_nodes_without_usage, ["detect_scenario_context"]);
    assert.equal(captured.payload.nerdstats.token_metrics_available, false);
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

test("contract fixture telemetry envelope workflow_basic", async () => {
  const fixture = loadFixture("contracts", "telemetry-envelope-v1", "workflow_basic.json");

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
      agentId: fixture.agent_id,
      workflowResult: fixture.workflow_result,
    });

    assert.equal(captured.event_type, fixture.expected_event.event_type);
    assert.equal(captured.trace_id, fixture.expected_event.trace_id);
    assert.equal(captured.conversation_id, fixture.expected_event.conversation_id);
    assert.equal(captured.request_id, fixture.expected_event.request_id);
    assert.equal(captured.user_id, fixture.expected_event.user_id);
    assert.equal(captured.payload.schema_version, fixture.expected_payload.schema_version);
    assert.equal(captured.payload.usage.total_tokens, fixture.expected_payload.usage.total_tokens);
    assert.equal(captured.payload.usage.reasoning_tokens, fixture.expected_payload.usage.reasoning_tokens);
    assert.equal(captured.payload.model_usage[0].model, fixture.expected_payload.model_usage_first.model);
  } finally {
    server.close();
  }
});

test("contract fixture runtime registration action path cases", async () => {
  const fixture = loadFixture("contracts", "runtime-registration", "action_path_cases.json");
  const client = new SimpleFlowClient({ baseUrl: "https://api.example" });

  for (const item of fixture.cases) {
    assert.equal(
      client._runtimeRegistrationActionPath(item.template, item.registration_id),
      item.expected,
    );
  }
});
