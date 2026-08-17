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
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str = "deepseek-ai/DeepSeek-V3.2"
    supermemory_api_key: str | None = None
    tavily_api_key: str | None = None

    # Server-controlled Supermemory container for the demo. Never accepted
    # from the browser — the backend is the only thing that sets this.
    supermemory_container_tag: str = "proofly_demo_maya"

    # Upload limits enforced by the document vault endpoints.
    max_upload_size_bytes: int = 10 * 1024 * 1024

    # Featherless extraction tuning (app/services/featherless_service.py).
    featherless_request_timeout_seconds: float = 60.0
    featherless_max_output_tokens: int = 4000
    featherless_max_total_input_characters: int = 120_000

    # Document-grounded chat retrieval tuning (Phase 5, app/services/supermemory_service.py).
    chat_retrieval_limit: int = 5
    chat_relevance_threshold: float | None = None
    chat_max_context_characters: int = 8000

    # Official immigration updates search (Phase 6, app/services/tavily_service.py).
    tavily_request_timeout_seconds: float = 15.0
    tavily_cache_ttl_seconds: int = 900

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
