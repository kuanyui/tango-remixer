;; In-repo demo. Resolves the wrapper path to an absolute path at .dir-locals
;; eval time (relative to this directory), so Eglot's cwd doesn't matter.
((text-mode . ((eval . (when (equal (file-name-nondirectory (or buffer-file-name "")) "included_icons.txt")
    (setq-local eglot-server-programs `((text-mode . (,(expand-file-name "../../included-icons-lsp" default-directory)))))
    (eglot-ensure))))))
