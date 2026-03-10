const crypto = require("node:crypto");
const { Client: SimpleAgentsClient } = require("simple-agents-node");
const { SimpleFlowClient } = require("simpleflow-sdk");
const {
  getRuntimeIdentity,
  optionalEnv,
  readJsonSafe,
  requireEnv,
  resolveWorkflowPath,
} = require("./shared");

function buildMessages() {
  const fromPath = optionalEnv("INPUT_MESSAGES_JSON", "");
  if (fromPath) {
    const parsed = readJsonSafe(fromPath);
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    throw new Error(`INPUT_MESSAGES_JSON is set but invalid: ${fromPath}`);
  }

  const userMessage = optionalEnv(
    "USER_MESSAGE",
    "Please draft a professional follow-up email to an employee for repeated late arrivals."
  );
  return [{ role: "user", content: userMessage }];
}

function readTerminalOutput(workflowResult) {
  if (workflowResult && typeof workflowResult === "object") {
    if (workflowResult.terminal_output) return workflowResult.terminal_output;
    if (workflowResult.output) return workflowResult.output;
  }
  return null;
}

async function main() {
  const identity = getRuntimeIdentity();
  const workflowPath = resolveWorkflowPath();
  const messages = buildMessages();

  const agents = new SimpleAgentsClient(optionalEnv("SIMPLE_AGENTS_PROVIDER", "openai"));
  const simpleflow = new SimpleFlowClient({
    baseUrl: requireEnv("SIMPLEFLOW_BASE_URL"),
    apiToken: requireEnv("SIMPLEFLOW_API_TOKEN"),
  });

  const workflowResult = await Promise.resolve(
    agents.runWorkflowYamlWithEvents(
      workflowPath,
      { input: { messages } },
      {
        trace: {
          tenant: {
            organization_id: identity.organizationId,
            user_id: identity.userId,
            conversation_id: identity.conversationId,
            request_id: identity.requestId,
            run_id: identity.runId,
          },
        },
      }
    )
  );

  await simpleflow.writeEventFromWorkflowResult({
    agentId: identity.agentId,
    organizationId: identity.organizationId,
    userId: identity.userId,
    workflowResult,
    requestId: identity.requestId,
    conversationId: identity.conversationId,
    runId: identity.runId,
    eventType: "runtime.workflow.completed",
    idempotencyKey: `idem_${crypto.randomUUID()}`,
  });

  const terminalOutput = readTerminalOutput(workflowResult);
  console.log("Workflow completed and telemetry sent.");
  console.log(`run_id: ${identity.runId}`);
  console.log(`request_id: ${identity.requestId}`);
  if (terminalOutput) {
    console.log("terminal_output:");
    console.log(JSON.stringify(terminalOutput, null, 2));
  }
}

main().catch((error) => {
  console.error("Failed to run local agent:", error.message || error);
  process.exitCode = 1;
});
