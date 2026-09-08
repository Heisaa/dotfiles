# Dotfiles Management with GNU Stow

This repository uses GNU Stow to manage dotfiles on Arch Linux.

## Initial Setup on a New Computer

### 1. Install Stow

```bash
paru -S git stow
```

### 2. Clone This Repository

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
```

## How Stow Works

Stow creates symlinks from your home directory to files in this repository. This
repo is a single package: its root mirrors `$HOME` directly, so paths are stored
exactly where they belong relative to the home directory.

### Directory Structure

```
~/dotfiles/
├── .claude/
├── .codex/
├── .config/
│   ├── nvim/
│   ├── sway/
│   └── ...
└── .zshrc
```

Running `stow .` from `~/dotfiles/` creates:
- `~/.config/nvim/` → `~/dotfiles/.config/nvim/`
- `~/.zshrc` → `~/dotfiles/.zshrc`

Stow ignores `.git`, `.gitignore`, and `README.*` by default, so they are not
symlinked into `$HOME`.

## Basic Commands

Run these from `~/dotfiles/`.

### Install (symlink) everything

```bash
stow .
```

### Remove (unlink) everything

```bash
stow -D .
```

### Restow (useful after making changes)

```bash
stow -R .
```

### Dry run (see what would happen)

```bash
stow -n .      # Shows what would be done without doing it
stow -nv .     # Verbose dry run
```

## Common Issues

### Conflicts with existing files

If you already have config files, Stow will refuse to overwrite them. You'll need to:

1. Back up existing configs:
   ```bash
   mv ~/.config/nvim ~/.config/nvim.backup
   ```

2. Then run stow:
   ```bash
   stow .
   ```

### Wrong target directory

By default, Stow symlinks to the parent directory. Always run stow commands from `~/dotfiles/`:

```bash
cd ~/dotfiles    # Important!
stow .           # This will symlink to ~/
```

To specify a different target:
```bash
stow -t ~ .      # Explicitly target home directory
```

## Tips

- Mirror the directory structure as it should appear in `$HOME`
- Use `stow -nv .` to preview changes before applying
- After adding new files, `stow -R .` to pick them up

## AUR Packages Note

Using `paru` for AUR packages. If any configs depend on AUR packages, install them first before stowing:

```bash
paru -S <package-name>
```
