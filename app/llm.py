"""One function, any LLM provider. Nothing outside this file knows which provider is in use."""

from functools import cache

from app.config import settings

PROVIDERS = ("anthropic", "openai_compatible")
MAX_TOKENS = 1024


class LLMError(RuntimeError):
    """The LLM is not configured, unreachable, refused, or returned nothing."""


def _cfg(role: str) -> tuple[str, str, str, str]:
    p = "judge" if role == "judge" else "llm"
    return tuple(getattr(settings, f"{p}_{f}") for f in ("provider", "model", "base_url", "api_key"))


@cache
def _client(provider: str, base_url: str, api_key: str):
    if provider == "anthropic":
        import anthropic

        # Explicit default URL so a stray ANTHROPIC_BASE_URL env var can't redirect requests.
        return anthropic.Anthropic(
            api_key=api_key or None, base_url=base_url or "https://api.anthropic.com"
        )
    import openai

    # Local servers such as Ollama ignore the key, but the SDK requires one.
    return openai.OpenAI(api_key=api_key or "not-needed", base_url=base_url or None)


def complete(system: str, user: str, role: str = "llm") -> str:
    provider, model, base_url, api_key = _cfg(role)
    prefix = "JUDGE" if role == "judge" else "LLM"
    if provider not in PROVIDERS:
        raise LLMError(f"{prefix}_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    if not model:
        raise LLMError(f"{prefix}_MODEL is not set in .env")
    try:
        client = _client(provider, base_url, api_key)
        if provider == "anthropic":
            return _anthropic(client, model, system, user)
        return _openai(client, model, system, user)
    except LLMError:
        raise
    except Exception as e:  # SDK errors differ per provider; surface them as one type
        raise LLMError(f"{provider} call failed: {e}") from e


def _anthropic(client, model: str, system: str, user: str) -> str:
    # No temperature: current Claude API versions reject it.
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise LLMError("model declined to answer")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise LLMError("model returned no text")
    return text


def _openai(client, model: str, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    if not text:
        raise LLMError("model returned no text")
    return text
