package simpleflow

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

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
		"run_id": "run_123",
		"metadata": map[string]any{
			"telemetry": map[string]any{
				"trace_id": "trace_123",
				"sampled":  true,
			},
			"trace": map[string]any{
				"tenant": map[string]any{
					"conversation_id": "chat_123",
					"request_id":      "req_123",
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
