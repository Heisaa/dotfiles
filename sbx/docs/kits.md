# Kit reference

[Back to README](../README.md)

Examples use `SBX_ROOT` as the absolute path to this checkout on the host:

```sh
export SBX_ROOT="$HOME/dotfiles/sbx" # Change if your checkout is elsewhere.
```

## Shared skills

The checkout includes the original `feature-planning` skill, unchanged,
`write-pr` for drafting or revising PR titles and descriptions, and
`write-commit` for drafting or revising commit messages. `sbx-agent` exposes
these through sbx 0.43's shared skill store instead of copying them into each
sandbox through a kit.

On each personal launch it:

1. Adds a non-destructive top-level symlink under
   `~/.agents/skills/<skill-name>` when that name is absent.
2. Runs `sbx skills import --force` to refresh the persistent host store.
3. Creates new sandboxes with `--skills=readonly`.

The shared store is mounted at the discovery path for the selected agent, so
the same imported skills work in both Codex and Claude sandboxes. Existing
same-named host skills are never replaced by the launcher. Set
`SBX_SHARED_SKILLS=false` to skip import and create a new sandbox with
`--skills=off`.

Skill-store changes are visible on the next agent session and do not require
sandbox recreation. The editable canonical copies live under
`kits/shared-skills/files/home/.agents/skills/`; the `.claude/skills` copies
remain as a compatibility mirror and should be kept identical.
`feature-planning.skill` is the original ZIP archive, not read during launch.

## node-toolchain

`kind: mixin`, agent-agnostic — works in a `codex` sandbox as well as a
`claude` one. It exists so a fresh sandbox arrives with the toolchain this
workspace expects instead of the older one baked into the agent image, without
anyone having to ask the agent to upgrade it by hand.

Additional packages and the standalone script's Node fallback are declared in
[`files/home/.local/share/sbx/node-toolchain/packages.conf`](../kits/node-toolchain/files/home/.local/share/sbx/node-toolchain/packages.conf):

| Variable | Effect |
| --- | --- |
| `NODE_VERSION` | Node major or exact version to install from nodejs.org. Empty skips Node entirely. |
| `APT_PACKAGES` | Extra apt packages, space separated. |
| `NPM_GLOBAL_PACKAGES` | `npm install -g` list; versions may be pinned (`typescript@5.9.2`). |

The kit argument `version` (default `26`) overrides the script fallback through
`SBX_NODE_VERSION`. The launcher sets it from the host variable of the same name.
For direct kit use, pass `--kit-arg node-toolchain.version=26.8.1`. Changing
`packages.conf` controls extra apt/npm packages; choose Node via the kit argument.
The base image's Node remains available at `/usr/bin/node`.

The script checks installed packages before installing them. A floating Node
major resolves its latest version on every container start and requires network
access; an already-installed exact Node version skips that request. Nonempty
`NPM_GLOBAL_PACKAGES` is installed again on each start.

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
- **`SHASUMS256.txt` is fetched from `latest-v<major>.x/` (or `v<exact-version>/`).** One request
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
  [`files/home/.local/share/sbx/claude-defaults/settings.json`](../kits/claude-defaults/files/home/.local/share/sbx/claude-defaults/settings.json)
  is merged into `~/.claude/settings.json` **only if the key is absent**:
  anything Claude Code or you set afterwards (for example `/model`) wins.
- [`files/home/.local/share/sbx/claude-defaults/CLAUDE.md`](../kits/claude-defaults/files/home/.local/share/sbx/claude-defaults/CLAUDE.md)
  is copied to `~/.claude/CLAUDE.md` (the user-level instructions file Claude
  Code loads in every session) **only if that file does not exist**. Edit the
  sandbox copy freely; the kit never overwrites it.

Invalid JSON, a non-object JSON value, and read errors other than a missing file
stop setup without overwriting settings. Existing keys, including explicit nulls,
are preserved. Add or change defaults by editing those two files.

Currently:

| Setting | Value | Why |
| --- | --- | --- |
| `model` | `fable` | Alias for the latest Fable model, so a new sandbox starts on Fable instead of the image default. `claude --help` lists `fable`, `opus`, `sonnet` as valid aliases. |
| `outputStyle` | `Concise` | |
| `CLAUDE.md` | no subagents unless asked | Claude Code otherwise reaches for the Agent tool on its own for searches and reviews. An instruction rather than a permission deny, so an explicit "use subagents" still works. |

## codex-defaults

`kind: mixin`, requires the `codex` agent and Python 3.11+ in the sandbox.
Selects `forced_login_method = "chatgpt"` and `model_provider = "openai"`,
and clears persisted Fast mode. Both behaviors are configurable with kit arguments
`auth=chatgpt|preserve` and `reset_fast=true|false`. The launcher passes these from
its configuration and also clears Fast mode before each agent launch, including
inside an already-running container. Explicit agent CLI overrides still win.

New sandboxes created through `sbx-agent codex` or `codex.sbxenv.yaml` get
these authentication settings from this kit. The launcher also applies them
to existing sandboxes on every launch and passes matching CLI overrides.
This replaces sbx's proxy-managed API authentication for Codex with a local
ChatGPT login, needed for remote control. Credentials are not copied or baked
into the image. Sign in once inside each sandbox with
`codex login --device-auth`, then relaunch `sbx-agent codex`. The launcher
checks for ChatGPT login and runs `codex remote-control start` on every launch
without forcing a daemon restart. If login is missing it prints the host-side
login command; if remote-control startup fails it warns and still launches
local Codex. Run `codex remote-control pair` inside the sandbox when pairing
is needed. For launches without `sbx-agent`, start remote control manually.
An already-running daemon using old authentication settings may need a one-time
`codex app-server daemon restart` after signing in.

