package simpleflow

import "encoding/json"

type InvokeTrace struct {
	TraceID  string `json:"trace_id"`
	SpanID   string `json:"span_id"`
	TenantID string `json:"tenant_id"`
}

type WorkflowTraceTenant struct {
	ConversationID string `json:"conversation_id,omitempty"`
	RequestID      string `json:"request_id,omitempty"`
	RunID          string `json:"run_id,omitempty"`
	AgentID        string `json:"agent_id,omitempty"`
	OrganizationID string `json:"organization_id,omitempty"`
}

type RuntimeRegistration struct {
	ID             string            `json:"id,omitempty"`
	RegistrationID string            `json:"registration_id,omitempty"`
	AgentID        string            `json:"agent_id,omitempty"`
	AgentVersion   string            `json:"agent_version,omitempty"`
	ExecutionMode  string            `json:"execution_mode,omitempty"`
	EndpointURL    string            `json:"endpoint_url,omitempty"`
	AuthMode       string            `json:"auth_mode,omitempty"`
	Capabilities   []string          `json:"capabilities,omitempty"`
	Metadata       map[string]string `json:"metadata,omitempty"`
	RuntimeID      string            `json:"runtime_id,omitempty"`
	RuntimeVersion string            `json:"runtime_version,omitempty"`
}

type RuntimeRegistrationValidationResult struct {
	ValidationOK bool                `json:"validation_ok"`
	Registration RuntimeRegistration `json:"registration"`
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
	EventType      string         `json:"event_type,omitempty"`
	Type           string         `json:"type,omitempty"`
	AgentID        string         `json:"agent_id"`
	AgentVersion   string         `json:"agent_version"`
	RunID          string         `json:"run_id"`
	ConversationID string         `json:"conversation_id,omitempty"`
	RequestID      string         `json:"request_id,omitempty"`
	TraceID        string         `json:"trace_id,omitempty"`
	Sampled        *bool          `json:"sampled,omitempty"`
	OrganizationID string         `json:"organization_id"`
	UserID         string         `json:"user_id"`
	TimestampMS    int64          `json:"timestamp_ms"`
	IdempotencyKey string         `json:"idempotency_key,omitempty"`
	Payload        map[string]any `json:"payload"`
}

type TelemetrySpan struct {
	Name         string         `json:"name"`
	StartTimeMS  int64          `json:"start_time_ms"`
	EndTimeMS    int64          `json:"end_time_ms"`
	Kind         string         `json:"kind,omitempty"`
	Attributes   map[string]any `json:"attributes,omitempty"`
	Status       string         `json:"status,omitempty"`
	StatusDetail string         `json:"status_detail,omitempty"`
}

type ChatMessageWrite struct {
	AgentID        string         `json:"agent_id"`
	OrganizationID string         `json:"organization_id"`
	RunID          string         `json:"run_id"`
	ChatID         string         `json:"chat_id,omitempty"`
	MessageID      string         `json:"message_id,omitempty"`
	Role           string         `json:"role"`
	Direction      string         `json:"direction,omitempty"`
	Content        any            `json:"content"`
	Metadata       map[string]any `json:"metadata"`
	IdempotencyKey string         `json:"idempotency_key,omitempty"`
	CreatedAtMS    int64          `json:"created_at_ms"`
}

type QueueContract struct {
	AgentID         string         `json:"agent_id,omitempty"`
	OrganizationID  string         `json:"organization_id,omitempty"`
	RunID           string         `json:"run_id,omitempty"`
	QueueName       string         `json:"queue_name"`
	ContractName    string         `json:"contract_name,omitempty"`
	ContractVersion string         `json:"contract_version,omitempty"`
	Schema          map[string]any `json:"schema,omitempty"`
	Transport       map[string]any `json:"transport,omitempty"`
	Status          string         `json:"status,omitempty"`
	MessageID       string         `json:"message_id,omitempty"`
	IdempotencyKey  string         `json:"idempotency_key"`
	RetryAttempt    int            `json:"retry_attempt"`
	MaxRetryAttempt int            `json:"max_retry_attempt"`
	Payload         map[string]any `json:"payload"`
}

type ChatHistoryMessage struct {
	ID        string         `json:"id,omitempty"`
	AgentID   string         `json:"agent_id"`
	ChatID    string         `json:"chat_id"`
	MessageID string         `json:"message_id"`
	UserID    string         `json:"user_id"`
	Role      string         `json:"role,omitempty"`
	Content   map[string]any `json:"content,omitempty"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

type ChatHistoryListInput struct {
	AgentID string
	ChatID  string
	UserID  string
	Limit   int
}
