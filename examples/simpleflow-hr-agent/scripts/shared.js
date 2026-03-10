const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

require("dotenv").config({ path: path.resolve(__dirname, "..", ".env") });

function requireEnv(name) {
  const value = String(process.env[name] || "").trim();
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

function optionalEnv(name, fallback = "") {
  const value = String(process.env[name] || "").trim();
  return value || fallback;
}

function getRuntimeIdentity() {
  return {
    agentId: optionalEnv("SIMPLEFLOW_AGENT_ID", "hr-agent-runtime"),
    agentVersion: optionalEnv("SIMPLEFLOW_AGENT_VERSION", "v1"),
    organizationId: optionalEnv("SIMPLEFLOW_ORGANIZATION_ID", "org_local_demo"),
    userId: optionalEnv("SIMPLEFLOW_USER_ID", "user_local_demo"),
    conversationId: optionalEnv("SIMPLEFLOW_CONVERSATION_ID", `chat_${crypto.randomUUID().slice(0, 8)}`),
    requestId: optionalEnv("SIMPLEFLOW_REQUEST_ID", `req_${crypto.randomUUID().slice(0, 8)}`),
    runId: optionalEnv("SIMPLEFLOW_RUN_ID", `run_${crypto.randomUUID().slice(0, 8)}`),
  };
}

function resolveWorkflowPath() {
  const fromEnv = optionalEnv("WORKFLOW_FILE", "");
  if (fromEnv) return path.resolve(fromEnv);
  return path.resolve(__dirname, "..", "workflows", "email-chat-draft-or-clarify.yaml");
}

function readJsonSafe(filePath) {
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

module.exports = {
  getRuntimeIdentity,
  optionalEnv,
  readJsonSafe,
  requireEnv,
  resolveWorkflowPath,
};
