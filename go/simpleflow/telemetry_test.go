package simpleflow

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestWithTelemetryRejectsInvalidSampleRate(t *testing.T) {
	client, err := NewClient(ClientConfig{BaseURL: "https://example.com"})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	rate := 1.2
	_, err = client.WithTelemetry(TelemetryConfig{Mode: TelemetryModeSimpleFlow, SampleRate: &rate})
	if err == nil {
		t.Fatalf("expected validation error")
	}
}

func TestEmitSpanWritesSimpleFlowEvent(t *testing.T) {
	called := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		defer r.Body.Close()
		payload := map[string]any{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		if payload["event_type"] != "runtime.telemetry.span" {
			t.Fatalf("unexpected event type: %v", payload["event_type"])
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client, err := NewClient(ClientConfig{BaseURL: server.URL})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	rate := 1.0
	emitter, err := client.WithTelemetry(TelemetryConfig{Mode: TelemetryModeSimpleFlow, SampleRate: &rate})
	if err != nil {
		t.Fatalf("with telemetry: %v", err)
	}

	err = emitter.EmitSpan(context.Background(), EmitSpanInput{
		AgentID:        "agent_1",
		OrganizationID: "org_1",
		RunID:          "run_1",
		TraceID:        "trace_1",
		Span: TelemetrySpan{
			Name:        "llm.call",
			StartTimeMS: 100,
			EndTimeMS:   120,
		},
	})
	if err != nil {
		t.Fatalf("emit span: %v", err)
	}
	if !called {
		t.Fatalf("expected runtime event request")
	}
}
