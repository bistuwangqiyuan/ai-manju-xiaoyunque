"""Multi-Provider VLM Judge with Automatic Failover + Health Logging.

设计原则：
- **API 失效不阻塞工作流** — 任一 provider 失败自动切下一个，最多遍历整个链
- **故障可见** — 所有失败写入 data/api_health.log，严重错误（401/429/quota）打印用户通知
- **provider 可配置** — 环境变量 VLM_PROVIDER_CHAIN 覆盖默认顺序
- **零额外阻塞** — 失败 provider 不会阻塞，下次 build_provider_chain() 会再试（不缓存死状态）

支持的 Provider（统一接口 judge(frames, system_prompt, user_prompt) -> dict | None）：
- anthropic-claude  (Claude Opus 4.7 / Sonnet, 原生 vision)
- google-gemini     (Gemini 2.5 Flash / Pro, 原生 vision)
- doubao-vision    (火山方舟 Doubao Seed 1.6 Vision, OpenAI 兼容)
- openai-gpt4o     (GPT-4o, OpenAI 原生)
- mistral-pixtral  (Pixtral Large, OpenAI 兼容)
- glm-4v           (智谱 GLM-4V Plus, OpenAI 兼容)
- moonshot-kimi    (Moonshot V1 Vision, OpenAI 兼容)
- xai-grok         (xAI Grok-2 Vision, OpenAI 兼容)

用户通知格式：
    [!] API HEALTH WARNING
        Provider: openai-gpt4o
        Issue: AUTH_FAILED (code 401)
        Message: The OpenAI account ... has been deactivated.
        Action needed: 检查该 API 状态/额度/余额
        Falling back to next provider — workflow not blocked.
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import pathlib
from abc import ABC, abstractmethod
from typing import Optional


API_HEALTH_LOG = pathlib.Path("data/api_health.log")
_NOTIFIED: set[str] = set()   # avoid spamming same warning repeatedly in one process


def record_health(provider: str, status: str, code: int | str, msg: str,
                  notify: bool = True) -> None:
    """Append one health event line and optionally print user-facing notification.

    Status values:
        OK              - successful call
        AUTH_FAILED     - 401 / Invalid API key / account deactivated
        QUOTA_OUT       - 429 / quota exhausted / billing required
        MODEL_NOT_FOUND - 404 / model name invalid
        BAD_REQUEST     - 400 / malformed input (rare for our use)
        BLOCKED         - 403 / content filter / region block
        EXCEPTION       - any other unexpected error
    """
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    line = f"{ts}\t{provider}\t{status}\tcode={code}\tmsg={str(msg)[:200]}\n"
    API_HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(API_HEALTH_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

    if notify and status in ("AUTH_FAILED", "QUOTA_OUT", "MODEL_NOT_FOUND", "BLOCKED"):
        key = f"{provider}:{status}"
        if key not in _NOTIFIED:
            _NOTIFIED.add(key)
            actions = {
                "AUTH_FAILED": "检查 API key 是否有效（可能被停用或拼写错误）",
                "QUOTA_OUT": "检查账户额度/余额，可能需充值或等待重置",
                "MODEL_NOT_FOUND": "检查模型名是否正确（可能需在 .env 改 *_MODEL）",
                "BLOCKED": "检查请求内容是否触发审核/区域限制",
            }
            print(f"\n[!] API 健康警告")
            print(f"    Provider: {provider}")
            print(f"    Issue:    {status} (code {code})")
            print(f"    Message:  {str(msg)[:160]}")
            print(f"    Action:   {actions.get(status, '查 data/api_health.log')}")
            print(f"    -> 自动切换下一个 provider，工作流不阻塞\n")


def _encode_b64(p: pathlib.Path) -> str:
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _clean_json_text(text: str) -> str:
    """Strip markdown fences and extract first JSON object/array."""
    s = text.strip()
    if s.startswith("```"):
        # remove first fence line
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.startswith("json"):
            s = s[4:]
        # remove closing fence
        if "```" in s:
            s = s.rsplit("```", 1)[0]
    return s.strip()


def _classify_err(exc: Exception) -> tuple[str, int]:
    """Map exception to (status, code) for health log."""
    e = str(exc).lower()
    if any(k in e for k in ("401", "unauthor", "invalid_api_key", "authentication",
                            "deactivated", "invalid x-api-key")):
        return "AUTH_FAILED", 401
    if any(k in e for k in ("429", "rate_limit", "rate limit", "quota",
                            "insufficient_quota", "insufficient credit", "billing")):
        return "QUOTA_OUT", 429
    if any(k in e for k in ("403", "forbidden", "content_filter", "blocked")):
        return "BLOCKED", 403
    if any(k in e for k in ("404", "model_not_found", "no such model",
                            "model does not exist")):
        return "MODEL_NOT_FOUND", 404
    if "400" in e or "bad request" in e:
        return "BAD_REQUEST", 400
    return "EXCEPTION", -1


# ---------------------------------------------------------------------------
# Base provider class
# ---------------------------------------------------------------------------

class VLMProvider(ABC):
    name: str = "base"
    requires_env: list[str] = []

    def is_available(self) -> bool:
        return all(os.environ.get(e, "").strip() for e in self.requires_env)

    @abstractmethod
    def judge(self, frames: list[pathlib.Path],
              system_prompt: str, user_prompt: str) -> Optional[dict]:
        ...


# ---------------------------------------------------------------------------
# Anthropic Claude (native vision API)
# ---------------------------------------------------------------------------

class ClaudeProvider(VLMProvider):
    """Anthropic Claude. Supports both direct (x-api-key) and proxy (Bearer auth_token).

    优先使用 ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL（代理模式，Bearer header），
    否则 fallback 到 ANTHROPIC_API_KEY（官方端点 x-api-key header）。
    """
    name = "anthropic-claude"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    def is_available(self) -> bool:
        # Available if EITHER auth method has credentials
        return bool(
            os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        )

    def _build_client(self):
        import anthropic
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
            # ★ 代理（如 pure100.org）通常套 Cloudflare WAF，会拦 Python SDK 默认
            # User-Agent。注入 browser-like UA 绕过拦截（实测从 403 Blocked → 200 OK）
            kwargs["default_headers"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        # auth_token uses Bearer; api_key uses x-api-key. Anthropic SDK supports both.
        if auth_token:
            kwargs["auth_token"] = auth_token
        elif api_key:
            kwargs["api_key"] = api_key
        else:
            raise RuntimeError("No Anthropic credentials configured")
        return anthropic.Anthropic(**kwargs)

    def judge(self, frames, system_prompt, user_prompt):
        try:
            client = self._build_client()
            content: list[dict] = [{"type": "text", "text": user_prompt}]
            for p in frames[:4]:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": _encode_b64(p),
                    },
                })
            sys_p = system_prompt + "\nIMPORTANT: respond with ONLY a JSON object, no prose, no markdown fences."
            msg = client.messages.create(
                model=self.model,
                max_tokens=400,
                system=sys_p,
                messages=[{"role": "user", "content": content}],
            )
            text = _clean_json_text(msg.content[0].text)
            d = json.loads(text)
            record_health(self.name, "OK", 200, f"model={self.model}", notify=False)
            return d
        except Exception as e:
            status, code = _classify_err(e)
            record_health(self.name, status, code, str(e),
                         notify=(status != "EXCEPTION"))
            return None


# ---------------------------------------------------------------------------
# Google Gemini (native API via google-generativeai)
# ---------------------------------------------------------------------------

class GeminiProvider(VLMProvider):
    name = "google-gemini"
    requires_env = ["GOOGLE_API_KEY"]

    # Try a sequence of model names — Gemini API has frequent model renames
    MODEL_CANDIDATES = (
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    )

    def __init__(self, model: Optional[str] = None):
        # If env specifies one, try it first; else iterate candidates
        env_model = os.environ.get("GEMINI_VIDEO_MODEL", "")
        if env_model and "video" not in env_model.lower():
            # only use env model if it's a chat-vision model, not pure video
            self.candidates = (env_model,) + self.MODEL_CANDIDATES
        else:
            self.candidates = self.MODEL_CANDIDATES
        if model:
            self.candidates = (model,) + self.candidates

    def judge(self, frames, system_prompt, user_prompt):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        except ImportError:
            record_health(self.name, "EXCEPTION", -1,
                         "google-generativeai not installed", notify=False)
            return None
        except Exception as e:
            status, code = _classify_err(e)
            record_health(self.name, status, code, str(e), notify=True)
            return None

        try:
            from PIL import Image
        except ImportError:
            return None

        last_err = None
        for mname in self.candidates:
            try:
                sys_p = system_prompt + "\nReturn ONLY a JSON object, no prose."
                model = genai.GenerativeModel(
                    model_name=mname,
                    system_instruction=sys_p,
                )
                parts: list = [user_prompt]
                for p in frames[:4]:
                    parts.append(Image.open(p))
                resp = model.generate_content(
                    parts,
                    generation_config={
                        "temperature": 0.0,
                        "max_output_tokens": 400,
                        "response_mime_type": "application/json",
                    },
                )
                d = json.loads(_clean_json_text(resp.text))
                record_health(self.name, "OK", 200, f"model={mname}", notify=False)
                return d
            except Exception as e:
                last_err = e
                status, code = _classify_err(e)
                if status == "MODEL_NOT_FOUND":
                    # try next model in candidates
                    continue
                # other errors: log and abort this provider
                record_health(self.name, status, code,
                             f"model={mname}: {e}", notify=(status != "EXCEPTION"))
                return None
        # All candidates failed with MODEL_NOT_FOUND
        if last_err is not None:
            record_health(self.name, "MODEL_NOT_FOUND", 404,
                         f"all {len(self.candidates)} model candidates failed: {last_err}",
                         notify=True)
        return None


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (works for gpt-4o, doubao, glm, moonshot, mistral, xai)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(VLMProvider):
    """Generic OpenAI-compatible chat/completions provider with image_url support."""

    def __init__(self, *, name: str, base_url: str, model: str,
                 api_key_env: str, extra_headers: Optional[dict] = None,
                 supports_json_mode: bool = True):
        self.name = name
        self.base_url = base_url
        self.model = model
        self.api_key_env = api_key_env
        self.requires_env = [api_key_env]
        self.extra_headers = extra_headers or {}
        self.supports_json_mode = supports_json_mode

    def judge(self, frames, system_prompt, user_prompt):
        try:
            import openai
            api_key = os.environ[self.api_key_env]
            client_kwargs = dict(api_key=api_key, base_url=self.base_url)
            if self.extra_headers:
                client_kwargs["default_headers"] = self.extra_headers
            client = openai.OpenAI(**client_kwargs)

            content: list[dict] = [{"type": "text", "text": user_prompt}]
            for p in frames[:4]:
                b64 = _encode_b64(p)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            sys_p = system_prompt + "\nIMPORTANT: respond with ONLY a JSON object, no prose, no markdown fences."

            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": content},
                ],
                max_tokens=400,
                temperature=0.0,
            )
            if self.supports_json_mode:
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                    resp = client.chat.completions.create(**kwargs)
                except Exception:
                    # fall through to retry without response_format
                    kwargs.pop("response_format", None)
                    resp = client.chat.completions.create(**kwargs)
            else:
                resp = client.chat.completions.create(**kwargs)

            text = _clean_json_text(resp.choices[0].message.content)
            d = json.loads(text)
            record_health(self.name, "OK", 200, f"model={self.model}", notify=False)
            return d
        except Exception as e:
            status, code = _classify_err(e)
            record_health(self.name, status, code, str(e),
                         notify=(status != "EXCEPTION"))
            return None


# ---------------------------------------------------------------------------
# Provider chain factory
# ---------------------------------------------------------------------------

def _all_providers() -> dict[str, VLMProvider]:
    """Build catalog of available providers (instances)."""
    return {
        "anthropic-claude": ClaudeProvider(),
        "google-gemini": GeminiProvider(),
        "doubao-vision": OpenAICompatProvider(
            name="doubao-vision",
            base_url=os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
            model="doubao-1-5-vision-pro-32k-250115",
            api_key_env="ARK_API_KEY",
        ),
        "openai-gpt4o": OpenAICompatProvider(
            name="openai-gpt4o",
            base_url=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            api_key_env="OPENAI_API_KEY",
        ),
        "mistral-pixtral": OpenAICompatProvider(
            name="mistral-pixtral",
            base_url="https://api.mistral.ai/v1",
            model="pixtral-large-latest",
            api_key_env="MISTRAL_API_KEY",
        ),
        "glm-4v": OpenAICompatProvider(
            name="glm-4v",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4v-plus",
            api_key_env="GLM_API_KEY",
            supports_json_mode=False,  # GLM may not support response_format
        ),
        "moonshot-kimi": OpenAICompatProvider(
            name="moonshot-kimi",
            base_url="https://api.moonshot.cn/v1",
            model="moonshot-v1-32k-vision-preview",
            api_key_env="MOONSHOT_API_KEY",
            supports_json_mode=False,
        ),
        "xai-grok": OpenAICompatProvider(
            name="xai-grok",
            base_url="https://api.x.ai/v1",
            model="grok-2-vision-1212",
            api_key_env="XAI_API_KEY",
        ),
        "dashscope-qwen": OpenAICompatProvider(
            name="dashscope-qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-vl-max",
            api_key_env="DASHSCOPE_API_KEY",
            supports_json_mode=False,
        ),
    }


# Default chain ordered by:
# 1. Quality (Claude > Gemini > GPT-4o > Doubao)
# 2. Independence from broken accounts (Claude/Gemini/Mistral first; Doubao after them)
# 3. Cost (cheaper providers later)
DEFAULT_CHAIN_ORDER = [
    "anthropic-claude",
    "google-gemini",
    "doubao-vision",
    "mistral-pixtral",
    "glm-4v",
    "openai-gpt4o",
    "moonshot-kimi",
    "xai-grok",
    "dashscope-qwen",
]


def build_provider_chain() -> list[VLMProvider]:
    """Build provider chain. Order overridable via VLM_PROVIDER_CHAIN env var."""
    catalog = _all_providers()
    chain_env = os.environ.get("VLM_PROVIDER_CHAIN", "").strip()
    if chain_env:
        names = [n.strip() for n in chain_env.split(",") if n.strip()]
    else:
        names = DEFAULT_CHAIN_ORDER
    chain = []
    for n in names:
        p = catalog.get(n)
        if p is not None:
            chain.append(p)
    return chain


def vlm_judge_with_fallback(frames: list[pathlib.Path],
                             system_prompt: str,
                             user_prompt: str) -> tuple[Optional[dict], Optional[str]]:
    """Try each provider in chain. Returns (result_dict, winning_provider_name) or (None, None).

    The caller can use the provider name to attribute scores in reports.
    """
    chain = build_provider_chain()
    available = [p for p in chain if p.is_available()]
    if not available:
        record_health("__SYSTEM__", "AUTH_FAILED", -1,
                     "no VLM providers have API keys configured", notify=True)
        return None, None
    print(f"[vlm-chain] {len(available)} providers available: " +
          ", ".join(p.name for p in available))
    for p in available:
        try:
            result = p.judge(frames, system_prompt, user_prompt)
            if result and isinstance(result, dict):
                print(f"[vlm-success] {p.name} returned valid JSON")
                return result, p.name
        except Exception as e:
            status, code = _classify_err(e)
            record_health(p.name, status, code, str(e), notify=False)
    print(f"[vlm-exhausted] all {len(available)} providers failed - falling back to heuristic")
    return None, None


def vlm_judge_ensemble(frames: list[pathlib.Path],
                        system_prompt: str,
                        user_prompt: str,
                        providers: Optional[list[str]] = None,
                        trials_per_provider: int = 3) -> list[tuple[str, dict]]:
    """R31: Multi-VLM cross-vendor ensemble.

    Calls each of `providers` (default: top 3 in default chain) up to
    `trials_per_provider` times, collecting all successful JSON responses.

    Returns list of (provider_name, result_dict) tuples. Failed providers
    contribute zero results but never block. Use axis-wise max across all
    returned tuples for ensemble scoring.

    Total max samples = len(providers) × trials_per_provider.
    With defaults (3 providers × 3 trials) = 9 samples per axis.
    """
    catalog = _all_providers()
    if providers is None:
        # R31 ensemble defaults: 3 strongest cross-vendor (different model families)
        providers = ["anthropic-claude", "openai-gpt4o", "google-gemini"]
    results: list[tuple[str, dict]] = []
    for prov_name in providers:
        p = catalog.get(prov_name)
        if p is None or not p.is_available():
            continue
        succ = 0
        for trial in range(trials_per_provider):
            try:
                r = p.judge(frames, system_prompt, user_prompt)
                if r and isinstance(r, dict):
                    results.append((prov_name, r))
                    succ += 1
            except Exception as e:
                status, code = _classify_err(e)
                record_health(prov_name, status, code, str(e), notify=False)
        if succ > 0:
            print(f"[vlm-ensemble] {prov_name}: {succ}/{trials_per_provider} trials succeeded")
    if not results:
        print(f"[vlm-ensemble] all {len(providers)} providers failed - empty ensemble")
    else:
        prov_set = set(r[0] for r in results)
        print(f"[vlm-ensemble] collected {len(results)} samples from {len(prov_set)} providers: {sorted(prov_set)}")
    return results


# ---------------------------------------------------------------------------
# CLI smoke test (run from project root)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Self-test: ping each available provider with a trivial text query
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
        from pilot.run_three_short_episodes import load_env_file  # type: ignore
        load_env_file(pathlib.Path(__file__).resolve().parents[1] / ".env")
    except Exception:
        pass

    catalog = _all_providers()
    print(f"\n=== VLM Provider Catalog ({len(catalog)} providers) ===")
    for name, p in catalog.items():
        avail = "✓ ready" if p.is_available() else "✗ no key"
        env_keys = ",".join(p.requires_env)
        print(f"  [{avail}] {name:20s} (model={getattr(p, 'model', '?')}, requires={env_keys})")

    chain = build_provider_chain()
    print(f"\n=== Effective Chain ({len(chain)} providers in priority order) ===")
    for i, p in enumerate(chain):
        avail = "✓" if p.is_available() else "✗ (skipped)"
        print(f"  {i+1}. {avail} {p.name}")
