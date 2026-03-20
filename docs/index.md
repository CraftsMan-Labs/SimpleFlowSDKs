---
layout: home

hero:
  name: SimpleFlow SDKs
  text: Runtime and telemetry SDKs for SimpleFlow
  tagline: Build agents in SimpleAgents, emit canonical telemetry, and analyze usage in SimpleFlow
  actions:
    - theme: brand
      text: Quick Start
      link: /quickstart
    - theme: alt
      text: Connect a SimpleAgent
      link: /agent-integration
    - theme: alt
      text: View GitHub
      link: https://github.com/CraftsMan-Labs/SimpleFlowSDKs

features:
  - title: Multi-language parity
    details: Node, Python, and Go expose aligned runtime write and workflow bridge APIs.
  - title: Canonical telemetry
    details: "telemetry-envelope.v1 standardizes usage, model, tool, and trace correlation metadata."
  - title: Runtime-ready
    details: Includes runtime connect and chat history integration helpers.
  - title: Control-plane analytics fit
    details: Payloads align to analytics dimensions like user, conversation, run, and token usage.
---

## What You Will Build

- Create or run a SimpleAgent workflow.
- Capture workflow output and emit `runtime.workflow.completed` via the SDK.
- Attach `user_id`, `conversation_id`, and `request_id` for chat history and analytics.
- Publish telemetry that SimpleFlow control plane can aggregate daily by usage dimensions.

## Start Here

- New integration: [Quick Start](/quickstart)
- SimpleAgents to SimpleFlow bridge: [Agent Integration](/agent-integration)
- Full from-zero runnable setup: [Zero to Control Plane](/agent-zero-to-control-plane)
- Canonical payload contract: [Telemetry Envelope V1](/telemetry-envelope-v1)
- Language-specific references: [Node](/sdk-node), [Python](/sdk-python), [Go](/sdk-go)
