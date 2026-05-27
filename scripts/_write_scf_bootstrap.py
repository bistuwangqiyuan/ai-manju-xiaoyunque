from pathlib import Path
import sys

minimal = "--minimal" in sys.argv
app_module = "app_minimal:app" if minimal else "app.main:app"
content = (
    "#!/bin/bash\n"
    "export PYTHONPATH=\"./third_party:$(pwd):$PYTHONPATH\"\n"
    "export MOCK_MODE=1\n"
    "export EMBEDDED_WORKER=1\n"
    "export DATABASE_URL=sqlite:////tmp/xyq.db\n"
    "export STORAGE_DIR=/tmp/storage\n"
    "export CORS_ORIGINS=*\n"
    f"exec /var/lang/python39/bin/python3.9 -m uvicorn {app_module} --host 0.0.0.0 --port 9000\n"
)
path = Path(__file__).resolve().parents[1] / "cloudfunctions" / "xyq-api" / "scf_bootstrap"
path.write_bytes(content.encode("utf-8"))
print("wrote", path, "bytes", path.stat().st_size, "minimal=", minimal)

