return {
  "https://github.com/Heisaa/reviewer-nvim",
  cmd = { "PRReview", "PRReviewToggle", "PRReviewPrepare", "PRReviewTour" },
  dependencies = { "lewis6991/gitsigns.nvim" }, -- optional but recommended
  opts = {},
  keys = {
    { "<leader>rr", "<cmd>PRReviewToggle<cr>", desc = "PR review: toggle" },
    { "<leader>rP", "<cmd>PRReviewPrepare<cr>", desc = "PR review: prepare (agent)" },
  },
}
