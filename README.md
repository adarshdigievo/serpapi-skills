# SerpApi skills [![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Search the web with 100+ SerpApi engines. Install both skills:

- `serpapi-setup` identifies the environment, helps you choose CLI, supported MCP, or raw cURL, stores credentials, and verifies access.
- `serpapi-web-search` handles engine selection and result extraction. Missing access or a failed request leads into guided setup, then back to the original search through SerpApi.

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

Both skills follow the open [Agent Skills specification](https://agentskills.io/specification).

To install manually, copy both skill folders into your client's directory:

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

## Ask your agent to install and set up

Copy this prompt into your coding agent:

```text
Install the serpapi-setup and serpapi-web-search skills for the agent/IDE we are using, at user scope so they are available across my projects.

Clone https://github.com/serpapi/skills.git into a temporary directory. Read the repository's installation instructions and inspect both skill folders under skills/.

Copy both complete folders, including their supporting files, into the same documented user-level skills directory. If you cannot identify the target agent/IDE, ask me. Back up any existing installation before updating it.

Verify both installed SKILL.md files and their relative references, then follow serpapi-setup. Reuse working access or help me choose CLI, MCP if this environment supports it, or raw cURL with no additional packages. Use a hidden prompt or credential UI for a missing key. Verify a real search through the chosen route and report the installation path, credential location without its value, and anything still pending. If a reload is required first, tell me how to resume setup afterward.
```

## Connect SerpApi

After installing, ask: **"Use serpapi-setup to configure and verify SerpApi for this environment."** You can also start a search with `serpapi-web-search`; its instructions direct the agent to help with missing access before searching. Setup reuses working access or helps you choose:

| Route | Setup |
|---|---|
| SerpApi CLI | [Install or reuse the CLI](skills/serpapi-setup/references/cli.md), then use an existing credential or hidden login prompt. |
| MCP | [Connect a supported client](skills/serpapi-setup/references/mcp.md) and verify its SerpApi tool. |
| Raw cURL | [Use cURL directly](skills/serpapi-setup/references/curl.md) with no additional packages. |

Get your API key from the [SerpApi dashboard](https://serpapi.com/dashboard). Enter it in a secret field or hidden prompt. On Windows, setup includes a [password-dialog helper](skills/serpapi-setup/references/credentials.md#windows-encrypted-storage) for agent terminals that cannot accept input. If setup needs your input or a client restart, the search stays pending. The skills instruct the agent to keep using SerpApi unless you explicitly choose another search provider.

## Verify

Start a fresh agent session and check that `serpapi-setup` and `serpapi-web-search` appear in its skill list. Ask the agent to follow `serpapi-setup` and finish any pending verification.

Setup makes one small real search through the selected route, which may use a credit. It checks the response as well as transport success. After it passes, ask **"Use serpapi-web-search to find recent news about SerpApi and cite the sources."**

## See Also

- [Contributing](CONTRIBUTING.md) — local checks, dependencies, API keys, and CI/CD setup
- [`skills/serpapi-web-search/SKILL.md`](skills/serpapi-web-search/SKILL.md) — engine selection, examples, parameters
- [`skills/serpapi-setup/SKILL.md`](skills/serpapi-setup/SKILL.md) — setup, credentials, verification, and repair
- [`serpapi-mcp`](https://github.com/serpapi/serpapi-mcp) — MCP server (hosted at mcp.serpapi.com)
- [`serpapi-cli`](https://github.com/serpapi/serpapi-cli) — terminal usage
- [serpapi.com/search-engine-apis](https://serpapi.com/search-engine-apis) — full API reference

## License

MIT
