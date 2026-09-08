#!/bin/bash
# Status line for swaybar (see the bar block in ~/.config/sway/config).
# Redraws when the clock ticks over to the next minute, on SIGUSR1 from the volume
# and brightness keybinds, and on keyboard layout changes. Output is pango markup; the bar sets pango_markup enabled.

battery_dir=/sys/class/power_supply/BAT0
layout_cache=${XDG_RUNTIME_DIR:-/tmp}/sway-status-layout

# Keeps $layout_cache current and pokes the main loop on every layout change.
watch_layout() {
    local main=$1 name
    swaymsg -t get_inputs |
        jq -r 'map(select(has("xkb_active_layout_name")))[0].xkb_active_layout_name' > "$layout_cache"
    kill -USR1 "$main"
    swaymsg -t subscribe -m '["input"]' |
        jq --unbuffered -r '.input.xkb_active_layout_name // empty' |
        while IFS= read -r name; do
            printf '%s\n' "$name" > "$layout_cache"
            kill -USR1 "$main"
        done
}

wp_volume() { # $1: label, $2: wireplumber node
    wpctl get-volume "$2" | awk -v label="$1" \
        '{v=sprintf("%s %d%%", label, $2*100); print ($3=="[MUTED]" ? "<s>" v "</s>" : v)}'
}

# Hours left as "1:20", from a charge (uAh) and a current draw (uA).
hours_left() { awk -v c="$1" -v r="$2" 'BEGIN {h=c/r; printf "%d:%02d", h, (h-int(h))*60}'; }

battery() {
    [[ -d $battery_dir ]] || return
    local level status charge rate text
    level=$(< "$battery_dir/capacity")
    status=$(< "$battery_dir/status")
    charge=$(< "$battery_dir/charge_now")
    rate=$(< "$battery_dir/current_now")
    text="$status $level%"
    if (( rate > 0 )); then
        case $status in
            Discharging) text+=" $(hours_left "$charge" "$rate") left" ;;
            Charging) text+=" $(hours_left "$(( $(< "$battery_dir/charge_full") - charge ))" "$rate") to full" ;;
        esac
    fi
    if [[ $status == Discharging ]] && (( level <= 15 )); then
        echo "<span color=\"#ff5555\">⚠️ $text</span>"
    else
        echo "$text"
    fi
}

# Joins the non-empty fields with separators, so a missing one leaves no gap.
join_fields() {
    local out="" field
    for field; do
        [[ -n $field ]] && out+="${out:+ | }$field"
    done
    echo " $out "
}

render() {
    local language="" brightness
    [[ -f $layout_cache ]] && language=$(< "$layout_cache")
    brightness=$(brightnessctl -m | cut -d, -f4)

    join_fields "$language" "Brightness $brightness" \
        "$(wp_volume Volume @DEFAULT_AUDIO_SINK@)" \
        "$(wp_volume Mic @DEFAULT_AUDIO_SOURCE@)" \
        "$(battery)" "$(date '+%a %F %H:%M')"
}

cleanup() {
    pkill -P "$watcher" 2>/dev/null
    kill "$watcher" 2>/dev/null
    exit
}

trap true USR1
watch_layout $$ &
watcher=$!
trap cleanup EXIT INT TERM HUP

while true; do
    render
    # The clock is the only field needing a timer, so wake on its next change.
    sleep $(( 60 - 10#$(date +%S) )) & wait $!; kill $! 2>/dev/null
done
