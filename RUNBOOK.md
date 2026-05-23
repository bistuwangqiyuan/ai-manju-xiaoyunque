# RUNBOOK — AI 漫剧 v8 一键部署

> Target audience: deployment operator who has never seen this repo.
> Time to live SaaS: **≤ 15 minutes** after API keys are in hand.
> Reference: [docs/api-contracts-2026-05.md](docs/api-contracts-2026-05.md) — full API contract.

---

## 0. Pre-flight (5 min, once)

You need accounts on these platforms. All have free tiers sufficient to bring the SaaS up; only Volcengine + Anthropic are pay-as-you-go for production traffic.

| Tier | Provider | URL | Cost |
|---|---|---|---|
| Hosting (backend + worker + Postgres) | **Railway** | <https://railway.app> | Free trial → $5/mo |
| Hosting (Next.js web) | **Vercel** | <https://vercel.com> | Free Hobby tier |
| Git host | **GitHub** | <https://github.com> | Free |
| AIGC core engine | **Volcengine** | <https://www.volcengine.com> | ¥0.36/秒 视频 |
| 主笔 LLM | **Anthropic** | <https://console.anthropic.com> | $25/M tokens |
| 事件抽取 LLM | **DeepSeek** | <https://platform.deepseek.com> | $1.74/M tokens |
| 海外 TTS / BGM / SFX | **ElevenLabs** | <https://elevenlabs.io> | $5/mo |
| 修复 / 编辑 | **fal.ai** | <https://fal.ai> | pay-per-call |
| 多角色锁 | **Replicate** | <https://replicate.com> | pay-per-call |

The **8 required API keys** are:

```text
VOLC_ACCESS_KEY        # 火山引擎 IAM AK
VOLC_SECRET_KEY        # 火山引擎 IAM SK
ANTHROPIC_API_KEY      # Claude Opus 4.7 主笔
DEEPSEEK_API_KEY       # DeepSeek V4-Pro 事件抽取
DOUBAO_API_KEY         # Doubao Seed 1.6 Vision 7-dim 质检
DOUBAO_TTS_APPID       # Doubao Seed-TTS 2.0 ICL 主路配音
DOUBAO_TTS_TOKEN
ELEVENLABS_API_KEY     # ElevenLabs Music + SFX + Multilingual TTS
FAL_API_KEY            # FLUX Kontext + InfiniteYou + Wan FLF
REPLICATE_API_TOKEN    # PuLID 多角色锁
```

Everything else is optional and gracefully degrades to mock mode at runtime.

---

## 1. Fork + push to GitHub (2 min)

```bash
# already done if you cloned
git clone https://github.com/<your>/ai-manju-xiaoyunque.git
cd ai-manju-xiaoyunque
git remote -v
```

Push to a repo you own. The deploy workflow needs a `main` branch.

---

## 2. Deploy backend on Railway (5 min)

1. Open Railway → **New Project** → **Deploy from GitHub repo** → pick your fork.
2. Railway auto-detects `backend/Dockerfile` via `railway.toml`. Wait for the first build to finish (~3 min).
3. Add a **Postgres** plugin: project → +New → Database → PostgreSQL.
   Railway auto-injects `DATABASE_URL` into the backend service.
4. Add a **Variables** group with the 8 required keys + this:

   ```text
   JWT_SECRET=<paste-32-char-random-string>
   CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
   SITE_URL=https://<your-vercel-domain>.vercel.app
   MOCK_MODE=0
   USE_REAL_COVER=1
   USE_REAL_UPSCALER=0      # set to 1 once GOOGLE_ACCESS_TOKEN is provided
   ```

5. Railway auto-redeploys. Once green, copy the public URL — call it `BACKEND_URL`.

---

## 3. Deploy frontend on Vercel (3 min)

1. Vercel → **Add New… → Project** → import the same GitHub repo.
2. **Root Directory** = `web`. Framework preset = Next.js.
3. **Environment Variables** (Production + Preview + Development):

   ```text
   NEXT_PUBLIC_BACKEND_URL=<paste BACKEND_URL from step 2>
   NEXT_PUBLIC_DEFAULT_LOCALE=zh-CN
   ```

4. Deploy. Once green, open the production URL — sign up, you should land on `/dashboard`.

---

## 4. Post-deploy smoke (1 min)

```bash
# from your laptop, against the live backend
python scripts/env_check.py                                  # MOCK_MODE check
python scripts/deploy_smoke.py --backend-url $BACKEND_URL    # end-to-end
```

Expected output:

```
→ smoke against https://....up.railway.app
  ✅ /api/health ok
  ✅ signup ok (smoke+xxx@xiaoyunque.test)
  ✅ job created (id=N)
  ✅ job succeeded (score=85)
  ✅ versions endpoint returns 1 entry/entries
  ✅ marketing endpoint ok (5 hashtags)
PASS — deploy_smoke completed successfully.
```

