from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://krishi:krishi@localhost:5433/krishi"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    # Small, fast on CPU (~1s). "BAAI/bge-reranker-base" is stronger but ~6s on this laptop.
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    chunk_config: str = "size512_overlap64"  # which stored chunking strategy /ask uses

    # Any provider: "anthropic" or "openai_compatible" (OpenAI, Gemini, Groq, OpenRouter, Ollama...)
    llm_provider: str = "openai_compatible"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""

    judge_provider: str = "openai_compatible"
    judge_model: str = ""
    judge_base_url: str = ""
    judge_api_key: str = ""


settings = Settings()

# Chunking strategies stored side by side (chunks.config) so the eval can compare them.
CHUNK_CONFIGS = {
    "size512_overlap64": (512, 64),
    "size256_overlap32": (256, 32),
}
