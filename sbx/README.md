# sbx config

Shared configuration and a launcher for running Codex or Claude Code in Docker
Sandboxes (`sbx`). Run `sbx-agent` from a project to create or reuse its sandbox
with shared skills, agent defaults, statuslines, and a Node toolchain.

## Requirements

On the host: Bash 4.4+, standard Unix utilities, and `sbx` 0.43 or newer with
the shared skills commands. Building the Codex image also requires Docker.
Kit APIs are experimental; validate against your host's `sbx` version.

## Quick start

1. On the host, point to this checkout and put the launcher on your `PATH`:

   ```sh
   export SBX_ROOT="$HOME/dotfiles/sbx" # Change if your checkout is elsewhere.
   mkdir -p "$HOME/.local/bin"
   ln -s "$SBX_ROOT/sbx-agent" "$HOME/.local/bin/sbx-agent"
   ```

   Make sure `~/.local/bin` is on `PATH`. The launcher resolves symlinks; keep
   `sbx-agent`, `lib/`, and `kits/` together in the checkout.

2. For Codex, build and import the image on the host (skip this for Claude):

   ```sh
   docker build -f "$SBX_ROOT/Dockerfile.codex" \
     -t docker.io/local/codex-native:latest "$SBX_ROOT"
   docker image save docker.io/local/codex-native:latest -o /tmp/codex-native.tar
   sbx template load /tmp/codex-native.tar
   ```

   Docker and `sbx` have separate image stores, so the import is required.
   The image includes native Codex, Docker Engine, and Playwright/Chromium.

3. From your project directory, launch either agent:

   ```sh
   sbx-agent codex
   # or
   sbx-agent claude
   ```

   Extra arguments after the agent name are forwarded to the agent. The launcher
   links the bundled skills into the host's standard skill directory, refreshes
   the sbx shared store, and waits for startup kits before opening the session.

The default Codex setup uses ChatGPT authentication. On first launch, follow the
login command printed by the launcher, then relaunch. See the
[Codex authentication and remote-control notes](docs/kits.md#codex-defaults)
for pairing and troubleshooting.

### Git worktrees

`sbx-agent` supports linked Git worktrees. When the workspace has a `.git`
pointer file, the launcher additionally mounts the worktree's shared Git
directory, allowing the agent to use history, status, branches, and commits.
The first launch uses a sandbox name ending in `-wt`, so it does not reuse an
older sandbox that was created without that mount. After confirming the new
sandbox works, remove the old sandbox with `sbx rm <old-sandbox-name>` if you
no longer need its sandbox-only files.

## Everyday use

The default `personal` preset enables automatic agent updates, shared skills,
statuslines, and Node 26. For Codex it also enables clipboard image paste, web
search, and remote control, and resets persisted Fast mode before each launch.

To leave agent settings alone and skip optional kits and automatic updates:

```sh
SBX_PRESET=minimal sbx-agent codex
```

The minimal preset uses a separate sandbox. To disable automatic agent updates
and update an existing sandbox explicitly:

```sh
SBX_AUTO_UPDATE=false sbx-agent codex
sbx-agent update codex
```

Use the same preset when launching and updating. Both commands also accept
`claude`. See [launcher configuration](docs/configuration.md) for all options.

Kit and image changes require recreating the sandbox; shared-skill changes are
imported on the next launch without recreation. Save sandbox-only files
before removing it; restarting does not apply new kits or images. See
[sandbox management](docs/sandbox-management.md) for the recreate workflow.

## Documentation

- [Launcher configuration](docs/configuration.md): presets, environment variables,
  updates, web search, and Herdr integration.
- [Codex image and pinned releases](docs/codex-image.md): custom builds, browser
  checks, image upgrades, and distribution by digest.
- [Sandbox management](docs/sandbox-management.md): direct `sbx` commands, YAML
  configuration, kit references, recreation, and network rules.
- [Kit reference](docs/kits.md): skills, agent defaults, authentication, clipboard,
  statuslines, and Node toolchain details.
- [Development and verification](docs/development.md): repository layout and checks.
