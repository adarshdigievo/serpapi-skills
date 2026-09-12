# SerpApi skills [![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Search the web with 100+ SerpApi engines. Install both skills:

- `serpapi-setup` identifies the environment, helps you choose CLI, supported MCP, or raw cURL, stores credentials, and verifies access.
- `serpapi-web-search` handles engine selection and result extraction. If a request fails, it returns to setup for diagnosis and verification.

## Install the skills across your projects

With Node.js installed, use the [Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add serpapi/skills --skill serpapi-setup --skill serpapi-web-search --global
```

Select your agents in the installer. If a client is missing or the proposed directory differs from its current documentation, use the manual paths below. `--global` installs for your OS user across projects, without administrator access. It does not install for other users, remote containers, or cloud agents. Install separately on the host where each agent runs.

For a specific set of clients:

```bash
npx skills add serpapi/skills --skill serpapi-setup --skill serpapi-web-search --global --agent codex claude-code cursor github-copilot
```

### Standard and manual installation

Both skills follow the open [Agent Skills specification](https://agentskills.io/specification): a named directory, a `SKILL.md` with YAML `name` and `description`, and supporting files reached through relative links. The format is portable; the standard does not require one universal installation directory.

To install manually, copy the **entire** `skills/serpapi-setup` and `skills/serpapi-web-search` directories into the same user-level skill directory below. The resulting paths must end in `serpapi-setup/SKILL.md` and `serpapi-web-search/SKILL.md`; copying only the Markdown entry points breaks their references. Back up an existing installation before replacing it.

| Client | User-level skill directory | Official instructions |
|---|---|---|
| Codex app, CLI and IDE extension | `~/.agents/skills/` | [Codex skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code, including its VS Code and JetBrains integrations | `~/.claude/skills/` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Cursor | `~/.agents/skills/` or `~/.cursor/skills/` | [Cursor skills](https://cursor.com/docs/skills) |
| GitHub Copilot in VS Code | `~/.agents/skills/` or `~/.copilot/skills/` | [VS Code skills](https://code.visualstudio.com/docs/agent-customization/agent-skills) |
| Junie CLI and JetBrains IDEs | `~/.agents/skills/` or `~/.junie/skills/` | [Junie skills](https://junie.jetbrains.com/docs/agent-skills.html) |
| Google Antigravity | `~/.gemini/config/skills/` | [Antigravity skills](https://antigravity.google/docs/skills) |
| Devin Desktop (formerly Windsurf), using Devin Local | `~/.agents/skills/` or `~/.config/devin/skills/` | [Devin skills](https://docs.devin.ai/cli/extensibility/skills/overview) |
| Gemini CLI | `~/.agents/skills/` or `~/.gemini/skills/` | [Gemini skills](https://geminicli.com/docs/cli/skills/) |
| OpenCode | `~/.agents/skills/` or `~/.config/opencode/skills/` | [OpenCode skills](https://opencode.ai/docs/skills/) |
| Cline | `~/.cline/skills/` | [Cline skills](https://docs.cline.bot/customization/skills) |

Choose one directory per client to avoid duplicate installations. `~` means your user home directory. On Windows, home-relative directories are beneath your user profile; Devin's native directory is `%APPDATA%\devin\skills\`. Client policies and disabled-skill settings can prevent discovery. Check the linked client documentation if the skill does not appear.

Windsurf continues as [Devin Desktop](https://docs.devin.ai/desktop/changelog). Its September 8, 2026 release removed Cascade. Use Devin Local and its current configuration, not the old Cascade MCP file.

## Ask your agent to install and set up

Copy this prompt into your coding agent:

```text
Install the serpapi-setup and serpapi-web-search skills for the agent/IDE we are using, at user scope so they are available across my projects.

Clone https://github.com/serpapi/skills.git into a temporary directory. Read the repository's installation instructions and inspect both skill folders under skills/.

Copy both complete folders, including their supporting files, into the same documented user-level skills directory. If you cannot identify the target agent/IDE, ask me. Back up any existing installation before updating it.

Verify both installed SKILL.md files and their relative references, then follow serpapi-setup. Reuse working access or help me choose CLI, MCP if this environment supports it, or raw cURL with no additional packages. Use a hidden prompt or credential UI for a missing key. Verify a real search through the chosen route and report the installation path, credential location without its value, and anything still pending. If a reload is required first, tell me how to resume setup afterward.
```

## Connect SerpApi

After installing, ask: **"Use serpapi-setup to configure and verify SerpApi for this environment."** Setup reuses working access or helps you choose:

| Route | Setup |
|---|---|
| SerpApi CLI | [Install or reuse the CLI](skills/serpapi-setup/references/cli.md), then use an existing credential or hidden login prompt. |
| MCP | [Connect a supported client](skills/serpapi-setup/references/mcp.md) and verify its SerpApi tool. |
| Raw cURL | [Use cURL directly](skills/serpapi-setup/references/curl.md) with no additional packages. |

Get a missing key from the [dashboard](https://serpapi.com/dashboard). Setup supports OS secret stores, existing CLI credentials, and a private-file fallback outside the repository. See [credential storage](skills/serpapi-setup/references/credentials.md) for protection limits and how agents retrieve keys. Enter keys through a hidden terminal prompt or credential UI.

## Verify

Start a fresh agent session and check that `serpapi-setup` and `serpapi-web-search` appear in its skill list. Ask the agent to follow `serpapi-setup` and finish any pending verification.

Setup makes one small real search through the selected route, which may use a credit. It checks the response as well as transport success. A saved key or registered MCP server is not enough. After it passes, ask **"Use serpapi-web-search to find recent news about SerpApi and cite the sources."**

## See Also

- [Contributing](CONTRIBUTING.md) — local checks, dependencies, API keys, and CI/CD setup
- [`skills/serpapi-web-search/SKILL.md`](skills/serpapi-web-search/SKILL.md) — engine selection, examples, parameters
- [`skills/serpapi-setup/SKILL.md`](skills/serpapi-setup/SKILL.md) — setup, credentials, verification, and repair
- [`serpapi-mcp`](https://github.com/serpapi/serpapi-mcp) — MCP server (hosted at mcp.serpapi.com)
- [`serpapi-cli`](https://github.com/serpapi/serpapi-cli) — terminal usage
- [serpapi.com/search-engine-apis](https://serpapi.com/search-engine-apis) — full API reference

## License

MIT
