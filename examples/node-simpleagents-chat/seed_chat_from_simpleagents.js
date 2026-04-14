"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const repoRoot = path.resolve(__dirname, "..", "..");
const { SimpleFlowClient } = require(path.join(
  repoRoot,
  "node",
  "simpleflow_sdk",
  "index.js"
));

function parseArgs(argv) {
  const out = {
    baseUrl: "http://localhost:8080",
    email: process.env.SIMPLEFLOW_USER_EMAIL || "",
    password: process.env.SIMPLEFLOW_USER_PASSWORD || "",
    agentId: process.env.SIMPLEFLOW_AGENT_ID || "",
    chatId: "",
    userInput: "Please classify this invoice and summarize key findings.",
    useLiveWorkflow: false,
    workflowFile: process.env.WORKFLOW_PATH || "",
    workflowResultFile: path.join(__dirname, "sample_workflow_result.json"),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];
    switch (key) {
      case "--base-url":
        out.baseUrl = String(next || "");
        i += 1;
        break;
      case "--email":
        out.email = String(next || "");
        i += 1;
        break;
      case "--password":
        out.password = String(next || "");
        i += 1;
        break;
      case "--agent-id":
        out.agentId = String(next || "");
        i += 1;
        break;
      case "--chat-id":
        out.chatId = String(next || "");
        i += 1;
        break;
      case "--user-input":
        out.userInput = String(next || "");
        i += 1;
        break;
      case "--workflow-file":
        out.workflowFile = String(next || "");
        i += 1;
        break;
      case "--workflow-result-file":
        out.workflowResultFile = String(next || "");
        i += 1;
        break;
      case "--use-live-workflow":
        out.useLiveWorkflow = true;
        break;
      default:
        break;
    }
  }
  return out;
}

function readJsonFile(filePath) {
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("workflow result file must contain a JSON object");
  }
  return parsed;
}

async function runSimpleAgentsWorkflow(workflowFile, userInput) {
  const provider = String(process.env.WORKFLOW_PROVIDER || "").trim();
  const apiBase = String(process.env.WORKFLOW_API_BASE || "").trim();
  const apiKey = String(process.env.WORKFLOW_API_KEY || "").trim();
  if (!provider || !apiBase || !apiKey) {
    throw new Error(
      "WORKFLOW_PROVIDER, WORKFLOW_API_BASE, and WORKFLOW_API_KEY are required for --use-live-workflow"
    );
  }
  if (!workflowFile || !fs.existsSync(workflowFile)) {
    throw new Error(`workflow file not found: ${workflowFile}`);
  }

  const { Client } = await import("simple-agents-node");
  const client = new Client(apiKey, apiBase);
  const result = await client.runWorkflow(workflowFile, {
    messages: [{ role: "user", content: userInput }],
  });
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    throw new Error("simple-agents workflow result must be a JSON object");
  }
  return result;
}

async function discoverAgentId(baseUrl, userToken) {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/api/v1/agents`, {
    method: "GET",
    headers: { Authorization: `Bearer ${userToken}` },
  });
  if (!response.ok) {
    throw new Error(`failed to list agents: ${response.status}`);
  }
  const payload = await response.json();
  let agents = [];
  if (Array.isArray(payload)) {
    agents = payload;
  } else if (payload && typeof payload === "object") {
    for (const key of ["agents", "items", "data"]) {
      if (Array.isArray(payload[key])) {
        agents = payload[key];
        break;
      }
    }
  }
  if (agents.length === 0) {
    throw new Error("no agents returned by /api/v1/agents; pass --agent-id explicitly");
  }
  for (const item of agents) {
    if (!item || typeof item !== "object") continue;
    for (const key of ["id", "ID", "agent_id"]) {
      const value = item[key];
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  throw new Error("could not resolve an agent id from /api/v1/agents response");
}

function generateId(prefix) {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0, 10)}`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.email.trim() || !args.password) {
    throw new Error("email and password are required (set --email/--password or SIMPLEFLOW_USER_* env vars)");
  }

  const workflowResult = args.useLiveWorkflow
    ? await runSimpleAgentsWorkflow(args.workflowFile, args.userInput)
    : readJsonFile(path.resolve(args.workflowResultFile));

  const client = new SimpleFlowClient({ baseUrl: args.baseUrl });
  const session = await client.createAuthSession({
    email: args.email,
    password: args.password,
    setAsDefaultToken: true,
  });
  const userToken = String(session.access_token || "").trim();
  if (!userToken) throw new Error("login succeeded but no access_token returned");

  const principal = await client.validateAccessToken({ authToken: userToken });
  const userId = String(principal.user_id || "").trim();
  if (!userId) throw new Error("could not resolve user_id from /v1/me response");

  const agentId = args.agentId.trim() || (await discoverAgentId(args.baseUrl, userToken));
  const chatId = args.chatId.trim() || `sdk_demo_${crypto.randomUUID().replace(/-/g, "").slice(0, 10)}`;
  const userMessageId = generateId("user");
  const assistantMessageId = generateId("assistant");

  await client.writeChatMessage(
    {
      agent_id: agentId,
      user_id: userId,
      chat_id: chatId,
      message_id: userMessageId,
      role: "user",
      content: { text: args.userInput },
      telemetry_data: { source: "sdk-example", event_type: "user.message" },
    },
    { authToken: userToken }
  );

  await client.writeChatMessageFromSimpleAgentsResult({
    agentId,
    userId,
    chatId,
    messageId: assistantMessageId,
    workflowResult,
    authToken: userToken,
  });

  const messages = await client.listChatMessages({
    agentId,
    chatId,
    userId,
    authToken: userToken,
  });
  const sessions = await client.listChatSessions({
    agentId,
    userId,
    authToken: userToken,
  });
  const output = await client.getChatMessageOutput({
    messageId: assistantMessageId,
    agentId,
    chatId,
    userId,
    authToken: userToken,
  });

  console.log(
    JSON.stringify(
      {
        base_url: args.baseUrl,
        agent_id: agentId,
        user_id: userId,
        chat_id: chatId,
        user_message_id: userMessageId,
        assistant_message_id: assistantMessageId,
        messages_count: messages.length,
        sessions_count: sessions.length,
        output_keys: Object.keys(output.output || {}).sort(),
      },
      null,
      2
    )
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
