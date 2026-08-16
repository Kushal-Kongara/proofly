"""Application settings loaded from environment variables.

Values are read via pydantic-settings from the repo-root .env file.
Only environment-variable *names* are referenced here — never literal
secret values. See .env.example for the full list of supported vars.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Comma-separated list of allowed frontend origins for CORS.
    cors_origins: str = "http://localhost:5173"

    # Names of future integration keys (values live only in .env, never here).
    featherless_api_key: str | None = None
    featherless_base_url: str | None = None
    supermemory_api_key: str | None = None
    tavily_api_key: str | None = None

    # Server-controlled Supermemory container for the demo. Never accepted
    # from the browser — the backend is the only thing that sets this.
    supermemory_container_tag: str = "proofly_demo_maya"

    # Upload limits enforced by the document vault endpoints.
    max_upload_size_bytes: int = 10 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
