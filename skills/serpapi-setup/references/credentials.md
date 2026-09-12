# Credential storage and retrieval

Reuse the credential source already working for the chosen route. The skill can use a key through the user's process or MCP connection without displaying it. Do not extract a key from a working MCP connector to create a second store.

For new storage, prefer the client's sensitive credential input or an available OS secret store. The commands below are for the user's terminal. Secret reads must happen inside a variable assignment or pipe, never as a standalone tool call that prints the key. Disable shell tracing before reading secrets. Do not put literal keys in commands, chat, `.env` files in repositories, or shell profiles.

The load functions return a failure without exiting your terminal and clear a stale environment key when loading fails. Stop on that failure; do not make a request. An environment variable lasts only in that process and its children. Load the key again for later agent commands, or launch the client from the process that loaded it. A desktop app already running will not inherit an export from an unrelated terminal. Cloud connectors cannot read the local keychain or filesystem.

| Environment | Preferred source | Retrieval |
|---|---|---|
| Connected MCP | Client-managed credential | Invoke the connected tool; no local key copy |
| macOS | Keychain | Assignment below in the requesting process |
| Linux desktop | Existing Secret Service | `secret-tool` assignment below |
| Native Windows | DPAPI-protected user file | PowerShell load step below |
| Headless/CI | Host secret manager | Inject `SERPAPI_KEY` into the job |
| No secret store | Private file outside Git | Helper below; permission-protected plaintext |

## macOS Keychain

Use service `serpapi` and the current login account. Check for an existing item with output redirected before adding one. Have the user run this command in their terminal, with `-w` last so `security` prompts for the password:

```bash
security add-generic-password -a "$USER" -s serpapi -w
```

Do not add `-A` or broaden the item's access controls. Keychain can ask the user to unlock or approve access. Load the key in the process that will run the CLI or cURL:

```bash
serpapi_load_key() {
  set +x
  SERPAPI_KEY="$(security find-generic-password -a "$USER" -s serpapi -w)" || { unset SERPAPI_KEY; return 1; }
  test -n "$SERPAPI_KEY" || { unset SERPAPI_KEY; printf 'Stored key is empty.\n' >&2; return 1; }
  export SERPAPI_KEY
}
serpapi_load_key
```

Then run the selected route in that same process. Verify access with a real request; successful retrieval alone does not validate the key. `security help add-generic-password` documents the hidden prompt.

## Linux Secret Service

If `secret-tool` and an unlocked Secret Service are already available, have the user store the key through its hidden terminal prompt:

```bash
secret-tool store --label=SerpApi service serpapi
```

Reuse an existing item; do not run `store` over it unless replacing the key is intended. Retrieve in the process that makes the request:

```bash
serpapi_load_key() {
  set +x
  SERPAPI_KEY="$(secret-tool lookup service serpapi)" || { unset SERPAPI_KEY; return 1; }
  test -n "$SERPAPI_KEY" || { unset SERPAPI_KEY; printf 'Stored key is empty.\n' >&2; return 1; }
  export SERPAPI_KEY
}
serpapi_load_key
```

