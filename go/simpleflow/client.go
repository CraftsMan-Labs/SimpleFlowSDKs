package simpleflow

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

type ClientConfig struct {
	BaseURL               string
	APIToken              string
	HTTPClient            *http.Client
	RuntimeRegisterPath   string
	RuntimeInvokePath     string
	RuntimeEventsPath     string
	RuntimeActivatePath   string
	RuntimeDeactivatePath string
	RuntimeValidatePath   string
	ChatMessagesPath      string
	QueueContractsPath    string
	ChatHistoryPath       string
	AuthorizationScheme   string
}

type Client struct {
	baseURL               *url.URL
	httpClient            *http.Client
	apiToken              string
	runtimeRegisterPath   string
	runtimeInvokePath     string
	runtimeEventsPath     string
	runtimeActivatePath   string
	runtimeDeactivatePath string
	runtimeValidatePath   string
	chatMessagesPath      string
	queueContractsPath    string
	chatHistoryPath       string
	authorizationScheme   string
}

func NewClient(cfg ClientConfig) (*Client, error) {
	trimmed := strings.TrimSpace(cfg.BaseURL)
	if trimmed == "" {
		return nil, fmt.Errorf("simpleflow sdk config error: base url is required")
	}
	parsed, err := url.Parse(trimmed)
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk config error: invalid base url: %w", err)
	}
	if strings.TrimSpace(parsed.Scheme) == "" || strings.TrimSpace(parsed.Host) == "" {
		return nil, fmt.Errorf("simpleflow sdk config error: base url must include scheme and host")
	}

	httpClient := cfg.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}

	runtimeRegisterPath := cfg.RuntimeRegisterPath
	if strings.TrimSpace(runtimeRegisterPath) == "" {
		runtimeRegisterPath = "/v1/runtime/registrations"
	}
	runtimeInvokePath := cfg.RuntimeInvokePath
	if strings.TrimSpace(runtimeInvokePath) == "" {
		runtimeInvokePath = "/v1/runtime/invoke"
	}
	runtimeEventsPath := cfg.RuntimeEventsPath
	if strings.TrimSpace(runtimeEventsPath) == "" {
		runtimeEventsPath = "/v1/runtime/events"
	}
	runtimeActivatePath := cfg.RuntimeActivatePath
	if strings.TrimSpace(runtimeActivatePath) == "" {
		runtimeActivatePath = "/v1/runtime/registrations/{registration_id}/activate"
	}
	runtimeDeactivatePath := cfg.RuntimeDeactivatePath
	if strings.TrimSpace(runtimeDeactivatePath) == "" {
		runtimeDeactivatePath = "/v1/runtime/registrations/{registration_id}/deactivate"
	}
	runtimeValidatePath := cfg.RuntimeValidatePath
	if strings.TrimSpace(runtimeValidatePath) == "" {
		runtimeValidatePath = "/v1/runtime/registrations/{registration_id}/validate"
	}
	chatMessagesPath := cfg.ChatMessagesPath
	if strings.TrimSpace(chatMessagesPath) == "" {
		chatMessagesPath = "/v1/runtime/chat/messages"
	}
	queueContractsPath := cfg.QueueContractsPath
	if strings.TrimSpace(queueContractsPath) == "" {
		queueContractsPath = "/v1/runtime/queue/contracts"
	}
	chatHistoryPath := cfg.ChatHistoryPath
	if strings.TrimSpace(chatHistoryPath) == "" {
		chatHistoryPath = "/v1/chat/history/messages"
	}
	authorizationScheme := strings.TrimSpace(cfg.AuthorizationScheme)
	if authorizationScheme == "" {
		authorizationScheme = "Bearer"
	}

	return &Client{
		baseURL:               parsed,
		httpClient:            httpClient,
		apiToken:              strings.TrimSpace(cfg.APIToken),
		runtimeRegisterPath:   runtimeRegisterPath,
		runtimeInvokePath:     runtimeInvokePath,
		runtimeEventsPath:     runtimeEventsPath,
		runtimeActivatePath:   runtimeActivatePath,
		runtimeDeactivatePath: runtimeDeactivatePath,
		runtimeValidatePath:   runtimeValidatePath,
		chatMessagesPath:      chatMessagesPath,
		queueContractsPath:    queueContractsPath,
		chatHistoryPath:       chatHistoryPath,
		authorizationScheme:   authorizationScheme,
	}, nil
}

