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
