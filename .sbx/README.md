# sbx config

Shared configuration for Docker Sandboxes (`sbx`).

```
.sbx/
├── base.sbxenv.yaml           # Claude defaults merged into every project's .sbxenv.yaml
├── codex.sbxenv.yaml          # same, for Codex sandboxes
├── pi.sbxenv.yaml             # same, for Pi sandboxes
├── sbx-agent                  # launcher: picks kits by agent, creates/updates/runs
└── kits/
    ├── claude-defaults/       # mixin kit: default Claude Code settings + global CLAUDE.md
    ├── claude-statusline/     # mixin kit: Claude Code status line
    ├── codex-defaults/        # mixin kit: never start Codex in Fast mode
    ├── codex-statusline/      # mixin kit: Codex status line
    ├── pi/                   # sandbox kit: Pi on shell-docker
    ├── node-toolchain/        # mixin kit: Node.js, Playwright + Chromium
    └── skills/               # mixin kit: shared Codex, Claude Code, and Pi skills
```

## There is no global sbx config file

`sbx` has no user-level config that applies to every sandbox. Settings reach a
sandbox three ways, and only the last is machine-wide:

| Mechanism | Scope |
| --- | --- |
| Kits | Per sandbox — referenced by path in `kits:` or passed with `--kit` |
| `.sbxenv.yaml` | Per project directory |
| `sbx policy` / `sbx secret` | Machine-wide (network rules, credentials) |

`base.sbxenv.yaml` is the workaround for the first two: `sbx env` deep-merges
multiple files (docker-compose `-f` semantics, later files win), so pass this
one first and the project file second.

## Kits are references, not installed names

There is no kit registry. `sbx kit` has no `ls` and no `install` subcommand —
only `add`, `inspect`, `pack`, `pull`, `push`, `sign`, `validate`, `verify`.
Every place that takes a kit takes a **reference**: a local directory, a ZIP
file, an OCI reference, or a git URL. A bare name like `claude-statusline` has
nothing to resolve against.

So `base.sbxenv.yaml` lists absolute paths, using the `${VAR}` expansion
`sbx env` performs on values. Absolute rather than relative because nothing
documents which directory a relative kit reference resolves against, and the
answer should not depend on where you happened to run `sbx` from.

## Usage

The executable [`sbx-agent`](sbx-agent) launcher selects kits by agent:

- `sbx-agent claude`: `claude-defaults`, `claude-statusline`, `node-toolchain`, `skills`.
- `sbx-agent codex`: `codex-defaults`, `codex-statusline`, `node-toolchain`, `skills`.
- `sbx-agent pi`: the `pi` sandbox kit, `node-toolchain`, `skills`.

Run `~/dotfiles/.sbx/sbx-agent claude`, `~/dotfiles/.sbx/sbx-agent codex`,
or `~/dotfiles/.sbx/sbx-agent pi`
from the project directory, or put the launcher on your `PATH`. Additional
arguments are forwarded to the agent. Pi launches directly with `sbx exec -it`
in the project directory, allowing interactive `/login`; when input or output
is redirected, it uses `-i` without allocating a terminal. Claude and Codex use
`sbx run`. Kits are validated before creation;
after creation, the launcher waits up to ten minutes for the startup dispatcher
to complete before updating or launching the agent. A kit failure or timeout
stops the launcher and prints the startup log. Existing containers are reused
without applying new kits.

The launcher prints a sandbox availability check before contacting the daemon
and stops if listing sandboxes fails. After the agent session returns, it restores the
terminal settings and main screen and reports a nonzero exit status. This helps
when an agent crashes while using raw input or the alternate screen; it cannot
recover output an application has already cleared or repair a stuck host daemon.

