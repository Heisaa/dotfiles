#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n bash "$0"
fi

missing=()
for package in xvfb python3-xlib; do
  dpkg-query -W -f='${Status}' "$package" 2>/dev/null |
    grep -q '^install ok installed$' || missing+=("$package")
done
if ((${#missing[@]})); then
  export DEBIAN_FRONTEND=noninteractive
  for ((attempt = 0; attempt < 300; attempt++)); do
    fuser /var/lib/apt/lists/lock /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1 || break
    sleep 1
  done
  if ! apt-get -o DPkg::Lock::Timeout=300 install -y -qq --no-install-recommends "${missing[@]}"; then
    apt-get update -qq
    apt-get -o DPkg::Lock::Timeout=300 install -y -qq --no-install-recommends "${missing[@]}"
  fi
fi

install -d -o root -g root -m 1777 /tmp/.X11-unix
# Keep a sandbox-local copy: an existing sandbox need not keep the dotfiles
# repository mounted after this one-time installation.
DEST=/home/agent/.local/share/sbx/codex-clipboard
install -d -o 1000 -g 1000 "$DEST"
if [ "$HERE" != "$DEST" ]; then
  install -o 1000 -g 1000 -m 644 "$HERE/bridge.py" "$DEST/bridge.py"
  install -o 1000 -g 1000 -m 755 "$HERE/setup.sh" "$DEST/setup.sh"
fi
sudo -u '#1000' -H /usr/bin/python3 "$DEST/bridge.py"
