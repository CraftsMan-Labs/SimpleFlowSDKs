.PHONY: help test test-go test-python test-node lint-go fmt-go build-go build-python build-node docs-dev docs-build docs-preview check-publish check-publish-all publish-python-dry publish-python publish-node-dry publish-node publish-node-doppler npm-login publish-all publish-go-tag version-get version-sync version-next-patch version-next-minor version-next-major version-patch version-minor version-major version-set tag-release release-commit-tag-push release-patch release-minor release-major release-set

GO_SDK_DIR ?= go/simpleflow
PYTHON_SDK_DIR ?= python
NODE_SDK_DIR ?= node/simpleflow_sdk
DOCS_DIR ?= docs
PYTHON_TEST_DIR ?= $(PYTHON_SDK_DIR)/tests
PYTHON_DIST_DIR ?= $(PYTHON_SDK_DIR)/dist
PYTHON_BUILD_TMP ?= /tmp/simpleflow-sdk-python-build
NODE_PACK_TMP ?= /tmp/simpleflow-sdk-node-pack
PYTHON_PYPROJECT ?= $(PYTHON_SDK_DIR)/pyproject.toml
NODE_PACKAGE_JSON ?= $(NODE_SDK_DIR)/package.json
VERSION ?=
DOPPLER_RUN ?= doppler run --command
NPM_OTP ?=
AUTO_GIT ?= 0
PUBLISH_CHECK_URL ?= https://pypi.org/simple

help:
	@echo "SimpleFlowSDKs developer commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test                - Run Go, Python, and Node tests"
	@echo "  make test-go             - Run Go SDK tests"
	@echo "  make test-python         - Run Python SDK tests"
	@echo "  make test-node           - Run Node SDK tests"
	@echo ""
	@echo "Quality:"
	@echo "  make fmt-go              - Format Go files"
	@echo "  make lint-go             - Run go vet"
	@echo ""
	@echo "Build:"
	@echo "  make build-go            - Build Go SDK module"
	@echo "  make build-python        - Build Python sdist and wheel"
	@echo "  make build-node          - Build Node package tarball"
	@echo "  make docs-dev            - Run VitePress docs locally"
	@echo "  make docs-build          - Build VitePress docs site"
	@echo "  make docs-preview        - Preview built VitePress docs site"
	@echo "  make check-publish       - Run release readiness checks"
	@echo "  make check-publish-all   - Run checks plus dry-run publish checks"
	@echo ""
	@echo "Publish:"
	@echo "  make publish-python-dry  - Build Python artifacts only"
	@echo "  make publish-python      - Upload Python package with Doppler + uv publish"
	@echo "  make publish-node-dry    - Run npm publish dry-run"
	@echo "  make publish-node        - Upload Node package with npm publish"
	@echo "  make publish-node-doppler - Upload Node package with Doppler + npm publish"
	@echo "  make npm-login           - Login to npm locally"
	@echo "  make publish-all         - Publish Python and Node packages"
	@echo ""
	@echo "Versioning:"
	@echo "  make version-get         - Show current SDK version (Python source of truth)"
	@echo "  make version-sync        - Sync Node package version to Python version"
	@echo "  make version-patch       - Bump patch version across Python + Node"
	@echo "  make version-minor       - Bump minor version across Python + Node"
	@echo "  make version-major       - Bump major version across Python + Node"
	@echo "  make version-set VERSION=X.Y.Z - Set version across Python + Node"
	@echo "  make release-patch       - Bump patch, commit, tag, and push"
	@echo "  make release-minor       - Bump minor, commit, tag, and push"
	@echo "  make release-major       - Bump major, commit, tag, and push"
	@echo "  make release-set VERSION=X.Y.Z - Set version, commit, tag, and push"
	@echo "  make tag-release         - Create git tag v<current-version>"
	@echo "  make publish-go-tag VERSION=vX.Y.Z - Tag and push for Go module release"

test: test-go test-python test-node

test-go:
	cd $(GO_SDK_DIR) && go test ./...

test-python:
	cd $(PYTHON_SDK_DIR) && python -m unittest discover -s tests -p "test_*.py"

test-node:
	cd $(NODE_SDK_DIR) && npm test

fmt-go:
	cd $(GO_SDK_DIR) && go fmt ./...

lint-go:
	cd $(GO_SDK_DIR) && go vet ./...

build-go:
	cd $(GO_SDK_DIR) && go build ./...

