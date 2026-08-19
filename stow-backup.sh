#!/usr/bin/env bash
#
# stow-backup.sh — back up files/folders in the target dir that would make
# `stow` fail, by renaming them to <name>.bak.
#
# It walks this package the same way stow does: an existing *directory* in the
# target is not a conflict (stow just descends into it), so only the actual
# colliding files and folders get renamed — e.g. ~/.config stays put, while
# ~/.config/nvim becomes ~/.config/nvim.bak.
#
# Usage:
#   ./stow-backup.sh [-n] [-v] [-t TARGET] [-d PACKAGE_DIR] [-s SUFFIX]
#
#   -n, --dry-run   show what would be renamed, change nothing
#   -v, --verbose   also report paths that are fine
#   -t, --target    where stow points (default: $HOME)
#   -d, --dir       package directory to stow (default: this script's dir)
#   -s, --suffix    backup suffix (default: .bak)
#   -h, --help      this help
#
# Symlinks that already point into this package are left alone, so it is safe
# to re-run after a partial stow.

set -euo pipefail

PKG_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TARGET="${HOME:-}"
SUFFIX=".bak"
DRY_RUN=0
VERBOSE=0

usage() { sed -n '2,${/^#/!q; s/^# \{0,1\}//p;}' "${BASH_SOURCE[0]}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run) DRY_RUN=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -t|--target)  TARGET="${2:?missing value for $1}"; shift 2 ;;
    -d|--dir)     PKG_DIR="${2:?missing value for $1}"; shift 2 ;;
    -s|--suffix)  SUFFIX="${2:?missing value for $1}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *) printf 'error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -d $PKG_DIR ]] || { printf 'error: package dir does not exist: %s\n' "$PKG_DIR" >&2; exit 1; }
[[ -n $TARGET   ]] || { printf 'error: no target dir (set HOME or pass -t)\n' >&2; exit 1; }
[[ -d $TARGET   ]] || { printf 'error: target dir does not exist: %s\n' "$TARGET" >&2; exit 1; }

PKG_DIR="$(cd -- "$PKG_DIR" && pwd -P)"
TARGET="$(cd -- "$TARGET" && pwd -P)"

[[ $PKG_DIR != "$TARGET" ]] || { printf 'error: package dir and target dir are the same\n' >&2; exit 1; }

# --- ignore list -------------------------------------------------------------
# Mirrors stow's defaults. A .stow-local-ignore in the package root replaces
# them (as in stow). Patterns are regexes: those containing "/" are matched
# against the path relative to the package root, the rest against the basename.
DEFAULT_IGNORE=(
  '\.git'
  '\.gitignore'
  '\.gitmodules'
  '\.agentbox'
  'CVS'
  '\.svn'
  '_darcs'
  '\.hg'
  '.+~'
  '\#.*\#'
  '^/README.*'
  '^/LICENSE.*'
  '^/COPYING'
)

IGNORE=()
if [[ -f $PKG_DIR/.stow-local-ignore ]]; then
  while IFS= read -r line || [[ -n $line ]]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -n $line ]] && IGNORE+=("$line")
  done < "$PKG_DIR/.stow-local-ignore"
else
  IGNORE=("${DEFAULT_IGNORE[@]}")
fi
# .stow-local-ignore itself is never stowed.
IGNORE+=('\.stow-local-ignore')

is_ignored() { # $1 = path relative to package root
  local rel="$1" base="${1##*/}" pat
  for pat in "${IGNORE[@]}"; do
    if [[ $pat == */* ]]; then
      [[ "/$rel" =~ ^${pat}$ ]] && return 0
    else
      [[ $base =~ ^${pat}$ ]] && return 0
    fi
  done
  return 1
}

# --- backup ------------------------------------------------------------------
conflicts=0
backed_up=0

backup_path() { # $1 = absolute path in the target dir, $2 = reason
  local dst="$1" reason="$2" bak="$1$SUFFIX" n=1
  while [[ -e $bak || -L $bak ]]; do
    bak="$1$SUFFIX.$((n++))"
  done
  conflicts=$((conflicts + 1))
  if (( DRY_RUN )); then
    printf 'would back up: %s -> %s   (%s)\n' "$dst" "$bak" "$reason"
  else
    mv -- "$dst" "$bak"
    backed_up=$((backed_up + 1))
    printf 'backed up:     %s -> %s   (%s)\n' "$dst" "$bak" "$reason"
  fi
}

walk() { # $1 = path relative to package root ("" for the root itself)
  local rel="$1" src dst name childrel
  local dir="$PKG_DIR${rel:+/$rel}"
  local entries=() 

  shopt -s dotglob nullglob
  entries=("$dir"/*)
  shopt -u dotglob nullglob

  for src in "${entries[@]}"; do
    name="${src##*/}"
    childrel="${rel:+$rel/}$name"
    dst="$TARGET/$childrel"

    if is_ignored "$childrel"; then
      (( VERBOSE )) && printf 'ignored:       %s\n' "$childrel"
      continue
    fi

    if [[ -L $dst ]]; then
      # Already a symlink: fine only if it already points at this package.
      if [[ -e $dst ]] && [[ "$(readlink -f -- "$dst")" == "$(readlink -f -- "$src")" ]]; then
        (( VERBOSE )) && printf 'already stowed: %s\n' "$dst"
      elif [[ -e $dst ]]; then
        backup_path "$dst" "symlink to something else"
      else
        backup_path "$dst" "broken symlink"
      fi
      continue
    fi

    if [[ ! -e $dst ]]; then
      (( VERBOSE )) && printf 'free:          %s\n' "$dst"
      continue
    fi

    if [[ -d $src && -d $dst ]]; then
      # stow descends into an existing real directory — so do we.
      (( VERBOSE )) && printf 'descending:    %s\n' "$dst"
      walk "$childrel"
      continue
    fi

    if [[ -d $src ]]; then
      backup_path "$dst" "file in the way of a directory"
    else
      backup_path "$dst" "existing file"
    fi
  done
}

printf 'package: %s\ntarget:  %s\n\n' "$PKG_DIR" "$TARGET"
walk ""

printf '\n'
if (( conflicts == 0 )); then
  printf 'No conflicts. `stow -t %s .` should run clean.\n' "$TARGET"
elif (( DRY_RUN )); then
  printf '%d conflict(s) found (dry run, nothing changed).\n' "$conflicts"
else
  printf '%d conflict(s) backed up. Now run: stow -t %s .\n' "$backed_up" "$TARGET"
fi
