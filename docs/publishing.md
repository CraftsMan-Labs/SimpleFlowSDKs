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

## Publish packages

Python:

```bash
make publish-python
```

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
