# Python SimpleAgents Chat Seed Example

This example logs in to the local control plane, writes a user message, writes an assistant message derived from a SimpleAgents workflow result, and verifies persisted chat output.

## Run with sample workflow result JSON

```bash
PYTHONPATH=python python examples/python-simpleagents-chat/seed_chat_from_simpleagents.py \
  --base-url http://localhost:8080 \
  --email "<user_email>" \
  --password "<user_password>"
```

## Run with live SimpleAgents typed workflow execution

Requirements:
- `simple-agents-py` available in your Python environment
- `WORKFLOW_PROVIDER`, `WORKFLOW_API_BASE`, `WORKFLOW_API_KEY` set
- a YAML workflow file

```bash
PYTHONPATH=python python examples/python-simpleagents-chat/seed_chat_from_simpleagents.py \
  --base-url http://localhost:8080 \
  --email "<user_email>" \
  --password "<user_password>" \
  --use-live-workflow \
  --workflow-file /path/to/test.yaml \
  --user-input "Classify this invoice"
```

The script prints a summary JSON including `chat_id`, message IDs, session/message counts, and persisted output keys.
