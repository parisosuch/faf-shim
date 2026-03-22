.PHONY: test lint format check dev hash-password gen-secret seed

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
	@read -p "Password: " pw && uv run python -c "import bcrypt, sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "$$pw"

gen-secret:
	uv run python -c "import secrets; print(secrets.token_hex(32))"

seed:
	uv run python seed.py
