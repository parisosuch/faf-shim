import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_username: str = "admin"
    admin_password: str | None = None  # plain text — hashed at startup
    admin_password_hash: str | None = None  # legacy override (takes precedence if set)
    jwt_secret: str = secrets.token_hex(32)
    jwt_expire_minutes: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
