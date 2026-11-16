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

## V4: GitHub-native draft repair pull requests

The explicit-approval GitHub publisher takes a V3 staged release ZIP,
verifies the original source hashes against the selected remote base branch,
creates a dedicated repair branch, uploads proposed replacements, and opens
a **draft** pull request. It never merges, deploys or runs project code.

```bash
GITHUB_TOKEN=your-fine-grained-token python tools/patchwork/github_publisher.py \
  owner/repository main ../patchwork-staged.zip --approve-draft-pr
```

Use a fine-grained GitHub token scoped to the target repository with
Contents: Read and write and Pull requests: Read and write. Do not paste
tokens into reports or commits. Branch creation and file uploads are
remote writes: use a test repository first. If the API fails mid-operation,
a partially populated branch may remain and require manual cleanup.
The publisher currently uses one GitHub Contents API commit per file and
does not automatically retry, resume, run tests, or merge. The target
repository should require branch protection and passing CI checks.

## V5: isolated repair verification

With Docker installed, validate an approved V3 staged ZIP against a Python
repository in a temporary copy, without changing the source repository:

```bash
python tools/patchwork/isolated_verify.py . ../patchwork-staged.zip \
  --approve-isolated-tests --output ../patchwork-test-report.json
```

The verifier checks source hashes before staging replacements, copies up to
3,000 Python files / 30 MB, then runs unittest discovery in a container
with networking disabled, dropped capabilities, no-new-privileges, a read-only
filesystem, limited memory/CPU/processes and a 120-second timeout.
Docker is required; there is no host-execution fallback. It records
pass/fail, output tails and elapsed time in a private JSON report.
The test discovery command does execute repository Python tests **inside**
the container, so use only with code you are authorized to test. Containers
are not a complete boundary against malicious code, and no secrets should
be exposed to the test environment. The default Python image may need
to be pulled beforehand, and Docker daemon access must be secured.
Passing tests do not automatically authorize a merge or deployment.

## V6: Verification-gated GitHub publishing

The GitHub draft PR publisher now **requires a successful isolated verification
report for the exact staged release ZIP**. It rejects missing, failed, stale,
zero-test and mismatched reports before contacting GitHub. The Docker verifier
records the ZIP SHA-256 and requires at least one discovered unittest test.

```bash
python tools/patchwork/isolated_verify.py . ../patchwork-staged.zip \
  --approve-isolated-tests --output ../patchwork-test-report.json

GITHUB_TOKEN=your-token python tools/patchwork/github_publisher.py \
  owner/repository main ../patchwork-staged.zip \
  --verification-report ../patchwork-test-report.json --approve-draft-pr
```

This is a **local workflow integrity gate**, not a cryptographic attestation.
A user with write access to the report can forge JSON; do not treat it as
independent proof of CI. Before production, require trusted CI-issued
attestations bound to immutable commit hashes and branch protections.
The publisher still creates draft PRs only; it never merges or deploys.

## V7: GitHub-native immutable-commit verification

A new `.github/workflows/patchwork-repair-pr.yml` workflow checks Python
syntax and PATCHWORK regression tests on draft repair branches named
`patchwork/review-*`. It runs on GitHub-hosted runners without repository
write permissions or credentials persisted by checkout.

After the draft PR is created, inspect GitHub's checks on its exact commit:

```bash
GITHUB_TOKEN=your-read-token python tools/patchwork/github_ci_gate.py \
  owner/repository 123 --expected-sha 0123456789abcdef0123456789abcdef01234567
```

The gate requires a single successful `patchwork-repair-ci` check from
GitHub Actions on that immutable SHA and rejects pending, failed, missing,
duplicate or stale checks. It is read-only and does not merge anything.
The workflow must exist on the repository's default branch for GitHub to
reliably recognize it for new PRs. Administrators must configure branch
protection/rulesets to require the check and independent human review;
this script alone cannot enforce a merge restriction. Tests executed on
GitHub-hosted runners are not equivalent to the separately constrained
Docker verifier and may execute project test code; use trusted PR sources.

## V8: Atomic multi-file GitHub repair commits

