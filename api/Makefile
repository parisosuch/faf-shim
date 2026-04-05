.PHONY: test lint format format-check check dev hash-password gen-secret seed

test:
	uv run pytest tests/ -v -n auto

lint:
	uvx ruff check

format:
	uvx ruff format

format-check:
	uvx ruff format --check

dev:
	uv sync
	uv run uvicorn app.main:app --reload

check: lint format-check test

hash-password:
	@read -p "Password: " pw && uv run python -c "import bcrypt, sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "$$pw"

gen-secret:
	uv run python -c "import secrets; print(secrets.token_hex(32))"

seed:
	uv run python seed.py
