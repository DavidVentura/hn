.PHONY: run test build

run: src/hn/resources
	PYTHONPATH=src PYTHONUNBUFFERED=1 python3 src/hn/app.py

test:
	poetry run pytest

build: src/hn/resources src/hn/*.py
	cd src && ../venv/bin/poetry build

src/hn/resources: src/hn/resources.gresource.xml src/hn/ui/*.ui src/hn/icons/* src/hn/css/* src/hn/js/*
	cd src/hn/ && glib-compile-resources resources.gresource.xml --target resources
