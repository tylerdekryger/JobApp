from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/job_intelligence"
    test_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/job_intelligence_test"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
