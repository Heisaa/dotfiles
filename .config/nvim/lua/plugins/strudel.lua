return {
  "gruvw/strudel.nvim",
  build = "npm ci",
  config = function()
    require("strudel").setup({
      update_on_save = true,
    })
  end,
}
