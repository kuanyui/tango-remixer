# `viewer/` is also a directory; without .PHONY make would report it as up to date.
.PHONY: viewer
viewer:
	python3 -m viewer

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