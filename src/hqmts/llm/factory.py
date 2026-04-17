"""LLM adapter factory.

Routes to the correct adapter based on environment and configuration.
Enforces Live environment local-only model constraint.
"""

from __future__ import annotations

from hqmts.llm.base import LLMAdapter
from hqmts.llm.ollama_adapter import OllamaAdapter
from hqmts.llm.openai_adapter import OpenAIAdapter


class LLMFactory:
    """Create LLM adapters based on environment and configuration."""

    def __init__(
        self,
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:7b",
    ) -> None:
        self._openai_api_key = openai_api_key
        self._openai_model = openai_model
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model

    def get_adapter(
        self,
        environment: str,
        model_provider: str | None = None,
    ) -> LLMAdapter:
        """Get the appropriate LLM adapter for the environment.

        Live environment: ONLY Ollama (data security constraint).
        Research/Backtest/Paper: Provider specified by model_provider.
        """
        if environment == "live":
            return OllamaAdapter(
                base_url=self._ollama_base_url,
                model=self._ollama_model,
            )

        # Non-live: use specified provider
        provider = model_provider or "openai"
        if provider == "ollama":
            return OllamaAdapter(
                base_url=self._ollama_base_url,
                model=self._ollama_model,
            )

        # Default: OpenAI
        return OpenAIAdapter(
            api_key=self._openai_api_key,
            model=self._openai_model,
        )

    def validate_provider(self, environment: str, model_provider: str) -> bool:
        """Check if a model provider is allowed for the given environment."""
        if environment == "live":
            return model_provider == "ollama"
        return model_provider in ("openai", "ollama", "claude")
