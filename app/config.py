from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://krishi:krishi@localhost:5433/krishi"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_hour: int = 20  # /ask requests per IP per hour; 0 turns it off
    # Small, fast on CPU (~1s). "BAAI/bge-reranker-base" is stronger but ~6s on this laptop.
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    chunk_config: str = "size512_overlap64"  # which stored index (CHUNK_CONFIGS) /ask uses
    # Weight of keyword hits vs vector hits in fusion (vector = 1). 0.5 chosen by eval (Day 4).
    keyword_weight: float = 0.5
    rerank_pool: int = 15  # fused candidates the reranker scores; ~0.07s each on CPU (MiniLM)

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

BGE_EN = "BAAI/bge-small-en-v1.5"
E5_MULTI = "intfloat/multilingual-e5-small"
MINILM_MULTI = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Index recipes stored side by side (chunks.config) so the eval can compare them:
# name -> (chunk size in tokens, overlap, embedding model). All models are 384-dimensional,
# matching the vector(384) column.
CHUNK_CONFIGS = {
    "size512_overlap64": (512, 64, BGE_EN),
    "size256_overlap32": (256, 32, BGE_EN),
    "size512_overlap64_e5": (512, 64, E5_MULTI),
    "size512_overlap64_minilm": (512, 64, MINILM_MULTI),
}


def embed_model_for(config: str) -> str:
    return CHUNK_CONFIGS[config][2]
