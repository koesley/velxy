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

## V0.7 authenticated website AI repair requests

The signed-in PATCHWORK page now offers a direct AI repair form. Disabled by
default: set `VELXTRIA_PATCHWORK_AI_ENABLED=1` and configure `OPENAI_API_KEY`
on the server to enable it. Optional `PATCHWORK_MODEL` selects the model.
Requests explicitly upload one UTF-8 Python file (40 KB maximum) to OpenAI.
Do not upload secrets, credentials, or customer data. API charges may apply.
The endpoint requires an authenticated session and CSRF token, throttles to
one request per account per hour in each server process, and returns a JSON
report with a unified diff. It never applies changes or runs project code.
The in-memory throttle is not distributed or durable; use a shared database
limiter before public/multi-instance rollout. The feature is experimental
and should remain disabled in production until security review and tests.

## V1 repository-wide repair campaigns

Run a bounded, read-only scan across a Python repository:

```bash
python tools/patchwork/campaign.py . --output patchwork-campaign.json
```

Optionally generate AI proposals for up to five syntax-error files not
handled by the conservative built-in colon rule. This **uploads source code
to OpenAI** and may incur API costs:

```bash
OPENAI_API_KEY=your-key python tools/patchwork/campaign.py . --output campaign-ai.json --ai --confirm-upload
```

The scanner considers up to 500 Python files, excludes symlinks and common
dependency directories, and limits individual AI input files to 40 KB.
Existing reports are never overwritten. Import the JSON into the
**Repository repair campaigns** panel in the authenticated PATCHWORK page.
No generated changes are applied or executed. Campaign reports may contain
sensitive code excerpts in proposed diffs; store them privately.

## V2 multi-language security triage

PATCHWORK now supports a read-only multi-language inventory alongside Python
repair campaigns. Run:

```bash
python tools/patchwork/triage.py . --output patchwork-triage.json
```

Import the report into the **Multi-language security triage** section of the
authenticated PATCHWORK dashboard. The scanner examines up to 2,000 source
and manifest files across Python, JavaScript, TypeScript, JSON, YAML, TOML,
Dockerfiles, and common package manifests. It validates JSON syntax, flags
selected risky code constructs, and identifies wildcard/latest dependency
versions in package.json. It skips symlinks and common generated/dependency
directories and limits text inspection to 256 KB per file. It does **not**
parse or validate YAML/TOML syntax, audit actual dependency CVEs, or prove
security vulnerabilities. Heuristic warnings require human review.
Reports are stored locally, never overwritten, and not uploaded by the CLI.

## V3: Approval-gated multi-file release packaging

PATCHWORK can now take up to 25 individually reviewed `patchwork-review-v1`
bundles, verify that their original source files have not changed, syntax
check every Python replacement, and produce a single staged ZIP outside the
repository. It **never** applies the changes, runs the proposed code, pushes
a Git branch, opens a PR, or deploys.

```bash
python tools/patchwork/release_gate.py . review-a.json review-b.json \
  --output ../patchwork-staged.zip --approve-staging
```

The explicit `--approve-staging` flag authorizes only ZIP creation. The
archive contains `patchwork-manifest.json` and proposed replacement files
under `proposed/`. Source hashes and duplicate target checks protect
against stale or ambiguous proposals. Do not extract or run untrusted
proposals without a separate security review and isolated test process.
