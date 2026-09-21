# Sandbox management

[Back to README](../README.md)

Examples use `SBX_ROOT` as the absolute path to this checkout on the host:

```sh
export SBX_ROOT="$HOME/dotfiles/sbx" # Change if your checkout is elsewhere.
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

## Direct sbx usage

Start a sandbox with the shared defaults:

```sh
sbx env run "$SBX_ROOT/base.sbxenv.yaml" ./.sbxenv.yaml
```

Or a one-off sandbox without an env file — note `sbx create` takes
`AGENT PATH`, and `--kit` takes the same references:

```sh
sbx skills import --force
sbx create \
  --skills=readonly \
  --kit "$SBX_ROOT/kits/claude-defaults" \
  --kit "$SBX_ROOT/kits/claude-statusline" \
  --kit "$SBX_ROOT/kits/node-toolchain" \
  claude .
```

## Editing a startup kit means recreating the sandbox

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

  The defaults, statusline, and toolchain kits here are startup kits, so
  `sbx kit add` cannot update them. Shared skills are managed separately with
  `sbx skills import` and do not require sandbox recreation.

The only way to pick up a startup kit change is therefore a full recreate:

```sh
sbx rm my-sandbox
sbx env run "$SBX_ROOT/base.sbxenv.yaml" ./.sbxenv.yaml
```

Check a kit before relying on it:

```sh
sbx kit validate "$SBX_ROOT/kits/node-toolchain"
```

## Network rules

The Node kit declares `nodejs.org` and `registry.npmjs.org` in
`permissions.network.allow`, scoped to sandboxes that use that kit. Add other
required registries to the relevant kit when adding dependencies. Machine-wide
rules remain available for local administration; they are not an installation
prerequisite for these two domains.

Organization policy and explicit deny rules can still block a kit's allow rules.
Inspect failures with `sbx policy log` and `sbx policy ls`.
See [Docker's kit network documentation](https://docs.docker.com/ai/sandboxes/customize/kits/#control-network-access).
