from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://krishi:krishi@localhost:5433/krishi"
    embed_model: str = "BAAI/bge-small-en-v1.5"


settings = Settings()

# Chunking strategies stored side by side (chunks.config) so the eval can compare them.
CHUNK_CONFIGS = {
    "size512_overlap64": (512, 64),
    "size256_overlap32": (256, 32),
}
