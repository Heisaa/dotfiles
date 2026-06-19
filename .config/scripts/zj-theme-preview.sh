#!/bin/bash
# Preview zellij themes in a throwaway session without touching your config.
#
# Usage:
#   zj-theme-preview.sh                 # interactive: pick from a fzf list (or numbered menu)
#   zj-theme-preview.sh <theme>         # preview a specific theme
#   zj-theme-preview.sh -l|--list       # just print the built-in theme names
#
# Inside the preview session, exit with Ctrl+q (or detach) to return.
set -u

# Built-in themes shipped with zellij (see zellij.dev/documentation/theme-list).
themes=(
  # Dark
  ansi ao atelier-sulphurpool ayu_mirage ayu_dark catppuccin-frappe
  catppuccin-macchiato cyber-noir blade-runner retro-wave dracula
  everforest-dark gruvbox-dark iceberg-dark kanagawa lucario menace
  molokai-dark night-owl nightfox nord one-half-dark onedark
  solarized-dark tokyo-night-dark tokyo-night-storm tokyo-night vesper
  # Light
  atelier-sulphurpool-light ayu_light catppuccin-latte everforest-light
  gruvbox-light iceberg-light one-half-light solarized-light tokyo-night-light
)

list_themes() { printf '%s\n' "${themes[@]}"; }

case "${1:-}" in
  -l|--list) list_themes; exit 0 ;;
esac

theme="${1:-}"

# No theme given -> let the user pick.
if [ -z "$theme" ]; then
  if command -v fzf >/dev/null 2>&1; then
    theme="$(list_themes | fzf --prompt='zellij theme> ' --height=40% --reverse)"
  else
    PS3="Pick a theme number: "
    select t in "${themes[@]}"; do
      [ -n "${t:-}" ] && theme="$t" && break
    done
  fi
fi

[ -z "$theme" ] && { echo "No theme selected." >&2; exit 1; }

echo "Previewing theme: $theme  (Ctrl+q to quit the preview session)"
# --theme is a startup override; the session is named so it never clobbers real ones.
exec zellij --session "preview-${theme}" options --theme "$theme"
