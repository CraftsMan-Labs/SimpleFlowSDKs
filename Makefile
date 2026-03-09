.PHONY: help test test-go test-python lint-go fmt-go build-go build-python check-publish publish-python-dry publish-python publish-go-tag

GO_SDK_DIR ?= go/simpleflow
PYTHON_SDK_DIR ?= python
PYTHON_TEST_DIR ?= $(PYTHON_SDK_DIR)/tests
PYTHON_DIST_DIR ?= $(PYTHON_SDK_DIR)/dist
VERSION ?=

help:
	@echo "SimpleFlowSDKs developer commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test                - Run Go and Python tests"
	@echo "  make test-go             - Run Go SDK tests"
	@echo "  make test-python         - Run Python SDK tests"
	@echo ""
	@echo "Quality:"
	@echo "  make fmt-go              - Format Go files"
	@echo "  make lint-go             - Run go vet"
	@echo ""
	@echo "Build:"
	@echo "  make build-go            - Build Go SDK module"
	@echo "  make build-python        - Build Python sdist and wheel"
	@echo "  make check-publish       - Run release readiness checks"
	@echo ""
	@echo "Publish:"
	@echo "  make publish-python-dry  - Build Python artifacts only"
	@echo "  make publish-python      - Upload Python package with twine"
	@echo "  make publish-go-tag VERSION=vX.Y.Z - Tag and push for Go module release"

test: test-go test-python

test-go:
	cd $(GO_SDK_DIR) && go test ./...

test-python:
	cd $(PYTHON_SDK_DIR) && python -m unittest discover -s tests -p "test_*.py"

fmt-go:
	cd $(GO_SDK_DIR) && go fmt ./...

lint-go:
	cd $(GO_SDK_DIR) && go vet ./...

build-go:
	cd $(GO_SDK_DIR) && go build ./...

build-python:
	cd $(PYTHON_SDK_DIR) && python -m build

check-publish: test lint-go build-go build-python

publish-python-dry: build-python
	@echo "Python package built in $(PYTHON_DIST_DIR)"

publish-python: build-python
	cd $(PYTHON_SDK_DIR) && python -m twine upload dist/*

publish-go-tag:
	@if [ -z "$(VERSION)" ]; then \
		echo "VERSION is required. Example: make publish-go-tag VERSION=v0.1.1"; \
		exit 1; \
	fi
	git tag -a $(VERSION) -m "Release $(VERSION)"
	git push origin $(VERSION)