func (c *Client) RegisterRuntime(ctx context.Context, registration RuntimeRegistration) error {
	return c.postJSON(ctx, c.runtimeRegisterPath, registration)
}

func (c *Client) CreateRuntimeRegistration(ctx context.Context, registration RuntimeRegistration) (RuntimeRegistration, error) {
	created := RuntimeRegistration{}
	if err := c.postJSONWithResponse(ctx, c.runtimeRegisterPath, registration, &created); err != nil {
		return RuntimeRegistration{}, err
	}
	return created, nil
}

func (c *Client) ActivateRuntimeRegistration(ctx context.Context, registrationID string) error {
	path, err := c.runtimeRegistrationActionPath(c.runtimeActivatePath, registrationID)
	if err != nil {
		return err
	}
	return c.postJSON(ctx, path, map[string]any{})
}

func (c *Client) DeactivateRuntimeRegistration(ctx context.Context, registrationID string) error {
	path, err := c.runtimeRegistrationActionPath(c.runtimeDeactivatePath, registrationID)
	if err != nil {
		return err
	}
	return c.postJSON(ctx, path, map[string]any{})
}

func (c *Client) ValidateRuntimeRegistration(ctx context.Context, registrationID string) (RuntimeRegistrationValidationResult, error) {
	path, err := c.runtimeRegistrationActionPath(c.runtimeValidatePath, registrationID)
	if err != nil {
		return RuntimeRegistrationValidationResult{}, err
	}
	result := RuntimeRegistrationValidationResult{}
	err = c.postJSONWithResponse(ctx, path, map[string]any{}, &result)
	if err != nil {
		return RuntimeRegistrationValidationResult{}, err
	}
	return result, nil
}

func (c *Client) Invoke(ctx context.Context, request InvokeRequest) (InvokeResult, error) {
	result := InvokeResult{}
	err := c.postJSONWithResponse(ctx, c.runtimeInvokePath, request, &result)
	if err != nil {
		return InvokeResult{}, err
	}
	return result, nil
}

func (c *Client) WriteEvent(ctx context.Context, event RuntimeEvent) error {
	payload := map[string]any{
		"agent_id":        event.AgentID,
		"organization_id": event.OrganizationID,
		"run_id":          event.RunID,
		"event_type":      firstNonEmpty(strings.TrimSpace(event.EventType), strings.TrimSpace(event.Type)),
		"trace_id":        strings.TrimSpace(event.TraceID),
		"conversation_id": strings.TrimSpace(event.ConversationID),
		"request_id":      strings.TrimSpace(event.RequestID),
		"payload":         event.Payload,
	}
	if payload["payload"] == nil {
		payload["payload"] = map[string]any{}
	}
	if event.Sampled != nil {
		payload["sampled"] = *event.Sampled
	}
	headers := map[string]string{}
	if strings.TrimSpace(event.IdempotencyKey) != "" {
		headers["Idempotency-Key"] = strings.TrimSpace(event.IdempotencyKey)
	}
	return c.postJSONWithHeaders(ctx, c.runtimeEventsPath, payload, headers)
}

func (c *Client) ReportRuntimeEvent(ctx context.Context, event RuntimeEvent) error {
	return c.WriteEvent(ctx, event)
}

