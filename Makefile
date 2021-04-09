.PHONY: run test

run: src/hn/resources
	venv/bin/hn

test:
	poetry run pytest

src/hn/resources: src/hn/resources.gresource.xml src/hn/ui/*.ui src/hn/icons/* src/hn/css/* src/hn/js/*
	cd src/hn/ && glib-compile-resources resources.gresource.xml --target resources
