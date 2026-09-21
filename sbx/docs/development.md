# Development and verification

[Back to README](../README.md)

## Repository layout

```
.sbx/
├── base.sbxenv.yaml           # Claude defaults merged into every project's .sbxenv.yaml
├── codex.sbxenv.yaml          # same, for Codex sandboxes
├── Dockerfile.codex           # native Codex + Docker Engine + Playwright/Chromium
├── codex-image/               # native updater and Chromium launcher
├── sbx-agent                  # launcher: picks kits by agent, creates/updates/runs
├── lib/                       # current-container startup readiness check
├── feature-planning.skill    # original skill archive
└── kits/
    ├── shared-skills/        # source skills imported into sbx's shared store
    ├── claude-defaults/       # mixin kit: default Claude Code settings + global CLAUDE.md
    ├── claude-statusline/     # mixin kit: Claude Code status line
    ├── codex-defaults/        # mixin kit: configurable auth and Fast-mode reset
    ├── codex-statusline/      # mixin kit: Codex status line
    ├── codex-clipboard/       # mixin kit: native Ctrl+V image paste through sbx
    └── node-toolchain/        # mixin kit: Node.js + extra packages
```

Run the following commands from the checkout root.

## Local verification

```sh
python3 -B -m unittest test_sbx_agent test_reliability -v
/usr/bin/python3 -B kits/codex-clipboard/test_bridge.py -v
```

Launcher tests use a fake `sbx`; reliability tests use temporary settings and
mock downloads. Clipboard tests require Xvfb and python3-xlib and use an isolated
display and fake host bridge. On the host, also run `sbx kit validate` on each kit
and smoke-test fresh creation, stopped-container restart and failed-startup retry.
The readiness helper depends on the dispatcher's timestamped log format. A
recognizable stale record triggers one launcher-managed replay to work around
sandboxd losing startup callbacks across daemon restarts; an incompatible log
format still fails closed after ten minutes instead of launching early.
