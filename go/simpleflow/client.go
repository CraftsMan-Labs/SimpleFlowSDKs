package simpleflow

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type ClientConfig struct {
	BaseURL             string
	APIToken            string
	HTTPClient          *http.Client
	RuntimeRegisterPath string
	RuntimeInvokePath   string
	RuntimeEventsPath   string
	ChatMessagesPath    string
	QueueContractsPath  string
	ChatHistoryPath     string
	AuthorizationScheme string
}

type Client struct {
	baseURL             *url.URL
	httpClient          *http.Client
	apiToken            string
	runtimeRegisterPath string
	runtimeInvokePath   string
	runtimeEventsPath   string
	chatMessagesPath    string
	queueContractsPath  string
	chatHistoryPath     string
	authorizationScheme string
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
		baseURL:             parsed,
		httpClient:          httpClient,
		apiToken:            strings.TrimSpace(cfg.APIToken),
		runtimeRegisterPath: runtimeRegisterPath,
		runtimeInvokePath:   runtimeInvokePath,
		runtimeEventsPath:   runtimeEventsPath,
		chatMessagesPath:    chatMessagesPath,
		queueContractsPath:  queueContractsPath,
		chatHistoryPath:     chatHistoryPath,
		authorizationScheme: authorizationScheme,
	}, nil
}

func (c *Client) RegisterRuntime(ctx context.Context, registration RuntimeRegistration) error {
	return c.postJSON(ctx, c.runtimeRegisterPath, registration)
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
	EventType      string
	WorkflowResult any
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
	traceID := stringValue(telemetry, "trace_id")
	sampled := boolPointerValue(telemetry, "sampled")

	event := RuntimeEvent{
		Type:           eventType,
		AgentID:        agentID,
		RunID:          runID,
		ConversationID: conversationID,
		RequestID:      requestID,
		TraceID:        traceID,
		Sampled:        sampled,
		Payload:        normalizedResult,
	}

	return c.WriteEvent(ctx, event)
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
