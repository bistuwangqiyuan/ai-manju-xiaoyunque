# 小云雀 · 后端 API

FastAPI + SQLAlchemy + 单进程 worker。MVP 设计为单容器跑 web + worker，并发上去之后把 worker 拆出来即可（`python -m app.worker_only` 模式后面再加）。

## 本地开发

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000/docs 看自动生成的 OpenAPI 文档。

## 接口约定

所有业务接口都在 `/api/*` 路径下：

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/signup` | 邮箱+密码注册，返回 token |
| `POST` | `/api/auth/login` | 登录，返回 token |
| `GET` | `/api/auth/me` | 当前用户信息 |
| `GET` | `/api/jobs` | 我的任务列表 |
| `POST` | `/api/jobs` | 创建渲染任务（扣额度） |
| `GET` | `/api/jobs/{id}` | 任务详情 |
| `GET` | `/api/jobs/{id}/logs` | 任务日志 |
| `POST` | `/api/jobs/{id}/cancel` | 取消任务（按剩余比例退款） |
| `POST` | `/api/billing/checkout` | 创建 Stripe Checkout 会话 |
| `POST` | `/api/billing/topup` | 开发用直接加额度（仅 mock 计费模式） |
| `POST` | `/api/billing/webhook` | Stripe Webhook |
| `GET` | `/api/health` | 健康检查（Railway probe 用） |

## Mock 模式 vs 真实模式

| 子系统 | Mock 触发条件 | 行为 |
|---|---|---|
| Worker | `VOLC_ACCESS_KEY` 或 `ANTHROPIC_API_KEY` 为空 | 模拟 5 壳流水线，返回示例视频 |
| Billing | `STRIPE_SECRET_KEY` 为空 | `/checkout` 直接给账户加额度并跳 success 页 |

接真实流水线时改 `backend/app/worker.py` 中的 `_run_real_pipeline()`，把 `src/shell1_*` 系列调用串起来。

## 部署

见根目录 [DEPLOY.md](../DEPLOY.md)。
