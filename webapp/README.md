# webapp（已降级为演示版）

> **生产主站已迁移至 [`web/`](../web/)**，Vercel 根目录 `vercel.json` 指向 `web/`。

本目录保留最简 Skylark 单 prompt 试玩 API，仅供开发调试。对外 SaaS 请使用：

- 前端：`web/` → Vercel
- 后端：`backend/` → Railway
- 6 步工作流 + 质量闭环：见 `src/pipeline/orchestrator.py`
