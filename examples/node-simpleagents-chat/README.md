# Node/TS SimpleAgents Chat Seed Example

This example logs in to the local control plane, writes a user message, writes an assistant message derived from a SimpleAgents workflow result, and verifies persisted chat output.

## JavaScript (runnable)

```bash
node examples/node-simpleagents-chat/seed_chat_from_simpleagents.js \
  --base-url http://localhost:8080 \
  --email "<user_email>" \
  --password "<user_password>"
```

## TypeScript reference

`seed_chat_from_simpleagents.ts` mirrors the same flow with typed SDK inputs.

Run with your preferred TS runner (for example `tsx`) if available:

```bash
tsx examples/node-simpleagents-chat/seed_chat_from_simpleagents.ts \
  --base-url http://localhost:8080 \
  --email "<user_email>" \
  --password "<user_password>"
```

## Optional: run live SimpleAgents workflow

Add `--use-live-workflow --workflow-file /path/to/test.yaml` and set:
- `WORKFLOW_PROVIDER`
- `WORKFLOW_API_BASE`
- `WORKFLOW_API_KEY`

If `--use-live-workflow` is not set, the script loads `sample_workflow_result.json`.