See the [secret-tool manual](https://manpages.debian.org/bookworm/libsecret-tools/secret-tool.1.en.html). Headless hosts may have no unlocked collection. Use an injected secret or the private-file fallback rather than installing a desktop keyring for a cURL-only workflow.

## Windows encrypted storage

On native Windows, PowerShell's [ConvertFrom-SecureString](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/convertfrom-securestring) uses DPAPI when no encryption key is supplied. Keep the encrypted file in the current user's local application data. This recipe is Windows-only; do not assume the same protection on other platforms.

Have the user run:

```powershell
$ErrorActionPreference = 'Stop'
$serpapiDir = Join-Path $env:LOCALAPPDATA 'SerpApi'
$serpapiKeyFile = Join-Path $serpapiDir 'api-key.dpapi'
if (Test-Path $serpapiKeyFile) { throw 'A stored key already exists; reuse it or explicitly rotate it.' }
New-Item -ItemType Directory -Force -Path $serpapiDir | Out-Null
Read-Host 'SerpApi API key' -AsSecureString | ConvertFrom-SecureString | Set-Content -LiteralPath $serpapiKeyFile
```

Load it in the calling PowerShell process:

```powershell
$ErrorActionPreference = 'Stop'
$serpapiKeyFile = Join-Path $env:LOCALAPPDATA 'SerpApi/api-key.dpapi'
$serpapiSecret = Get-Content -LiteralPath $serpapiKeyFile -Raw | ConvertTo-SecureString
$env:SERPAPI_KEY = [System.Net.NetworkCredential]::new('', $serpapiSecret).Password
if ([string]::IsNullOrWhiteSpace($env:SERPAPI_KEY)) { throw 'Stored key is empty.' }
```

The file belongs to that Windows user and machine. Supply credentials separately inside WSL, containers, and remote hosts. Do not log the decrypted environment or run secret-loading commands under a debugger that prints values.

## Private file on macOS, Linux, or WSL

If an OS secret store is unavailable or the user prefers a file, use `${XDG_CONFIG_HOME:-$HOME/.config}/serpapi/api_key`. This is **permission-protected plaintext, not encrypted storage**. Use an OS store or managed secret if encryption is required. Ensure the chosen config directory is outside the repository and is not a shared or synced location.

Run [save-key.sh](../scripts/save-key.sh) with Bash, resolving its path relative to this installed skill. It uses an existing `SERPAPI_KEY` or hidden terminal input, creates a `700` directory and `600` file, and refuses overwrites and symlinks at the store location. It resolves existing ancestors to reject Git worktrees, dot components, and a config parent writable by other users. Synced directories cannot be detected reliably; choose a local, unshared location. The helper stores the key; setup must still verify it with the API.

```bash
bash /absolute/path/to/serpapi-setup/scripts/save-key.sh
```

Later commands can use cURL's `api_key@filename` form without loading the value into command arguments. For CLI or a client that inherits environment variables:

```bash
serpapi_load_key() {
  set +x
  SERPAPI_KEY="$(cat "${XDG_CONFIG_HOME:-$HOME/.config}/serpapi/api_key")" || { unset SERPAPI_KEY; return 1; }
  test -n "$SERPAPI_KEY" || { unset SERPAPI_KEY; printf 'Stored key is empty.\n' >&2; return 1; }
  export SERPAPI_KEY
}
serpapi_load_key
```

Check ownership and permissions before reuse; require directory mode `700` and key-file mode `600`, and reject symlinks. Read with `cat` only inside the assignment above. Rotate only when intended, and verify the replacement through the selected route.

## Existing CLI login

`serpapi login` stores `config.toml` under the OS config directory's `serpapi` subdirectory, as implemented in the [CLI config source](https://github.com/serpapi/serpapi-cli/blob/main/pkg/config/config.go):

| OS | Location |
|---|---|
| macOS | `~/Library/Application Support/serpapi/config.toml` |
| Linux | `${XDG_CONFIG_HOME:-$HOME/.config}/serpapi/config.toml` |
| Windows | `%APPDATA%\serpapi\config.toml` |

Use the path reported by the installed CLI if its version differs. The file contains plaintext. The Unix implementation creates the directory with mode `700` and files with `600`; verify existing permissions. On Windows, verify the file's user ACL rather than assuming Unix mode bits provide protection. For encrypted storage, load an OS-stored key into `SERPAPI_KEY` instead of saving a second copy with `login`.

The CLI reads its own config. Do not `source` a TOML file or print it to recover a key. If an authorized route switch requires reusing that file, parse it locally with an available TOML parser and pass the key directly into the requesting process without displaying it.

## CI and remote agents

Use the host's secret manager to inject `SERPAPI_KEY` into the job or agent process. Record only the secret's name and scope. Do not copy local key files into a repository, image, or artifact. Confirm that the actual job or MCP client receives the variable before testing access.