func (c *Client) WriteChatMessage(ctx context.Context, message ChatMessageWrite) error {
	payload := map[string]any{
		"agent_id":        message.AgentID,
		"organization_id": message.OrganizationID,
		"run_id":          message.RunID,
		"chat_id":         message.ChatID,
		"message_id":      message.MessageID,
		"role":            message.Role,
		"direction":       firstNonEmpty(strings.TrimSpace(message.Direction), "outbound"),
		"content":         message.Content,
		"metadata":        message.Metadata,
	}
	if payload["content"] == nil {
		payload["content"] = map[string]any{}
	}
	if payload["metadata"] == nil {
		payload["metadata"] = map[string]any{}
	}
	headers := map[string]string{}
	if strings.TrimSpace(message.IdempotencyKey) != "" {
		headers["Idempotency-Key"] = strings.TrimSpace(message.IdempotencyKey)
	}
	return c.postJSONWithHeaders(ctx, c.chatMessagesPath, payload, headers)
}

func (c *Client) PublishQueueContract(ctx context.Context, contract QueueContract) error {
	payload := map[string]any{
		"agent_id":         contract.AgentID,
		"organization_id":  contract.OrganizationID,
		"run_id":           contract.RunID,
		"queue_name":       contract.QueueName,
		"contract_name":    firstNonEmpty(strings.TrimSpace(contract.ContractName), strings.TrimSpace(contract.MessageID), "runtime.queue.contract"),
		"contract_version": firstNonEmpty(strings.TrimSpace(contract.ContractVersion), "v1"),
		"schema":           contract.Schema,
		"transport":        contract.Transport,
		"status":           firstNonEmpty(strings.TrimSpace(contract.Status), "draft"),
	}
	if payload["schema"] == nil {
		if contract.Payload != nil {
			payload["schema"] = contract.Payload
		} else {
			payload["schema"] = map[string]any{}
		}
	}
	if payload["transport"] == nil {
		payload["transport"] = map[string]any{}
	}
	headers := map[string]string{}
	if strings.TrimSpace(contract.IdempotencyKey) != "" {
		headers["Idempotency-Key"] = strings.TrimSpace(contract.IdempotencyKey)
	}
	return c.postJSONWithHeaders(ctx, c.queueContractsPath, payload, headers)
}

func (c *Client) ListChatHistoryMessages(ctx context.Context, input ChatHistoryListInput) ([]ChatHistoryMessage, error) {
	values := url.Values{}
	values.Set("agent_id", strings.TrimSpace(input.AgentID))
	values.Set("chat_id", strings.TrimSpace(input.ChatID))
	values.Set("user_id", strings.TrimSpace(input.UserID))
	if input.Limit > 0 {
		values.Set("limit", fmt.Sprintf("%d", input.Limit))
	}

	out := struct {
		Messages []ChatHistoryMessage `json:"messages"`
	}{}
	endpoint := c.baseURL.JoinPath(c.chatHistoryPath)
	query := endpoint.Query()
	for key, value := range values {
		for i := range value {
			query.Add(key, value[i])
		}
	}
	endpoint.RawQuery = query.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk request error: build request: %w", err)
	}
	if c.apiToken != "" {
		req.Header.Set("Authorization", c.authorizationScheme+" "+c.apiToken)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk request error: send request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, fmt.Errorf("simpleflow sdk request error: status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
	}
	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk request error: read response body: %w", err)
	}
	if len(responseBody) == 0 {
		return nil, nil
	}
	if err = json.Unmarshal(responseBody, &out); err != nil {
		return nil, err
	}
	return out.Messages, nil
}

func (c *Client) CreateChatHistoryMessage(ctx context.Context, message ChatHistoryMessage) (ChatHistoryMessage, error) {
	created := ChatHistoryMessage{}
	if err := c.postJSONWithResponse(ctx, c.chatHistoryPath, message, &created); err != nil {
		return ChatHistoryMessage{}, err
	}
	return created, nil
}

