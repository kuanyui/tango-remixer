;; In-repo demo, self-contained. Defines a one-shot derived mode inline so
;; Eglot's auto-attach (`provided-mode-derived-p`) won't grab unrelated
;; text-mode buffers (e.g. magit's COMMIT_EDITMSG). Wrapper path is
;; resolved at .dir-locals eval time (relative to this directory), so
;; Eglot's cwd doesn't matter.
((nil . ((eval . (when (and buffer-file-name
                              (equal (file-name-nondirectory buffer-file-name) "included_icons.txt"))
    (unless (fboundp 'tango-included-icons-mode)
      (define-derived-mode tango-included-icons-mode text-mode "TangoIcons"))
    (unless (eq major-mode 'tango-included-icons-mode)
      (tango-included-icons-mode))
    (setq-local eglot-server-programs
                `((tango-included-icons-mode . (,(expand-file-name "../../included-icons-lsp" default-directory)))))
    (eglot-ensure))))))
