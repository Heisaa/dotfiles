local palettes = {
  github_dark_default = {
    bg0 = "#000000",
    bg1 = "#000000",
    bg2 = "#000000"
  }
}

return {
  {
    "projekt0n/github-nvim-theme",
    lazy = false, -- make sure we load this during startup if it is your main colorscheme
    priority = 1000, -- make sure to load this before all the other start plugins
    config = function()
      require("github-theme").setup({
        --palettes = palettes,
      })

      vim.cmd("colorscheme github_light_default")
    end,
  },
}