func (c *Client) UpdateChatHistoryMessage(ctx context.Context, message ChatHistoryMessage) (ChatHistoryMessage, error) {
	updated := ChatHistoryMessage{}
	path := strings.TrimRight(c.chatHistoryPath, "/") + "/" + strings.TrimSpace(message.MessageID)
	payload := map[string]any{
		"agent_id": message.AgentID,
		"chat_id":  message.ChatID,
		"user_id":  message.UserID,
		"content":  message.Content,
		"metadata": message.Metadata,
	}
	if err := c.patchJSONWithResponse(ctx, path, payload, &updated); err != nil {
		return ChatHistoryMessage{}, err
	}
	return updated, nil
}

type WriteEventFromWorkflowResultInput struct {
	AgentID        string
	OrganizationID string
	UserID         string
	EventType      string
	WorkflowResult any
	IncludeRaw     bool
}

func (c *Client) WriteEventFromWorkflowResult(ctx context.Context, input WriteEventFromWorkflowResultInput) error {
	agentID := strings.TrimSpace(input.AgentID)
	if agentID == "" {
		return fmt.Errorf("simpleflow sdk payload error: agent_id is required")
	}
	eventType := strings.TrimSpace(input.EventType)
	if eventType == "" {
		eventType = "runtime.workflow.completed"
	}

	normalizedResult, err := normalizeMap(input.WorkflowResult)
	if err != nil {
		return err
	}

	metadata := nestedMap(normalizedResult, "metadata")
	telemetry := nestedMap(metadata, "telemetry")
	trace := nestedMap(metadata, "trace")
	tenant := nestedMap(trace, "tenant")

	conversationID := stringValue(tenant, "conversation_id")
	if conversationID == "" {
		conversationID = stringValue(trace, "conversation_id")
	}
	requestID := stringValue(tenant, "request_id")
	if requestID == "" {
		requestID = stringValue(trace, "request_id")
	}
	runID := stringValue(tenant, "run_id")
	if runID == "" {
		runID = stringValue(normalizedResult, "run_id")
	}
	organizationID := firstNonEmpty(strings.TrimSpace(input.OrganizationID), stringValue(tenant, "organization_id"), stringValue(trace, "organization_id"), stringValue(normalizedResult, "organization_id"))
	userID := firstNonEmpty(strings.TrimSpace(input.UserID), stringValue(tenant, "user_id"), stringValue(trace, "user_id"), stringValue(normalizedResult, "user_id"))
	traceID := stringValue(telemetry, "trace_id")
	sampled := boolPointerValue(telemetry, "sampled")
	canonicalPayload := buildCanonicalTelemetryEnvelope(normalizedResult, agentID, organizationID, userID, runID, traceID, conversationID, requestID, sampled, input.IncludeRaw)

	event := RuntimeEvent{
		Type:           eventType,
		AgentID:        agentID,
		OrganizationID: organizationID,
		UserID:         userID,
		RunID:          runID,
		ConversationID: conversationID,
		RequestID:      requestID,
		TraceID:        traceID,
		Sampled:        sampled,
		Payload:        canonicalPayload,
	}

	return c.WriteEvent(ctx, event)
}

