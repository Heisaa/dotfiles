#!/bin/bash
set -u

theme="${1:-}"
case "$theme" in
  dark)
    gtk_scheme="prefer-dark"
    nvim_scheme="github_dark_high_contrast"
    foot_signal="USR1"
    ;;
  light)
    gtk_scheme="prefer-light"
    nvim_scheme="github_light"
    foot_signal="USR2"
    ;;
  *)
    printf 'Usage: %s dark|light\n' "${0##*/}" >&2
    exit 2
    ;;
esac

config_home="${XDG_CONFIG_HOME:-$HOME/.config}"

# GTK/portal.
if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.interface color-scheme "$gtk_scheme" 2>/dev/null || true
fi

# WezTerm watches this state file and reloads itself.
printf '%s\n' "$theme" > "$config_home/wezterm/current_theme"

# Foot reads this when a new process starts.
printf 'initial-color-theme=%s\n' "$theme" > "$config_home/foot/current-theme.ini"

# Foot switches [colors-dark]/[colors-light] on SIGUSR1/SIGUSR2.
if command -v pkill >/dev/null 2>&1; then
  pkill "-$foot_signal" -x foot 2>/dev/null || true
  pkill "-$foot_signal" -x footclient 2>/dev/null || true
fi

# Neovim (all instances).
if command -v nvim >/dev/null 2>&1; then
  runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$UID}"
  for sock in "$runtime_dir"/nvim.*.0; do
    [ -S "$sock" ] || continue
    nvim --server "$sock" --remote-send "<Cmd>colorscheme $nvim_scheme<CR>" 2>/dev/null || true
  done
fi

if command -v swaymsg >/dev/null 2>&1; then
  swaymsg reload >/dev/null 2>&1 || true
fi
