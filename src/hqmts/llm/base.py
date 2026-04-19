"""Abstract LLM adapter interface."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from typing import Any


class LLMAdapter(abc.ABC):
    """Abstract base class for LLM providers."""

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """Send messages and return a complete response."""

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Send messages and yield response chunks."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM provider is reachable."""
