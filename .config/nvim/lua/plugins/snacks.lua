return {
  "folke/snacks.nvim",
  opts = {
    picker = {
      sources = {
        explorer = {
          hidden = true,
          win = {
            input = {
              keys = {
                ["<esc>"] = { "", mode = "n" },
              },
            },
            list = {
              keys = {
                ["<esc>"] = { "", mode = "n" },
              },
            },
          },
        },
      },
    },
  },
}
