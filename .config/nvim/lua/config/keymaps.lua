-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- Keep what was yanked in the register
vim.keymap.set("n", "<A-p>", "p", { noremap = true, desc = "Normal lowercase paste functionality" })
vim.keymap.set("n", "<A-P>", "P", { noremap = true, desc = "Normal uppercase paste functionality" })
vim.keymap.set("x", "<A-p>", "p", { noremap = true, desc = "Normal lowercase paste functionality in visual mode" })
vim.keymap.set("x", "<A-P>", "P", { noremap = true, desc = "Normal uppercase paste functionality in visual mode" })
vim.keymap.set("n", "p", '"0p', { noremap = true })
vim.keymap.set("n", "P", '"0P', { noremap = true })
vim.keymap.set("x", "p", '"0p', { noremap = true })
vim.keymap.set("x", "P", '"0P', { noremap = true })
-- Delete whole word with ctrl + backspace
vim.keymap.set("i", "<C-BS>", "<C-W>", { noremap = true })