func buildCanonicalTelemetryEnvelope(
	workflowResult map[string]any,
	agentID string,
	organizationID string,
	userID string,
	runID string,
	traceID string,
	conversationID string,
	requestID string,
	sampled *bool,
	includeRaw bool,
) map[string]any {
	metadata := nestedMap(workflowResult, "metadata")
	traceRoot := nestedMap(metadata, "trace")
	telemetry := nestedMap(metadata, "telemetry")
	events := listValue(workflowResult, "events")
	eventCounts := countEventsByType(events)
	nerdstats := extractNerdstats(workflowResult, events)
	usage := buildUsage(nerdstats)
	modelUsage := buildModelUsage(nerdstats)
	toolUsage := buildToolUsage(eventCounts)

	workflowStatus := firstNonEmpty(stringValue(workflowResult, "status"), "completed")
	traceSampled := sampled
	if traceSampled == nil {
		traceSampled = boolPointerValue(telemetry, "sampled")
	}
	if traceSampled == nil {
		traceSampled = boolPointer(true)
	}

	payload := map[string]any{
		"schema_version": "telemetry-envelope.v1",
		"identity": map[string]any{
			"organization_id": strings.TrimSpace(organizationID),
			"agent_id":        strings.TrimSpace(agentID),
			"user_id":         strings.TrimSpace(userID),
		},
		"trace": map[string]any{
			"trace_id":        firstNonEmpty(strings.TrimSpace(traceID), stringValue(telemetry, "trace_id")),
			"span_id":         stringValue(traceRoot, "span_id"),
			"tenant_id":       stringValue(traceRoot, "tenant_id"),
			"conversation_id": strings.TrimSpace(conversationID),
			"request_id":      strings.TrimSpace(requestID),
			"run_id":          strings.TrimSpace(runID),
			"sampled":         *traceSampled,
		},
		"workflow": map[string]any{
			"workflow_id":      stringValue(workflowResult, "workflow_id"),
			"terminal_node":    stringValue(workflowResult, "terminal_node"),
			"status":           workflowStatus,
			"total_elapsed_ms": numericValue(workflowResult, "total_elapsed_ms"),
			"ttft_ms":          firstNumericOrNil(nerdstats, "ttft_ms"),
		},
		"usage":        usage,
		"model_usage":  modelUsage,
		"tool_usage":   toolUsage,
		"event_counts": eventCounts,
	}

	if len(nerdstats) > 0 {
		payload["nerdstats"] = nerdstats
	}
	if includeRaw {
		payload["raw"] = workflowResult
	}

	return payload
}

func extractNerdstats(workflowResult map[string]any, events []any) map[string]any {
	if topLevel, ok := workflowResult["nerdstats"].(map[string]any); ok {
		return topLevel
	}
	metadata := nestedMap(workflowResult, "metadata")
	if direct := nestedMap(metadata, "nerdstats"); len(direct) > 0 {
		return direct
	}
	for i := len(events) - 1; i >= 0; i-- {
		event, ok := events[i].(map[string]any)
		if !ok {
			continue
		}
		if strings.TrimSpace(stringAny(event["event_type"])) != "workflow_completed" {
			continue
		}
		eventMetadata, ok := event["metadata"].(map[string]any)
		if !ok {
			continue
		}
		if stats, ok := eventMetadata["nerdstats"].(map[string]any); ok {
			return stats
		}
	}
	return map[string]any{}
}

func buildUsage(nerdstats map[string]any) map[string]any {
	tokenMetricsAvailable := true
	if len(nerdstats) == 0 {
		tokenMetricsAvailable = false
	} else if value, ok := nerdstats["token_metrics_available"].(bool); ok {
		tokenMetricsAvailable = value
	}

	return map[string]any{
		"prompt_tokens":           usageTokenMetric(nerdstats, tokenMetricsAvailable, "total_input_tokens", "prompt_tokens"),
		"completion_tokens":       usageTokenMetric(nerdstats, tokenMetricsAvailable, "total_output_tokens", "completion_tokens"),
		"total_tokens":            usageTokenMetric(nerdstats, tokenMetricsAvailable, "total_tokens"),
		"reasoning_tokens":        usageTokenMetric(nerdstats, tokenMetricsAvailable, "total_reasoning_tokens", "reasoning_tokens"),
		"ttft_ms":                 firstNumericOrNil(nerdstats, "ttft_ms"),
		"total_elapsed_ms":        firstNumericOrNil(nerdstats, "total_elapsed_ms"),
		"tokens_per_second":       firstNumericOrNil(nerdstats, "tokens_per_second"),
		"token_metrics_available": tokenMetricsAvailable,
		"token_metrics_source":    stringValueOrNil(nerdstats, "token_metrics_source"),
		"llm_nodes_without_usage": stringListValue(nerdstats, "llm_nodes_without_usage"),
	}
}

