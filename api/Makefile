.PHONY: test lint format check dev hash-password gen-secret

test:
	uv run pytest tests/ -v

lint:
	uvx ruff check

format:
	uvx ruff format

dev:
	uv sync
	uv run uvicorn app.main:app --reload

check: lint test

hash-password:
	@read -p "Password: " pw && uv run python -c "import bcrypt; print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())"

gen-secret:
	uv run python -c "import secrets; print(secrets.token_hex(32))"
