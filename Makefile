build:
	python3 ./build_icons.py

test:
	python3 tests/run_all_tests.py

clean-tarballs:
	rm -rf thirdparty

clear:
	rm -rf dist