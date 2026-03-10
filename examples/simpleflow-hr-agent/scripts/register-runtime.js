const { SimpleFlowClient } = require("simpleflow-sdk");
const { getRuntimeIdentity, optionalEnv, requireEnv } = require("./shared");

async function main() {
  const client = new SimpleFlowClient({
    baseUrl: requireEnv("SIMPLEFLOW_BASE_URL"),
    apiToken: requireEnv("SIMPLEFLOW_API_TOKEN"),
  });

  const identity = getRuntimeIdentity();
  const endpointUrl = requireEnv("RUNTIME_ENDPOINT_URL");

  const registration = {
    agent_id: identity.agentId,
    agent_version: identity.agentVersion,
    execution_mode: "remote_runtime",
    endpoint_url: endpointUrl,
    auth_mode: optionalEnv("RUNTIME_AUTH_MODE", "jwt"),
    capabilities: ["chat", "webhook", "queue"],
    runtime_id: optionalEnv("SIMPLEFLOW_RUNTIME_ID", "runtime_local_hr_agent"),
  };

  const result = await client.ensureRuntimeRegistrationActive({ registration });
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error("Failed to register runtime:", error.message || error);
  process.exitCode = 1;
});
