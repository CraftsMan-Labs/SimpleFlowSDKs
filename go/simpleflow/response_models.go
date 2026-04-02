package simpleflow

type UsageSummary struct {
	PromptTokens          any      `json:"prompt_tokens"`
	CompletionTokens      any      `json:"completion_tokens"`
	TotalTokens           any      `json:"total_tokens"`
	ReasoningTokens       any      `json:"reasoning_tokens"`
	TTFTMS                any      `json:"ttft_ms"`
	TotalElapsedMS        any      `json:"total_elapsed_ms"`
	TokensPerSecond       any      `json:"tokens_per_second"`
	TokenMetricsAvailable bool     `json:"token_metrics_available"`
	TokenMetricsSource    any      `json:"token_metrics_source"`
	LLMNodesWithoutUsage  []string `json:"llm_nodes_without_usage"`
}

type ModelUsageRow struct {
	Model            string `json:"model"`
	RequestCount     int64  `json:"request_count"`
	PromptTokens     int64  `json:"prompt_tokens"`
	CompletionTokens int64  `json:"completion_tokens"`
	TotalTokens      int64  `json:"total_tokens"`
	ReasoningTokens  int64  `json:"reasoning_tokens"`
	ElapsedMS        int64  `json:"elapsed_ms"`
}

type ToolUsageRow struct {
	Tool           string `json:"tool"`
	StartedCount   int64  `json:"started_count"`
	CompletedCount int64  `json:"completed_count"`
	ErrorCount     int64  `json:"error_count"`
}

type TelemetryIdentity struct {
	OrganizationID string `json:"organization_id"`
	AgentID        string `json:"agent_id"`
	UserID         string `json:"user_id"`
}

type TelemetryTrace struct {
	TraceID        string `json:"trace_id"`
	SpanID         string `json:"span_id"`
	TenantID       string `json:"tenant_id"`
	ConversationID string `json:"conversation_id"`
	RequestID      string `json:"request_id"`
	RunID          string `json:"run_id"`
	Sampled        bool   `json:"sampled"`
}

type TelemetryWorkflow struct {
	WorkflowID     string `json:"workflow_id"`
	TerminalNode   string `json:"terminal_node"`
	Status         string `json:"status"`
	TotalElapsedMS any    `json:"total_elapsed_ms"`
	TTFTMS         any    `json:"ttft_ms"`
}

type TelemetryEnvelopeV1 struct {
	SchemaVersion string            `json:"schema_version"`
	Identity      TelemetryIdentity `json:"identity"`
	Trace         TelemetryTrace    `json:"trace"`
	Workflow      TelemetryWorkflow `json:"workflow"`
	Usage         UsageSummary      `json:"usage"`
	ModelUsage    []ModelUsageRow   `json:"model_usage"`
	ToolUsage     []ToolUsageRow    `json:"tool_usage"`
	EventCounts   map[string]int64  `json:"event_counts"`
	Nerdstats     map[string]any    `json:"nerdstats,omitempty"`
	Raw           map[string]any    `json:"raw,omitempty"`
}

type RuntimeActivationResult struct {
	Status         string                              `json:"status"`
	Registration   RuntimeRegistration                 `json:"registration"`
	RegistrationID string                              `json:"registration_id"`
	Validation     RuntimeRegistrationValidationResult `json:"validation,omitempty"`
	Created        bool                                `json:"created"`
	Validated      bool                                `json:"validated"`
	Activated      bool                                `json:"activated"`
}

type ChatSession struct {
	ChatID   string         `json:"chat_id"`
	Status   string         `json:"status,omitempty"`
	AgentID  string         `json:"agent_id,omitempty"`
	UserID   string         `json:"user_id,omitempty"`
	Metadata map[string]any `json:"metadata,omitempty"`
}
