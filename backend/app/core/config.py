from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    POSTGRES_URL: str = ""
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    QUERY_TIMEOUT_SECONDS: int = 60
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-opus-4-5"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # App URL used in password-reset links
    APP_URL: str = "http://localhost:3001"

    # SMTP (optional) — if not set, reset tokens are printed to the backend console
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@datachat.local"

    # AWS Athena / Glue
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    ATHENA_WORKGROUP: str = "primary"
    ATHENA_OUTPUT_BUCKET: str = ""  # e.g. s3://my-bucket/athena-results/

    # DuckDB — absolute path overrides the default (backend/business_assistant.db)
    DUCKDB_PATH: str = ""

    # Comma-separated admin emails — these users can manage the shared Athena connection.
    # If empty, ALL authenticated users can manage it (backwards-compatible default).
    ADMIN_EMAILS: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
