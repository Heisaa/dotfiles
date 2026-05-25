return {
  dir = "~/Projects/nvim_colors",
  name = "nvim_colors",
  lazy = true,
  cmd = "ColorBuilder",
  keys = {
    { "<leader>uC", "<cmd>ColorBuilder<cr>",          desc = "nvim_colors builder (simple)" },
    { "<leader>uc", "<cmd>ColorBuilder pick<cr>",     desc = "nvim_colors: pick group at cursor" },
  },
  config = function()
    require("nvim_colors").setup()
  end,
}
