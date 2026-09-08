return {
  {
    "google/vim-colorscheme-primary",
    lazy = false,
    priority = 900,
  },
  {
    "projekt0n/github-nvim-theme",
    lazy = false,
    priority = 900,
    config = function()
      require("github-theme").setup({})
    end,
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = function()
        require("config.theme").apply()
      end,
    },
  },
}
