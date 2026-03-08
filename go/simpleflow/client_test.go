package simpleflow

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
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

	if got := captured["type"]; got != "runtime.workflow.completed" {
		t.Fatalf("unexpected type: %v", got)
	}
	if got := captured["trace_id"]; got != "trace_123" {
		t.Fatalf("unexpected trace_id: %v", got)
	}
	if got := captured["conversation_id"]; got != "chat_123" {
		t.Fatalf("unexpected conversation_id: %v", got)
	}
}
