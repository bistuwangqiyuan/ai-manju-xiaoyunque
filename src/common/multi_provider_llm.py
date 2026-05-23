"""Multi-Provider TEXT LLM fallback chain (Phase 2).

Companion to `tools/multi_provider_vlm.py` (which handles VISION judging).
This module handles **plain text** chat completions for scriptwriting,
event extraction, marketing copy, subtitle translation, etc.

Design principles (mirrors VLM router):
- **API failure never blocks the workflow** — try each provider in chain
- **Failures are visible** — log to `data/api_health.log`, print user warning
  on AUTH_FAILED / QUOTA_OUT / MODEL_NOT_FOUND
- **Chain is configurable** — `LLM_PROVIDER_CHAIN` env var overrides default
- **No status caching** — each call rebuilds the chain so a key fix takes
  effect immediately

Providers (10, all OpenAI-compatible except Anthropic + Spark):

| name        | env var              | default model                 | base URL                                        |
|-------------|----------------------|-------------------------------|-------------------------------------------------|
| anthropic   | ANTHROPIC_API_KEY    | claude-opus-4-7-20260413      | https://api.anthropic.com (custom protocol)     |
| deepseek    | DEEPSEEK_API_KEY     | deepseek-chat                 | https://api.deepseek.com/v1                     |
| glm         | GLM_API_KEY          | glm-4-plus                    | https://open.bigmodel.cn/api/paas/v4            |
| tongyi      | TONGYI_API_KEY       | qwen-max-latest               | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| dashscope   | DASHSCOPE_API_KEY    | qwen-plus                     | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| moonshot    | MOONSHOT_API_KEY     | moonshot-v1-128k              | https://api.moonshot.cn/v1                      |
| mistral     | MISTRAL_API_KEY      | mistral-large-latest          | https://api.mistral.ai/v1                       |
| groq        | GROQ_API_KEY         | llama-3.3-70b-versatile       | https://api.groq.com/openai/v1                  |
| xai         | XAI_API_KEY          | grok-3-latest                 | https://api.x.ai/v1                             |
| spark       | SPARK_API_KEY        | 4.0Ultra                      | https://spark-api-open.xf-yun.com/v1            |
| openai      | OPENAI_API_KEY       | gpt-4o-mini                   | https://api.openai.com/v1                       |
| doubao      | VOLC_ARK_API_KEY     | doubao-seed-1-6-thinking      | https://ark.cn-beijing.volces.com/api/v3        |

Public API:
    from src.common.multi_provider_llm import llm_complete_with_fallback
    text, provider = llm_complete_with_fallback(
        system="You are a screenwriter.",
        user="Write a 2-line scene.",
        json_mode=False,
        max_tokens=2000,
    )

Returns `(None, None)` only when ALL providers fail or no keys are configured.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import pathlib
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger(__name__)

API_HEALTH_LOG = pathlib.Path("data/api_health.log")
_NOTIFIED: set[str] = set()


# ---------------------------------------------------------------------------
# Health logging (shared format with VLM router)
# ---------------------------------------------------------------------------

def record_health(provider: str, status: str, code: int | str, msg: str,
                  notify: bool = True) -> None:
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    line = f"{ts}\t{provider}\t{status}\tcode={code}\tmsg={str(msg)[:200]}\n"
    try:
        API_HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(API_HEALTH_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

    if notify and status in ("AUTH_FAILED", "QUOTA_OUT", "MODEL_NOT_FOUND", "BLOCKED"):
        key = f"{provider}:{status}"
        if key not in _NOTIFIED:
            _NOTIFIED.add(key)
            actions = {
                "AUTH_FAILED": "检查 API key 是否有效（被停用或拼写错）",
                "QUOTA_OUT": "检查账户额度/余额",
                "MODEL_NOT_FOUND": "检查模型名（在 .env 改 *_MODEL）",
                "BLOCKED": "检查内容是否触发审核/区域限制",
            }
            print(
                f"\n[!] LLM 健康警告  "
                f"provider={provider}  status={status} ({code})\n"
                f"    msg : {str(msg)[:160]}\n"
                f"    fix : {actions.get(status, '查 data/api_health.log')}\n"
                f"    -> 自动切下一个 provider, 不阻塞工作流\n"
            )


def _classify_err(exc: Exception) -> tuple[str, int]:
    e = str(exc).lower()
    code = -1
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
    if code == 401 or any(k in e for k in ("401", "unauthor", "invalid_api_key",
                                            "authentication", "deactivated")):
        return "AUTH_FAILED", code if code > 0 else 401
    if code in (402, 429) or any(k in e for k in (
            "402", "payment required", "429", "rate_limit", "rate limit",
            "quota", "insufficient_quota", "insufficient credit", "billing",
            "余额不足", "欠费")):
        return "QUOTA_OUT", code if code > 0 else 429
    if code == 403 or any(k in e for k in ("403", "forbidden", "content_filter",
                                            "blocked")):
        return "BLOCKED", code if code > 0 else 403
    if code == 404 or any(k in e for k in ("404", "model_not_found",
                                            "no such model")):
        return "MODEL_NOT_FOUND", code if code > 0 else 404
    if code == 400 or "bad request" in e:
        return "BAD_REQUEST", code if code > 0 else 400
    return "EXCEPTION", code


# ---------------------------------------------------------------------------
# Provider base class
# ---------------------------------------------------------------------------

@dataclass
class LLMRequest:
    system: str
    user: str
    json_mode: bool = False
    max_tokens: int = 2000
    temperature: float = 0.5


class LLMProvider(ABC):
    name: str = "base"
    requires_env: list[str] = []

    def is_available(self) -> bool:
        return all(os.environ.get(e, "").strip() for e in self.requires_env)

    @abstractmethod
    def complete(self, req: LLMRequest) -> Optional[str]:
        ...


# ---------------------------------------------------------------------------
# OpenAI-compatible (Bearer auth, /v1/chat/completions)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(LLMProvider):
    """Generic OpenAI-compatible chat/completions provider."""

    def __init__(self, *, name: str, base_url: str, model_env: str,
                 default_model: str, api_key_env: str,
                 supports_json_mode: bool = True,
                 timeout: int = 180):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model_env = model_env
        self.default_model = default_model
        self.api_key_env = api_key_env
        self.requires_env = [api_key_env]
        self.supports_json_mode = supports_json_mode
        self.timeout = timeout

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env, self.default_model)

    def complete(self, req: LLMRequest) -> Optional[str]:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            return None
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.json_mode and self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
            record_health(self.name, "OK", 200, f"model={self.model}",
                          notify=False)
            return text
        except Exception as e:  # noqa: BLE001
            status, code = _classify_err(e)
            # Special case: if json mode caused a 400, retry without it
            if status == "BAD_REQUEST" and req.json_mode and self.supports_json_mode:
                try:
                    payload.pop("response_format", None)
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    request = urllib.request.Request(
                        f"{self.base_url}/chat/completions",
                        data=body,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                        data = json.loads(resp.read())
                    text = data["choices"][0]["message"]["content"]
                    record_health(self.name, "OK", 200,
                                  f"model={self.model} (no-json-mode)",
                                  notify=False)
                    return text
                except Exception as e2:  # noqa: BLE001
                    status, code = _classify_err(e2)
                    record_health(self.name, status, code, str(e2),
                                  notify=(status != "EXCEPTION"))
                    return None
            record_health(self.name, status, code, str(e),
                          notify=(status != "EXCEPTION"))
            return None


# ---------------------------------------------------------------------------
# Anthropic Claude (different protocol: x-api-key + /v1/messages)
# ---------------------------------------------------------------------------

class ClaudeProvider(LLMProvider):
    name = "anthropic"

    def is_available(self) -> bool:
        return bool(
            os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        )

    @property
    def model(self) -> str:
        return os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7-20260413")

    def complete(self, req: LLMRequest) -> Optional[str]:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        base_url = os.environ.get("ANTHROPIC_BASE_URL",
                                  "https://api.anthropic.com").rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
            headers["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                     "AppleWebKit/537.36")
        elif api_key:
            headers["x-api-key"] = api_key
        else:
            return None
        body = {
            "model": self.model,
            "max_tokens": req.max_tokens,
            "system": req.system,
            "messages": [{"role": "user", "content": req.user}],
            "temperature": req.temperature,
        }
        request = urllib.request.Request(
            f"{base_url}/v1/messages",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as resp:
                data = json.loads(resp.read())
            parts: list[str] = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = "\n".join(parts).strip()
            record_health(self.name, "OK", 200, f"model={self.model}",
                          notify=False)
            return text or None
        except Exception as e:  # noqa: BLE001
            status, code = _classify_err(e)
            record_health(self.name, status, code, str(e),
                          notify=(status != "EXCEPTION"))
            return None


# ---------------------------------------------------------------------------
# iFlytek Spark (OpenAI-compatible since 2024-09; key format is "id:secret")
# ---------------------------------------------------------------------------

class SparkProvider(OpenAICompatProvider):
    """Spark's compat endpoint takes the raw 'id:secret' as Bearer token."""

    def __init__(self):
        super().__init__(
            name="spark",
            base_url="https://spark-api-open.xf-yun.com/v1",
            model_env="SPARK_MODEL",
            default_model="4.0Ultra",
            api_key_env="SPARK_API_KEY",
            supports_json_mode=False,
            timeout=180,
        )