If your shell function calls `~/.local/bin/sbx-agent`, keep that path linked to
this launcher so edits take effect (check with `ls -l ~/.local/bin/sbx-agent`).
If commands also hang in a fresh host terminal, Docker recommends
`sbx daemon restart`, which preserves sandbox data, followed by `sbx diagnose`
if the problem persists. See the
[daemon troubleshooting guide](https://docs.docker.com/ai/sandboxes/troubleshooting/#restart-the-sandbox-daemon).

Start a sandbox with the shared defaults:

```sh
sbx env run ~/dotfiles/.sbx/base.sbxenv.yaml ./.sbxenv.yaml
```

Or a one-off sandbox without an env file — note `sbx create` takes
`AGENT PATH`, and `--kit` takes the same references:

```sh
sbx create \
  --kit ~/dotfiles/.sbx/kits/claude-defaults \
  --kit ~/dotfiles/.sbx/kits/claude-statusline \
  --kit ~/dotfiles/.sbx/kits/node-toolchain \
  claude .
```

### Editing a kit means recreating the sandbox

Kits are read at sandbox creation, so an edit reaches the *next* sandbox you
create. Two things stand between you and a shorter loop, and both bite:

- `sbx env run` on a sandbox that already exists starts and re-attaches it
  **without re-provisioning**, so an edited `base.sbxenv.yaml` is never read.
- `sbx kit add SANDBOX REFERENCE` refuses any kit that declares
  `setup.startup`:

  ```
  ERROR: kit "node-toolchain" declares setup.startup, which the kit-add
  recreate flow does not yet apply; recreate the sandbox from scratch via
  `sbx rm` + `sbx create --kit` to use this kit
  ```

  All kits here are startup kits, so `sbx kit add` is never the answer for
  them.

The only way to pick up a kit change is therefore a full recreate:

```sh
sbx rm my-sandbox
sbx env run ~/dotfiles/.sbx/base.sbxenv.yaml ./.sbxenv.yaml
```

Check a kit before relying on it:

```sh
sbx kit validate ~/dotfiles/.sbx/kits/node-toolchain
```

## Shared skills

The agent-agnostic `skills` kit is included in all three base environment files and
all launcher modes. It contains `write-design-doc`, extracted with all supporting
files from `write-design-doc.zip`.

Keep skill folders under `kits/skills/files/home/.local/share/sbx/skills/`.
The startup installer links each folder containing `SKILL.md` into both
`~/.agents/skills/` (Codex) and `~/.claude/skills/` (Claude Code). Both links
point to the same sandbox copy. Pi also discovers `~/.agents/skills/`. Repeated startup is safe; an existing unrelated
skill with the same directory name causes an error instead of being overwritten.

Invoke it with `$write-design-doc` in Codex, `/write-design-doc` in Claude Code,
or `/skill:write-design-doc` in Pi.
The personal discovery locations and symlinks are supported by the
[Codex documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)
and [Claude Code documentation](https://code.claude.com/docs/en/skills#choose-where-skills-load).

Kit files are snapshots taken at creation, so recreate existing sandboxes to
receive this kit or later skill edits. The launcher reuses existing sandboxes
without adding kits. To validate the kit on the host:

```sh
sbx kit validate ~/dotfiles/.sbx/kits/skills
```

## Machine-wide network rules

The Node toolchain kit declares download hosts in `permissions.network.allow`.
For sandboxes outside these defaults, equivalent machine-wide rules can be
applied once on the host:

```sh
sbx policy allow network nodejs.org,registry.npmjs.org,pypi.org,cdn.playwright.dev,playwright.download.prss.microsoft.com,cdn.download.prss.microsoft.com
sbx policy ls
```

Explicit local or organization deny rules still take precedence. Apt repositories
need network access too; use `sbx policy log` to diagnose blocked downloads.

## node-toolchain

`kind: mixin`, agent-agnostic — used by Claude, Codex, and Pi sandboxes. It exists so a fresh sandbox arrives with the toolchain this
workspace expects instead of the older one baked into the agent image, without
anyone having to ask the agent to upgrade it by hand.

Everything it installs is declared in one file,
[`files/home/.local/share/sbx/node-toolchain/packages.conf`](kits/node-toolchain/files/home/.local/share/sbx/node-toolchain/packages.conf):

| Variable | Effect |
| --- | --- |
| `NODE_MAJOR` | Node major to install from nodejs.org. Empty skips Node entirely. |
| `APT_PACKAGES` | Extra apt packages, space separated. |
| `NPM_GLOBAL_PACKAGES` | `npm install -g` list; versions may be pinned (`typescript@5.9.2`). |
| `PLAYWRIGHT_VERSION` | Pinned Playwright Test version, with matching Chromium and headless shell. Empty disables browser installation. |

Currently `NODE_MAJOR=26` — the base image ships the distro's Node 22.

The first run downloads Chromium and installs its system libraries, so allow
several minutes. Subsequent starts reuse the pinned Playwright package, browser
cache, and a versioned system-dependency marker. Node still checks its latest
patch version online.

The startup step declares `user: "0"` so it runs as root. This is required:
`sbx create` shows a step without `user:` as `user=1000`, i.e. the agent user,
not root. The script still re-execs itself through `sudo -n` if it ever runs
unprivileged.

Startup steps run on **every container start**, after `sbx create` has
returned, so `sbx exec NAME node -v` immediately after creation can still show
the distro Node. Check `/var/log/sbx-kit-startup.log` inside the sandbox to
see whether the step has finished.

### How Node is installed

The official tarball is unpacked to `/opt/node/<version>`, `current` points at
it, and `node`, `npm`, `npx` and `corepack` are symlinked into
`/usr/local/bin`. That directory already precedes `/usr/bin` on `PATH`, so
nothing is appended to `/etc/sandbox-persistent.sh` and no shell profile is
touched. The distro package stays installed at `/usr/bin/node` as a fallback.

Details worth knowing before editing the script:

- **apt waits for the lock.** The `claude` kit's own startup step runs
  `apt-get update` in the background, so on a fresh start apt's lists lock is
  still held when this script reaches `apt-get install`. apt fails instantly
  on a held lock (exit 100), which took the whole dispatcher down with it.
  `apt_wait` polls `fuser` on the apt/dpkg lock files for up to five minutes
  before any apt call.
- **`.tar.gz`, not `.tar.xz`.** The base image has no `xz` binary, and pulling
  one in would add an apt round-trip to every sandbox start.
- **`libatomic1` is installed unconditionally with Node.** The official builds
  link against it and the image omits it; without it the new binary dies at
  exec with a loader error.
- **`SHASUMS256.txt` is fetched from `latest-v$NODE_MAJOR.x/`.** One request
  yields both the floating patch version's exact filename and its checksum,
  which is verified before unpacking.
- **The version is resolved before anything is downloaded**, so a sandbox that
  already has the right Node exits immediately.
- **Global npm packages install as uid 1000 with `sudo -E -H`.** `-H` matters:
  without it `HOME` stays `/root` and npm fails on a cache it cannot read.
  `NPM_CONFIG_PREFIX` is restated on the command line because sudo's
  `env_reset` drops it even under `-E` — otherwise npm falls back to its
  builtin prefix inside `/opt/node/<version>`, which this script deletes on the
  next Node upgrade, silently taking every global package with it.

## claude-defaults

`kind: mixin`, requires the `claude` agent. The host has no `~/.claude` for
sbx to copy settings from, so this kit is how Claude Code defaults reach a
sandbox. Two startup steps, both run on every container start:

- Every key in
  [`files/home/.local/share/sbx/claude-defaults/settings.json`](kits/claude-defaults/files/home/.local/share/sbx/claude-defaults/settings.json)
  is merged into `~/.claude/settings.json` **only if the key is absent**:
  anything Claude Code or you set afterwards (for example `/model`) wins.
- [`files/home/.local/share/sbx/claude-defaults/CLAUDE.md`](kits/claude-defaults/files/home/.local/share/sbx/claude-defaults/CLAUDE.md)
  is copied to `~/.claude/CLAUDE.md` (the user-level instructions file Claude
  Code loads in every session) **only if that file does not exist**. Edit the
  sandbox copy freely; the kit never overwrites it.

Add or change defaults by editing those two files.

Currently:

| Setting | Value | Why |
| --- | --- | --- |
| `model` | `fable` | Alias for the latest Fable model, so a new sandbox starts on Fable instead of the image default. `claude --help` lists `fable`, `opus`, `sonnet` as valid aliases. |
| `outputStyle` | `Concise` | |
| `CLAUDE.md` | no subagents unless asked | Claude Code otherwise reaches for the Agent tool on its own for searches and reviews. An instruction rather than a permission deny, so an explicit "use subagents" still works. |

## codex-defaults

`kind: mixin`, requires the `codex` agent and Python 3.11+ in the sandbox.
Makes sure Codex never **starts** in Fast mode.

Codex's `/fast` toggle is not session-only: the TUI persists it by writing
`service_tier = "fast"` to the root of `$CODEX_HOME/config.toml` (see
`build_service_tier_selection_edits` in `codex-rs/tui/src/config_update.rs`),
so once toggled on, every later session starts fast and burns plan usage at
the Fast rate. Turning it off again clears the key; there is no "standard"
value — the only accepted values are `fast` and `flex`, and absence means the
standard tier.

The startup step therefore deletes any `service_tier = "fast"` line (root or
`[profiles.*]`) on every container start, and leaves everything else alone:
`flex` stays, comments stay, and a match inside a multiline string is never
touched because each removal is re-parsed and compared against the original
config before it is accepted. Inline-table profiles
(`profiles = { work = { service_tier = "fast" } }`) cannot be edited safely and
fail with a message naming the file; Codex itself never writes that form.

`/fast` still works inside a session — this only resets the persisted default.
To remove the toggle entirely instead, add `features.fast_mode = false` to
`config.toml`.

## codex-statusline

`kind: mixin`, requires the `codex` agent and Python 3.11+ in the sandbox.
Configures Codex's native terminal footer with context **used**, five-hour
quota **remaining**, and weekly quota **remaining**:

```toml
[tui]
status_line = ["context-used", "five-hour-limit", "weekly-limit"]
```

Create a Codex sandbox with the dedicated base file:

```sh
sbx env run ~/dotfiles/.sbx/codex.sbxenv.yaml ./.sbxenv.yaml
```

The project file must use `agent: codex` (or omit `agent`) and compatible kits.
Use this base instead of `base.sbxenv.yaml`, which selects Claude and Claude kits.
For a one-off sandbox:

```sh
sbx create \
  --kit ~/dotfiles/.sbx/kits/codex-defaults \
  --kit ~/dotfiles/.sbx/kits/codex-statusline \
  codex .
```

The inline Python startup command adds the default to `$CODEX_HOME/config.toml` (normally
`~/.codex/config.toml`) only when `tui.status_line` is absent. Existing settings,
comments, and customized statuslines are preserved. Change an existing
statusline interactively with `/statusline`. Invalid TOML fails without
overwriting the file.

The setup code is embedded in `spec.yaml` so startup does not depend on the
timing of kit file copies. Version 0.1.0 could fail with a missing `setup.py`
when the dispatcher ran before that file was available.

Quota fields depend on the rate-limit information available to Codex for the
signed-in account; the kit does not fetch usage or credentials itself. These
are terminal UI fields, not output from noninteractive `codex exec`.
Item identifiers were checked against Codex CLI 0.153.4.
See the [official configuration reference](https://developers.openai.com/codex/config-reference/)
for `tui.status_line`.

As with the other startup kits, recreate an existing sandbox to pick up the kit.

## claude-statusline

`kind: mixin`, requires the `claude` agent. Renders:

```
📦 sandbox-name | Opus 5 | dotfiles | ⎇ work | ctx 34% | left 5h 77% · 7d 59%
```

`ctx` is context window **used** (green under 70%, yellow under 90%, red above).
Everything after `left` is plan quota **remaining** (red at 10% or less, yellow
at 25% or less), from `rate_limits`:

| Segment | Source | Notes |
| --- | --- | --- |
| `5h` | `rate_limits.five_hour` | Rolling five-hour window |
| `7d` | `rate_limits.seven_day` | Weekly window |
| `$` | `rate_limits.spend_limit` | Only behind a Claude apps gateway with a spend limit |

`rate_limits` exists only for Pro and Max subscribers, and only after the first
API response of a session. Each window can be absent independently, and Claude
Code drops a window once its `resets_at` passes — the whole `left` group is
omitted when nothing is available.

### There is no Fable weekly window

Claude Code's status line exposes exactly three windows: `five_hour`,
`seven_day`, `spend_limit`. There is no Fable-specific (or Opus-specific)
rate limit in the JSON, so it cannot be displayed. This matches how the limits
actually work:

- **Max**: Fable draws from the same weekly limit as every other model, capped
  at 50% of it. It is already counted inside `7d` — a separate bar would be
  double-counting.
- **Pro**: Fable runs on pay-as-you-go usage credits and is outside plan limits
  entirely. The nearest available signal is `$`, which is why `spend_limit` is
  rendered when present.

Model-family limits do exist as *errors* ("You've hit your Opus limit"), but
Claude Code does not surface them as a percentage anywhere a script can read.

- `files/home/.claude/statusline.mjs` is copied to `/home/agent/.claude/` at
  sandbox creation. Edit it to change what the line shows; the JSON it reads on
  stdin is documented at <https://code.claude.com/docs/en/statusline>.
- A startup command merges the `statusLine` key into
  `~/.claude/settings.json` rather than overwriting the file, so it does not
  clobber settings the agent kit, `claude-defaults` or your workspace put
  there.
- Written in Node, not `jq`/bash, because Node is guaranteed present in a
  Claude Code sandbox and `jq` is not — this keeps the kit free of an install
  step and of any network access.

## Pi

From your project directory:

```sh
~/dotfiles/.sbx/sbx-agent pi
# Agent arguments are forwarded, for example:
~/dotfiles/.sbx/sbx-agent pi --provider anthropic
```

Pi is a custom `kind: sandbox` kit based on `docker/sandbox-templates:shell-docker`.
The launcher supplies `--kit /absolute/path/to/kits/pi` and selects the agent
by its spec name, `pi`. This supports sbx releases before 0.42, which reject a
kit path in the agent position with `unknown agent`. The path-as-agent syntax
was added in [sbx 0.42](https://github.com/docker/sbx-releases/releases/tag/v0.42.0);
the older form is retained here for compatibility. Pi is installed
at creation and checked for npm updates before each launch, under a stable,
agent-writable npm prefix that survives Node upgrades.

New Pi sandboxes install these extensions as the agent user during creation:

- `npm:@juicesharp/rpiv-ask-user-question`
- `npm:@juicesharp/rpiv-todo`
- `npm:pi-goal-x`
- `npm:@juicesharp/rpiv-voice`
- `npm:pi-background-tasks`

The kit runs `pi install` for each package, which registers it in the agent's
user settings. Versions are unpinned, so creation installs the latest releases.
Use `pi list` to inspect installed packages and `pi update --extensions` to
update them. Recreate existing sandboxes to apply this kit change, or run the
five `pi install` commands from `kits/pi/spec.yaml` inside an existing sandbox.

Pi voice models are shared across sandboxes created through `sbx-agent pi` or
`pi.sbxenv.yaml`. Before creation, the host downloads Whisper once into
`~/.cache/sbx/pi-voice/whisper-base/`. Each sandbox mounts the cache read-only
and links `~/.pi/models/whisper-base` to it. The cache survives sandbox removal;
each running recognizer still uses its own RAM.

The host needs Python 3 and curl. A file lock serializes simultaneous launches;
downloads are staged and only published after all three required files are
extracted. Subsequent launches reuse the completed cache without downloading.
Only the int8 encoder, int8 decoder, tokens, and `.download-complete` marker
are kept (about 157 MB). To prepare the cache separately:

```sh
python3 ~/dotfiles/.sbx/kits/pi/prepare-voice-model.py
```

Existing sandboxes must be recreated to acquire the additional mount. A plain
`sbx create --kit … pi .` does not configure sharing: also pass
`--env "SBX_PI_VOICE_CACHE=$HOME/.cache/sbx/pi-voice"` before `pi` and
`"$HOME/.cache/sbx/pi-voice:ro"` after the project path, with the cache prepared
first. Without that environment variable, the kit leaves voice model storage
local. A conflicting local model directory is preserved and reported rather
than overwritten. Microphone access from the sandbox remains unverified;
sharing model files does not forward the host microphone.

This uses Docker's [additional workspace mounts](https://docs.docker.com/ai/sandboxes/usage/#multiple-workspaces)
and the extension's [fixed model path and completion marker](https://github.com/juicesharp/rpiv-mono/blob/main/packages/rpiv-voice/docs/model.md).

The current official package is `@earendil-works/pi-coding-agent`; see the
[Pi quick start](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/README.md#quick-start).
Run `/login` inside Pi to authenticate with your provider, then `/model` to
select a model. Authentication is sandbox-local; host Pi credentials are not
copied. The kit allows common Anthropic and OpenAI API/login hosts and the DeepInfra API. Other
providers may need additional network rules, visible in `sbx policy log`.

DeepInfra is registered on startup in `~/.pi/agent/models.json`, with
five current featured coding models from the [DeepInfra catalog](https://deepinfra.com/models)
(checked September 13, 2026):

- `deepseek-ai/DeepSeek-V4.1-Flash`
- `zai-org/GLM-5.3`
- `zai-org/GLM-5.3-Flash`
- `moonshotai/Kimi-K3`
- `Qwen/Qwen3.8-2.4T-A95B`

These are featured models; no public usage ranking was available to verify
which models are most used. Startup removes the previous DeepSeek V3.2 entry
and adds missing models from this list. Existing provider settings, custom
models, and overrides for these model IDs are preserved. The configuration uses DeepInfra's
[OpenAI-compatible API](https://docs.deepinfra.com/quickstart) and Pi's
[custom provider format](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md).
Inside Pi, run `/login`, select `deepinfra`, and enter your DeepInfra API key;
then select the model with `/model`. Alternatively, set `DEEPINFRA_API_KEY`
in the sandbox environment before launching Pi. Host environment variables
are not automatically forwarded by the launcher.

```sh
~/dotfiles/.sbx/sbx-agent pi --provider deepinfra --model deepseek-ai/DeepSeek-V4.1-Flash
```

Add more model entries in the sandbox's `~/.pi/agent/models.json` as needed.
Listed prices are a snapshot of standard-tier rates, including the current
GLM Flash discount; refresh them in `models.json` when rates change. Explicit
paid cache retention is not enabled. The output limit is capped at 32,768 tokens; Pi thinking-level controls
are disabled for this provider because reasoning parameters vary by backend.
Existing sandboxes need recreation to pick up this kit change (see above).

For an environment file workflow:

```sh
sbx env run ~/dotfiles/.sbx/pi.sbxenv.yaml ./.sbxenv.yaml
```

The project file must omit `agent` or use `agent: pi`; it must not
include Claude/Codex-specific kits. For a one-off creation:

```sh
sbx create \
  --kit ~/dotfiles/.sbx/kits/pi \
  --kit ~/dotfiles/.sbx/kits/node-toolchain \
  --kit ~/dotfiles/.sbx/kits/skills \
  pi .
```

The custom-agent structure follows Docker's
[kit reference](https://docs.docker.com/ai/sandboxes/customize/kit-reference/).
Use `sbx-agent` to wait for toolchain startup before attaching.

## Playwright and headless Chromium

Every new sandbox created through these launcher modes or base environment
files includes `@playwright/test` (currently 1.63.0), the `playwright` CLI,
Chromium, its headless shell, and the required Linux libraries. Bare `sbx run`
commands that omit these kits do not inherit these defaults.

Browser binaries download as the agent user into `~/.cache/ms-playwright`,
where Playwright looks by default. System libraries install as root. The setup
uses Playwright's [browser installation commands](https://playwright.dev/docs/browsers).

Inside a sandbox, check the CLI or take a screenshot:

```sh
playwright --version
playwright screenshot --browser chromium https://example.com /tmp/example.png
```

For project tests, declare `@playwright/test` in the project's dev dependencies;
Node does not automatically resolve global npm packages in project imports.
Matching the shared version reuses the downloaded browser. A project with a
different Playwright version needs its own `npx playwright install chromium`.
For a standalone script using the preinstalled package:

```sh
node <<'JS'
const { chromium } = require('/usr/local/share/npm-global/lib/node_modules/@playwright/test');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setContent('<h1>Chromium works</h1>');
  console.log(await page.locator('h1').innerText());
  await browser.close();
})();
JS
```

Recreate existing sandboxes to receive these defaults; the launcher deliberately
reuses them without provisioning. Save any needed sandbox-local state first.

## Development checks

Run `python3 -m unittest discover -s tests -v` for launcher routing, argument
forwarding, reuse, and failure handling. Validate kit specs on the host with
`sbx kit validate kits/pi` and `sbx kit validate kits/node-toolchain`.
