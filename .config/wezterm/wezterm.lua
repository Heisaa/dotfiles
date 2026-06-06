-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()
-- local bar = wezterm.plugin.require("https://github.com/adriankarlen/bar.wezterm")

local theme_file = os.getenv("HOME") .. "/.config/wezterm/current_theme"

-- Reload whenever the theme state file changes.
wezterm.add_to_config_reload_watch_list(theme_file)

local function read_theme()
  local f = io.open(theme_file, "r")
  if not f then return "dark" end
  local t = f:read("*l")
  f:close()
  return t or "dark"
end

local function scheme_for(theme)
  if theme == "light" then
    return "Google (light) (terminal.sexy)"
  end
  return "3024 (base16)"
end

local function tab_bar_colors_for(theme)
  if theme == "light" then
    return {
      background = "#e8e8e8",
      active_tab = {
        bg_color = "#f7f7f7",
        fg_color = "#222222",
        intensity = "Bold",
      },
      inactive_tab = {
        bg_color = "#e8e8e8",
        fg_color = "#6f6f6f",
      },
      inactive_tab_hover = {
        bg_color = "#dedede",
        fg_color = "#333333",
      },
      new_tab = {
        bg_color = "#e8e8e8",
        fg_color = "#777777",
      },
      new_tab_hover = {
        bg_color = "#dedede",
        fg_color = "#333333",
      },
    }
  end

  return {
    background = "#101010",
    active_tab = {
      bg_color = "#1a1a1a",
      fg_color = "#e8e8e8",
      intensity = "Bold",
    },
    inactive_tab = {
      bg_color = "#101010",
      fg_color = "#767676",
    },
    inactive_tab_hover = {
      bg_color = "#202020",
      fg_color = "#d0d0d0",
    },
    new_tab = {
      bg_color = "#101010",
      fg_color = "#767676",
    },
    new_tab_hover = {
      bg_color = "#202020",
      fg_color = "#d0d0d0",
    },
  }
end

local function colors_for(theme)
  return {
    tab_bar = tab_bar_colors_for(theme),
  }
end

local initial_theme = read_theme()
wezterm.log_info("wezterm theme state: " .. initial_theme .. " -> " .. scheme_for(initial_theme))
config.color_scheme = scheme_for(initial_theme)
config.colors = colors_for(initial_theme)
config.use_fancy_tab_bar = false
config.hide_tab_bar_if_only_one_tab = true
config.show_new_tab_button_in_tab_bar = false
config.tab_max_width = 28

-- Re-apply the scheme when current_theme changes.
wezterm.on('window-config-reloaded', function(window, _)
  local overrides = window:get_config_overrides() or {}
  local theme = read_theme()
  local scheme = scheme_for(theme)
  local tab_background = tab_bar_colors_for(theme).background
  local current_tab_background = nil
  if overrides.colors and overrides.colors.tab_bar then
    current_tab_background = overrides.colors.tab_bar.background
  end

  if overrides.color_scheme ~= scheme or current_tab_background ~= tab_background then
    overrides.color_scheme = scheme
    overrides.colors = colors_for(theme)
    window:set_config_overrides(overrides)
  end
end)

-- bar.apply_to_config(config)


return config
