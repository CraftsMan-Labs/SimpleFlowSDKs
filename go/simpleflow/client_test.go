package simpleflow

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func loadJSONFixtureMap(t *testing.T, fixturePath string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	fixture := map[string]any{}
	if err := json.Unmarshal(raw, &fixture); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}
	return fixture
}

func TestWriteEventFromWorkflowResult(t *testing.T) {
	var captured map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&captured); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	workflowResult := map[string]any{
		"run_id":        "run_123",
		"workflow_id":   "email-chat-draft-or-clarify",
		"terminal_node": "ask_for_scenario",
		"metadata": map[string]any{
			"telemetry": map[string]any{
				"trace_id": "trace_123",
				"sampled":  true,
			},
			"trace": map[string]any{
				"tenant": map[string]any{
					"conversation_id": "chat_123",
					"request_id":      "req_123",
					"user_id":         "user_123",
				},
			},
		},
		"events": []map[string]any{
			{"event_type": "workflow_started"},
			{
				"event_type": "workflow_completed",
				"metadata": map[string]any{
					"nerdstats": map[string]any{
						"total_input_tokens":     10,
						"total_output_tokens":    5,
						"total_tokens":           15,
						"total_reasoning_tokens": 2,
						"step_details": []map[string]any{{
							"model_name":        "gpt-5-mini",
							"prompt_tokens":     10,
							"completion_tokens": 5,
							"total_tokens":      15,
						}},
					},
				},
			},
		},
	}

	err = client.WriteEventFromWorkflowResult(context.Background(), WriteEventFromWorkflowResultInput{
		AgentID:        "agent_support_v1",
		WorkflowResult: workflowResult,
	})
	if err != nil {
		t.Fatalf("write event from workflow result: %v", err)
	}

	if got := captured["event_type"]; got != "runtime.workflow.completed" {
		t.Fatalf("unexpected event_type: %v", got)
	}
	if got := captured["trace_id"]; got != "trace_123" {
		t.Fatalf("unexpected trace_id: %v", got)
	}
	if got := captured["conversation_id"]; got != "chat_123" {
		t.Fatalf("unexpected conversation_id: %v", got)
	}
	payload, ok := captured["payload"].(map[string]any)
	if !ok {
		t.Fatalf("expected payload map, got %T", captured["payload"])
	}
	if got := payload["schema_version"]; got != "telemetry-envelope.v1" {
		t.Fatalf("unexpected schema_version: %v", got)
	}
	usage, ok := payload["usage"].(map[string]any)
	if !ok {
		t.Fatalf("expected usage map, got %T", payload["usage"])
	}
	if got := usage["total_tokens"]; got != float64(15) {
		t.Fatalf("unexpected usage.total_tokens: %v", got)
	}
	if got := usage["reasoning_tokens"]; got != float64(2) {
		t.Fatalf("unexpected usage.reasoning_tokens: %v", got)
	}
}

func TestWriteEventFromWorkflowResultTopLevelNerdstatsAndNullableUsage(t *testing.T) {
	var captured map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&captured); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	err = client.WriteEventFromWorkflowResult(context.Background(), WriteEventFromWorkflowResultInput{
		AgentID: "agent_support_v1",
		WorkflowResult: map[string]any{
			"workflow_id":   "email-chat-draft-or-clarify",
			"terminal_node": "ask_for_scenario",
			"nerdstats": map[string]any{
				"total_input_tokens":      999,
				"total_output_tokens":     888,
				"total_tokens":            777,
				"token_metrics_available": false,
				"token_metrics_source":    "provider_stream_usage_unavailable",
				"llm_nodes_without_usage": []any{"detect_scenario_context"},
				"total_elapsed_ms":        321,
			},
		},
	})
	if err != nil {
		t.Fatalf("write event from workflow result: %v", err)
	}

	payload, ok := captured["payload"].(map[string]any)
	if !ok {
		t.Fatalf("expected payload map, got %T", captured["payload"])
	}
	usage, ok := payload["usage"].(map[string]any)
	if !ok {
		t.Fatalf("expected usage map, got %T", payload["usage"])
	}
	if got := usage["prompt_tokens"]; got != nil {
		t.Fatalf("expected prompt_tokens nil, got %v", got)
	}
	if got := usage["completion_tokens"]; got != nil {
		t.Fatalf("expected completion_tokens nil, got %v", got)
	}
	if got := usage["total_tokens"]; got != nil {
		t.Fatalf("expected total_tokens nil, got %v", got)
	}
	if got := usage["reasoning_tokens"]; got != nil {
		t.Fatalf("expected reasoning_tokens nil, got %v", got)
	}
	if got := usage["token_metrics_available"]; got != false {
		t.Fatalf("expected token_metrics_available false, got %v", got)
	}
	if got := usage["token_metrics_source"]; got != "provider_stream_usage_unavailable" {
		t.Fatalf("unexpected token_metrics_source: %v", got)
	}
	if got := usage["total_elapsed_ms"]; got != float64(321) {
		t.Fatalf("unexpected usage.total_elapsed_ms: %v", got)
	}
}

