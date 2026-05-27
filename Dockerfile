FROM python:3.11-slim
RUN pip install --no-cache-dir fastapi uvicorn[standard] -i https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /app
RUN printf 'from fastapi import FastAPI\napp=FastAPI()\n@app.get(\"/api/health\")\ndef health(): return {\"status\":\"ok\"}\n@app.get(\"/\")\ndef root(): return {\"hello\":\"xyq\"}\n' > main.py
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
