build:
	python3 ./build_icons.py

test:
	python3 -m unittest discover -s tests -v

clean-tarballs:
	rm -rf thirdparty

clear:
	rm -rf dist