package simpleflow

import (
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func TestInvokeTokenVerifierWithSharedKeyHS256(t *testing.T) {
	verifier, err := NewInvokeTokenVerifierWithSharedKey(InvokeSharedKeyVerifierConfig{
		SharedKey: "local-secret",
		Issuer:    "simpleflow",
		Audience:  "runtime",
	})
	if err != nil {
		t.Fatalf("new verifier: %v", err)
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, InvokeTokenClaims{
		AgentID: "agent_1",
		OrgID:   "org_1",
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "simpleflow",
			Audience:  jwt.ClaimStrings{"runtime"},
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(5 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(time.Now().Add(-1 * time.Minute)),
		},
	})
	rawToken, err := token.SignedString([]byte("local-secret"))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}

	claims, err := verifier.Verify(rawToken)
	if err != nil {
		t.Fatalf("verify token: %v", err)
	}
	if claims.AgentID != "agent_1" || claims.OrgID != "org_1" {
		t.Fatalf("unexpected claims: %+v", claims)
	}
}

func TestInvokeTokenVerifierWithSharedKeyHS256RejectsMismatchedKey(t *testing.T) {
	verifier, err := NewInvokeTokenVerifierWithSharedKey(InvokeSharedKeyVerifierConfig{
		SharedKey: "local-secret",
		Issuer:    "simpleflow",
		Audience:  "runtime",
	})
	if err != nil {
		t.Fatalf("new verifier: %v", err)
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, InvokeTokenClaims{
		AgentID: "agent_1",
		OrgID:   "org_1",
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "simpleflow",
			Audience:  jwt.ClaimStrings{"runtime"},
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(5 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(time.Now().Add(-1 * time.Minute)),
		},
	})
	rawToken, err := token.SignedString([]byte("wrong-secret"))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}

	_, err = verifier.Verify(rawToken)
	if err == nil {
		t.Fatalf("expected verify failure for mismatched key")
	}
}

func TestInvokeTokenVerifierWithJWKSRS256Compatibility(t *testing.T) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generate rsa key: %v", err)
	}
	jwksPayload := map[string]any{
		"keys": []map[string]any{{
			"kty": "RSA",
			"kid": "test-key",
			"use": "sig",
			"alg": "RS256",
			"n":   base64.RawURLEncoding.EncodeToString(privateKey.PublicKey.N.Bytes()),
			"e":   base64.RawURLEncoding.EncodeToString(big.NewInt(int64(privateKey.PublicKey.E)).Bytes()),
		}},
	}

	jwksServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(jwksPayload)
	}))
	defer jwksServer.Close()

	verifier, err := NewInvokeTokenVerifier(InvokeTokenVerifierConfig{
		JWKSURL:  jwksServer.URL,
		Issuer:   "simpleflow",
		Audience: "runtime",
	})
	if err != nil {
		t.Fatalf("new verifier: %v", err)
	}
	defer verifier.Close()

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, InvokeTokenClaims{
		AgentID: "agent_1",
		OrgID:   "org_1",
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "simpleflow",
			Audience:  jwt.ClaimStrings{"runtime"},
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(5 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(time.Now().Add(-1 * time.Minute)),
		},
	})
	token.Header["kid"] = "test-key"
	rawToken, err := token.SignedString(privateKey)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}

	claims, err := verifier.Verify(rawToken)
	if err != nil {
		t.Fatalf("verify token: %v", err)
	}
	if claims.AgentID != "agent_1" || claims.OrgID != "org_1" {
		t.Fatalf("unexpected claims: %+v", claims)
	}
}
