run: src/hn/resources
	python3 -u src/hn/hn.py

src/hn/resources: src/hn/resources.gresource.xml src/hn/ui/*.ui
	cd src/hn/ && glib-compile-resources resources.gresource.xml --target resources
