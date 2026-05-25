"""Contract tests for ``deploy/cn-volc-vefaas/deploy.py``.

Goals (dry-run only — never hits real OpenAPI):
  - _is_placeholder correctly filters dummy values out of the env payload
  - DeployConfig.from_args_and_env resolves from CLI > env defaults
  - build_create_function_payload returns a fully-formed OpenAPI payload
  - VeApiClient.call(dry_run=True) does NOT make network requests
  - _sign_volc_v4 produces a stable ``Authorization`` header shape

Run::

    pytest -q tests/test_vefaas_deploy.py
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

_DEPLOY_PY = _REPO / "deploy" / "cn-volc-vefaas" / "deploy.py"


def _load_deploy_module():
    """Import deploy.py as a top-level module ``vefaas_deploy``.

    Python 3.14 dataclass / typing internals look up ``sys.modules[__module__]``
    when computing fields, so the module must be registered before exec.
    """
    name = "vefaas_deploy"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _DEPLOY_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


@pytest.fixture(scope="module")
def deploy_mod():
    if not _DEPLOY_PY.exists():
        pytest.skip(f"missing {_DEPLOY_PY}")
    return _load_deploy_module()


@pytest.fixture
def base_args():
    """Minimal args namespace matching what argparse would produce."""
    return argparse.Namespace(
        access_key=None, secret_key=None, region=None,
        app_name=None, image_repo=None, image_tag=None,
        cpu=None, memory_mb=None, timeout=None,
        config=None,
        apig_instance=None, apig_service=None, apig_upstream=None,
    )


# ---------------------------------------------------------------------------
# 1. _is_placeholder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("v,expected", [
    ("", True),
    ("abc", True),                          # too short
    ("<paste-rotated-AK>", True),
    ("<paste_secret>", True),
    ("REPLACE_ME_AT_DEPLOY", True),
    ("your-bucket-name", True),
    ("YOUR_VOLC_AK", True),
    ("xxxxxxx", True),
    ("placeholder", True),
    ("{{TEMPLATE}}", True),
    ("${VOLC_AK}", True),
    ("AKLTValidLookingAccessKey1234567890==", False),
    ("sk-1234567890abcdef", False),
    ("real-cluster-default-name", False),
])
def test_is_placeholder(deploy_mod, v, expected):
    assert deploy_mod._is_placeholder(v) is expected


# ---------------------------------------------------------------------------
# 2. DeployConfig.from_args_and_env
# ---------------------------------------------------------------------------

def test_from_args_and_env_uses_cli_first(monkeypatch, deploy_mod, base_args):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "env-ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "env-sk")
    base_args.access_key = "cli-ak"
    base_args.secret_key = "cli-sk"
    base_args.app_name = "xyq_under_score"     # underscores not allowed
    base_args.image_repo = "cr.example/xyq/x"
    base_args.image_tag = "v9.0.0"

    cfg = deploy_mod.DeployConfig.from_args_and_env(base_args)
    assert cfg.access_key == "cli-ak"          # CLI beats env
    assert cfg.secret_key == "cli-sk"
    assert cfg.app_name == "xyq-under-score"   # underscores replaced
    assert cfg.image_repo == "cr.example/xyq/x"
    assert cfg.image_tag == "v9.0.0"
    assert cfg.full_image == "cr.example/xyq/x:v9.0.0"


def test_from_args_and_env_raises_when_no_creds(monkeypatch, deploy_mod, base_args):
    for k in ("VOLC_ACCESS_KEY", "VOLC_SECRET_KEY", "VOLC_AK", "VOLC_SK"):
        monkeypatch.delenv(k, raising=False)
    # disable Windows registry path
    monkeypatch.setattr("os.name", "posix", raising=False)
    with pytest.raises(SystemExit, match="Missing VOLC_"):
        deploy_mod.DeployConfig.from_args_and_env(base_args)


def test_envs_default_to_tos_storage_and_shanghai_tz(monkeypatch, deploy_mod, base_args):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    # avoid registry path during test
    monkeypatch.setattr("os.name", "posix", raising=False)
    cfg = deploy_mod.DeployConfig.from_args_and_env(base_args)
    assert cfg.envs.get("STORAGE_BACKEND") == "tos"
    assert cfg.envs.get("TZ") == "Asia/Shanghai"
    assert cfg.envs.get("EMBEDDED_WORKER") == "1"


def test_placeholder_envs_are_filtered_out(monkeypatch, deploy_mod, base_args):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("DOUBAO_TTS_APPID", "<paste-numeric-AppID>")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-1234567890")
    monkeypatch.setattr("os.name", "posix", raising=False)
    cfg = deploy_mod.DeployConfig.from_args_and_env(base_args)
    assert "DOUBAO_TTS_APPID" not in cfg.envs
    assert cfg.envs.get("DEEPSEEK_API_KEY") == "sk-real-deepseek-1234567890"


# ---------------------------------------------------------------------------
# 3. build_create_function_payload
# ---------------------------------------------------------------------------

def test_build_create_function_payload_shape(deploy_mod):
    cfg = deploy_mod.DeployConfig(
        access_key="ak", secret_key="sk", region="cn-beijing",
        app_name="xyq-manju", image_repo="cr/x", image_tag="v9",
        envs={"VOLC_ACCESS_KEY": "ak", "STORAGE_BACKEND": "tos"},
        tos_mounts=[{"bucket": "xyq", "mount": "/mnt/tos"}],
        nas_mounts=[{"nas_id": "nas-1", "mount": "/mnt/nas"}],
    )
    payload = deploy_mod.build_create_function_payload(cfg)
    assert payload["Name"] == "xyq-manju"
    assert payload["Source"] == "cr/x:v9"
    assert payload["SourceType"] == "image"
    assert payload["Port"] == 8000
    assert payload["Command"] == "/app/run.sh"
    assert payload["Runtime"] == deploy_mod.DEFAULT_RUNTIME
    keys = {e["Key"] for e in payload["Envs"]}
    assert "VOLC_ACCESS_KEY" in keys
    assert payload["TosMountConfig"]["TosMountPoints"][0]["Bucket"] == "xyq"
    assert payload["NasStorage"]["NasConfigs"][0]["NasId"] == "nas-1"


def test_payload_omits_storage_blocks_when_empty(deploy_mod):
    cfg = deploy_mod.DeployConfig(
        access_key="ak", secret_key="sk", region="cn-beijing",
        app_name="xyq", image_repo="cr/x", image_tag="v9",
    )
    payload = deploy_mod.build_create_function_payload(cfg)
    # None values must NOT be in the cleaned payload (caller filters)
    cleaned = {k: v for k, v in payload.items() if v is not None}
    assert "NasStorage" not in cleaned
    assert "TosMountConfig" not in cleaned


# ---------------------------------------------------------------------------
# 4. VeApiClient.call dry-run does not network
# ---------------------------------------------------------------------------

def test_veapi_client_dry_run_no_network(monkeypatch, deploy_mod):
    def _no_net(*args, **kwargs):
        raise AssertionError("urlopen called during dry-run")

    monkeypatch.setattr("urllib.request.urlopen", _no_net)
    client = deploy_mod.VeApiClient(
        access_key="ak", secret_key="sk",
        region="cn-beijing", host="open.volcengineapi.com", dry_run=True,
    )
    resp = client.call(service="vefaas", action="CreateFunction",
                       version="2024-06-06", body={"Name": "xyq"})
    assert resp == {"_dry_run": True}


# ---------------------------------------------------------------------------
# 5. _sign_volc_v4 header shape
# ---------------------------------------------------------------------------

def test_sign_volc_v4_produces_required_headers(deploy_mod):
    headers = deploy_mod._sign_volc_v4(
        ak="AKLT-test-key", sk="sk-test-secret",
        service="vefaas", region="cn-beijing",
        host="open.volcengineapi.com",
        method="POST",
        query={"Action": "CreateFunction", "Version": "2024-06-06"},
        body=b'{"Name":"xyq"}',
    )
    for required in ("Host", "Content-Type", "X-Date",
                     "X-Content-Sha256", "Authorization"):
        assert required in headers, f"missing {required}"
    auth = headers["Authorization"]
    assert auth.startswith("HMAC-SHA256 Credential=AKLT-test-key/")
    assert "SignedHeaders=content-type;host;x-content-sha256;x-date" in auth
    assert "Signature=" in auth and len(auth.split("Signature=")[1]) == 64


def test_sign_volc_v4_body_hash_matches(deploy_mod):
    import hashlib
    body = b'{"hello":"world"}'
    headers = deploy_mod._sign_volc_v4(
        ak="ak", sk="sk", service="vefaas", region="cn-beijing",
        host="open.volcengineapi.com",
        method="POST",
        query={"Action": "X", "Version": "1"},
        body=body,
    )
    assert headers["X-Content-Sha256"] == hashlib.sha256(body).hexdigest()
