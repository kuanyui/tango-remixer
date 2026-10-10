# LSP Server for `included_icons.txt`

An optional Language Server Protocol implementation that provides diagnostics and syntax highlighting for `included_icons.txt` files in any LSP-capable editor. What it gives the editor:

- **Diagnostics**: parses `included_icons.txt` on open / change / save, flags syntax errors and bad size-matrix expressions with line + column ranges.
- **Theme validation**: built-in theme NAMES plus any `# @extra-icon-theme NAME PATH` directives in the file are accepted; anything else gets an "Unknown theme" error. The LSP does not read CLI flags, so themes added only via `--extra-icon-theme` won't be recognized -- declare them with the in-file directive (see README).
- **Directive path check**: a directive whose PATH doesn't resolve gets a Warning (not Error), so editing in-flight doesn't go red.
- **Semantic tokens**: colors theme name, context, icon name, size matrix pieces (input number / output number / operator / `scalable` keyword), comments, and the `# @extra-icon-theme` directive parts (decorator-style keyword + NAME + PATH). Needs an LSP client that supports `textDocument/semanticTokens/full` (Eglot >= 1.20; Neovim, Helix).
- **Hover**: mouse-over (or `M-x eldoc-print-current-symbol-info` / `K` in Neovim) shows what each token means -- theme name, context, icon name, size matrix pieces, directive parts, etc.

## Install

Prefer your distro's package manager (PEP 668 blocks system-wide `pip` on most modern distros):

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

To check that it starts, open a shell in your tango-remixer checkout (the folder that has `lsp/` in it; as a submodule, typically `resources/tango-remixer/`) and run:

```sh
python3 -m lsp
```

Nothing is printed: the server waits for LSP messages on standard input. Silence means pygls was found; an `ImportError` means it was not. Ctrl-C stops it. That is the only time you start it by hand: editors launch it themselves and talk to it over stdio.

## Editor Setup

### Emacs (Eglot)

> [!IMPORTANT]
> Syntax highlighting needs **Eglot >= 1.20** (introduced `eglot-semantic-tokens-mode`). Older Eglot still gets diagnostics, just no colors.
>
> Check via `M-x list-packages` (find `eglot`). If too old, install the latest from GNU ELPA:
>
> ```
> M-x package-refresh-contents
> M-x package-install RET eglot RET
> ```
>
> The ELPA copy shadows the bundled one.

Emacs support is one file, [`editors/emacs/tango-included-icons.el`](../editors/emacs/tango-included-icons.el): a dedicated major mode for `included_icons.txt` plus the Eglot wiring. There is nothing to install -- pick one of the two ways to load it.

#### Option A: per file, inside `included_icons.txt` (recommended)

Put this on the **first line** of your `included_icons.txt`. The path is relative to the file's own directory; adjust it to where you keep the submodule.

```
# -*- eval: (load-file "tango-remixer/editors/emacs/tango-included-icons.el") -*-
```

It combines with the usual mode cookie, which then serves as the fallback when the `eval` is declined:

```
# -*- mode: conf; eval: (load-file "tango-remixer/editors/emacs/tango-included-icons.el") -*-
```

The same thing as a block at the **end** of the file (Emacs only looks for this block near the end, so keep it last):

```
# Local Variables:
# eval: (load-file "tango-remixer/editors/emacs/tango-included-icons.el")
# End:
```

On first visit Emacs asks whether to run that `eval`. **Press `!`**: the form is then saved to your `custom-file` and never asked again, and later changes to the `.el` file don't re-trigger the prompt. Answering `y` works too, but you'll be asked twice per visit (switching major mode makes Emacs re-read the local variables) and again on every visit.

The prompt is not a defect: it is the only thing standing between "opening a file" and "running code shipped in the repository". Nothing here runs without that one-time consent. If your `enable-local-variables` is `:safe`, Emacs silently skips the form instead of asking; allow exactly this form with:

```elisp
(add-to-list 'safe-local-eval-forms
             '(load-file "tango-remixer/editors/emacs/tango-included-icons.el"))
```

#### Option B: global init.el setup

Load the file from your init file with an absolute path. It registers `auto-mode-alist`, so every `included_icons.txt` you open gets the mode and Eglot; the server is located relative to the `.el` file itself.

```elisp
(load "/absolute/path/to/tango-remixer/editors/emacs/tango-included-icons.el")
```

Trade-off: pins one checkout. Use Option A when each project carries its own `tango-remixer/` submodule.

A `# -*- mode: conf -*-` cookie on the first line of `included_icons.txt` takes precedence over `auto-mode-alist`, so with Option B either remove the cookie or change it to `# -*- mode: tango-included-icons -*-`.

#### Notes

- The mode starts the server as `python3 lsp/server.py` directly: no wrapper script, no cwd dependency, works on Windows. If pygls lives in a venv, point `tango-included-icons-python` at that interpreter in your init file.
- Why a dedicated mode instead of `text-mode`: Eglot attaches the running server to every buffer in the same project whose major mode derives from the managed one (`provided-mode-derived-p`). Bound to `text-mode`, it would grab magit's commit message buffer and spam it with bogus diagnostics. `tango-included-icons-mode` derives from `text-mode` but nothing derives from *it*, so only `included_icons.txt` is managed.

### Neovim (nvim-lspconfig)

Bind a custom filetype to the `included_icons.txt` filename so Neovim only loads the LSP for that one file (not every `.txt` you open):

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

In `~/.config/helix/languages.toml` (or per-project `.helix/languages.toml`). Register a dedicated language matched by the filename only, so other text files keep their normal treatment:

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

No first-class support. You need a generic-LSP-client extension, or to write a small wrapper extension yourself. Not documented here.