func TestWriteEventSetsIdempotencyHeader(t *testing.T) {
	headers := http.Header{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		headers = r.Header.Clone()
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	err = client.WriteEvent(context.Background(), RuntimeEvent{
		EventType:      "runtime.workflow.completed",
		AgentID:        "agent_1",
		OrganizationID: "org_1",
		RunID:          "run_1",
		IdempotencyKey: "idem_1",
		Payload:        map[string]any{"ok": true},
	})
	if err != nil {
		t.Fatalf("write event: %v", err)
	}
	if headers.Get("Idempotency-Key") != "idem_1" {
		t.Fatalf("expected idempotency header, got %q", headers.Get("Idempotency-Key"))
	}
}

func TestRegisterRuntimeUsesCurrentPath(t *testing.T) {
	calledPath := ""
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calledPath = r.URL.Path
		w.WriteHeader(http.StatusCreated)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	err = client.RegisterRuntime(context.Background(), RuntimeRegistration{AgentID: "agent_1", AgentVersion: "v1", EndpointURL: "https://runtime.example", AuthMode: "jwt"})
	if err != nil {
		t.Fatalf("register runtime: %v", err)
	}
	if calledPath != "/v1/runtime/registrations" {
		t.Fatalf("unexpected register path: %s", calledPath)
	}
}

func TestRuntimeLifecycleHelpersUseCurrentPaths(t *testing.T) {
	calledPaths := make([]string, 0, 3)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calledPaths = append(calledPaths, r.URL.Path)
		if r.URL.Path == "/v1/runtime/registrations/reg_123/validate" {
			_ = json.NewEncoder(w).Encode(map[string]any{"validation_ok": true, "registration": map[string]any{"id": "reg_123"}})
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	if err := client.ActivateRuntimeRegistration(context.Background(), "reg_123"); err != nil {
		t.Fatalf("activate runtime registration: %v", err)
	}
	if err := client.DeactivateRuntimeRegistration(context.Background(), "reg_123"); err != nil {
		t.Fatalf("deactivate runtime registration: %v", err)
	}
	validation, err := client.ValidateRuntimeRegistration(context.Background(), "reg_123")
	if err != nil {
		t.Fatalf("validate runtime registration: %v", err)
	}

	if len(calledPaths) != 3 {
		t.Fatalf("expected three lifecycle calls, got %d", len(calledPaths))
	}
	if calledPaths[0] != "/v1/runtime/registrations/reg_123/activate" {
		t.Fatalf("unexpected activate path: %s", calledPaths[0])
	}
	if calledPaths[1] != "/v1/runtime/registrations/reg_123/deactivate" {
		t.Fatalf("unexpected deactivate path: %s", calledPaths[1])
	}
	if calledPaths[2] != "/v1/runtime/registrations/reg_123/validate" {
		t.Fatalf("unexpected validate path: %s", calledPaths[2])
	}
	if !validation.ValidationOK || validation.Registration.ID != "reg_123" {
		t.Fatalf("unexpected validation response: %+v", validation)
	}
}

func TestListChatHistoryMessages(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Fatalf("expected GET, got %s", r.Method)
		}
		if !strings.Contains(r.URL.RawQuery, "chat_id=chat_1") {
			t.Fatalf("expected chat_id query, got %s", r.URL.RawQuery)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"messages": []map[string]any{{"message_id": "m1"}}})
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	messages, err := client.ListChatHistoryMessages(context.Background(), ChatHistoryListInput{AgentID: "agent_1", ChatID: "chat_1", UserID: "user_1", Limit: 10})
	if err != nil {
		t.Fatalf("list chat history: %v", err)
	}
	if len(messages) != 1 || messages[0].MessageID != "m1" {
		t.Fatalf("unexpected messages: %+v", messages)
	}
}

