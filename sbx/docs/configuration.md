# Launcher configuration

[Back to README](../README.md)

Examples use `SBX_ROOT` as the absolute path to this checkout on the host:

```sh
export SBX_ROOT="$HOME/dotfiles/sbx" # Change if your checkout is elsewhere.
```

The launcher resolves its checkout location automatically and does not require
`SBX_ROOT`; direct `sbx env` commands using the supplied YAML files do. Sandbox
images require Python 3.11+, Node, and the Docker startup dispatcher.

## Presets and options

`SBX_PRESET=personal` is the default and preserves this setup's preferences.
`SBX_PRESET=minimal sbx-agent codex` leaves agent settings alone and skips optional
kits, clipboard setup, remote control, search overrides and automatic updates.
Minimal sandboxes have a separate `-minimal` name so trying the preset does not
reuse a sandbox already provisioned with personal settings.

Configure the launcher with environment variables (booleans are `true`/`false`):

| Variable | Personal default | Effect |
| --- | --- | --- |
| `SBX_PRESET` | `personal` | `personal` or `minimal` |
| `SBX_AUTO_UPDATE` | `true` | Update the agent before launch |
| `SBX_CODEX_AUTH` | `chatgpt` | `chatgpt` or `preserve`; preserve leaves the provider/login configuration alone |
| `SBX_REMOTE_CONTROL` | `true` | Attempt Codex remote control after checking login |
| `SBX_CODEX_SEARCH` | `true` | Enable search flags and suppress unstable-feature warnings |
| `SBX_RESET_FAST` | `true` | Clear persisted Fast mode before each Codex launch |
| `SBX_SHARED_SKILLS` | `true` | Import host skills into sbx and mount the shared store read-only; `false` creates the sandbox with `--skills=off` |
| `SBX_AGENT_DEFAULTS` | `true` | Include Claude's model/style/instruction defaults; Codex uses AUTH and RESET_FAST instead |
| `SBX_STATUSLINE` | `true` | Include the agent's statusline kit |
| `SBX_NODE_TOOLCHAIN` | `true` | Include the Node toolchain kit |
| `SBX_NODE_VERSION` | `26` | Major, exact version such as `26.8.1`, or empty to keep image Node |
| `SBX_CLIPBOARD` | `true` | Install/start the Codex clipboard adapter |
| `SBX_CODEX_TEMPLATE` | `docker.io/local/codex-native:latest` | Codex image reference |
| `SBX_CLAUDE_TEMPLATE` | unset | Optional Claude image reference |
| `SBX_RELEASE_MODE` | `rolling` | `rolling` or `pinned` |

In the minimal preset all booleans default to `false` and authentication defaults
to `preserve`; explicit variables override the preset. CLI arguments after the
agent name are forwarded unchanged. Do not put secrets in these variables.

Example: keep sandbox-managed API authentication, omit remote control, and
update only when requested:

```sh
SBX_CODEX_AUTH=preserve SBX_REMOTE_CONTROL=false SBX_AUTO_UPDATE=false sbx-agent codex
sbx-agent update codex
```

`update` updates an existing project sandbox without opening the agent. It exits
nonzero on failure and never creates a missing sandbox. Use the same preset as
when launching. Updating Node is separate: select a new version and recreate.
Kit selection and kit arguments are captured at creation. Changing them does
not remove previously installed kits or undo their settings; recreate the sandbox
after saving sandbox-only files. Launch-time settings apply immediately, but an
old startup kit can still apply its saved preferences on the next container start.
Direct YAML use selects the personal kits and read-only shared store but does
not refresh it or read launcher preferences. Run `sbx skills import --force`
before direct YAML use when host skills changed.

## Usage

The executable [`sbx-agent`](../sbx-agent) launcher selects kits by agent:

- `sbx-agent claude`: `claude-defaults`, `claude-statusline`, `node-toolchain`.
- `sbx-agent codex`: `codex-defaults`, `codex-statusline`, `node-toolchain`.

Run `$SBX_ROOT/sbx-agent claude` or `$SBX_ROOT/sbx-agent codex`
from the project directory, or symlink the launcher onto your `PATH`. The
launcher resolves symlinks before locating the kits beside it. Additional
arguments are forwarded to `sbx run`. Kits are validated before creation;
on every personal launch, it links missing bundled skills into
`~/.agents/skills`, runs `sbx skills import --force`, and mounts the shared
store read-only. Existing same-named host skills are preserved. The launcher
then waits for the current container startup dispatcher to complete before
updating or launching the agent. Stale completion records from previous
container starts are ignored. If sandboxd fails to replay registered startup
commands after a daemon or host restart, the launcher detects the stale record
after a short grace period and replays the root-owned dispatcher once. A kit
failure or an otherwise unresponsive dispatcher times out after ten minutes,
stops the launcher, and prints the startup log. Existing containers are reused
without applying new kits; kits are only applied at creation. The Codex launcher
also installs the clipboard adapter directly in new and existing sandboxes.
If that optional setup fails, it prints the error and still starts Codex.

## Codex web search

The launcher enables live web search and the experimental standalone search
feature with the OpenAI provider. It passes:

```text
--search --enable standalone_web_search -c forced_login_method=chatgpt -c model_provider=openai
-c suppress_unstable_features_warning=true
```

Web search and page opening previously worked with the sandboxd provider.
Search with the new ChatGPT authentication settings still needs a live check
after signing in.

The [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
describes standalone search as under development and off by default.

The launcher also suppresses startup warnings for all unstable features without
disabling them. This setting lives in the shared `.sbx/sbx-agent` script; no host
Codex config or manual edit to the sandbox's `/home/agent/.codex/config.toml` is
needed. To apply the launcher flags to an existing sandbox, exit and relaunch
through `sbx-agent codex`; rebuilding the image is not required. With direct
`sbx run`, pass the flags after `--`.

## Herdr detection

`sbx-agent` sets `HERDR_AGENT=claude` or `HERDR_AGENT=codex` immediately
before replacing itself with `sbx run`. This lets Herdr on the host select
the agent's existing screen manifest even though the agent process is inside
the sandbox. Relaunch through `sbx-agent` to pick up this change; existing
sandboxes do not need to be recreated.

When running `sbx` directly, set the hint on the host command:

```sh
HERDR_AGENT=claude sbx run --name my-claude-sandbox
HERDR_AGENT=codex sbx run --name my-codex-sandbox
HERDR_AGENT=claude sbx env run "$SBX_ROOT/base.sbxenv.yaml" ./.sbxenv.yaml
```

Use the agent matching the sandbox. Setting the hint only inside a kit or
container cannot help host-side Herdr. Avoid exporting it globally, since
unrelated foreground commands would inherit the agent identity.

`HERDR_PROCESS_DETECTION=child-groups` addresses a separate issue: restricted
Linux runtimes where Herdr cannot obtain the terminal's foreground process
group. Use it only if that problem occurs, in the environment of the Herdr
server, and restart the server. Setting it on an attaching client has no
effect. Native detection remains preferred; child-group inference can mistake
a newer background job for the foreground job.
