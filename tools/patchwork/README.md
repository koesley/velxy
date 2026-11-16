# PATCHWORK — VELXTRIA code diagnostics

PATCHWORK is an experimental, read-only software diagnostic module within VELXTRIA.

Run from the repository root:

```bash
python tools/patchwork/scan.py . --json
```

Requires Python 3.9+ and no third-party dependencies. Scans Python source for syntax errors without executing project code, editing files, or making network requests.

This is an early scanner, **not** an AI repair agent. A clean scan does not prove correctness or security. Future versions may add reviewable suggested patches and isolated tests; no automatic production changes.

## Opt-in AI repair proposals (V0.4)

This feature is available from the command line only, not the website. It sends
**the complete contents of the selected Python file** to the OpenAI API, which
may incur charges. Do not use it with secrets, credentials, or private customer
data. No background uploads occur.

```bash
export OPENAI_API_KEY="your-key"
python tools/patchwork/ai_repair.py . path/to/broken.py --confirm-upload
```

Use `--model` or `PATCHWORK_MODEL` to select a model supported by your API
account. The module generates a review-only unified diff, verifies replacement
Python syntax, and checks source SHA-256 to avoid stale edits. It **does not**
run tests, apply patches, open pull requests, or deploy. Human review is
required; syntax checks alone cannot prove a patch is safe.

Run unit tests locally with:
```bash
python -m unittest discover -s tools/patchwork -p 'test_*.py' -v
```

## V0.6 AI-to-dashboard review bridge

Generate a review bundle using the opt-in AI command:

```bash
python tools/patchwork/ai_repair.py . broken.py --confirm-upload --review-file patchwork-review.json
```

Then sign in to the VELXTRIA portal, visit `/patchwork`, and select the
JSON file under **AI proposal review**. The file is parsed locally in the
browser. The CLI bundle contains the complete original and proposed source:
keep it private and delete it when no longer needed. Existing output paths
are never overwritten. This feature does not execute tests, apply patches,
create GitHub pull requests, or make AI calls from the website.
