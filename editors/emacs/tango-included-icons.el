;;; tango-included-icons.el --- Emacs support for tango-remixer's included_icons.txt  -*- lexical-binding: t -*-

;; This file is not a package and needs no installation.  Two ways to use it:
;;
;; 1. Per file (recommended): put this on the first line of included_icons.txt,
;;    with the path relative to that file's directory.  Emacs asks once
;;    whether to run the `eval'; answer `!' so it is remembered.
;;
;;      # -*- eval: (load-file "tango-remixer/editors/emacs/tango-included-icons.el") -*-
;;
;;    or, as a block at the end of the file:
;;
;;      # Local Variables:
;;      # eval: (load-file "tango-remixer/editors/emacs/tango-included-icons.el")
;;      # End:
;;
;; 2. Globally: (load "/path/to/tango-remixer/editors/emacs/tango-included-icons.el")
;;    in your init file.  Every included_icons.txt then gets the mode and
;;    Eglot through `auto-mode-alist'.
;;
;; Emacs may evaluate the file-local form more than once per visit (switching
;; major mode re-runs local variables), so everything below is idempotent.

;;; Code:

(defconst tango-included-icons-directory
  (expand-file-name "../.." (file-name-directory (or load-file-name buffer-file-name)))
  "Root of the tango-remixer checkout this file lives in.")

(defvar tango-included-icons-python nil
  "Python interpreter used to run the LSP server, or nil for python3 on PATH.
Set it in your init file when pygls lives in a venv.")
;; A file must not be able to pick the interpreter: keep this prompt-guarded.
(put 'tango-included-icons-python 'risky-local-variable t)

(defun tango-included-icons-server-command ()
  "LSP server command.  Runs lsp/server.py directly: no cwd, no /bin/sh."
  (list (or tango-included-icons-python (executable-find "python3") "python")
        (expand-file-name "lsp/server.py" tango-included-icons-directory)))

(define-derived-mode tango-included-icons-mode text-mode "TangoIcons"
  "Major mode for tango-remixer's included_icons.txt.
A dedicated mode keeps Eglot from attaching to other text-mode buffers
of the same project, such as commit messages."
  (setq-local comment-start "# "
              comment-start-skip "#+[ \t]*")
  (setq-local eglot-server-programs
              `((tango-included-icons-mode . ,(tango-included-icons-server-command))))
  (when (fboundp 'eglot-ensure)
    (eglot-ensure)))

(add-to-list 'auto-mode-alist '("included_icons\\.txt\\'" . tango-included-icons-mode))

;; Bootstrap the buffer whose local variables loaded us.
(when (and buffer-file-name
           (equal (file-name-nondirectory buffer-file-name) "included_icons.txt")
           (not (derived-mode-p 'tango-included-icons-mode)))
  (tango-included-icons-mode))

(provide 'tango-included-icons)
;;; tango-included-icons.el ends here
