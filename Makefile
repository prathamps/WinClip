.PHONY: dev test lint run install uninstall

dev:            ## create a dev virtualenv with test tooling
	@if command -v uv >/dev/null; then \
		uv venv --python /usr/bin/python3 --system-site-packages .venv && \
		uv pip install -e .[dev]; \
	else \
		python3 -m venv .venv --system-site-packages && \
		.venv/bin/pip install -e .[dev]; \
	fi

test:           ## run the test suite
	.venv/bin/pytest

lint:           ## run ruff
	.venv/bin/ruff check src tests

run:            ## run the daemon from the working tree
	PYTHONPATH=src python3 -m winclip -v

install:        ## full user install (deps, service, keybinding)
	bash scripts/install.sh

uninstall:
	bash scripts/uninstall.sh
