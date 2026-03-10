# Publishing

Use root Makefile targets for release actions.

## Pre-publish checks

```bash
make check-publish-all
```

## Version bump

```bash
make version-patch
```

Also available: `make version-minor`, `make version-major`, and `make version-set VERSION=X.Y.Z`.

To bump + auto-commit + tag + push in one step:

```bash
make release-patch
```

You can also use `AUTO_GIT=1` directly, for example: `make version-patch AUTO_GIT=1`.

## Publish packages

Python:

```bash
make publish-python
```

`publish-python` now uploads only artifacts matching the current version in `python/pyproject.toml`, which avoids stale files in `python/dist` from blocking uploads.

Node:

```bash
make publish-node
```

With Doppler for Node token injection:

```bash
make publish-node-doppler
```

All packages:

```bash
make publish-all
```
