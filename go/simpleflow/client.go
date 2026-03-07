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
	RuntimeEventsPath   string
	ChatMessagesPath    string
	QueueContractsPath  string
	AuthorizationScheme string
}

type Client struct {
	baseURL             *url.URL
	httpClient          *http.Client
	apiToken            string
	runtimeEventsPath   string
	chatMessagesPath    string
	queueContractsPath  string
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
	authorizationScheme := strings.TrimSpace(cfg.AuthorizationScheme)
	if authorizationScheme == "" {
		authorizationScheme = "Bearer"
	}

	return &Client{
		baseURL:             parsed,
		httpClient:          httpClient,
		apiToken:            strings.TrimSpace(cfg.APIToken),
		runtimeEventsPath:   runtimeEventsPath,
		chatMessagesPath:    chatMessagesPath,
		queueContractsPath:  queueContractsPath,
		authorizationScheme: authorizationScheme,
	}, nil
}

func (c *Client) ReportRuntimeEvent(ctx context.Context, event RuntimeEvent) error {
	return c.postJSON(ctx, c.runtimeEventsPath, event)
}

func (c *Client) WriteChatMessage(ctx context.Context, message ChatMessageWrite) error {
	return c.postJSON(ctx, c.chatMessagesPath, message)
}

func (c *Client) PublishQueueContract(ctx context.Context, contract QueueContract) error {
	return c.postJSON(ctx, c.queueContractsPath, contract)
}

func (c *Client) postJSON(ctx context.Context, path string, body any) error {
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

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("simpleflow sdk request error: send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("simpleflow sdk request error: status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
	}

	return nil
}