func usageTokenMetric(nerdstats map[string]any, tokenMetricsAvailable bool, keys ...string) any {
	if !tokenMetricsAvailable {
		return nil
	}
	return firstNumericOrNil(nerdstats, keys...)
}

func buildModelUsage(nerdstats map[string]any) []map[string]any {
	stepDetails, _ := nerdstats["step_details"].([]any)
	totalsByModel := map[string]map[string]float64{}

	for i := range stepDetails {
		step, ok := stepDetails[i].(map[string]any)
		if !ok {
			continue
		}
		modelName := strings.TrimSpace(stringAny(step["model_name"]))
		if modelName == "" {
			continue
		}
		bucket, ok := totalsByModel[modelName]
		if !ok {
			bucket = map[string]float64{"request_count": 0}
			totalsByModel[modelName] = bucket
		}
		bucket["request_count"] += 1
		bucket["prompt_tokens"] += floatNumericValue(step, "prompt_tokens")
		bucket["completion_tokens"] += floatNumericValue(step, "completion_tokens")
		bucket["total_tokens"] += floatNumericValue(step, "total_tokens")
		bucket["reasoning_tokens"] += floatNumericValue(step, "reasoning_tokens")
		bucket["elapsed_ms"] += floatNumericValue(step, "elapsed_ms")
	}

	if modelsByNode, ok := nerdstats["llm_node_models"].(map[string]any); ok {
		for _, rawModel := range modelsByNode {
			modelName := strings.TrimSpace(stringAny(rawModel))
			if modelName == "" {
				continue
			}
			if _, exists := totalsByModel[modelName]; !exists {
				totalsByModel[modelName] = map[string]float64{"request_count": 0}
			}
		}
	}

	modelNames := make([]string, 0, len(totalsByModel))
	for modelName := range totalsByModel {
		modelNames = append(modelNames, modelName)
	}
	sort.Strings(modelNames)

	rows := make([]map[string]any, 0, len(modelNames))
	for i := range modelNames {
		modelName := modelNames[i]
		bucket := totalsByModel[modelName]
		rows = append(rows, map[string]any{
			"model":             modelName,
			"request_count":     int64(bucket["request_count"]),
			"prompt_tokens":     int64(bucket["prompt_tokens"]),
			"completion_tokens": int64(bucket["completion_tokens"]),
			"total_tokens":      int64(bucket["total_tokens"]),
			"reasoning_tokens":  int64(bucket["reasoning_tokens"]),
			"elapsed_ms":        int64(bucket["elapsed_ms"]),
		})
	}
	return rows
}

func buildToolUsage(eventCounts map[string]int64) []map[string]any {
	started := eventCounts["node_tool_start"]
	completed := eventCounts["node_tool_completed"]
	failed := eventCounts["node_tool_error"]
	if started == 0 && completed == 0 && failed == 0 {
		return []map[string]any{}
	}
	return []map[string]any{{
		"tool":            "workflow_tools",
		"started_count":   started,
		"completed_count": completed,
		"error_count":     failed,
	}}
}

func countEventsByType(events []any) map[string]int64 {
	counts := map[string]int64{}
	for i := range events {
		event, ok := events[i].(map[string]any)
		if !ok {
			continue
		}
		eventType := strings.TrimSpace(stringAny(event["event_type"]))
		if eventType == "" {
			continue
		}
		counts[eventType] += 1
	}
	return counts
}

func listValue(root map[string]any, key string) []any {
	raw, ok := root[key]
	if !ok || raw == nil {
		return []any{}
	}
	switch values := raw.(type) {
	case []any:
		return values
	case []map[string]any:
		list := make([]any, 0, len(values))
		for i := range values {
			list = append(list, values[i])
		}
		return list
	default:
		return []any{}
	}
}

func stringAny(value any) string {
	if value == nil {
		return ""
	}
	switch v := value.(type) {
	case string:
		return v
	default:
		return fmt.Sprintf("%v", value)
	}
}

