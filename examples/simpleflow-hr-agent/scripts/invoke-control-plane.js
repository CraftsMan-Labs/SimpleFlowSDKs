const crypto = require("node:crypto");
const { SimpleFlowClient } = require("simpleflow-sdk");
const { getRuntimeIdentity, optionalEnv, requireEnv } = require("./shared");

async function main() {
  const identity = getRuntimeIdentity();
  const client = new SimpleFlowClient({
    baseUrl: requireEnv("SIMPLEFLOW_BASE_URL"),
    apiToken: requireEnv("SIMPLEFLOW_API_TOKEN"),
  });

  const request = {
    schema_version: "v1",
    run_id: identity.runId,
    agent_id: identity.agentId,
    agent_version: identity.agentVersion,
    mode: "realtime",
    trace: {
      trace_id: `trace_${crypto.randomUUID().slice(0, 12)}`,
      span_id: `span_${crypto.randomUUID().slice(0, 12)}`,
      tenant_id: identity.organizationId,
    },
    input: {
      message: optionalEnv(
        "USER_MESSAGE",
        "Please draft a professional follow-up email to an employee for repeated late arrivals."
      ),
    },
    deadline_ms: Number(optionalEnv("INVOKE_DEADLINE_MS", "120000")),
    idempotency_key: `invoke_${crypto.randomUUID()}`,
  };

  const response = await client.invoke(request);
  console.log(JSON.stringify(response, null, 2));
}

main().catch((error) => {
  console.error("Failed to invoke runtime:", error.message || error);
  process.exitCode = 1;
});
