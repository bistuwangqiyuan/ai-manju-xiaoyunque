"""Contract tests for `src.common.tos_storage.TosStorage`.

We do *not* hit the real TOS endpoint here. Instead we:
  - Verify TosConfig.from_env() resolves keys across all aliases.
  - Stub out boto3's S3 client and assert TosStorage maps the calls correctly.
  - Verify integration with src.common.storage.default_storage() backend
    auto-detection.

Run::

    pytest -q tests/test_tos_storage.py
"""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


# ---------------------------------------------------------------------------
# Stub boto3 + botocore so we don't require them installed for tests
# ---------------------------------------------------------------------------

class _FakeS3Client:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.objects: dict[str, bytes] = {}

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {"ETag": '"deadbeef"'}

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        body = self.objects.get(kwargs["Key"], b"")
        return {"Body": types.SimpleNamespace(read=lambda: body)}

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {"ContentLength": len(self.objects.get(kwargs["Key"], b""))}

    def list_objects_v2(self, **kwargs):
        self.calls.append(("list_objects_v2", kwargs))
        prefix = kwargs.get("Prefix", "")
        return {"Contents": [{"Key": k, "Size": len(v)}
                             for k, v in self.objects.items()
                             if k.startswith(prefix)]}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        self.objects.pop(kwargs["Key"], None)
        return {}

    def generate_presigned_url(self, action, Params, ExpiresIn=3600):
        self.calls.append(("presign", {"action": action, "params": Params,
                                       "ttl": ExpiresIn}))
        return f"https://presigned.local/{Params['Bucket']}/{Params['Key']}?ttl={ExpiresIn}"


