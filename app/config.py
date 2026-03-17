from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_username: str = "admin"
    admin_password_hash: str  # bcrypt hash of the admin password
    jwt_secret: str  # long random string
    jwt_expire_minutes: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
