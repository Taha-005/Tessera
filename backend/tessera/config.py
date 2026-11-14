"""The one settings module: every setting comes from the environment or a local .env file."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        # An empty value (e.g. "JWT_SECRET_KEY=") counts as missing, so it also fails fast.
        env_ignore_empty=True,
        # Startup errors name the setting but never echo values, which can be secrets.
        hide_input_in_errors=True,
    )

    # Required: the app refuses to start without them.
    database_url: SecretStr  # secret because it contains the database password
    data_dir: Path  # where the department data lives, outside this repository
    jwt_secret_key: SecretStr  # signs the JWTs every endpoint will use

    # Optional.
    cors_allowed_origins: list[str] = []  # empty: no browser origin may call the API
    llm_api_key: SecretStr | None = None  # stays optional until O-12 is decided
