# Troubleshooting

## npm publish returns `E404 Scope not found`

Your package scope is not owned by your npm account.

- Use an unscoped package name (current default: `simpleflow-sdk`), or
- create/own the scoped org and grant publish rights.

## npm publish returns `EOTP`

Your npm account requires MFA.

- pass OTP: `NPM_OTP=123456 make publish-node`
- or log in interactively: `make npm-login`

## Runtime writes accepted but analytics stay zero

Verify payload is canonical:

- `payload.schema_version == telemetry-envelope.v1`
- usage fields present under `payload.usage`
- workflow timing under `payload.workflow`

## Missing chat history linkage

Ensure these IDs are always populated:

- `user_id`
- `conversation_id`
- `request_id`
- `run_id`
