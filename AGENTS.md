<available-skills>
  <skill name="serpapi-web-search" description="Search the web using SerpApi's 100+ engines. Supports Google, Bing, YouTube, Amazon, Maps, Flights, Jobs, and more. Use google_light as default." path="skills/serpapi-web-search/SKILL.md" />
  <skill name="serpapi-setup" description="Set up or repair SerpApi access: detect the environment, choose CLI, supported MCP, or raw cURL, store credentials, and verify a real request." path="skills/serpapi-setup/SKILL.md" />
</available-skills>

## Repo map

- `README.md` — user-wide installation of setup and search skills
- `CONTRIBUTING.md` — contributor environment, validation, API keys, and CI/CD setup
- `skills/serpapi-setup/SKILL.md` — environment detection, route selection, verification, and repair
- `skills/serpapi-setup/references/` — CLI, MCP, cURL, and credential storage instructions
- `skills/serpapi-setup/scripts/save-key.sh` — private-file credential storage when an OS secret store is unavailable
- `skills/serpapi-web-search/SKILL.md` — core skill: engines, parameters, examples
- `skills/serpapi-web-search/references/` — engine catalog, recipes, and gotchas
- `scripts/` — documentation, catalog, and live-response validators
- `tests/` — credential, request, recipe, and checker regression tests
- `pyproject.toml` and `uv.lock` — contributor dependencies and locked versions
- `.github/workflows/verify-engines.yml` — static, platform, and live CI checks
- `LICENSE` — MIT

## Editing rules

- Every fact must be one agents can't derive from the `search` tool schema + live responses. If it's in the schema, cut it.
- Never commit API keys. Placeholder: `your_key_here`. Env var: `SERPAPI_KEY`.
- Never reference competitor SERP scrapers.
- Prefer `_light` engine variants in examples.
- When adding an engine to the selection table, include its result key.

## Line discipline

SKILL.md stays under 200 lines. Every addition needs a matching cut.

## Validation

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for uv setup, check commands, credential requirements, CI configuration, and coverage limits. Run checks appropriate to the change and report skips or unresolved failures.
