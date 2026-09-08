-- ~/.config/nvim/lua/plugins/image.lua
return {
  {
    "folke/snacks.nvim",
    opts = {
      image = { enabled = false },
    },
  },

  {
    "3rd/image.nvim",
    opts = {
      backend = "sixel",
      processor = "magick_cli",

      integrations = {
        markdown = {
          enabled = true,
          clear_in_insert_mode = false,
          download_remote_images = true,

          -- Recommended for Sixel performance
          only_render_image_at_cursor = true,
          only_render_image_at_cursor_mode = "popup",
        },
      },

      max_width_window_percentage = 50,
      max_height_window_percentage = 50,
    },
  },
}