build-python:
	rm -rf "$(PYTHON_BUILD_TMP)"
	rm -rf "$(PYTHON_DIST_DIR)"
	mkdir -p "$(PYTHON_BUILD_TMP)"
	rsync -a --delete --exclude 'dist' --exclude '*.egg-info' "$(PYTHON_SDK_DIR)/" "$(PYTHON_BUILD_TMP)/"
	cd "$(PYTHON_BUILD_TMP)" && uv build
	mkdir -p "$(PYTHON_DIST_DIR)"
	cp -f "$(PYTHON_BUILD_TMP)/dist/"* "$(PYTHON_DIST_DIR)/"

build-node:
	rm -rf "$(NODE_PACK_TMP)"
	mkdir -p "$(NODE_PACK_TMP)"
	cd "$(NODE_SDK_DIR)" && npm pack --pack-destination "$(NODE_PACK_TMP)"

docs-dev:
	cd "$(DOCS_DIR)" && npm install && npm run docs:dev

docs-build:
	cd "$(DOCS_DIR)" && npm install && npm run docs:build

docs-preview:
	cd "$(DOCS_DIR)" && npm install && npm run docs:preview

check-publish: test lint-go build-go build-python build-node

check-publish-all: check-publish publish-python-dry publish-node-dry

publish-python-dry: build-python
	@echo "Python package built in $(PYTHON_DIST_DIR)"

publish-python: build-python
	$(DOPPLER_RUN) 'TOKEN_SOURCE=$$(if [ -n "$$V_PUBLISH_TOKEN" ]; then echo V_PUBLISH_TOKEN; elif [ -n "$$UV_PUBLISH_TOKEN" ]; then echo UV_PUBLISH_TOKEN; else echo NONE; fi); \
	TOKEN_VALUE=$${V_PUBLISH_TOKEN:-$${UV_PUBLISH_TOKEN}}; \
	VERSION_VALUE=$$($(MAKE) --no-print-directory version-get); \
	set -- "$(PYTHON_DIST_DIR)"/simpleflow_sdk-$$VERSION_VALUE*; \
	if [ "$$1" = "$(PYTHON_DIST_DIR)/simpleflow_sdk-$$VERSION_VALUE*" ]; then echo "[publish-python] missing dist artifacts for version $$VERSION_VALUE"; exit 1; fi; \
	echo "[publish-python] token_source=$$TOKEN_SOURCE token_len=$${#TOKEN_VALUE}"; \
	if [ -z "$$TOKEN_VALUE" ]; then echo "[publish-python] missing V_PUBLISH_TOKEN/UV_PUBLISH_TOKEN"; exit 1; fi; \
	UV_PUBLISH_TOKEN=$$TOKEN_VALUE uv publish --check-url "$${UV_PUBLISH_CHECK_URL:-$(PUBLISH_CHECK_URL)}" "$$@"'

publish-node-dry:
	cd "$(NODE_SDK_DIR)" && npm publish --access public --dry-run

publish-node: build-node
	@set -e; \
	cd "$(NODE_SDK_DIR)"; \
	token=$${NPM_TOKEN:-$$NODE_AUTH_TOKEN}; \
	otp_arg=""; \
	if [ -n "$(NPM_OTP)" ]; then otp_arg="--otp $(NPM_OTP)"; fi; \
	if [ -n "$$token" ]; then \
		tmp_npmrc=$$(mktemp); \
		trap 'rm -f "$$tmp_npmrc"' EXIT; \
		printf 'registry=https://registry.npmjs.org/\n//registry.npmjs.org/:_authToken=%s\n' "$$token" > "$$tmp_npmrc"; \
		echo '==> Using token-based npm auth (NPM_TOKEN/NODE_AUTH_TOKEN)'; \
		NPM_CONFIG_USERCONFIG="$$tmp_npmrc" npm whoami; \
		NPM_CONFIG_USERCONFIG="$$tmp_npmrc" npm publish --access public $$otp_arg; \
	else \
		echo '==> No token provided; using local npm session (~/.npmrc)'; \
		echo '==> If this fails, run: make npm-login'; \
		npm whoami; \
		npm publish --access public $$otp_arg; \
	fi

publish-node-doppler: build-node
	$(DOPPLER_RUN) '$(MAKE) --no-print-directory publish-node NPM_OTP=$(NPM_OTP)'

npm-login:
	cd "$(NODE_SDK_DIR)" && npm login

publish-all: publish-python publish-node

version-get:
	@awk -F '"' '/^version = / {print $$2; exit}' "$(PYTHON_PYPROJECT)"

