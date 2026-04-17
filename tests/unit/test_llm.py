"""Tests for LLM adapter factory and context builder."""

from __future__ import annotations

import pytest

from hqmts.llm.factory import LLMFactory
from hqmts.llm.ollama_adapter import OllamaAdapter
from hqmts.llm.openai_adapter import OpenAIAdapter
from hqmts.llm.context_builder import build_system_prompt


class TestLLMFactory:
    def test_live_env_returns_ollama(self):
        factory = LLMFactory()
        adapter = factory.get_adapter("live")
        assert isinstance(adapter, OllamaAdapter)

    def test_live_env_ignores_provider_param(self):
        factory = LLMFactory()
        adapter = factory.get_adapter("live", model_provider="openai")
        assert isinstance(adapter, OllamaAdapter)

    def test_research_default_returns_openai(self):
        factory = LLMFactory(openai_api_key="test-key")
        adapter = factory.get_adapter("research")
        assert isinstance(adapter, OpenAIAdapter)

    def test_research_ollama_provider(self):
        factory = LLMFactory()
        adapter = factory.get_adapter("research", model_provider="ollama")
        assert isinstance(adapter, OllamaAdapter)

    def test_validate_provider_live_only_ollama(self):
        factory = LLMFactory()
        assert factory.validate_provider("live", "ollama")
        assert not factory.validate_provider("live", "openai")
        assert not factory.validate_provider("live", "claude")

    def test_validate_provider_research_allows_all(self):
        factory = LLMFactory()
        assert factory.validate_provider("research", "openai")
        assert factory.validate_provider("research", "ollama")
        assert factory.validate_provider("research", "claude")

    def test_validate_provider_paper_allows_all(self):
        factory = LLMFactory()
        assert factory.validate_provider("paper", "openai")
        assert factory.validate_provider("paper", "ollama")


class TestContextBuilder:
    def test_live_env_prompt(self):
        prompt = build_system_prompt("live")
        assert "实盘" in prompt
        assert "本地模型" in prompt

    def test_research_env_prompt(self):
        prompt = build_system_prompt("research")
        assert "研究" in prompt

    def test_paper_env_prompt(self):
        prompt = build_system_prompt("paper")
        assert "模拟盘" in prompt

    def test_base_prompt_contains_constraints(self):
        prompt = build_system_prompt("research")
        assert "不可以" in prompt
        assert "直接下单" in prompt
