# RELEASE_CHECKLIST — v8 green-light gate

> Tick every item before flipping `MOCK_MODE=0` in production.
> Last verified: 2026-05-23 (see [docs/api-contracts-2026-05.md](docs/api-contracts-2026-05.md)).

## Code health

- [ ] `git status` clean on `main` (no uncommitted files).
- [ ] `git log --oneline -10` makes sense (no leaked secrets).
- [ ] `python -m pytest -q tests/test_orchestrator_v2.py tests/test_repair_loop.py tests/test_genre_templates.py tests/test_batch_redraw.py tests/test_platform_export.py tests/test_theme_to_novel.py tests/test_backend_api.py tests/test_api_contracts.py tests/test_v8_gap_closures.py` → **41 passed** (or higher).
- [ ] `cd web && npx tsc --noEmit` → 0 errors.
- [ ] `cd web && npx next build` → 0 errors (19+ routes).
- [ ] `python scripts/env_check.py` → ✅ all required keys present.

## Phase A — API contracts

- [ ] `docs/api-contracts-2026-05.md` reviewed within the last 30 days.
- [ ] Skylark `req_key = pippit_iv2v_v20_cvtob_with_vinput` confirmed in [src/shell3_skylark_engine/client.py](src/shell3_skylark_engine/client.py).
- [ ] Anthropic default model id = `claude-opus-4-7-20260413` in all 5 callsites + env templates.

## Phase B — Drift fixes

- [ ] `tests/test_v8_gap_closures.py::test_repair_router_wires_actual_class_names` green.
- [ ] `tests/test_api_contracts.py::test_anthropic_default_model_is_opus_4_7` green.
- [ ] `.env.example` + `backend/.env.example` use `claude-opus-4-7-20260413` defaults.

## Phase C — Gap closures (10 deliverables)

- [ ] C-1 Wan-Animate fight route present in `_step4_render` (test_v8_gap_closures.test_orchestrator_v8_tags_fight_shot_routes).
- [ ] C-2 Seedance multi-char route tag present (≥ 3 主角).
- [ ] C-3 PuLID multi-character lock helper (test_v8_gap_closures.test_multi_character_lock_falls_back_without_replicate_token).
- [ ] C-4 Hedra lip-sync handler wired (test_v8_gap_closures.test_repair_router_wires_actual_class_names).
- [ ] C-5 Veo upscaler invocation in `_step6_fine_cut` for ep01/04/09.
- [ ] C-6 Seedream 4.0 cover when `USE_REAL_COVER=1` else ffmpeg frame.
- [ ] C-7 MiniMax Speech 2.5 HD module wired (test_api_contracts.test_minimax_speech_2_5_body).
- [ ] C-8 C2PA sidecar always emitted (test_v8_gap_closures.test_c2pa_sidecar_includes_sha256_and_ai_systems).
- [ ] C-9 广电备案 auto-fill (test_v8_gap_closures.test_filing_autogen_writes_markdown_and_sidecar).
- [ ] C-10 Bilingual subtitle wiring (test_v8_gap_closures.test_orchestrator_v8_emits_c2pa_filing_and_bilingual_artifacts).

## Phase E — Deploy package

- [ ] `RUNBOOK.md` present and current.
- [ ] `scripts/env_check.py` exits 0 with all 8 keys set.
- [ ] `scripts/deploy_smoke.py --backend-url http://localhost:8000` PASS against `uvicorn app.main:app` locally.
- [ ] `.github/workflows/ci.yml` includes both `test_api_contracts.py` and `test_v8_gap_closures.py`.
- [ ] `.github/workflows/deploy.yml` present with Railway + Vercel + post-deploy smoke steps.
- [ ] `backend/Dockerfile` bakes `ffmpeg`, `libpq5`, `fonts-noto-cjk` (思源黑体).

## Compliance / AIGC

- [ ] AIGC explicit watermark active in `master.mp4` ("AI 生成" visible).
- [ ] C2PA sidecar JSON next to every `master.mp4`.
- [ ] Filing auto-fill produces `filing_filled.md` + `checklist.json` per job.
- [ ] Skylark `req_json` includes valid `aigc_meta.producer_id`.
- [ ] Title prefix "【AI】" + synopsis 首行 AI 声明 in marketing copy.

## Production toggles

- [ ] `MOCK_MODE=0` set in Railway env.
- [ ] `USE_REAL_COVER=1`.
- [ ] `USE_REAL_UPSCALER=1` (only if Google Vertex token provisioned).
- [ ] `USE_REAL_WAN_ANIMATE=1` (only if DashScope key provisioned).
- [ ] `CORS_ORIGINS` pinned to your Vercel domain.
- [ ] `SITE_URL` matches Vercel domain.
- [ ] `JWT_SECRET` is ≥ 32-char random string (not the placeholder).

## Rollback readiness

- [ ] Previous Railway deployment ID written down for fast rollback.
- [ ] Postgres backup snapshot taken before release.
- [ ] Vercel previous production deployment URL written down.

When every box is ticked → push the tag `v8.0` and announce.
