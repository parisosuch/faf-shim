.PHONY: test lint format check

test:
	uv run pytest tests/ -v

lint:
	uvx ruff check

format:
	uvx ruff format

check: lint test
