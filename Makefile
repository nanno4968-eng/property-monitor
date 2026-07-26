.PHONY: install install-dev run test lint init-db

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

init-db:
	python -m app.cli init-db

run:
	python -m app.cli run

test:
	pytest -q

lint:
	ruff check app tests
