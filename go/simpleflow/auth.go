package simpleflow

import (
	"fmt"
	"strings"

	"github.com/MicahParks/keyfunc/v2"
	"github.com/golang-jwt/jwt/v5"
)

type InvokeTokenVerifierConfig struct {
	JWKSURL  string
	Issuer   string
	Audience string
}

type InvokeTokenClaims struct {
	AgentID string `json:"agent_id"`
	OrgID   string `json:"org_id"`
	UserID  string `json:"user_id"`
	Role    string `json:"role"`
	RunID   string `json:"run_id"`
	jwt.RegisteredClaims
}

type InvokeTokenVerifier struct {
	issuer   string
	audience string
	jwks     *keyfunc.JWKS
	keyfunc  jwt.Keyfunc
	methods  []string
}

func NewInvokeTokenVerifier(cfg InvokeTokenVerifierConfig) (*InvokeTokenVerifier, error) {
	jwksURL := strings.TrimSpace(cfg.JWKSURL)
	if jwksURL == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: jwks url is required")
	}
	issuer := strings.TrimSpace(cfg.Issuer)
	if issuer == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: issuer is required")
	}
	audience := strings.TrimSpace(cfg.Audience)
	if audience == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: audience is required")
	}

	jwks, err := keyfunc.Get(jwksURL, keyfunc.Options{RefreshUnknownKID: true})
	if err != nil {
		return nil, fmt.Errorf("simpleflow sdk auth config error: load jwks: %w", err)
	}

	return &InvokeTokenVerifier{
		issuer:   issuer,
		audience: audience,
		jwks:     jwks,
		keyfunc:  jwks.Keyfunc,
		methods:  []string{"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"},
	}, nil
}

type InvokeSharedKeyVerifierConfig struct {
	SharedKey string
	Issuer    string
	Audience  string
}

func NewInvokeTokenVerifierWithSharedKey(cfg InvokeSharedKeyVerifierConfig) (*InvokeTokenVerifier, error) {
	sharedKey := strings.TrimSpace(cfg.SharedKey)
	if sharedKey == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: shared key is required")
	}
	issuer := strings.TrimSpace(cfg.Issuer)
	if issuer == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: issuer is required")
	}
	audience := strings.TrimSpace(cfg.Audience)
	if audience == "" {
		return nil, fmt.Errorf("simpleflow sdk auth config error: audience is required")
	}

	sharedKeyBytes := []byte(sharedKey)
	return &InvokeTokenVerifier{
		issuer:   issuer,
		audience: audience,
		methods:  []string{"HS256"},
		keyfunc: func(*jwt.Token) (any, error) {
			return sharedKeyBytes, nil
		},
	}, nil
}

func (v *InvokeTokenVerifier) Close() {
	if v.jwks != nil {
		v.jwks.EndBackground()
	}
}

func (v *InvokeTokenVerifier) Verify(rawToken string) (InvokeTokenClaims, error) {
	claims := InvokeTokenClaims{}
	trimmed := strings.TrimSpace(rawToken)
	if trimmed == "" {
		return claims, fmt.Errorf("simpleflow sdk auth error: token is required")
	}

	if v.keyfunc == nil {
		return InvokeTokenClaims{}, fmt.Errorf("simpleflow sdk auth error: verifier is not configured")
	}
	if len(v.methods) == 0 {
		return InvokeTokenClaims{}, fmt.Errorf("simpleflow sdk auth error: verifier valid methods are not configured")
	}

	parsed, err := jwt.ParseWithClaims(trimmed, &claims, v.keyfunc,
		jwt.WithIssuer(v.issuer),
		jwt.WithAudience(v.audience),
		jwt.WithValidMethods(v.methods),
	)
	if err != nil {
		return InvokeTokenClaims{}, fmt.Errorf("simpleflow sdk auth error: verify token: %w", err)
	}
	if parsed == nil || !parsed.Valid {
		return InvokeTokenClaims{}, fmt.Errorf("simpleflow sdk auth error: token is invalid")
	}

	if strings.TrimSpace(claims.AgentID) == "" || strings.TrimSpace(claims.OrgID) == "" {
		return InvokeTokenClaims{}, fmt.Errorf("simpleflow sdk auth error: token missing required agent or org claims")
	}

	return claims, nil
}
