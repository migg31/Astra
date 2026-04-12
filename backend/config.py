from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://certifexpert:devpass@localhost:5433/certifexpert"
    database_url_sync: str = "postgresql://certifexpert:devpass@localhost:5433/certifexpert"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "mistral"


settings = Settings()