Use `atomic_publisher.py` instead of the legacy per-file publisher for
approved repair releases. It validates local Docker test evidence and all
source hashes against an immutable Git base commit before writing Git objects.
It creates a single Git tree and commit containing every replacement, then
creates a dedicated branch pointing at that complete commit and opens a draft
PR. This avoids partially updated repair branches if a file upload fails.

```bash
GITHUB_TOKEN=your-token python tools/patchwork/atomic_publisher.py \
  owner/repository main ../patchwork-staged.zip \
  --verification-report ../patchwork-test-report.json --approve-draft-pr
```

The tool rechecks the base branch before creating its repair branch. Git
objects may remain unreferenced after a failed request; a branch may remain
if PR creation fails. It does not merge, deploy or change the base branch.
The local JSON verification report is not cryptographically authenticated,
so production merge rules must rely on independent GitHub CI checks and
human review. GitHub Contents API limits and file restrictions still apply.

## V9: Repair blast-radius and release policy analyzer

Before publishing an atomic repair, inspect its entire staged ZIP with:

```bash
python tools/patchwork/release_policy.py . ../patchwork-staged.zip \
  --output ../patchwork-policy-report.json
```

The read-only policy analyzer checks every source digest, parses both versions
of each Python file, measures changed lines, flags newly introduced
high-risk calls and imports, identifies sensitive modules (authentication,
payments, secrets, database migrations), and enforces a configurable
1,200-line change budget. It returns `eligible`, `needs_review` or
`blocked` with per-file findings. A blocked report exits nonzero.
This is an additional manual preflight step; it is **not yet enforced by
the GitHub atomic publisher**. Heuristic AST checks cannot prove security,
and a passing report does not replace CI or human code review.

## V10: Enforced release policy at atomic publication

Atomic publishing now **fails closed** unless the caller supplies a local
repository checkout via `--source-root`. It checks original source digests,
runs V9's policy analysis, and rejects blocked releases before any GitHub API
request. Sensitive modules or new dependencies require explicit
`--approve-sensitive-review`; passing this flag does not waive blockers.

```bash
GITHUB_TOKEN=your-token python tools/patchwork/atomic_publisher.py \
  owner/repository main ../patchwork-staged.zip \
  --source-root . --verification-report ../patchwork-test-report.json \
  --approve-draft-pr
```

For reviewed sensitive changes, append `--approve-sensitive-review`.
The older `github_publisher.py` remains available for compatibility and
**does not enforce V9 policy**. Production users should disable the legacy
entrypoint or restrict it separately. The local policy and test reports
are not trusted attestations; enforce independent GitHub CI and review
through repository rulesets.

## V11: Staged archive security hardening

All repair consumers using `github_publisher.load_release` now reject
duplicate target paths, unexpected archive entries, ZIP symlinks,
encrypted entries, directory entries, oversized manifests, and oversized
uncompressed ZIP entries before extracting replacement contents. An
adversarial regression suite tests duplicate targets, compressed oversized
payloads, symlink entries, and valid archives.

These checks reduce archive-processing risks but are not a complete
defense against malicious code or compromised repositories. V10's
policy gate remains mandatory for the atomic publisher. Production
deployment is not automatic.

## V12: Full lifecycle integration rehearsal

Run `python tools/patchwork/rehearsal.py` to exercise a **two-file**
release from review JSON through approved staging, risk policy,
isolated-verifier command generation, atomic GitHub draft PR creation and
immutable-SHA CI gate inspection. The rehearsal verifies that source
files remain unchanged and the GitHub write sequence creates exactly one
commit, with no per-file PUT operations.

**Docker and GitHub are mocked.** This rehearsal does not run a real
container, push a branch, open a PR, verify a live CI job, merge or deploy.
Its purpose is to catch interface and orchestration regressions before
a separate disposable-repository integration test with real services.
The regression test runs under the PATCHWORK validation workflow.

## V13: Real Docker verification integration

