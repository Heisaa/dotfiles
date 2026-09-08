#!/usr/bin/env bash
# Bring a fresh sandbox up to the toolchain versions this dotfiles repo expects.
# Runs once per sandbox creation, as a kit startup step. Everything here is
# idempotent, so a re-run is cheap and safe.
#
# What to install is declared in packages.conf next to this script.

set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=packages.conf
. "$HERE/packages.conf"

NODE_PREFIX=/opt/node
AGENT_UID=1000
NPM_PREFIX="${NPM_CONFIG_PREFIX:-/usr/local/share/npm-global}"
DIST="${NODE_DIST_URL:-https://nodejs.org/dist}"

# Root is needed for /opt, /usr/local/bin and apt. Kit startup steps run as
# root by default; re-exec through sudo if invoked as the agent user instead.
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n bash "$0" "$@"
fi

log() { printf 'node-toolchain: %s\n' "$*"; }

# The claude kit's own startup step runs `apt-get update` in the background,
# so on a fresh start apt's lists lock is usually still held when this script
# reaches apt. apt-get fails immediately on a held lock (DPkg::Lock::Timeout
# only covers the dpkg lock), so poll until no apt/dpkg process holds one.
apt_wait() {
  local i
  for ((i = 0; i < 300; i++)); do
    fuser /var/lib/apt/lists/lock /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1 || return 0
    [ "$i" -eq 0 ] && log "apt: waiting for another apt process to finish"
    sleep 1
  done
  log "apt: gave up waiting for the apt lock" >&2
  return 1
}

apt_install() {
  [ "$#" -gt 0 ] || return 0
  local missing=()
  local p
  for p in "$@"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q '^install ok installed$' || missing+=("$p")
  done
  [ "${#missing[@]}" -gt 0 ] || return 0
  log "apt: installing ${missing[*]}"
  export DEBIAN_FRONTEND=noninteractive
  apt_wait
  # The image ships a populated apt cache, so try the install first and only
  # pay for an update when the cache turns out to be stale.
  apt-get install -y -qq --no-install-recommends "${missing[@]}" >/dev/null 2>&1 && return 0
  apt-get update -qq >/dev/null
  apt-get install -y -qq --no-install-recommends "${missing[@]}" >/dev/null
}

install_node() {
  local major="$1" arch tarball sums version tmp b
  case "$(uname -m)" in
    x86_64)          arch=x64 ;;
    aarch64 | arm64) arch=arm64 ;;
    *) log "unsupported architecture $(uname -m), keeping distro node" >&2; return 1 ;;
  esac

  # SHASUMS256.txt yields both the exact filename (the patch version floats
  # within a major) and its checksum, in a single request.
  sums="$(curl -fsSL --retry 3 --retry-delay 2 "$DIST/latest-v$major.x/SHASUMS256.txt")"
  tarball="$(awk -v a="linux-$arch.tar.gz" '$2 ~ ("node-v.*-" a "$") {print $2; exit}' <<<"$sums")"
  [ -n "$tarball" ] || { log "no linux-$arch build in latest-v$major.x" >&2; return 1; }
  version="${tarball#node-}"; version="${version%%-linux-*}"   # -> v26.8.1

  if [ "$(/usr/local/bin/node --version 2>/dev/null)" = "$version" ]; then
    log "node $version already installed"
    return 0
  fi

  # .tar.gz rather than .tar.xz: the base image has no xz binary, and pulling
  # one in would add an apt round-trip to every sandbox start.
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN
  curl -fsSL --retry 3 --retry-delay 2 -o "$tmp/$tarball" "$DIST/latest-v$major.x/$tarball"
  grep -F " $tarball" <<<"$sums" > "$tmp/SHASUMS256.txt"
  ( cd "$tmp" && sha256sum -c --status SHASUMS256.txt ) || {
    log "checksum mismatch for $tarball" >&2; return 1; }

  mkdir -p "$NODE_PREFIX"
  rm -rf "${NODE_PREFIX:?}/$version"
  tar -xzf "$tmp/$tarball" -C "$NODE_PREFIX"
  mv "$NODE_PREFIX/${tarball%.tar.gz}" "$NODE_PREFIX/$version"
  ln -sfn "$NODE_PREFIX/$version" "$NODE_PREFIX/current"

  # /usr/local/bin precedes /usr/bin on PATH, so linking here is enough: no
  # profile edit, and nothing appended to /etc/sandbox-persistent.sh. The
  # distro node stays in place at /usr/bin/node as a fallback.
  for b in node npm npx corepack; do
    [ -e "$NODE_PREFIX/current/bin/$b" ] && ln -sfn "$NODE_PREFIX/current/bin/$b" "/usr/local/bin/$b"
  done

  find "$NODE_PREFIX" -maxdepth 1 -name 'v*' ! -name "$version" -exec rm -rf {} +
  log "node $(/usr/local/bin/node --version)"
}

apt_install ${APT_PACKAGES:-}

if [ -n "${NODE_MAJOR:-}" ]; then
  # The official Node builds link against libatomic, which the base image
  # omits; without it the new binary dies at exec with a loader error.
  apt_install libatomic1
  install_node "$NODE_MAJOR"
fi

if [ -n "${NPM_GLOBAL_PACKAGES:-}" ]; then
  log "npm -g: $NPM_GLOBAL_PACKAGES"
  # Installed as the agent user so the tree stays writable afterwards. -H is
  # required alongside -E: without it HOME stays /root, and npm then fails
  # trying to read a cache the agent user cannot touch.
  #
  # NPM_CONFIG_PREFIX has to be restated: sudo's env_reset drops it even under
  # -E, and npm would then fall back to its builtin prefix inside
  # /opt/node/<version> -- a directory this script deletes on the next Node
  # upgrade, silently taking every global package with it.
  sudo -u "#$AGENT_UID" -E -H env \
    PATH="/usr/local/bin:$PATH" \
    NPM_CONFIG_PREFIX="$NPM_PREFIX" \
    npm install -g --no-fund --no-audit ${NPM_GLOBAL_PACKAGES}
fi
