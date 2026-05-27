from fastapi import FastAPI

app = FastAPI(title="xyq-api-minimal")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "xyq-api-minimal"}


@app.get("/api/gallery")
def gallery():
    return {"items": [], "official_samples": 4}
