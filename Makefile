# `viewer/` is also a directory; without .PHONY make would report it as up to date.
.PHONY: viewer
viewer:
	python3 -m viewer

test:
	python3 tests/run_all_tests.py

clean-tarballs:
	rm -rf thirdparty

clear:
	rm -rf dist