---

## 5. Auto-deploy on push (already configured)

Push to `main` triggers `.github/workflows/deploy.yml`:

1. Run CI tests (≥ 41 pytest cases, frontend typecheck + build).
2. `railway up` deploys the backend (needs `RAILWAY_TOKEN` repo secret).
3. `vercel deploy --prod` deploys the frontend (needs `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` repo secrets).
4. Post-deploy smoke runs `scripts/deploy_smoke.py` against the live URL.

To enable, add these GitHub repo secrets (Settings → Secrets and variables → Actions):

| Secret | Where to get |
|---|---|
| `RAILWAY_TOKEN` | Railway → Account → Tokens |
| `VERCEL_TOKEN` | Vercel → Account → Tokens |
| `VERCEL_ORG_ID` | Vercel → Project Settings → General → IDs |
| `VERCEL_PROJECT_ID` | same as above |
| `BACKEND_URL` | output of step 2 |

---

## 6. Going to production (after smoke green)

Promote from mock-mode → real-mode by toggling these in Railway:

```text
MOCK_MODE=0
FORCE_MOCK_SCORER=0
FORCE_MOCK_THEME=0
FORCE_MOCK_NOVELTY=0
FORCE_MOCK_MARKETING=0
FORCE_MOCK_TRANSLATE=0
FORCE_MOCK_WAN_ANIMATE=0     # only if DASHSCOPE_API_KEY is set
FORCE_MOCK_TTS_MINIMAX=0     # only if MINIMAX_API_KEY is set
USE_REAL_COVER=1
USE_REAL_UPSCALER=1          # only if GOOGLE_ACCESS_TOKEN is set
```

Then re-run `deploy_smoke.py` to confirm.

---

## 7. Optional: enable advanced AIGC compliance

For PRC distribution (抖音 / 红果 / B 站) the 2026 广电新规 requires
SynthID + C2PA + 备案. v8 already emits a C2PA sidecar JSON next to every
`master.mp4`, plus an auto-filled filing template under `data/filing/<job_id>/`.

To embed a full JUMBF C2PA block (instead of sidecar JSON):

```bash
# inside the Railway container or local dev:
sudo apt install c2patool                # https://github.com/contentauth/c2patool
railway variables set USE_C2PATOOL=1
```

---

## 8. Rollback

If a bad deploy lands in production:

```bash
# Railway: redeploy a prior successful build
railway up --service backend --version <prev_release_id>

# Vercel: instant rollback
vercel rollback <deployment-url>
```

Postgres data is preserved (separate plugin), so rolling back the app
container is safe.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/api/health` 502 on Railway | first build still running | wait 90s |
| `signup 422 email` | seeded a user already | use a fresh `email=` |
| job stuck `running` 5+ min in real mode | Skylark queue / out of quota | check Volcengine 控制台 |
| `deploy_smoke` fails with `429` | Skylark hit per-minute quota | back off, retry |
| `tsc --noEmit` fails on push | new linker dep added | `cd web && npm install && npx tsc --noEmit` locally |
| Postgres can't connect | `DATABASE_URL` missing `?sslmode=require` | append it (Railway default) |

---

## 10. What's where

| Concern | File / path |
|---|---|
| 6-step pipeline | `src/pipeline/orchestrator_v2.py` |
| Skylark Agent 2.0 client | `src/shell3_skylark_engine/client.py` |
| 7-dim QA + auto-repair | `src/shell4_qa_repair/` |
| TTS / BGM / SFX / 字幕 / 封面 | `src/shell5_post_production/` |
| 多平台导出 + 营销文案 | `src/shell5_post_production/platform_export.py`, `marketing_copy.py` |
| AIGC C2PA sidecar | `src/shell5_post_production/aigc_sidecar.py` (Gap C-8) |
| 广电备案 auto-fill | `src/compliance/filing_autogen.py` (Gap C-9) |
| Wan-Animate 武打 | `src/shell3_skylark_engine/wan_animate.py` (Gap C-1) |
| MiniMax 高情感 TTS | `src/shell5_post_production/tts_minimax.py` (Gap C-7) |
| Backend API | `backend/app/main.py` + `routes/` |
| Frontend Studio | `web/app/dashboard/` |
| Mock-mode test suite (41 tests) | `tests/` |
| API contracts source-of-truth | `docs/api-contracts-2026-05.md` |
| Release checklist | `RELEASE_CHECKLIST.md` |

The user's only remaining work after a fresh repo fork is **three clicks**:

1. Railway → import GitHub repo.
2. Vercel → import GitHub repo, set Root = `web`, paste `NEXT_PUBLIC_BACKEND_URL`.
3. Railway → variables → paste 8 keys → redeploy.

That's it. Total time ≤ 15 min, zero code.