func TestContractFixtureTelemetryEnvelopeWorkflowBasic(t *testing.T) {
	fixturePath := filepath.Join("..", "..", "contracts", "telemetry-envelope-v1", "workflow_basic.json")
	fixture := loadJSONFixtureMap(t, fixturePath)

	var captured map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&captured); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	if err := client.WriteEventFromWorkflowResult(context.Background(), WriteEventFromWorkflowResultInput{
		AgentID:        fixture["agent_id"].(string),
		WorkflowResult: fixture["workflow_result"],
	}); err != nil {
		t.Fatalf("write event from workflow result: %v", err)
	}

	expectedEvent := fixture["expected_event"].(map[string]any)
	if got := captured["event_type"]; got != expectedEvent["event_type"] {
		t.Fatalf("unexpected event_type: %v", got)
	}
	if got := captured["trace_id"]; got != expectedEvent["trace_id"] {
		t.Fatalf("unexpected trace_id: %v", got)
	}
	if got := captured["conversation_id"]; got != expectedEvent["conversation_id"] {
		t.Fatalf("unexpected conversation_id: %v", got)
	}
	if got := captured["request_id"]; got != expectedEvent["request_id"] {
		t.Fatalf("unexpected request_id: %v", got)
	}

	expectedPayload := fixture["expected_payload"].(map[string]any)
	payload := captured["payload"].(map[string]any)
	if got := payload["schema_version"]; got != expectedPayload["schema_version"] {
		t.Fatalf("unexpected schema_version: %v", got)
	}
	usage := payload["usage"].(map[string]any)
	expectedUsage := expectedPayload["usage"].(map[string]any)
	if got := usage["total_tokens"]; got != expectedUsage["total_tokens"] {
		t.Fatalf("unexpected usage.total_tokens: %v", got)
	}
	if got := usage["reasoning_tokens"]; got != expectedUsage["reasoning_tokens"] {
		t.Fatalf("unexpected usage.reasoning_tokens: %v", got)
	}
	modelUsage := payload["model_usage"].([]any)
	expectedFirstModel := expectedPayload["model_usage_first"].(map[string]any)
	if got := modelUsage[0].(map[string]any)["model"]; got != expectedFirstModel["model"] {
		t.Fatalf("unexpected model_usage[0].model: %v", got)
	}
}

func TestContractFixtureRuntimeRegistrationActionPaths(t *testing.T) {
	fixturePath := filepath.Join("..", "..", "contracts", "runtime-registration", "action_path_cases.json")
	raw, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	fixture := struct {
		Cases []struct {
			Template       string `json:"template"`
			RegistrationID string `json:"registration_id"`
			Expected       string `json:"expected"`
		} `json:"cases"`
	}{}
	if err := json.Unmarshal(raw, &fixture); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}

	client, err := NewClient(ClientConfig{BaseURL: "https://api.example"})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	for i := range fixture.Cases {
		actual, err := client.runtimeRegistrationActionPath(fixture.Cases[i].Template, fixture.Cases[i].RegistrationID)
		if err != nil {
			t.Fatalf("case %d unexpected error: %v", i, err)
		}
		if actual != fixture.Cases[i].Expected {
			t.Fatalf("case %d expected %q got %q", i, fixture.Cases[i].Expected, actual)
		}
	}
}
