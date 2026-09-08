# sbx config

Shared configuration for Docker Sandboxes (`sbx`).

```
.sbx/
├── base.sbxenv.yaml           # Claude defaults merged into every project's .sbxenv.yaml
├── codex.sbxenv.yaml          # same, for Codex sandboxes
├── sbx-agent                  # launcher: picks kits by agent, creates/updates/runs
└── kits/
    ├── claude-defaults/       # mixin kit: default Claude Code settings + global CLAUDE.md
    ├── claude-statusline/     # mixin kit: Claude Code status line
    ├── codex-defaults/        # mixin kit: never start Codex in Fast mode
    ├── codex-statusline/      # mixin kit: Codex status line
    └── node-toolchain/        # mixin kit: Node.js + extra packages
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

- `sbx-agent claude`: `claude-defaults`, `claude-statusline`, `node-toolchain`.
- `sbx-agent codex`: `codex-defaults`, `codex-statusline`, `node-toolchain`.

Run `~/dotfiles/.sbx/sbx-agent claude` or `~/dotfiles/.sbx/sbx-agent codex`
from the project directory, or put the launcher on your `PATH`. Additional
arguments are forwarded to `sbx run`. Kits are validated before creation;
after creation, the launcher waits up to ten minutes for the startup dispatcher
to complete before updating or launching the agent. A kit failure or timeout
stops the launcher and prints the startup log. Existing containers are reused
without applying new kits.

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

## Machine-wide network rules

Not expressible in a kit. Apply once per machine:

```sh
sbx policy allow network nodejs.org,registry.npmjs.org,pypi.org
sbx policy ls
```

`nodejs.org` is what the `node-toolchain` kit downloads from; without it every
sandbox creation fails the Node step with a 403.

## node-toolchain

`kind: mixin`, agent-agnostic — works in a `codex` sandbox as well as a
`claude` one. It exists so a fresh sandbox arrives with the toolchain this
workspace expects instead of the older one baked into the agent image, without
anyone having to ask the agent to upgrade it by hand.

Everything it installs is declared in one file,
[`files/home/.local/share/sbx/node-toolchain/packages.conf`](kits/node-toolchain/files/home/.local/share/sbx/node-toolchain/packages.conf):

| Variable | Effect |
| --- | --- |
| `NODE_MAJOR` | Node major to install from nodejs.org. Empty skips Node entirely. |
| `APT_PACKAGES` | Extra apt packages, space separated. |
| `NPM_GLOBAL_PACKAGES` | `npm install -g` list; versions may be pinned (`typescript@5.9.2`). |

Currently `NODE_MAJOR=26` — the base image ships the distro's Node 22.

Cold run takes about 9 seconds; a re-run is a no-op in well under a second, so
the step is safe to leave enabled on every sandbox.

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