version-sync:
	@version=$$(awk -F '"' '/^version = / {print $$2; exit}' "$(PYTHON_PYPROJECT)"); \
	node -e "const fs=require('fs'); const p=process.argv[1]; const v=process.argv[2]; const j=JSON.parse(fs.readFileSync(p,'utf8')); j.version=v; fs.writeFileSync(p, JSON.stringify(j, null, 2)+'\\n');" "$(NODE_PACKAGE_JSON)" "$$version"; \
	echo "Synced Node package version -> $$version"

version-next-patch:
	@current=$$($(MAKE) --no-print-directory version-get); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	echo "$$major.$$minor.$$((patch + 1))"

version-next-minor:
	@current=$$($(MAKE) --no-print-directory version-get); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	echo "$$major.$$((minor + 1)).0"

version-next-major:
	@current=$$($(MAKE) --no-print-directory version-get); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	echo "$$((major + 1)).0.0"

version-patch:
	@$(MAKE) --no-print-directory version-set VERSION=$$($(MAKE) --no-print-directory version-next-patch)
	@if [ "$(AUTO_GIT)" = "1" ]; then $(MAKE) --no-print-directory release-commit-tag-push; fi

version-minor:
	@$(MAKE) --no-print-directory version-set VERSION=$$($(MAKE) --no-print-directory version-next-minor)
	@if [ "$(AUTO_GIT)" = "1" ]; then $(MAKE) --no-print-directory release-commit-tag-push; fi

version-major:
	@$(MAKE) --no-print-directory version-set VERSION=$$($(MAKE) --no-print-directory version-next-major)
	@if [ "$(AUTO_GIT)" = "1" ]; then $(MAKE) --no-print-directory release-commit-tag-push; fi

version-set:
	@if [ -z "$(VERSION)" ]; then \
		echo "VERSION is required. Example: make version-set VERSION=0.1.1"; \
		exit 1; \
	fi
	@sed -i.bak 's/^version = ".*"/version = "$(VERSION)"/' "$(PYTHON_PYPROJECT)" && rm -f "$(PYTHON_PYPROJECT).bak"
	@node -e "const fs=require('fs'); const p=process.argv[1]; const v=process.argv[2]; const j=JSON.parse(fs.readFileSync(p,'utf8')); j.version=v; fs.writeFileSync(p, JSON.stringify(j, null, 2)+'\n');" "$(NODE_PACKAGE_JSON)" "$(VERSION)"
	@echo "Updated versions -> Python + Node = $(VERSION)"
	@if [ "$(AUTO_GIT)" = "1" ]; then $(MAKE) --no-print-directory release-commit-tag-push; fi

release-commit-tag-push:
	@set -e; \
	version=$$($(MAKE) --no-print-directory version-get); \
	if [ -n "$$(git status --short --untracked-files=no | awk '$$2 != "$(PYTHON_PYPROJECT)" && $$2 != "$(NODE_PACKAGE_JSON)" {print}')" ]; then \
		echo "Refusing auto release: unrelated tracked changes detected"; \
		exit 1; \
	fi; \
	if git diff --quiet -- "$(PYTHON_PYPROJECT)" "$(NODE_PACKAGE_JSON)" && git diff --cached --quiet -- "$(PYTHON_PYPROJECT)" "$(NODE_PACKAGE_JSON)"; then \
		echo "No version changes to commit"; \
		exit 1; \
	fi; \
	git add "$(PYTHON_PYPROJECT)" "$(NODE_PACKAGE_JSON)"; \
	git commit -m "chore(release): bump sdk version to $$version"; \
	if git rev-parse "v$$version" >/dev/null 2>&1; then \
		echo "Tag v$$version already exists"; \
		exit 1; \
	fi; \
	git tag -a "v$$version" -m "Release v$$version"; \
	git push origin HEAD; \
	git push origin "v$$version"

release-patch:
	@$(MAKE) --no-print-directory version-patch AUTO_GIT=1

release-minor:
	@$(MAKE) --no-print-directory version-minor AUTO_GIT=1

release-major:
	@$(MAKE) --no-print-directory version-major AUTO_GIT=1

release-set:
	@$(MAKE) --no-print-directory version-set VERSION=$(VERSION) AUTO_GIT=1

tag-release:
	@version=$$($(MAKE) --no-print-directory version-get); \
	echo "Creating tag v$$version"; \
	git tag -a "v$$version" -m "Release v$$version"

publish-go-tag:
	@if [ -z "$(VERSION)" ]; then \
		echo "VERSION is required. Example: make publish-go-tag VERSION=v0.1.1"; \
		exit 1; \
	fi
	git tag -a $(VERSION) -m "Release $(VERSION)"
	git push origin $(VERSION)