Run `python tools/patchwork/real_docker_integration.py` on a host
with Docker installed and access to the allowlisted
`python:3.11-alpine` image. This creates a disposable two-file Python
fixture, stages an approved repair, checks V9 release policy, and runs
the repaired fixture's unittest suite in a real Docker container using
PATCHWORK's constrained `isolated_verify.verify` command. It checks
the resulting release-bound evidence and proves the original fixture
was unchanged. It does not contact GitHub, create PRs, merge or deploy.

The `PATCHWORK real Docker integration` GitHub Actions workflow runs
this fixture on pushes to the development branch and on explicit
workflow dispatch. It is separate from the offline mock rehearsal.
Only the controlled fixture is executed; this is not a guarantee that
arbitrary customer repositories or untrusted code are safe to execute.
A green run is required before calling the real-container path tested.

## V14: Opt-in real GitHub disposable-repository integration

The `live_integration.py` probe is designed to validate real Docker
execution followed by GitHub Git-object publishing, branch creation,
and draft-PR inspection. It **does not run automatically in CI**.

Prerequisites: create a separate disposable GitHub repository (never
`koesley/velxy`), place `patchwork_integration_fixture.py` on its
default branch containing exactly:

```python
def patchwork_fixture():
    return 1
```

Ensure Docker is installed, the allowlisted image is available, and a
least-privilege GitHub token can create draft pull requests in that
disposable repository. Then run:

```bash
export PATCHWORK_DISPOSABLE_REPOSITORY=owner/disposable-repo
export GITHUB_TOKEN=your-disposable-repo-token
python tools/patchwork/live_integration.py owner/disposable-repo main \
  --approve-live-disposable-test
```

The probe rejects production repository `koesley/velxy`, requires an
exact environment allowlist and approval, verifies the remote baseline,
uses a real Docker verification report, and checks the resulting Git
commit, branch and open draft PR against the expected immutable SHA.
It intentionally leaves the draft PR open; there is no automatic merge,
deployment or deletion. **No live GitHub integration run is claimed
until a separate disposable repository is configured and tested.**

## V15: Read-only GitHub integration readiness audit

Before running the V14 live publisher, audit a **private disposable**
repository without modifying it:

```bash
export PATCHWORK_DISPOSABLE_REPOSITORY=owner/disposable-repo
export GITHUB_TOKEN=your-disposable-repo-token
python tools/patchwork/live_readiness.py owner/disposable-repo main
```

The audit validates repository identity and privacy, active state,
default branch, read/write permissions, immutable base SHA, and the
expected fixture contents. It uses GET requests only, never creates
branches or PRs. The live integration probe additionally checks the
published file bytes and exact draft PR branch identity.

No real GitHub publishing test has been executed merely by adding
these tools. The disposable repository and explicit opt-in are still
required. Use a dedicated least-privilege token, not production secrets.

## V16: High-risk AST occurrence policy

The release policy now compares **counts of high-risk function calls**
between the original and replacement Python ASTs. A newly added
`exec()` is blocked even if the original source already used
`exec()`. The denylist also covers newly added destructive file
operations (`shutil.rmtree`, `os.remove`, `os.unlink`,
`os.chmod`, `os.chown`) and additional subprocess execution
helpers. Four focused tests guard these cases. The atomic publisher
enforces the updated policy before GitHub writes.

This remains heuristic static analysis, not proof that a change is safe.
Aliases, dynamic dispatch, semantic changes to existing calls and
malicious code can evade the heuristic; human review is still required.

## V17: Unified policy-enforced publishing

The legacy `github_publisher.publish` function and CLI no longer
write GitHub files one-by-one. They delegate to
`atomic_publisher.publish_atomic`, which requires a passing
release-bound verification report, a local source checkout for the
release policy, explicit staging approval, immutable remote source
checks, and one atomic Git commit plus draft PR. The compatibility CLI
now requires `--source-root`; sensitive changes additionally require
`--approve-sensitive-review`.

Previously documented V4 per-file publication behavior is retired.
New regression tests ensure the compatibility entrypoint fails closed
without policy context, rejects high-risk changes before network
access, and delegates to the atomic implementation. This closes the
known supported legacy publication bypass; it does not prove that
other GitHub credentials or manual repository writes are impossible.
