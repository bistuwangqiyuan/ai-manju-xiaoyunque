"""Phase 2 multi-LLM fallback chain — offline tests."""
from __future__ import annotations

import json
import os

import pytest


# --------------------------------------------------------------------------
# Catalog / chain construction
# --------------------------------------------------------------------------

def test_catalog_contains_all_phase2_providers(monkeypatch):
    from src.common.multi_provider_llm import _all_providers

    cat = _all_providers()
    expected = {
        "anthropic", "deepseek", "glm", "tongyi", "dashscope",
        "moonshot", "mistral", "groq", "xai", "spark", "openai", "doubao",
    }
    assert expected.issubset(cat.keys()), (
        f"missing providers: {expected - cat.keys()}"
    )


def test_default_chain_order_is_consistent():
    from src.common.multi_provider_llm import (
        DEFAULT_CHAIN_ORDER, _all_providers,
    )
    cat = _all_providers()
    for name in DEFAULT_CHAIN_ORDER:
        assert name in cat, f"DEFAULT_CHAIN_ORDER references unknown: {name}"


def test_build_chain_respects_env_override(monkeypatch):
    from src.common.multi_provider_llm import build_provider_chain
    monkeypatch.setenv("LLM_PROVIDER_CHAIN", "groq,glm,deepseek")
    chain = build_provider_chain()
    names = [p.name for p in chain]
    assert names == ["groq", "glm", "deepseek"]


def test_build_chain_skips_unknown_names(monkeypatch):
    from src.common.multi_provider_llm import build_provider_chain
    monkeypatch.setenv("LLM_PROVIDER_CHAIN", "groq,bogus,glm")
    chain = build_provider_chain()
    assert [p.name for p in chain] == ["groq", "glm"]


# --------------------------------------------------------------------------
# Availability gating (no key → not available)
# --------------------------------------------------------------------------

def test_provider_unavailable_without_key(monkeypatch):
    from src.common.multi_provider_llm import _all_providers

    for v in ("DEEPSEEK_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
              "MISTRAL_API_KEY", "GROQ_API_KEY", "XAI_API_KEY",
              "SPARK_API_KEY", "TONGYI_API_KEY", "DASHSCOPE_API_KEY",
              "VOLC_ARK_API_KEY", "OPENAI_API_KEY",
              "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(v, raising=False)

    cat = _all_providers()
    for name, p in cat.items():
        assert not p.is_available(), f"{name} should NOT be available without key"


def test_provider_available_when_key_present(monkeypatch):
    from src.common.multi_provider_llm import _all_providers

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SPARK_API_KEY", "id:secret")

    cat = _all_providers()
    assert cat["deepseek"].is_available()
    assert cat["groq"].is_available()
    assert cat["anthropic"].is_available()
    assert cat["spark"].is_available()


# --------------------------------------------------------------------------
# Mock-mode end-to-end (no network)
# --------------------------------------------------------------------------

def test_force_mock_llm_chain_returns_synthetic_text(monkeypatch):
    from src.common.multi_provider_llm import llm_complete_with_fallback
    monkeypatch.setenv("FORCE_MOCK_LLM_CHAIN", "1")
    text, provider = llm_complete_with_fallback(
        system="You are a screenwriter.", user="Write a scene.",
    )
    assert provider == "mock"
    assert text is not None and "MOCK_LLM_CHAIN" in text


def test_chain_returns_none_when_no_keys(monkeypatch):
    from src.common.multi_provider_llm import llm_complete_with_fallback

    for v in ("FORCE_MOCK_LLM_CHAIN", "DEEPSEEK_API_KEY", "GLM_API_KEY",
              "MOONSHOT_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY",
              "XAI_API_KEY", "SPARK_API_KEY", "TONGYI_API_KEY",
              "DASHSCOPE_API_KEY", "VOLC_ARK_API_KEY", "OPENAI_API_KEY",
              "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "LLM_PROVIDER_CHAIN"):
        monkeypatch.delenv(v, raising=False)

    text, provider = llm_complete_with_fallback(
        system="x", user="y",
    )
    assert text is None
    assert provider is None


def test_chat_helper_raises_on_total_failure(monkeypatch):
    from src.common.multi_provider_llm import chat

    for v in ("FORCE_MOCK_LLM_CHAIN", "DEEPSEEK_API_KEY", "GLM_API_KEY",
              "MOONSHOT_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY",
              "XAI_API_KEY", "SPARK_API_KEY", "TONGYI_API_KEY",
              "DASHSCOPE_API_KEY", "VOLC_ARK_API_KEY", "OPENAI_API_KEY",
              "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "LLM_PROVIDER_CHAIN"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        chat(system="x", user="y")


# --------------------------------------------------------------------------
# Fallback wiring — theme_to_novel routes through the chain when keys present
# --------------------------------------------------------------------------

def test_theme_to_novel_routes_to_chain_when_keys_present(monkeypatch):
    """When ANY phase-2 key is present, _pick_backend() picks 'chain'."""
    from src.shell1_screenwriter import theme_to_novel as t2n

    for v in ("FORCE_MOCK_THEME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "DEEPSEEK_API_KEY", "GLM_API_KEY", "TONGYI_API_KEY",
              "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY", "MISTRAL_API_KEY",
              "GROQ_API_KEY", "XAI_API_KEY", "SPARK_API_KEY",
              "VOLC_ARK_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    assert t2n._pick_backend() == "mock"

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert t2n._pick_backend() == "chain"


def test_theme_to_novel_chain_path_falls_back_to_mock_on_failure(monkeypatch):
    """When chain returns nothing, theme_to_novel falls back to mock instead
    of raising — keeps the pipeline running."""
    from src.shell1_screenwriter import theme_to_novel as t2n

    # No keys → chain has nothing → mock
    for v in ("FORCE_MOCK_THEME", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
              "GLM_API_KEY", "TONGYI_API_KEY", "DASHSCOPE_API_KEY",
              "MOONSHOT_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY",
              "XAI_API_KEY", "SPARK_API_KEY", "VOLC_ARK_API_KEY",
              "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(v, raising=False)

    out = t2n.theme_to_novel("test theme", backend="chain")
    assert isinstance(out, str)
    assert len(out) > 0


# --------------------------------------------------------------------------
# Spark provider has special key format (id:secret) but should still validate
# --------------------------------------------------------------------------

def test_spark_provider_accepts_id_secret_format(monkeypatch):
    from src.common.multi_provider_llm import SparkProvider
    monkeypatch.setenv("SPARK_API_KEY", "DdOqdySdMfPVdUPKleqG:oynXFFHutBcilZdqMvpK")
    p = SparkProvider()
    assert p.is_available()
    assert p.name == "spark"
    assert "spark-api-open" in p.base_url