func firstNumericOrNil(root map[string]any, keys ...string) any {
	for i := range keys {
		if value, ok := numericValueWithOK(root, keys[i]); ok {
			return value
		}
	}
	return nil
}

func numericValue(root map[string]any, key string) any {
	value, _ := numericValueWithOK(root, key)
	return value
}

func numericValueWithOK(root map[string]any, key string) (any, bool) {
	raw, ok := root[key]
	if !ok || raw == nil {
		return int64(0), false
	}
	switch v := raw.(type) {
	case int:
		return int64(v), true
	case int8:
		return int64(v), true
	case int16:
		return int64(v), true
	case int32:
		return int64(v), true
	case int64:
		return v, true
	case uint:
		return int64(v), true
	case uint8:
		return int64(v), true
	case uint16:
		return int64(v), true
	case uint32:
		return int64(v), true
	case uint64:
		return int64(v), true
	case float32:
		return float64(v), true
	case float64:
		return v, true
	default:
		return int64(0), false
	}
}

func stringValueOrNil(root map[string]any, key string) any {
	value := stringValue(root, key)
	if value == "" {
		return nil
	}
	return value
}

func stringListValue(root map[string]any, key string) []string {
	raw, ok := root[key]
	if !ok || raw == nil {
		return []string{}
	}
	values, ok := raw.([]any)
	if !ok {
		return []string{}
	}
	result := make([]string, 0, len(values))
	for i := range values {
		text := strings.TrimSpace(stringAny(values[i]))
		if text != "" {
			result = append(result, text)
		}
	}
	return result
}

func floatNumericValue(root map[string]any, key string) float64 {
	raw, ok := root[key]
	if !ok || raw == nil {
		return 0
	}
	switch v := raw.(type) {
	case int:
		return float64(v)
	case int8:
		return float64(v)
	case int16:
		return float64(v)
	case int32:
		return float64(v)
	case int64:
		return float64(v)
	case uint:
		return float64(v)
	case uint8:
		return float64(v)
	case uint16:
		return float64(v)
	case uint32:
		return float64(v)
	case uint64:
		return float64(v)
	case float32:
		return float64(v)
	case float64:
		return v
	default:
		return 0
	}
}

func (c *Client) postJSON(ctx context.Context, path string, body any) error {
	return c.postJSONWithHeaders(ctx, path, body, nil)
}

func (c *Client) postJSONWithHeaders(ctx context.Context, path string, body any, extraHeaders map[string]string) error {
	return c.postJSONWithResponseAndHeaders(ctx, path, body, nil, extraHeaders)
}

func (c *Client) postJSONWithResponse(ctx context.Context, path string, body any, out any) error {
	return c.postJSONWithResponseAndHeaders(ctx, path, body, out, nil)
}

func (c *Client) postJSONWithResponseAndHeaders(ctx context.Context, path string, body any, out any, extraHeaders map[string]string) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: marshal body: %w", err)
	}

	relativePath := strings.TrimSpace(path)
	if !strings.HasPrefix(relativePath, "/") {
		relativePath = "/" + relativePath
	}

	endpoint := c.baseURL.JoinPath(relativePath)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.String(), bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiToken != "" {
		req.Header.Set("Authorization", c.authorizationScheme+" "+c.apiToken)
	}
	for key, value := range extraHeaders {
		if strings.TrimSpace(value) != "" {
			req.Header.Set(key, value)
		}
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("simpleflow sdk request error: status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
	}

	if out != nil {
		responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
		if err != nil {
			return fmt.Errorf("simpleflow sdk request error: read response body: %w", err)
		}
		if len(responseBody) == 0 {
			return fmt.Errorf("simpleflow sdk request error: empty response body")
		}
		if err := json.Unmarshal(responseBody, out); err != nil {
			return fmt.Errorf("simpleflow sdk request error: decode response body: %w", err)
		}
	}

	return nil
}

