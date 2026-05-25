# LSP Server for `included_icons.txt`

An optional Language Server Protocol implementation that provides
diagnostics and syntax highlighting for `included_icons.txt` files in
any LSP-capable editor.

## Install

Prefer your distro's package manager (PEP 668 blocks system-wide `pip` on
most modern distros):

```sh
# Debian / Ubuntu
sudo apt install python3-pygls

# Fedora
sudo dnf install python3-pygls

# openSUSE
sudo zypper install python3-pygls

# Arch (AUR or community)
sudo pacman -S python-pygls
```

Fallback (use a venv or `--user`):

```sh
pip install --user pygls
```

Then start manually (sanity check):

```sh
python3 -m lsp
```

The server reads/writes LSP messages over stdio. Editors launch it for you.

## Editor Setup

### Emacs (Eglot)

Add a `.dir-locals.el` at **your project's** root (the project that uses
tango-remixer as a submodule). The `when` guard makes sure Eglot only
fires on `included_icons.txt`, not every text file in your tree:

Place this `.dir-locals.el` in the SAME directory as your
`included_icons.txt`. The wrapper path is expanded to an absolute path
at load time (relative to `included_icons.txt`'s directory), so Eglot's
working directory at launch doesn't matter:

```elisp
;; Adjust the relative segment to match where you keep the submodule.
((text-mode . ((eval . (when (equal (file-name-nondirectory (or buffer-file-name "")) "included_icons.txt")
    (setq-local eglot-server-programs `((text-mode . (,(expand-file-name "tango-remixer/included-icons-lsp" default-directory)))))
    (eglot-ensure))))))
```

The wrapper (`included-icons-lsp`) handles `cd`-ing into the
tango-remixer repo root so `python3 -m lsp` can find the `lsp/` package.

On first visit Emacs will ask whether to trust the dir-locals; press `!`
to accept permanently.

### Neovim (nvim-lspconfig)

Bind a custom filetype to the `included_icons.txt` filename so Neovim
only loads the LSP for that one file (not every `.txt` you open):

```lua
-- Map the filename to its own filetype.
vim.filetype.add({
  filename = { ["included_icons.txt"] = "included_icons" },
})

-- Register the server, scoped to that filetype.
local lspconfig = require("lspconfig")
local configs = require("lspconfig.configs")
if not configs.tango_icons_lsp then
  configs.tango_icons_lsp = {
    default_config = {
      cmd = { "./resources/tango-remixer/included-icons-lsp" },
      filetypes = { "included_icons" },
      root_dir = lspconfig.util.root_pattern("included_icons.txt"),
    },
  }
end
lspconfig.tango_icons_lsp.setup({})
```

### Helix

In `~/.config/helix/languages.toml` (or per-project `.helix/languages.toml`).
Register a dedicated language matched by the filename only, so other
text files keep their normal treatment:

```toml
[language-server.tango-icons]
command = "./resources/tango-remixer/included-icons-lsp"

[[language]]
name = "included-icons"
scope = "text.included-icons"
file-types = [{ glob = "included_icons.txt" }]
language-servers = ["tango-icons"]
```

### VSCode

No first-class support. You need a generic-LSP-client extension, or to
write a small wrapper extension yourself. Not documented here.

## What the server does (current scope)

Skeleton only: wires up `didOpen` / `didChange` / `didSave`. The actual
diagnostics / semantic-tokens logic is implemented in `lsp/server.py`'s
`_validate()` and is being built out incrementally.
