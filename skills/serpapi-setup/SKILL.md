---
name: serpapi-setup
description: Set up or repair SerpApi access. Use for first use, API keys, credential storage, CLI installation, MCP connections, raw cURL without additional packages, or failed requests. Detect the execution environment, reuse existing access, and verify a real search through the selected route.
license: MIT
---

## Identify and choose

1. Identify the client, OS, shell, and execution host. Desktop apps, SSH hosts, containers, WSL, and cloud connectors can have different credentials and network access. Ask only for context the session does not establish.
2. Discover SerpApi MCP tools through the host's tool list/search. With a shell, check for `serpapi`, `curl` (`curl.exe` in PowerShell), and `SERPAPI_KEY` by presence only. Never dump the environment or credential files. A config entry alone does not prove connectivity.
3. Honor the user's preference or reuse working access. Otherwise offer the supported choices once, recommending what fits the environment:

| Route | Requirements | Guide |
|---|---|---|
| MCP | Client supports hosted HTTP MCP or a supported desktop extension; execution host can reach `mcp.serpapi.com` | [MCP](references/mcp.md) |
| CLI | Shell, user wants the command interface, HTTPS access to `serpapi.com` | [CLI](references/cli.md) |
| Raw cURL | Existing curl, HTTPS access to `serpapi.com`; no additional packages | [cURL](references/curl.md) |

Read only the chosen guide and relevant [credential section](references/credentials.md). Do not install Python, Node.js, jq, a package manager, or an MCP bridge for a no-additional-setup request. If curl is absent, explain the limitation and offer an available route. Existing SDK integrations can stay in use and be verified in their own runtime.

When handling a failed request, start with diagnosis below. Keep its route and original task; repeat onboarding only if access must change.

## Configure

Get a missing key from the user's [dashboard](https://serpapi.com/dashboard), entered through a hidden terminal prompt, native secret store, or client credential UI. Never request it in chat. Follow [credential storage](references/credentials.md); keep keys out of skill files, workspace notes, command arguments, and shell history.

Preserve existing credentials, other MCP entries, and scope. MCP access needs no CLI login or local key copy. If input or a restart is required, give the exact action and leave verification pending. Do not replace keys, duplicate servers, disable TLS verification, or bypass host policy to make a check pass.

## Verify and resume

Make one small real search with `engine=google_light`, `q=coffee`, or the original task's valid request. It may use one credit. Do not force a fresh crawl, paginate, or test every route by default.

1. Verify **through the selected route**: CLI executable/account then search; cURL HTTP status and JSON body; MCP discovery and tool invocation inside the target client. A separate HTTP request cannot verify a client's MCP connection.
2. Require transport/process success and no API `error` or MCP `isError`. Decode JSON returned as MCP text; treat plain-text errors as failures. HTTP 200, exit code 0, login, or discovery alone is insufficient. The coffee probe must return a nonempty organic title and link. Empty results from another query are inconclusive; use the probe if needed.
3. After repair, repeat the corrected original operation through the same route. A passing probe with a failing task means access works but the task remains unresolved.
4. Report the route, execution host, credential source/location without its value, checks passed, and anything pending. Keep the retrieval method available for future sessions; do not write a permanent verified flag.
5. Resume [serpapi-web-search](../serpapi-web-search/SKILL.md), discovering it by name if the sibling link is unavailable. If live calls are disallowed or results cannot be inspected, report verification pending.

## Diagnose failures

Retain the engine, route, sanitized error, and original task. Stay here until verification succeeds or a specific blocker is established.

| Failure | Action |
|---|---|
| Missing executable/tool | Check execution-host PATH, MCP discovery, scope, disabled servers, and reload requirements. Follow the chosen route's install guide. |
| 401/missing key | Check source and process access. A stale environment key overrides CLI login. Repair that source, then verify once. |
| 403 | Distinguish host policy, service access, and account restrictions from authentication. |
| 400/invalid or mismatched arguments | Fetch [SerpApi's documentation index](https://serpapi.com/llms.txt), open the selected engine's linked API page, and correct argument names, required inputs, and values before retrying. Do not reinstall or rotate credentials. |
| 429 | Check quota/throughput and retry delay; stop immediate retries. Report needed account action without purchasing credits or changing plans. |
| DNS/TLS/timeout/5xx | Check host, endpoint, proxy, and service availability. Retry once after a concrete correction or advised delay. |
| HTTP 200 with API error, malformed JSON, or empty probe | Inspect the sanitized error/structure and resolve it before claiming readiness. |

If a route is unavailable, offer another supported route. Identify any fallback as the route actually verified and keep the original failure explicit.