If remote-control enrollment returns HTTP 403 with
`Multi-factor authentication required`, enable MFA for your ChatGPT account,
then sign in again inside the sandbox and restart remote control. A successful
`codex login status` only confirms the CLI login; it does not confirm that
remote-control enrollment or pairing succeeded.

Sandboxes created directly with `sbx create` must include this kit to get
these defaults. Existing sandboxes must be relaunched through `sbx-agent codex`
to receive the migration; this does not change sbx's machine-wide defaults.

Codex's `/fast` toggle is not session-only: the TUI persists it by writing
`service_tier = "fast"` to the root of `$CODEX_HOME/config.toml` (see
`build_service_tier_selection_edits` in `codex-rs/tui/src/config_update.rs`),
so once toggled on, every later session starts fast and burns plan usage at
the Fast rate. Turning it off again clears the key; there is no "standard"
value — the only accepted values are `fast` and `flex`, and absence means the
standard tier.

The shared `reset-fast.py` helper, used by startup and the launcher, deletes any `service_tier = "fast"` line (root or
`[profiles.*]`) on every container start, and leaves everything else alone:
`flex` stays, comments stay, and a match inside a multiline string is never
touched because each removal is re-parsed and compared against the original
config before it is accepted. Inline-table profiles
(`profiles = { work = { service_tier = "fast" } }`) cannot be edited safely and
fail with a message naming the file; Codex itself never writes that form.

`/fast` still works inside a session — this only resets the persisted default.
To remove the toggle entirely instead, add `features.fast_mode = false` to
`config.toml`.

## codex-clipboard

Makes **Ctrl+V attach the host clipboard image directly in Codex**. Codex
0.154.0 uses arboard's native X11 reader, which does not invoke sbx's `wl-paste`
or `xclip` shims. Without a display, it reports an X11 connection timeout even
though `wl-paste --type image/png` can retrieve the image successfully.

The kit installs `xvfb` and `python3-xlib`, starts a small local display on
`:0` with TCP disabled, and serves its clipboard through sbx's existing HTTP
bridge. Images are fetched on demand when pasted; there is no clipboard
polling. XRes identifies the requesting process, and its
`SBX_HOST_SESSION_ID` selects the right host clipboard. This also works when
the service starts before a host session attaches. Large images use X11's
incremental transfer protocol. Native text copies are forwarded to sbx's
clipboard-write endpoint so `/copy` continues to reach the host.

`sbx-agent codex` installs the adapter and sets `DISPLAY=:0` automatically.
All source files live in this shared checkout:

```text
.sbx/kits/codex-clipboard/files/home/.local/share/sbx/codex-clipboard/
├── bridge.py
└── setup.sh
```

The launcher reads these files relative to its resolved location and sends
their contents into the target sandbox with `sbx exec`. The installed path
`/home/agent/.local/share/sbx/codex-clipboard/` is **inside the sandbox**; no
matching directory or symlink is required on the host. This works even when
launching a different project that does not share this checkout.

Exit and relaunch Codex through `sbx-agent codex` to pick up the display
variable. If a source file is missing or installation fails, the launcher
prints the failing path and starts Codex without the adapter.

For direct sbx usage, the adapter remains an optional kit, not included in
`codex.sbxenv.yaml`. Create a sandbox with it:

```sh
sbx create \
  --kit "$SBX_ROOT/kits/codex-clipboard" \
  codex .
```

Then launch with an explicit display:

```sh
sbx run --name my-codex-sandbox --env DISPLAY=:0
```

The display variable must reach the agent process: setting it only in a shell
profile does not affect an agent that sbx launches directly. For a sandbox
that was created without this kit, running the repository's `setup.sh` inside
it installs the adapter.

Service files live in `~/.local/share/sbx/codex-clipboard/`; the log is
`~/.cache/sbx-codex-clipboard/bridge.log`. The kit starts the service on every
container start. The adapter reserves display `:0` and refuses to replace an
unrelated server there. Image reads require the sbx host session identifier
and are limited to 64 MiB. Host clipboard text reads are not exposed.

Native X11 integration tests use a separate display and a fake host bridge;
they do not touch your clipboard:

```sh
python3 kits/codex-clipboard/test_bridge.py -v
```

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
sbx env run "$SBX_ROOT/codex.sbxenv.yaml" ./.sbxenv.yaml
```

The project file must use `agent: codex` (or omit `agent`) and compatible kits.
Use this base instead of `base.sbxenv.yaml`, which selects Claude and Claude kits.
For a one-off sandbox:

```sh
sbx create \
  --skills=readonly \
  --kit "$SBX_ROOT/kits/codex-defaults" \
  --kit "$SBX_ROOT/kits/codex-statusline" \
  codex .
```

The inline Python startup command adds the default to `$CODEX_HOME/config.toml` (normally
`~/.codex/config.toml`) only when `tui.status_line` is absent. Existing settings,
comments, and customized statuslines are preserved. Change an existing
statusline interactively with `/statusline`. Invalid TOML fails without
overwriting the file.

The statusline setup code is embedded in `spec.yaml` so startup does not depend on the
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
  `~/.claude/settings.json` only when `statusLine` is absent. Existing custom
  statuslines and unrelated settings are preserved; invalid JSON fails without
  overwriting the file.
- Written in Node, not `jq`/bash, because Node is guaranteed present in a
  Claude Code sandbox and `jq` is not — this keeps the kit free of an install
  step and of any network access.