func (c *Client) patchJSONWithResponse(ctx context.Context, path string, body any, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: marshal body: %w", err)
	}
	relativePath := strings.TrimSpace(path)
	if !strings.HasPrefix(relativePath, "/") {
		relativePath = "/" + relativePath
	}
	endpoint := c.baseURL.JoinPath(relativePath)
	req, err := http.NewRequestWithContext(ctx, http.MethodPatch, endpoint.String(), bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiToken != "" {
		req.Header.Set("Authorization", c.authorizationScheme+" "+c.apiToken)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: send request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("simpleflow sdk request error: status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
	}
	if out == nil {
		return nil
	}
	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: read response body: %w", err)
	}
	if len(responseBody) == 0 {
		return fmt.Errorf("simpleflow sdk request error: empty response body")
	}
	if err = json.Unmarshal(responseBody, out); err != nil {
		return fmt.Errorf("simpleflow sdk request error: decode response body: %w", err)
	}
	return nil
}

func (c *Client) getJSON(ctx context.Context, path string, out any) error {
	relativePath := strings.TrimSpace(path)
	if !strings.HasPrefix(relativePath, "/") {
		relativePath = "/" + relativePath
	}
	endpoint := c.baseURL.JoinPath(relativePath)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: build request: %w", err)
	}
	if c.apiToken != "" {
		req.Header.Set("Authorization", c.authorizationScheme+" "+c.apiToken)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: send request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("simpleflow sdk request error: status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
	}
	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: read response body: %w", err)
	}
	if len(responseBody) == 0 {
		return fmt.Errorf("simpleflow sdk request error: empty response body")
	}
	if err = json.Unmarshal(responseBody, out); err != nil {
		return fmt.Errorf("simpleflow sdk request error: decode response body: %w", err)
	}
	return nil
}

func normalizeMap(payload any) (map[string]any, error) {
	if payload == nil {
		return map[string]any{}, nil
	}
	if direct, ok := payload.(map[string]any); ok {
		return direct, nil
	}

	encoded, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk payload error: marshal workflow result: %w", err)
	}
	decoded := map[string]any{}
	if err := json.Unmarshal(encoded, &decoded); err != nil {
		return nil, fmt.Errorf("simpleflow sdk payload error: normalize workflow result: %w", err)
	}
	return decoded, nil
}

func nestedMap(root map[string]any, key string) map[string]any {
	raw, ok := root[key]
	if !ok || raw == nil {
		return map[string]any{}
	}
	nested, ok := raw.(map[string]any)
	if !ok {
		return map[string]any{}
	}
	return nested
}

func stringValue(root map[string]any, key string) string {
	raw, ok := root[key]
	if !ok || raw == nil {
		return ""
	}
	text, ok := raw.(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(text)
}

func boolPointerValue(root map[string]any, key string) *bool {
	raw, ok := root[key]
	if !ok || raw == nil {
		return nil
	}
	value, ok := raw.(bool)
	if !ok {
		return nil
	}
	return &value
}

func firstNonEmpty(values ...string) string {
	for i := range values {
		if strings.TrimSpace(values[i]) != "" {
			return strings.TrimSpace(values[i])
		}
	}
	return ""
}

func (c *Client) runtimeRegistrationActionPath(templatePath string, registrationID string) (string, error) {
	trimmedID := strings.TrimSpace(registrationID)
	if trimmedID == "" {
		return "", fmt.Errorf("simpleflow sdk payload error: registration_id is required")
	}
	trimmedPath := strings.TrimSpace(templatePath)
	if trimmedPath == "" {
		return "", fmt.Errorf("simpleflow sdk config error: runtime registration path is required")
	}
	if strings.Contains(trimmedPath, "{registration_id}") {
		return strings.ReplaceAll(trimmedPath, "{registration_id}", trimmedID), nil
	}
	if strings.HasSuffix(trimmedPath, "/") {
		return trimmedPath + trimmedID, nil
	}
	return trimmedPath + "/" + trimmedID, nil
}
