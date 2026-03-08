package simpleflow

import (
	"context"
	"fmt"
	"hash/fnv"
	"math"
	"strings"
)

type TelemetryMode string

const (
	TelemetryModeSimpleFlow TelemetryMode = "simpleflow"
	TelemetryModeOTLP       TelemetryMode = "otlp"
)

type TelemetryConfig struct {
	Mode         TelemetryMode
	SampleRate   *float64
	OTLPSink     func(context.Context, TelemetrySpan) error
	DefaultTrace WorkflowTraceTenant
}

type TelemetryEmitter struct {
	client *Client
	cfg    TelemetryConfig
}

func (c *Client) WithTelemetry(cfg TelemetryConfig) (*TelemetryEmitter, error) {
	mode := strings.TrimSpace(string(cfg.Mode))
	if mode == "" {
		cfg.Mode = TelemetryModeSimpleFlow
	}
	if cfg.Mode != TelemetryModeSimpleFlow && cfg.Mode != TelemetryModeOTLP {
		return nil, fmt.Errorf("simpleflow sdk config error: telemetry mode must be one of simpleflow or otlp")
	}
	if cfg.SampleRate != nil {
		if math.IsNaN(*cfg.SampleRate) || math.IsInf(*cfg.SampleRate, 0) || *cfg.SampleRate < 0.0 || *cfg.SampleRate > 1.0 {
			return nil, fmt.Errorf("simpleflow sdk config error: telemetry sample_rate must be a finite value between 0.0 and 1.0")
		}
	}
	return &TelemetryEmitter{client: c, cfg: cfg}, nil
}

type EmitSpanInput struct {
	AgentID        string
	OrganizationID string
	RunID          string
	TraceID        string
	RequestID      string
	ConversationID string
	Span           TelemetrySpan
}

func (e *TelemetryEmitter) EmitSpan(ctx context.Context, input EmitSpanInput) error {
	if e == nil {
		return fmt.Errorf("simpleflow sdk telemetry error: emitter is nil")
	}

	traceID := strings.TrimSpace(input.TraceID)
	sampled := shouldSample(e.cfg.SampleRate, traceID)
	if !sampled {
		return nil
	}

	if e.cfg.Mode == TelemetryModeOTLP {
		if e.cfg.OTLPSink == nil {
			return nil
		}
		return e.cfg.OTLPSink(ctx, input.Span)
	}

	runID := strings.TrimSpace(input.RunID)
	if runID == "" {
		runID = strings.TrimSpace(e.cfg.DefaultTrace.RunID)
	}
	agentID := strings.TrimSpace(input.AgentID)
	if agentID == "" {
		agentID = strings.TrimSpace(e.cfg.DefaultTrace.AgentID)
	}
	conversationID := strings.TrimSpace(input.ConversationID)
	if conversationID == "" {
		conversationID = strings.TrimSpace(e.cfg.DefaultTrace.ConversationID)
	}
	requestID := strings.TrimSpace(input.RequestID)
	if requestID == "" {
		requestID = strings.TrimSpace(e.cfg.DefaultTrace.RequestID)
	}
	organizationID := strings.TrimSpace(input.OrganizationID)
	if organizationID == "" {
		organizationID = strings.TrimSpace(e.cfg.DefaultTrace.OrganizationID)
	}

	event := RuntimeEvent{
		EventType:      "runtime.telemetry.span",
		AgentID:        agentID,
		OrganizationID: organizationID,
		RunID:          runID,
		ConversationID: conversationID,
		RequestID:      requestID,
		TraceID:        traceID,
		Sampled:        boolPointer(true),
		Payload: map[string]any{
			"span": input.Span,
		},
	}
	return e.client.WriteEvent(ctx, event)
}

func boolPointer(value bool) *bool {
	return &value
}

func shouldSample(sampleRate *float64, traceID string) bool {
	if sampleRate == nil {
		return true
	}
	if *sampleRate <= 0 {
		return false
	}
	if *sampleRate >= 1 {
		return true
	}
	hasher := fnv.New64a()
	_, _ = hasher.Write([]byte(traceID))
	ratio := float64(hasher.Sum64()) / float64(math.MaxUint64)
	return ratio <= *sampleRate
}