@pytest.fixture
def fake_boto3(monkeypatch):
    """Inject a fake boto3 + botocore into sys.modules before TosStorage imports."""
    fake_client = _FakeS3Client()

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda *a, **kw: fake_client  # type: ignore[attr-defined]

    fake_botocore = types.ModuleType("botocore")
    fake_botocore_config = types.ModuleType("botocore.config")

    class _BotoConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_botocore_config.Config = _BotoConfig

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", fake_botocore_config)

    # Reload tos_storage so it picks up the fakes
    import src.common.tos_storage as mod  # noqa: PLC0415
    importlib.reload(mod)
    yield fake_client


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Strip all TOS / S3 / VOLC env vars so each test starts from a clean slate."""

    for prefix in ("TOS_", "S3_", "VOLC_", "STORAGE_"):
        for k in list(__import__("os").environ.keys()):
            if k.startswith(prefix):
                monkeypatch.delenv(k, raising=False)
    yield


# ---------------------------------------------------------------------------
# TosConfig.from_env tests
# ---------------------------------------------------------------------------

def test_from_env_resolves_volc_aliases(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak-volc-1")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk-volc-1")
    monkeypatch.setenv("TOS_BUCKET", "xyq-prod")
    from src.common.tos_storage import TosConfig
    cfg = TosConfig.from_env()
    assert cfg.access_key == "ak-volc-1"
    assert cfg.secret_key == "sk-volc-1"
    assert cfg.bucket == "xyq-prod"
    assert cfg.region == "cn-beijing"
    assert cfg.endpoint.startswith("https://tos-cn-beijing")


def test_from_env_prefers_tos_specific_keys(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak-volc-1")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk-volc-1")
    monkeypatch.setenv("TOS_ACCESS_KEY", "ak-tos-2")
    monkeypatch.setenv("TOS_SECRET_KEY", "sk-tos-2")
    monkeypatch.setenv("TOS_BUCKET", "xyq")
    from src.common.tos_storage import TosConfig
    cfg = TosConfig.from_env()
    assert cfg.access_key == "ak-tos-2"
    assert cfg.secret_key == "sk-tos-2"


def test_from_env_raises_when_missing(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak-only")
    # no SK + no bucket
    from src.common.tos_storage import TosConfig
    with pytest.raises(RuntimeError, match="missing credentials"):
        TosConfig.from_env()


def test_from_env_normalises_endpoint(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "b")
    monkeypatch.setenv("TOS_ENDPOINT", "tos-cn-shanghai.volces.com")
    monkeypatch.setenv("TOS_REGION", "cn-shanghai")
    from src.common.tos_storage import TosConfig
    cfg = TosConfig.from_env()
    assert cfg.endpoint.startswith("https://tos-cn-shanghai")
    assert cfg.region == "cn-shanghai"


# ---------------------------------------------------------------------------
# TosStorage put / get round-trip via fake client
# ---------------------------------------------------------------------------

def test_put_bytes_calls_s3_put_object(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    from src.common.tos_storage import TosStorage
    store = TosStorage()
    obj = store.put_bytes("manju/episode_001.mp4", b"fakebytes")
    assert obj.path == "tos://bk/manju/episode_001.mp4"
    assert obj.size_bytes == len(b"fakebytes")
    assert obj.sha256 == __import__("hashlib").sha256(b"fakebytes").hexdigest()

    [last_call] = [c for c in fake_boto3.calls if c[0] == "put_object"]
    assert last_call[1]["Bucket"] == "bk"
    assert last_call[1]["Key"] == "manju/episode_001.mp4"
    assert last_call[1]["Body"] == b"fakebytes"


def test_put_file_reads_disk_and_uploads(tmp_path, monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    src = tmp_path / "a.mp4"
    src.write_bytes(b"hello world")

    from src.common.tos_storage import TosStorage
    store = TosStorage()
    obj = store.put_file("manju/a.mp4", src)
    assert obj.size_bytes == 11
    [put] = [c for c in fake_boto3.calls if c[0] == "put_object"]
    assert put[1]["Key"] == "manju/a.mp4"


def test_archive_url_downloads_and_reuploads(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")

    fake_response_bytes = b"x" * 8192

    class _FakeResp:
        def read(self):
            return fake_response_bytes
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=600):
        return _FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    from src.common.tos_storage import TosStorage
    store = TosStorage()
    obj = store.archive_url("manju/dl.mp4", "https://mock/dl.mp4")
    assert obj.size_bytes == 8192
    [put] = [c for c in fake_boto3.calls if c[0] == "put_object"]
    assert put[1]["Key"] == "manju/dl.mp4"


def test_list_prefix(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    from src.common.tos_storage import TosStorage
    store = TosStorage()
    store.put_bytes("a/1.txt", b"1")
    store.put_bytes("a/2.txt", b"2")
    store.put_bytes("b/3.txt", b"3")
    listing = store.list_prefix("a/")
    keys = {item["Key"] for item in listing}
    assert keys == {"a/1.txt", "a/2.txt"}


def test_public_url_uses_public_base_when_public(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    monkeypatch.setenv("TOS_PUBLIC_BASE", "https://cdn.example.com")
    from src.common.tos_storage import TosStorage
    store = TosStorage()
    obj = store.put_bytes("public/test.txt", b"hello", public=True)
    assert obj.public_url == "https://cdn.example.com/public/test.txt"


def test_public_url_is_presigned_when_private(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    from src.common.tos_storage import TosStorage
    store = TosStorage()
    obj = store.put_bytes("priv/x.bin", b"hello")
    assert obj.public_url and "presigned.local" in obj.public_url


# ---------------------------------------------------------------------------
# Default storage backend auto-detect
# ---------------------------------------------------------------------------

def test_default_storage_picks_tos_when_creds_present(monkeypatch, fake_boto3):
    monkeypatch.setenv("VOLC_ACCESS_KEY", "ak")
    monkeypatch.setenv("VOLC_SECRET_KEY", "sk")
    monkeypatch.setenv("TOS_BUCKET", "bk")
    # reload storage too so it sees our fake boto3 via tos_storage
    import src.common.storage as storage_mod
    importlib.reload(storage_mod)
    s = storage_mod.default_storage()
    assert getattr(s, "backend_name", "") == "tos"


def test_default_storage_picks_local_when_no_bucket(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    import src.common.storage as storage_mod
    importlib.reload(storage_mod)
    s = storage_mod.default_storage()
    assert getattr(s, "backend_name", "") == "local"
