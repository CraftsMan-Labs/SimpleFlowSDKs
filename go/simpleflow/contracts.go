package simpleflow

import "encoding/json"

type InvokeTrace struct {
	TraceID  string `json:"trace_id"`
	SpanID   string `json:"span_id"`
	TenantID string `json:"tenant_id"`
}

type InvokeRequest struct {
	SchemaVersion  string          `json:"schema_version"`
	RunID          string          `json:"run_id"`
	AgentID        string          `json:"agent_id"`
	AgentVersion   string          `json:"agent_version"`
	Mode           string          `json:"mode"`
	Trace          InvokeTrace     `json:"trace"`
	Input          json.RawMessage `json:"input"`
	DeadlineMS     int64           `json:"deadline_ms"`
	IdempotencyKey string          `json:"idempotency_key"`
}

type ErrorEnvelope struct {
	SchemaVersion string         `json:"schema_version"`
	Code          string         `json:"code"`
	Message       string         `json:"message"`
	Retryable     bool           `json:"retryable"`
	Details       map[string]any `json:"details"`
}

type InvokeMetrics struct {
	StartedAtMS  int64 `json:"started_at_ms"`
	FinishedAtMS int64 `json:"finished_at_ms"`
	DurationMS   int64 `json:"duration_ms"`
}

type InvokeResult struct {
	SchemaVersion string          `json:"schema_version"`
	RunID         string          `json:"run_id"`
	Status        string          `json:"status"`
	Output        json.RawMessage `json:"output"`
	Error         *ErrorEnvelope  `json:"error"`
	Metrics       InvokeMetrics   `json:"metrics"`
}

type RuntimeEvent struct {
	Type           string         `json:"type"`
	AgentID        string         `json:"agent_id"`
	AgentVersion   string         `json:"agent_version"`
	RunID          string         `json:"run_id"`
	OrganizationID string         `json:"organization_id"`
	UserID         string         `json:"user_id"`
	TimestampMS    int64          `json:"timestamp_ms"`
	Payload        map[string]any `json:"payload"`
}

type ChatMessageWrite struct {
	AgentID        string         `json:"agent_id"`
	OrganizationID string         `json:"organization_id"`
	RunID          string         `json:"run_id"`
	Role           string         `json:"role"`
	Content        string         `json:"content"`
	Metadata       map[string]any `json:"metadata"`
	CreatedAtMS    int64          `json:"created_at_ms"`
}

type QueueContract struct {
	QueueName       string         `json:"queue_name"`
	MessageID       string         `json:"message_id"`
	IdempotencyKey  string         `json:"idempotency_key"`
	RetryAttempt    int            `json:"retry_attempt"`
	MaxRetryAttempt int            `json:"max_retry_attempt"`
	Payload         map[string]any `json:"payload"`
}
