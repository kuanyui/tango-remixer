# LSP Server for `included_icons.txt`

An optional Language Server Protocol implementation that provides diagnostics and syntax highlighting for `included_icons.txt` files in any LSP-capable editor.

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

Then start manually (sanity check):

```sh
python3 -m lsp
```

The server reads/writes LSP messages over stdio. Editors launch it for you.

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

Pick one of the two setups below.

#### Option A: per-project `.dir-locals.el` (self-contained, no init.el changes)

Drop a single `.dir-locals.el` next to your `included_icons.txt`. Nothing else to touch -- it defines a one-shot derived mode inline, switches to it, and tells Eglot to attach. The wrapper path is resolved relative to the file's directory at load time, so Eglot's cwd at launch doesn't matter.

```elisp
;; Adjust the relative segment to match where you keep the submodule.
((nil . ((eval . (when (and buffer-file-name
                              (equal (file-name-nondirectory buffer-file-name) "included_icons.txt"))
    (unless (fboundp 'tango-included-icons-mode)
      (define-derived-mode tango-included-icons-mode text-mode "TangoIcons"))
    (unless (eq major-mode 'tango-included-icons-mode)
      (tango-included-icons-mode))
    (setq-local eglot-server-programs
                `((tango-included-icons-mode . (,(expand-file-name "tango-remixer/included-icons-lsp" default-directory)))))
    (eglot-ensure))))))
```

The wrapper (`included-icons-lsp`) handles `cd`-ing into the tango-remixer repo root so `python3 -m lsp` can find the `lsp/` package.

On first visit Emacs will ask whether to trust the dir-locals; press `!` to accept permanently.

#### Option B: global init.el setup (one-time, works across all projects)

Put this in your `init.el` (or `~/.emacs.d/init.el`). The derived mode + auto-mode-alist binding means every `included_icons.txt` you ever open gets the right mode automatically; the eglot-server-programs entry tells Eglot where to find the wrapper; the mode hook starts Eglot on entry.

```elisp
;; Dedicated mode so Eglot only attaches to this one file, not every
;; text-mode buffer in the project (see the NOTE below).
(define-derived-mode tango-included-icons-mode text-mode "TangoIcons"
  "Major mode for tango-remixer's included_icons.txt config.")
(add-to-list 'auto-mode-alist '("included_icons\\.txt\\'" . tango-included-icons-mode))

(with-eval-after-load 'eglot
  ;; Use an absolute path -- adjust to wherever you cloned tango-remixer.
  ;; If tango-remixer lives inside each project as a submodule, prefer
  ;; Option A so the path stays relative.
  (add-to-list 'eglot-server-programs
               '(tango-included-icons-mode . ("/absolute/path/to/tango-remixer/included-icons-lsp"))))

(add-hook 'tango-included-icons-mode-hook #'eglot-ensure)
```

Trade-off: simpler config, but you pin a single absolute wrapper path. Use Option A if you have multiple projects each with their own `tango-remixer/` submodule.

> [!NOTE]
> The dedicated `tango-included-icons-mode` is **not optional** in either option. If you bind Eglot to plain `text-mode`, Eglot's `after-change-major-mode-hook` will auto-attach the running server to every text-mode (or derived) buffer in the same project -- including your magit commit message buffer -- and spam them with bogus diagnostics. The attach check is `provided-mode-derived-p`, which we sidestep by giving `included_icons.txt` a mode that's a *sibling* of `git-commit-mode`, not an ancestor.

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

## What the server does

- **Diagnostics**: parses `included_icons.txt` on open / change / save, flags syntax errors and bad size-matrix expressions with line + column ranges.
- **Semantic tokens**: colors theme name, context, icon name, size matrix, and comments. Needs an LSP client that supports `textDocument/semanticTokens/full` (Eglot >= 1.20; Neovim, Helix).
