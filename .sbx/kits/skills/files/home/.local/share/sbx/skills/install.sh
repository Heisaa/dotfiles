#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
shopt -s nullglob
skills=("$source_dir"/*/SKILL.md)
if ((${#skills[@]} == 0)); then
  echo "skills: no SKILL.md files found in $source_dir" >&2
  exit 1
fi

# Check all destinations before making changes; never replace a personal skill.
for skill in "${skills[@]}"; do
  source="${skill%/SKILL.md}"
  name="${source##*/}"
  for dir in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
    dest="$dir/$name"
    if [[ -L "$dest" && "$(readlink -- "$dest")" == "$source" ]]; then
      continue
    fi
    if [[ -e "$dest" || -L "$dest" ]]; then
      echo "skills: refusing to replace existing skill $dest" >&2
      exit 1
    fi
  done
done

for skill in "${skills[@]}"; do
  source="${skill%/SKILL.md}"
  name="${source##*/}"
  for dir in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
    mkdir -p -- "$dir"
    dest="$dir/$name"
    [[ -L "$dest" ]] || ln -s -- "$source" "$dest"
  done
done
