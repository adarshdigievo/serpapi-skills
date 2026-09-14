# Contributing

This repository contains the setup and search skills plus tools for validating their instructions. Read [AGENTS.md](AGENTS.md) for editing rules and the repository map. For installing and using the skills, follow the [README](README.md).

## Local development

Use Python 3.12 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/). CI uses Python 3.12. Run commands from the repository root:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked scripts/verify_doc_examples.py --offline
```

Install Bash and jq for the POSIX shell and extraction checks, and PowerShell (`pwsh`) for PowerShell syntax and request checks. Missing jq or PowerShell causes relevant tests to report skips. To require PowerShell syntax coverage, use:

```bash
uv run --locked scripts/verify_doc_examples.py --offline --require-powershell
```

The Python dependencies support contributor checks. Installing the skills does not require this Python environment. The CLI embeds its query evaluator; host jq is used by the extraction tests. Native Windows DPAPI tests run only on Windows, while POSIX credential tests run on macOS and Linux. The hidden-input test needs a terminal that permits PTY control; run it in an ordinary local terminal if a sandbox blocks `stty`.

## Python configuration and dependencies

[pyproject.toml](pyproject.toml) defines the check environment:

| Setting | Purpose |
|---|---|
| `[project]` | Names the check project, requires Python 3.12+, and declares the parsers used by the scripts. |
| `beautifulsoup4` | Reads HTML parameter tables and JSON examples from official API pages. |
| `json5` | Parses upstream JSON examples that contain comments or trailing commas. |
| `markdown-it-py` | Parses Markdown fences, links, and inline code. |
| `pyyaml` | Parses skill frontmatter and YAML examples with duplicate-key rejection. |
| `[dependency-groups].dev` | Adds pytest for regression tests. uv includes this group by default. |
| `[tool.pytest.ini_options]` | Discovers tests under `tests/` and makes `scripts/` importable by those tests. |
| `[tool.uv].package = false` | Tells uv to install dependencies without building or installing this repository as a Python package. |

[uv.lock](uv.lock) records resolved dependency versions. `uv sync --locked` prepares `.venv/` from that lockfile, and `uv run --locked` runs commands in the project environment. Both reject a stale lockfile instead of updating it. See uv's [locking and syncing guide](https://docs.astral.sh/uv/concepts/projects/sync/) and [package configuration](https://docs.astral.sh/uv/concepts/projects/config/#project-packaging).

Use `uv add` for a script dependency or `uv add --dev` for a test dependency. If you edit dependency requirements in `pyproject.toml` directly, run `uv lock`, then `uv sync --locked` and the affected checks. Include both dependency files in the change. Keep dependency upgrades separate from unrelated skill edits. There is no Python package build or publishing step in the workflow.

## What each check does

| Command, after `uv run --locked` | Coverage | Network and key requirements |
|---|---|---|
| `pytest` | Credential handling, documented requests and recipes, skill-folder portability, and checker regression tests. | Fake keys and mocked requests; no SerpApi key or live API calls. |
| `scripts/verify_doc_examples.py --offline` | Skill frontmatter and line limits, local Markdown links, fenced-code syntax, and unclosed fences. Covers README, AGENTS, this guide, and all skill Markdown. | Local only after dependencies are installed. |
| `scripts/verify_doc_examples.py --require-powershell` | The same checks, plus public-link reachability and required PowerShell syntax coverage. | Public websites; no SerpApi key. HTTP 403/429 results are warnings because reachability is unresolved. |
| `scripts/verify_engine_catalog.py` | Catalog rows, names, URLs, required inputs, parsed request parameters, selected conditional rules, and documented response paths. | Current official SerpApi documentation; no key or search credits. |
| `scripts/verify_live_responses.py` | Selected response fields, alternate result sections, echoed parameter values, and JSON Restrictor behavior using real searches. | Requires `SERPAPI_KEY`; requests can use credits. |

For the upstream documentation checks, run:

```bash
uv run --locked scripts/verify_engine_catalog.py
uv run --locked scripts/verify_doc_examples.py --require-powershell
```

The catalog checker reads `llms.txt`, canonical API pages, and configured nested APIs. Response-path claims must occur in parsed JSON examples; matching a word in prose does not establish a response contract. Individual source failures are collected while other checks continue, but still fail the command.

The tests in [tests/](tests/) cover different boundaries:

- `test_setup_credentials.py` exercises private-file permissions, hidden input, exact key storage, overwrite handling, concurrent writers, symlinks, Git worktrees, and shell tracing with synthetic keys.
- `test_setup_requests.py` executes the documented cURL and credential-loading snippets with mocked commands, tests the CLI verification filter, and checks PowerShell syntax, HTTP, API, JSON, and cleanup behavior. Native Windows also tests the credential helper's DPAPI round trip, rejected input, cancellation, overwrite refusal, and junction refusal. POSIX cURL still requires the documented JSON inspection after transport success.
- `test_skill_recipes.py` copies both skill folders into an isolated directory, checks that their links stay within the bundle, and exercises parallel request failures, cleanup, and Maps extraction. Flights extraction is covered in `test_documentation_checks.py`.
- `test_documentation_checks.py` and `test_checker_resilience.py` test malformed documentation, request validation, response paths, catalog refresh behavior, live-response assertions, and partial upstream failures.

Host jq tests do not establish the behavior of the CLI's embedded evaluator. Copying skill folders does not exercise an IDE's loader or register an MCP server. Verify those changes in the affected client and record the result in your PR. Syntax checks do not validate every prose instruction, dynamic token, parameter combination, or engine's live availability.

For setup changes, use a fresh client session with neither a SerpApi connection nor a stored key. Ask for a search using SerpApi and check that the agent starts setup, asks only for needed choices, waits for secret input, verifies the selected route, and resumes the original search. It should keep the task pending if setup is declined or blocked. On Windows, also launch the helper from the actual agent host and confirm the masked dialog is usable, Save stores the key, and Cancel leaves setup pending. Automated credential tests replace console input and do not prove that a desktop dialog is visible or usable from a client.

### Refreshing the engine catalog

Check for drift without writing:

```bash
uv run --locked scripts/refresh_engine_catalog.py --check
```

To update source-derived names, links, required inputs, and counts:

```bash
uv run --locked scripts/refresh_engine_catalog.py
uv run --locked scripts/verify_engine_catalog.py
```

The refresh preserves curated descriptions and response mappings. It refuses to write a partial catalog if a source fails. Review the diff and current upstream requirements before accepting a change; do not remove an assertion merely to hide an upstream outage.

## API keys and live checks

Only the live checker needs a real key. Get one from the [SerpApi dashboard](https://serpapi.com/dashboard) and make `SERPAPI_KEY` available in the process environment through your secret manager or the documented [credential-loading instructions](skills/serpapi-setup/references/credentials.md). The checker reads that variable directly; it does not discover CLI login files, OS secret stores, `.env` files, or MCP credentials on its own.

```bash
uv run --locked scripts/verify_live_responses.py
```

The current suite has 30 search contracts, with six requests in parallel. It permits one retry for transport failures and selected HTTP errors, so a run may issue more than 30 requests. Travel dates are generated at runtime. HTTP 200 responses containing an API `error` fail. A missing key exits with status 2; a failed contract exits with status 1.

Walmart reviews is currently excluded from live checks after repeated upstream HTTP 503 responses. Its catalog and response documentation remain covered by static checks.

Keep keys out of committed files, chat, shell history, screenshots, and test fixtures. Use `your_key_here` when a placeholder is needed. Tests use synthetic keys and temporary directories. The live checker redacts the configured key from reported errors; inspect any additional diagnostics before sharing them.

## CI/CD setup

The [Verify SerpApi documentation workflow](.github/workflows/verify-engines.yml) validates changes and checks for upstream drift. It does not deploy a site, publish a package, or update installed skills.

### Configure a repository or fork

1. Enable GitHub Actions for the repository and allow the actions referenced by the workflow under your organization's policy.
2. For live checks, open **Settings > Secrets and variables > Actions > Secrets > New repository secret**. Name it `SERPAPI_KEY` and enter the key in GitHub's secret field. The workflow expects a repository-accessible secret; an environment secret alone is insufficient because its jobs do not select a GitHub environment. See [GitHub's secret instructions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
3. Open **Actions > Verify SerpApi documentation > Run workflow**, choose the branch, and set **Run live response checks that may use SerpApi credits**. The input defaults to enabled. Disable it for a manual run without a key. The workflow must exist on the default branch for manual dispatch, and running it requires write access. See [manual workflow runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Only the live job receives `${{ secrets.SERPAPI_KEY }}`. Static and platform checks need no repository secrets, and no separate GitHub API token is required. A local CLI login does not configure a CI runner. Missing or invalid keys fail the live job; they do not turn it into a successful skip.

### Triggers and jobs

| Trigger | Checks |
|---|---|
| Pull request touching watched files | Static checks and platform credential tests; live checks are disabled, including for fork PRs. |
| Push touching watched files | Static, platform, and live checks. There is no branch filter. |
| Weekly schedule | All checks, Mondays at 09:00 UTC. |
| Manual run | Static and platform checks; live checks follow the input above. |

Watched paths include README, AGENTS, CONTRIBUTING, both skill folders, `scripts/`, `tests/`, `pyproject.toml`, `uv.lock`, and the workflow itself.

The `static` matrix runs regression tests, catalog/API contracts, and Markdown syntax/link checks independently on Ubuntu. It requires jq for regression tests and PowerShell for the document check. The `platform-credentials` matrix runs credential and request tests on macOS and Windows; Windows explicitly requires PowerShell. The `live` job runs on Ubuntu with the repository key. All jobs use Python 3.12 and `uv sync --locked`.

Matrix fail-fast is disabled so one failure does not hide other results. A newer run for the same Git ref cancels the older run. The workflow requests read-only repository contents permission and does not write changes back to the repository.

## Submitting a change

Keep both skill folders self-contained and preserve their relative references. Follow the size and content rules in AGENTS.md. For simple wording changes, run the document checker; for scripts, request examples, or credential changes, run the affected behavioral tests. Run catalog or live checks when the changed claim needs that evidence.

Describe the resulting behavior and the checks you ran in the PR. Include skipped platforms, unavailable tools, unresolved external-link warnings, and any manual client verification. Use tests that exercise behavior or failure handling; avoid assertions that only repeat the wording of a document or workflow.
