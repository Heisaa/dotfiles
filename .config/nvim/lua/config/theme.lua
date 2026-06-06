local M = {}

M.default = "blueprint"
M.file = vim.fn.stdpath("config") .. "/.colorscheme"

local function notify(message, level)
  vim.notify(message, level or vim.log.levels.INFO, { title = "Colorscheme" })
end

function M.get()
  local lines = vim.fn.filereadable(M.file) == 1 and vim.fn.readfile(M.file) or {}
  local name = lines[1]

  if type(name) == "string" and name ~= "" then
    return name
  end

  return M.default
end

function M.save(name)
  if type(name) ~= "string" or name == "" then
    return false
  end

  vim.fn.writefile({ name }, M.file)
  return true
end

function M.apply(name)
  name = name or M.get()

  local ok, err = pcall(vim.cmd.colorscheme, name)
  if ok then
    return true
  end

  if name ~= M.default then
    notify("Could not load " .. name .. "; falling back to " .. M.default, vim.log.levels.WARN)
    M.save(M.default)
    return M.apply(M.default)
  end

  notify("Could not load " .. name .. ": " .. tostring(err), vim.log.levels.ERROR)
  return false
end

function M.persist(name)
  name = name ~= "" and name or vim.g.colors_name

  if type(name) ~= "string" or name == "" then
    notify("No colorscheme selected", vim.log.levels.WARN)
    return
  end

  if M.apply(name) then
    M.save(name)
    notify("Saved " .. name .. " as your default colorscheme")
  end
end

function M.setup()
  vim.api.nvim_create_user_command("ColorSchemePersist", function(opts)
    M.persist(opts.args)
  end, {
    nargs = "?",
    complete = "color",
    desc = "Set and permanently save a colorscheme",
  })

  vim.api.nvim_create_user_command("ColorSchemeReset", function()
    M.persist(M.default)
  end, {
    desc = "Reset the persisted colorscheme to the default",
  })

  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("persisted_colorscheme", { clear = true }),
    callback = function()
      M.save(vim.g.colors_name)
    end,
    desc = "Persist colorscheme changes made with :colorscheme",
  })
end

return M
