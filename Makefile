# `make` (or `make help`) lists the targets and variables below, the way the Makefile of the qkiss repository
# (two folders up) does: `help` reads this file and prints every `target: ## text` line and every `## text` line
# above a `VAR := value`; `###` and `##@` lines are its section titles. Ordinary comments keep a single `#`.
.DEFAULT_GOAL := help

##@ -- Website ---------------------------------------------------------

## Where `homepage-build` writes the website: the folder GitHub Pages and GitLab Pages publish (gitignored). (Default: `homepage/_build`)
HOMEPAGE_OUT := homepage/_build
## Port `homepage-dev-server` serves the website on. (Default: `8000`)
HOMEPAGE_PORT := 8000

define print_title
printf "\n"; \
printf "\033[36m=============================================================\033[0m\n"; \
printf "\033[36m %s \033[0m\n" $(1); \
printf "\033[36m=============================================================\033[0m\n" ;
endef

define __DOC_QUICK_START__
# Links
- GitHub: https://github.com/kuanyui/tango-remixer
- Website (README.md + the icon viewer): https://kuanyui.github.io/tango-remixer/

# Typical use
- `make viewer` to browse the source icon themes and copy lines for `included_icons.txt`
- `python3 ./build_icons.py --included-icon-file included_icons.txt` to build the theme into `dist/` (`--help` lists the options)

# About this Makefile
- Use `make` or `make help` to show this help info.
- To set variables, use `make VAR1=foo VAR2=bar target`


endef
export __DOC_QUICK_START__


.PHONY: help
help:    ## Show this self-documented help message.
	@# Some operating system / Linux distro may use `mawk` (e.g. Ubuntu), so prefer more portable `perl` over `awk`.
	@S=$$(basename "$${SHELL:-sh}"); if [ "$${S}" != "zsh" ] && [ "$${S}" != "fish" ]; then echo "(Tip: You are using \`$${S}\`, but you can consider to use \`zsh\` or \`fish\` because they support tab completions for Makefile targets & variables.)"; fi
	@if command -v perl >/dev/null 2>&1; then \
		$(call print_title,"Quick Start") \
		printf "$$__DOC_QUICK_START__" | perl -pe 's/`([^`]+)`/\033[33m`\1`\033[0m/g; s/^(#+ .+)/\033[32m\1\033[0m/g; s/(https?:\/\/[a-zA-Z0-9.\/_#?-]+)/\033[34m\1\033[0m/g'; \
		$(call print_title,"Variables") \
		perl -ne 'if (/^## /) { $$desc = substr($$_, 3); $$next = <>; if ($$next =~ /^([A-Za-z0-9_]+)\s*[:?+]?=\s*(.*)$$/) { $$target=$$1; $$desc=~s/(`[^`]*?`)/\033[33m\1\033[0m/g; printf "\033[35m%-30s\033[0m %s", $$target, $$desc; } } elsif (/^[ \t]*##@ *(.*)/) { print "\033[34m$$1\033[0m\n"; }' $(MAKEFILE_LIST); \
		$(call print_title,"Targets") \
		perl -ne 'if (/^([a-zA-Z0-9_-]+):.*?## (.*)$$/) { $$target = $$1; $$desc = $$2; if ($$desc =~ /DEPRECATED/) { printf "\033[2m%-30s %s\033[0m\n", $$target, $$desc; } else { $$desc=~s/(`[^`]*?`)/\033[33m\1\033[0m/g; printf "\033[32m%-30s\033[0m %s\n", $$target, $$desc; } } elsif (/^[ \t]*### *(.*)/) { print "\033[34m$$1\033[0m\n"; }' $(MAKEFILE_LIST); \
	else \
		$(call print_title,"Quick Start") \
		printf "$$__DOC_QUICK_START__" | gawk '{gsub(/`[^`]+`/, "\033[33m&\033[0m"); gsub(/^#+ .+/, "\033[32m&\033[0m"); gsub(/https?:\/\/[a-zA-Z0-9.\/_#?-]+/, "\033[34m&\033[0m"); print}'; \
		$(call print_title,"Variables") \
		gawk '/^## /{desc=substr($$0, 4); gsub(/`[^`]*`/, "\033[33m&\033[0m", desc); getline; if ($$1 ~ /^[A-Za-z0-9_]+$$/ && match($$0, /^[^:?+]*[:?+]?=/, m)) printf "\033[35m%-30s\033[0m %s\n", $$1, desc} /^[ \t]*##@/{sub(/^[ \t]*##@ */, ""); printf "\033[34m%s\033[0m\n", $$0}' $(MAKEFILE_LIST) ; \
		$(call print_title,"Targets") \
		gawk 'match($$0, /^([a-zA-Z0-9_-]+):.*?## (.*)$$/, m) { target=m[1]; desc=m[2]; if (desc ~ /DEPRECATED/) { printf "\033[2m%-30s %s\033[0m\n", target, desc } else { gsub(/`[^`]*`/, "\033[33m&\033[0m", desc); printf "\033[32m%-30s\033[0m %s\n", target, desc } } match($$0, /^[ \t]*### *(.*)/, m){printf "\033[34m%s\033[0m\n", m[1]}' $(MAKEFILE_LIST); \
	fi

