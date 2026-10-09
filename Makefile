# `viewer/` is also a directory; without .PHONY make would report it as up to date.
.PHONY: viewer
viewer:
	python3 -m viewer

# The website (this README + the icon viewer) as plain files in homepage/_build/, as GitHub Pages and GitLab Pages publish
# it. Needs Python-Markdown: `apt install python3-markdown` (Debian / Ubuntu) or `pip install markdown`.
homepage-build:
	python3 homepage/generate_static_site.py homepage/_build

# The same, then served at http://127.0.0.1:8000/ for a look before pushing. Ctrl-C stops it; run again after edits.
homepage-dev-server: homepage-build
	python3 -m http.server --directory homepage/_build --bind 127.0.0.1 8000

test:

	python3 tests/run_all_tests.py

# Source SVGs that Inkscape draws but browsers do not (see tools/fix_svg_for_browsers.py): list / repair in place.
check-svg:
	python3 tools/fix_svg_for_browsers.py --check

fix-svg:
	python3 tools/fix_svg_for_browsers.py

clean-tarballs:
	rm -rf thirdparty

clear:
	rm -rf dist