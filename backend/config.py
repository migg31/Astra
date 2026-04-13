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

    # --- Chat LLM provider (reranker + answer generation) ---
    # Ollama local:  base_url=http://localhost:11434/v1  api_key=ollama  model=mistral
    # Groq:          base_url=https://api.groq.com/openai/v1  api_key=<GROQ_API_KEY>  model=llama-3.3-70b-versatile
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model: str = "mistral"

    # --- Embedding provider ---
    # Ollama local:  base_url=http://localhost:11434/v1  api_key=ollama  model=nomic-embed-text
    # Nomic.ai:      base_url=https://api-atlas.nomic.ai/v1  api_key=<NOMIC_API_KEY>  model=nomic-embed-text-v1.5
    embed_base_url: str = "http://localhost:11434/v1"
    embed_api_key: str = "ollama"
    embed_model: str = "nomic-embed-text"
    embed_dimensions: int = 768  # 768 for nomic-embed-text, 768 for nomic-v1.5, update if switching


settings = Settings()
