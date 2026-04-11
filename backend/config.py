from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://certifexpert:devpass@localhost:5433/certifexpert"
    database_url_sync: str = "postgresql://certifexpert:devpass@localhost:5433/certifexpert"


settings = Settings()
