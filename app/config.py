from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_environment: str = "development"
    routewise_api_key: str = ""
    rate_limit_requests_per_minute: int = 0
    cors_allowed_origins: str = ""

    cache_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://routewise:routewise@localhost:5432/routewise"
    request_logging_enabled: bool = False
    auto_create_db_tables: bool = False

    small_model: str = "ollama/llama3.2"
    medium_model: str = "gpt-4o-mini"
    frontier_model: str = "gpt-4o"
    model_call_timeout_seconds: float = 60.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_http_timeout_seconds: float = 60.0
    readiness_timeout_seconds: float = 3.0
    model_prices_json: str = ""
    openai_api_key: str = ""
    preflight_default_completion_tokens: int = 256

    exact_cache_ttl_seconds: int = 86400
    semantic_cache_preview_enabled: bool = True
    semantic_cache_similarity_threshold: float = 0.80
    semantic_cache_reuse_enabled: bool = True
    semantic_cache_reuse_similarity_threshold: float = 0.95
    semantic_cache_hydration_limit: int = 1000
    semantic_cache_embedding_dimensions: int = 256
    prompt_compression_enabled: bool = True
    prompt_compression_word_threshold: int = 600
    prompt_compression_target_words: int = 350

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
