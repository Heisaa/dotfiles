local plugins = {
  { lazy = true, "nvim-lua/plenary.nvim" },

  {
    "edeneast/nightfox.nvim",
    priority = 1000,
    config = function()
      require("nightfox").setup {
        groups = {
          all = { vertsplit = { fg = "bg3" } },
        },
      }
    end,
  },

  {
    'projekt0n/github-nvim-theme',
    lazy = false, -- make sure we load this during startup if it is your main colorscheme
    priority = 1000, -- make sure to load this before all the other start plugins
    config = function()
      require('github-theme').setup({
        -- ...
      })

      vim.cmd('colorscheme github_dark_default')
    end,
  },

  -- file tree
  {
    "nvim-tree/nvim-tree.lua",
    config = function()
        require "plugins.configs.nvimtree"
      require("nvim-tree").setup()
    end,
  },

  -- icons, for ui related plugins
  {
    "nvim-tree/nvim-web-devicons",
    config = function()
      require("nvim-web-devicons").setup()
    end,
  },

  -- syntax highlighting
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function()
      require "plugins.configs.treesitter"
    end,
  },

  -- buffer + tab line
  {
    "akinsho/bufferline.nvim",
    event = "BufReadPre",
    config = function()
      require "plugins.configs.bufferline"
    end,
  },

  -- statusline (byta ut mot lua line med lazy config)
  {
    "nvim-lualine/lualine.nvim",
    config = function()
      require("lualine").setup({
        sections = {
          lualine_c = {{"filename", path = 1}}
        }
      })
    end,
  },

  -- we use cmp plugin only when in insert mode
  -- so lets lazyload it at insertenter event, to know all the events check h-events
  -- completion , now all of these plugins are dependent on cmp, we load them after cmp
  {
    "hrsh7th/nvim-cmp",
    event = "insertenter",
    dependencies = {
      -- cmp sources
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "hrsh7th/cmp-nvim-lsp",
      "saadparwaiz1/cmp_luasnip",
      "hrsh7th/cmp-nvim-lua",

      -- snippets
      --list of default snippets
      "rafamadriz/friendly-snippets",

      -- snippets engine
      {
        "l3mon4d3/luasnip",
        config = function()
          require("luasnip.loaders.from_vscode").lazy_load()
        end,
      },

      -- autopairs , autocompletes ()[] etc
      {
        "windwp/nvim-autopairs",
        config = function()
          require("nvim-autopairs").setup()

          --  cmp integration
          local cmp_autopairs = require "nvim-autopairs.completion.cmp"
          local cmp = require "cmp"
          cmp.event:on("confirm_done", cmp_autopairs.on_confirm_done())
        end,
      },
    },
    config = function()
      require "plugins.configs.cmp"
    end,
  },

  {
    "williamboman/mason.nvim",
    build = ":MasonUpdate",
    cmd = { "Mason", "MasonInstall" },
    config = function()
      require("mason").setup()
    end,
  },

  -- lsp
  {
    "neovim/nvim-lspconfig",
    event = { "bufreadpre", "bufnewfile" },
    config = function()
      require "plugins.configs.lspconfig"
    end,
  },

  -- rust tools
  -- {
  --   "simrat39/rust-tools.nvim",
  -- },

  -- formatting , linting
  {
    "stevearc/conform.nvim",
    lazy = true,
    config = function()
      require "plugins.configs.conform"
    end,
  },

  -- indent lines
  {
    "lukas-reineke/indent-blankline.nvim",
    event = { "bufreadpre", "bufnewfile" },
    config = function()
      require("ibl").setup()
    end,
  },

  -- files finder etc
  {
    "nvim-telescope/telescope.nvim",
    config = function()
      require "plugins.configs.telescope"
    end,
  },

  -- git status on signcolumn etc
  {
    "lewis6991/gitsigns.nvim",
    event = { "bufreadpre", "bufnewfile" },
    config = function()
      require("gitsigns").setup()
    end,
  },

  -- comment plugin
  {
    "numtostr/comment.nvim",
    lazy = true,
    config = function()
      require("Comment").setup()
    end,
  },

  -- delete buffers without messing up window layouts
  {'famiu/bufdelete.nvim'},

  -- sessions
  {
    "folke/persistence.nvim",
    event = "bufreadpre", -- this will only start session saving when an actual file was opened
    opts = {
      -- add any custom options here
    }
  },

  -- hardtime
  -- {
  --   "m4xshen/hardtime.nvim",
  --   dependencies = { "muniftanjim/nui.nvim", "nvim-lua/plenary.nvim" },
  --   opts = {}
  -- },

  -- Copilot
  {
    "zbirenbaum/copilot.lua",
    cmd = "Copilot",
    event = "InsertEnter",
    config = function()
      require("copilot").setup({
        suggestion = {
          auto_trigger = true,
        }
      })
    end,
  },

  -- Surround
  {
    "kylechui/nvim-surround",
    version = "*", -- Use for stability; omit to use `main` branch for the latest features
    event = "VeryLazy",
    config = function()
      require("nvim-surround").setup({
        -- Configuration here, or leave empty to use defaults
      })
    end
  },

  -- Zen mode
  {
    "folke/zen-mode.nvim",
    opts = {
      -- your configuration comes here
      -- or leave it empty to use the default settings
      -- refer to the configuration section below
    }
  },

  -- Ufo (fold)
  {
    "kevinhwang91/nvim-ufo",
    dependencies = 'kevinhwang91/promise-async',
    config = function()
      require "plugins.configs.ufo"
    end,
  },

  {
    "rust-lang/rust.vim",
    ft = "rust",
    init = function()
      vim.g.rustfmt_autosave = 1
    end,
  },

  {
    "folke/trouble.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
    -- your configuration comes here
    -- or leave it empty to use the default settings
    -- refer to the configuration section below
    }
  }

  -- Hover  
  -- {
  --   "lewis6991/hover.nvim",
  --   config = function()
  --     require("hover").setup({
  --       init = function()
  --         -- Require providers
  --         require("hover.providers.lsp")
  --         -- require('hover.providers.gh')
  --         -- require('hover.providers.gh_user')
  --         -- require('hover.providers.jira')
  --         -- require('hover.providers.man')
  --         -- require('hover.providers.dictionary')
  --       end,
  --       preview_opts = {
  --         border = 'single'
  --       },
  --       -- Whether the contents of a currently open hover window should be moved
  --       -- to a :h preview-window when pressing the hover keymap.
  --       preview_window = false,
  --       title = true,
  --       mouse_providers = {
  --         'LSP'
  --       },
  --       mouse_delay = 1000
  --     })
  --
  --     -- Setup keymaps
  --     vim.keymap.set("n", "K", require("hover").hover, {desc = "hover.nvim"})
  --     vim.keymap.set("n", "gK", require("hover").hover_select, {desc = "hover.nvim (select)"})
  --
  --     -- Mouse support
  --     vim.keymap.set('n', '<MouseMove>', require('hover').hover_mouse, { desc = "hover.nvim (mouse)" })
  --     vim.o.mousemoveevent = true
  --   end,
  -- }
}

require("lazy").setup(plugins, require "plugins.configs.lazy")
