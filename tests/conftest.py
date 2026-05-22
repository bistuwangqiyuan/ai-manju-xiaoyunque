"""Pytest config — add repo root to sys.path so `from src...` works everywhere."""
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Default to mock mode for all backends so tests never hit live APIs
os.environ.setdefault("FORCE_MOCK_SCORER", "1")
os.environ.setdefault("FORCE_MOCK_THEME", "1")
os.environ.setdefault("FORCE_MOCK_NOVELTY", "1")
os.environ.setdefault("FORCE_MOCK_MARKETING", "1")
os.environ.setdefault("FORCE_MOCK_CONTINUATION", "1")
os.environ.setdefault("FORCE_MOCK_RESTYLE", "1")
os.environ.setdefault("FORCE_MOCK_TRANSLATE", "1")
os.environ.setdefault("FORCE_MOCK_REDRAW", "1")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_REPO / 'data' / 'test.db'}")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STORAGE_DIR", str(_REPO / "data" / "test_storage"))
os.environ.setdefault("SKIP_CINEMATIC_MASTER", "1")
