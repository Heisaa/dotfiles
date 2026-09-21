# Codex image and pinned releases

[Back to README](../README.md)

Examples use `SBX_ROOT` as the absolute path to this checkout on the host:

```sh
export SBX_ROOT="$HOME/dotfiles/sbx" # Change if your checkout is elsewhere.
```

## Build and use the image

New Codex sandboxes use `docker.io/local/codex-native:latest`, extending
`docker/sandbox-templates:codex-docker`. It retains Docker Engine and the
sandbox's automatic daemon startup, replaces the npm Codex package with the
[official native installer](https://developers.openai.com/codex/cli/), and
includes Playwright Test 1.63.0 with its matching Chromium and headless shell.
In the personal rolling preset, the launcher updates Codex through the native
installer on each launch unless `SBX_AUTO_UPDATE=false`.

Build and import it **on the host** before creating a Codex sandbox:

```sh
cd "$SBX_ROOT"
docker build -f Dockerfile.codex -t docker.io/local/codex-native:latest .
docker image save docker.io/local/codex-native:latest -o /tmp/codex-native.tar
sbx template load /tmp/codex-native.tar
```

Docker and sbx have separate image stores, so the import is required. Then
run `sbx-agent codex` from your project as usual. `codex.sbxenv.yaml` selects
the same image for `sbx env`. The launcher accepts `SBX_CODEX_TEMPLATE` to
override the image; env-file users can override `sandboxOptions.template`.
Build arguments `BASE_IMAGE`, `CODEX_RELEASE` and `PLAYWRIGHT_VERSION` allow
version overrides; in rolling mode the optional launch-time updater follows the
latest release even when an exact version was selected at build time.

Existing sandboxes retain their old image. Save any work and files stored
only inside the sandbox, then remove the old sandbox with `sbx rm NAME` and
launch again to recreate it. The launcher prints its sandbox name. Until
recreation, it warns that native updates are unavailable and keeps launching
the existing Codex installation.

Inside the new sandbox, `docker info`, `codex --version` and
`playwright --version` verify the tools. `chromium --headless --no-sandbox
--dump-dom https://example.com` runs Chromium directly. For a browser smoke
test without network access:

```sh
node - <<'JS'
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent('<title>Chromium works</title>');
    console.log(await page.title());
  } finally {
    await browser.close();
  }
})();
JS
```

The bundled modules live in `/opt/playwright` and browsers in
`/opt/playwright-browsers`, independent of the Node toolchain kit's upgrades.
`NODE_PATH` exposes the bundled modules to CommonJS scripts. Projects using
ES module imports or their own test suite should declare `@playwright/test`
locally; match the bundled version to reuse its browsers, or run
`PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright npx playwright install chromium`
and use that same path when running the project's tests.

The native installation supplies the Codex components needed by remote
control; account pairing and remote connectivity still need to be configured
in Codex. They are not baked into the image.

## Pinned releases

For distribution, build an image with an exact native Codex release and a
base-image digest. `Dockerfile.codex` accepts `RELEASE_MODE=pinned` and rejects
floating base references or non-exact Codex releases in that mode:

```sh
# Set these to your chosen published base digest and tested Codex version.
: "${BASE_IMAGE:?Set a base image reference ending in @sha256:<digest>}"
: "${CODEX_RELEASE:?Set an exact x.y.z Codex release}"
docker build -f "$SBX_ROOT/Dockerfile.codex" \
  --build-arg RELEASE_MODE=pinned \
  --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg CODEX_RELEASE="$CODEX_RELEASE" \
  -t local/codex-native:release "$SBX_ROOT"
```

Publish/import the result using your normal image workflow. Launch with the
resulting **image digest**, not a mutable tag:

```sh
SBX_RELEASE_MODE=pinned SBX_CODEX_TEMPLATE="$CODEX_IMAGE_DIGEST" sbx-agent codex
```

Pinned mode disables this launcher's agent updates, Node startup installation,
and clipboard package installation, regardless of their boolean overrides. It
uses the versions baked into the image. For a different Node version, bake it
into the image before publishing. It uses a separate sandbox name incorporating
the image reference, so a new digest creates a new sandbox and leaves the old
one available. `sbx-agent update` refuses pinned mode; release a new image instead.
Claude pinned mode uses `SBX_CLAUDE_TEMPLATE` with a digest in the same way.

This fixes the selected image and prevents launcher-driven dependency upgrades;
it does not freeze agent actions, upstream built-in startup kits, or mutable
local kit files. Distribute a tagged checkout alongside the image digest and
record the tested `sbx` version. The Dockerfile still downloads its installer and
apt/npm dependencies when building, so separate rebuilds are not promised to be
byte-for-byte identical. Distribute the tested image digest itself.