# ---------------------------------------------------------------------------
# Provider catalog + chain
# ---------------------------------------------------------------------------

def _all_providers() -> dict[str, LLMProvider]:
    return {
        "anthropic": ClaudeProvider(),
        "deepseek": OpenAICompatProvider(
            name="deepseek",
            base_url="https://api.deepseek.com/v1",
            model_env="DEEPSEEK_MODEL",
            default_model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
            supports_json_mode=True,
        ),
        "glm": OpenAICompatProvider(
            name="glm",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model_env="GLM_MODEL",
            default_model="glm-4-plus",
            api_key_env="GLM_API_KEY",
            supports_json_mode=False,
        ),
        "tongyi": OpenAICompatProvider(
            name="tongyi",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_env="TONGYI_MODEL",
            default_model="qwen-max-latest",
            api_key_env="TONGYI_API_KEY",
            supports_json_mode=True,
        ),
        "dashscope": OpenAICompatProvider(
            name="dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_env="DASHSCOPE_MODEL",
            default_model="qwen-plus",
            api_key_env="DASHSCOPE_API_KEY",
            supports_json_mode=True,
        ),
        "moonshot": OpenAICompatProvider(
            name="moonshot",
            base_url="https://api.moonshot.cn/v1",
            model_env="MOONSHOT_MODEL",
            default_model="moonshot-v1-128k",
            api_key_env="MOONSHOT_API_KEY",
            supports_json_mode=True,
        ),
        "mistral": OpenAICompatProvider(
            name="mistral",
            base_url="https://api.mistral.ai/v1",
            model_env="MISTRAL_MODEL",
            default_model="mistral-large-latest",
            api_key_env="MISTRAL_API_KEY",
            supports_json_mode=True,
        ),
        "groq": OpenAICompatProvider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            model_env="GROQ_MODEL",
            default_model="llama-3.3-70b-versatile",
            api_key_env="GROQ_API_KEY",
            supports_json_mode=True,
            timeout=60,  # Groq is fast
        ),
        "xai": OpenAICompatProvider(
            name="xai",
            base_url="https://api.x.ai/v1",
            model_env="XAI_MODEL",
            default_model="grok-3-latest",
            api_key_env="XAI_API_KEY",
            supports_json_mode=True,
        ),
        "spark": SparkProvider(),
        "openai": OpenAICompatProvider(
            name="openai",
            base_url=os.environ.get("OPENAI_API_BASE",
                                    "https://api.openai.com/v1"),
            model_env="OPENAI_MODEL",
            default_model="gpt-4o-mini",
            api_key_env="OPENAI_API_KEY",
            supports_json_mode=True,
        ),
        "doubao": OpenAICompatProvider(
            name="doubao",
            base_url=os.environ.get("ARK_BASE_URL",
                                    "https://ark.cn-beijing.volces.com/api/v3"),
            model_env="DOUBAO_MODEL",
            default_model="doubao-seed-1-6-thinking-250715",
            api_key_env="VOLC_ARK_API_KEY",
            supports_json_mode=True,
        ),
    }