###
### -- Icon viewer and website ---------------------------------------------

# `viewer/` is also a directory; without .PHONY make would report it as up to date.
.PHONY: viewer
viewer:    ## Browse the source icon themes (`submodules/`, no build needed): a web UI on every interface, open one of the printed URLs.
	python3 -m viewer

# The website (this README + the icon viewer) as plain files, as GitHub Pages and GitLab Pages publish it. Needs
# Python-Markdown and Pygments: `apt install python3-markdown python3-pygments` (Debian / Ubuntu) or
# `pip install markdown pygments`. It also needs rsvg-convert, for the link-preview image: `apt install librsvg2-bin`.
.PHONY: homepage-build
homepage-build:    ## Generate the website (README.md + the icon viewer) into `HOMEPAGE_OUT`. Needs `python3-markdown`, `python3-pygments` and `rsvg-convert`.
	python3 homepage/generate_static_site.py $(HOMEPAGE_OUT)

# The same, then served on every interface (as `make viewer`), so the host of a VM can open it too. The URLs to
# open are printed, this machine's LAN addresses among them. A change to README.md, homepage/, viewer/static/
# or lib/color_converter.py rebuilds the site while it is served (reload the page). Ctrl-C stops it.
.PHONY: homepage-dev-server
homepage-dev-server:    ## Generate the website, serve it on port `HOMEPAGE_PORT` on every interface (the URLs to open are printed, LAN addresses included) and rebuild it when README.md, homepage/ or viewer/static/ change. Ctrl-C stops it.
	python3 homepage/generate_static_site.py $(HOMEPAGE_OUT) --serve $(HOMEPAGE_PORT)

###
### -- Development -----------------------------------------------------------

.PHONY: test
test:    ## Run the test suite (`tests/run_all_tests.py`).
	python3 tests/run_all_tests.py

# Source SVGs that Inkscape draws but browsers do not (see tools/fix_svg_for_browsers.py): list / repair in place.
.PHONY: check-svg
check-svg:    ## List the source SVGs that Inkscape draws but browsers do not (`tools/fix_svg_for_browsers.py`).
	python3 tools/fix_svg_for_browsers.py --check

.PHONY: fix-svg
fix-svg:    ## Repair those SVGs in place.
	python3 tools/fix_svg_for_browsers.py

###
### -- Cleaning --------------------------------------------------------------

.PHONY: clean
clean:    ## Delete `dist/`, the built icon theme.
	rm -rf dist

.PHONY: clean-tarballs
clean-tarballs:    ## Delete `thirdparty/`, the downloaded tarballs, so that `build_icons.py` fetches them again.
	rm -rf thirdparty

.PHONY: clear
clear: clean    ## DEPRECATED: the old name of `clean`.
