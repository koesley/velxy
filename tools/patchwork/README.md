# PATCHWORK — VELXTRIA code diagnostics

PATCHWORK is an experimental, read-only software diagnostic module within VELXTRIA.

Run from the repository root:

```bash
python tools/patchwork/scan.py . --json
```

Requires Python 3.9+ and no third-party dependencies. Scans Python source for syntax errors without executing project code, editing files, or making network requests.

This is an early scanner, **not** an AI repair agent. A clean scan does not prove correctness or security. Future versions may add reviewable suggested patches and isolated tests; no automatic production changes.
