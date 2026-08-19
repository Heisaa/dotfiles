# Dotfiles Management with GNU Stow

This repository uses GNU Stow to manage dotfiles on Arch Linux.

## Initial Setup on a New Computer

### 1. Install Stow

```bash
sudo paru -S git
sudo paru -S stow
```

### 2. Clone This Repository

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
```

## How Stow Works

Stow creates symlinks from your home directory to files in this repository. Each top-level directory in this repo represents a "package" (e.g., `nvim/`, `zsh/`, `tmux/`).

### Directory Structure Example

```
~/dotfiles/
├── nvim/
│   └── .config/
│       └── nvim/
│           └── init.vim
├── zsh/
│   ├── .zshrc
│   └── .zshenv
└── tmux/
    └── .tmux.conf
```

When you run `stow nvim` from `~/dotfiles/`, it creates:
- `~/.config/nvim/init.vim` → `~/dotfiles/nvim/.config/nvim/init.vim`

## Basic Commands

### Install (symlink) a package

```bash
cd ~/dotfiles
stow nvim        # Creates symlinks for nvim config
stow zsh         # Creates symlinks for zsh config
stow tmux        # Creates symlinks for tmux config
```

### Install all packages at once

```bash
stow .
```

### Remove (unlink) a package

```bash
stow -D nvim     # Removes nvim symlinks
```

### Restow (useful after making changes)

```bash
stow -R nvim     # Re-creates symlinks (removes old, adds new)
```

### Dry run (see what would happen)

```bash
stow -n nvim     # Shows what would be done without doing it
stow -nv nvim    # Verbose dry run
```

## Common Issues

### Conflicts with existing files

If you already have config files, Stow will refuse to overwrite them. Use
`stow-backup.sh` in this repo to rename every conflicting file/folder to
`<name>.bak`:

```bash
cd ~/dotfiles
./stow-backup.sh -n     # dry run: list what would be renamed
./stow-backup.sh        # do it
stow -t ~ .
```

It walks the repo the way stow does, so an existing *directory* is not treated
as a conflict — `~/.config` is left alone and only the real collisions move
(e.g. `~/.config/nvim` → `~/.config/nvim.bak`). Symlinks that already point
into this repo are skipped, so it is safe to re-run after a partial stow.

Options: `-t` target dir (default `$HOME`), `-s` backup suffix (default
`.bak`), `-v` verbose, `-h` help. If a `.bak` already exists it uses
`.bak.1`, `.bak.2`, …

To restore a backup, just move it back:

```bash
rm ~/.config/nvim && mv ~/.config/nvim.bak ~/.config/nvim
```

### Wrong target directory

By default, Stow symlinks to the parent directory. Always run stow commands from `~/dotfiles/`:

```bash
cd ~/dotfiles    # Important!
stow nvim        # This will symlink to ~/
```

To specify a different target:
```bash
stow -t ~ nvim   # Explicitly target home directory
```

## Tips

- Keep each application's configs in its own directory
- Mirror the directory structure as it should appear in `$HOME`
- Use `stow -nv` to preview changes before applying
- You can stow multiple packages: `stow nvim zsh tmux`

## AUR Packages Note

Using `paru` for AUR packages. If any configs depend on AUR packages, install them first before stowing:

```bash
paru -S <package-name>
```
