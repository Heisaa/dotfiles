#!/bin/sh
# Restart the wallpaper (sway runs this on every config reload).
pkill -f "wallpaper/wallpaper.py" 2>/dev/null
exec "$(dirname "$0")/wallpaper.py" >>"${XDG_RUNTIME_DIR:-/tmp}/sway-wallpaper.log" 2>&1