# Default chain — ordered by quality + diversity (avoid all-cn-stack failure)
# Override via LLM_PROVIDER_CHAIN env var (comma-separated)
DEFAULT_CHAIN_ORDER = [
    "anthropic",   # 顶级质量, 优先
    "deepseek",    # 性价比之王, 128k context
    "glm",         # 智谱, 国内稳, 128k
    "tongyi",      # 阿里通义千问-max
    "moonshot",    # 月之暗面 128k
    "mistral",     # 海外多样性, EU
    "groq",        # 超快推理 (Llama 3.3)
    "xai",         # Grok-3
    "spark",       # 讯飞星火, 国内异源后备
    "doubao",      # 火山方舟 Doubao-Seed
    "openai",      # GPT-4o-mini 兜底
]


def build_provider_chain() -> list[LLMProvider]:
    catalog = _all_providers()
    chain_env = os.environ.get("LLM_PROVIDER_CHAIN", "").strip()
    names = ([n.strip() for n in chain_env.split(",") if n.strip()]
             if chain_env else DEFAULT_CHAIN_ORDER)
    return [catalog[n] for n in names if n in catalog]


def llm_complete_with_fallback(
    *,
    system: str,
    user: str,
    json_mode: bool = False,
    max_tokens: int = 2000,
    temperature: float = 0.5,
    chain_override: list[str] | None = None,
) -> tuple[Optional[str], Optional[str]]:
    """Try each provider; return (text, provider_name) on first success.

    Returns (None, None) only when all providers fail or no keys configured.
    """
    if os.environ.get("FORCE_MOCK_LLM_CHAIN") == "1":
        # Test hook — deterministic fake provider response
        return f"[MOCK_LLM_CHAIN] sys={system[:30]}... usr={user[:60]}...", "mock"

    if chain_override:
        catalog = _all_providers()
        chain = [catalog[n] for n in chain_override if n in catalog]
    else:
        chain = build_provider_chain()

    available = [p for p in chain if p.is_available()]
    if not available:
        record_health("__SYSTEM__", "AUTH_FAILED", -1,
                      "no LLM providers have API keys configured", notify=True)
        return None, None

    _log.info("[llm-chain] %d providers available: %s",
              len(available), ", ".join(p.name for p in available))

    req = LLMRequest(system=system, user=user, json_mode=json_mode,
                     max_tokens=max_tokens, temperature=temperature)
    for p in available:
        try:
            out = p.complete(req)
            if out and isinstance(out, str) and out.strip():
                _log.info("[llm-success] %s returned %d chars",
                          p.name, len(out))
                return out.strip(), p.name
        except Exception as e:  # noqa: BLE001
            status, code = _classify_err(e)
            record_health(p.name, status, code, str(e), notify=False)
    return None, None


# Convenience helper — same call signature as the old anthropic/deepseek
# raw functions used in shell1 modules.
def chat(system: str, user: str, *, json_mode: bool = False,
         max_tokens: int = 2000, temperature: float = 0.5) -> str:
    """Synchronous text completion through the full provider chain.

    Raises RuntimeError only if all providers fail (so callers can fall back
    to a mock generator themselves).
    """
    text, provider = llm_complete_with_fallback(
        system=system, user=user, json_mode=json_mode,
        max_tokens=max_tokens, temperature=temperature,
    )
    if text is None:
        raise RuntimeError(
            "All LLM providers failed. Check data/api_health.log; "
            "set FORCE_MOCK_THEME=1 (or similar) to use deterministic mock."
        )
    return text


__all__ = [
    "LLMProvider",
    "LLMRequest",
    "OpenAICompatProvider",
    "ClaudeProvider",
    "SparkProvider",
    "build_provider_chain",
    "llm_complete_with_fallback",
    "chat",
    "record_health",
    "DEFAULT_CHAIN_ORDER",
]
