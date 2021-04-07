.PHONY: run test

run: src/hn/resources
	hn

test:
	poetry run pytest

src/hn/resources: src/hn/resources.gresource.xml src/hn/ui/*.ui src/hn/icons/* src/hn/css/*
	cd src/hn/ && glib-compile-resources resources.gresource.xml --target resources
