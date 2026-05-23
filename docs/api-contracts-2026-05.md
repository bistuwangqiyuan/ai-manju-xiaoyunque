# API Contracts (2026-05) — 19 providers · world-class AI 漫剧 production stack

> Single source of truth for every external API the platform calls.
> Each section lists: official doc · model id · endpoint · request shape ·
> response shape · auth · pricing today · known quirks · `config/production.yaml`
> line that pins it · `src/` file that calls it · **STATUS** (ok / drift / gap).
>
> "STATUS = drift" means an API field, model id, or endpoint has changed since
> v7 shipped and Phase B will patch the caller. "STATUS = gap" means a doc
> requirement is unwired and Phase C will close it.

---

## Stack overview

| Step | Provider · Model | File | Status |
|---|---|---|---|
| 1. 剧本分析 — 事件抽取 | DeepSeek V4-Pro | `src/shell1_screenwriter/extract_events.py` | ok |
| 1. 剧本分析 — 分集主笔 | Anthropic Claude Opus 4.7 | `src/shell1_screenwriter/write_episodes.py` | ok |
| 1. 剧本分析 — schema 校验 | Google Gemini 2.5 Pro | `src/shell1_screenwriter/schema_validate.py` | ok |
| 1. 剧本分析 — theme→novel | Anthropic Claude / DeepSeek | `src/shell1_screenwriter/theme_to_novel.py` | **drift** (model id) |
| 1. 剧本分析 — 版权 LLM novelty | Anthropic Claude | `src/compliance/copyright_novelty.py` | **drift** (model id) |
| 2. 人物图 — 主图 | Volcengine Seedream 5 Lite | `src/shell2_character_assets/gen_seedream.py` | ok |
| 2. 人物图 — 变体 | Volcengine 即梦 4.6 | `src/shell2_character_assets/gen_jimeng.py` | ok |
| 2. 人物图 — 单角色 ID 锁 | FAL InfiniteYou | `src/shell2_character_assets/id_lock_infiniteyou.py` | ok |
| 2. 人物图 — 多角色 ID 锁 (≤4) | Replicate PuLID | `src/shell2_character_assets/multi_id_pulid.py` | **gap** (not invoked) |
| 2. 人物图 — 换装 / 局部编辑 | FAL FLUX Kontext Pro | `src/shell2_character_assets/edit_flux_kontext.py` | ok |
| 3. 分镜 — 整集量产 | **Volcengine 小云雀 Agent 2.0** (Pippit IV2V) | `src/shell3_skylark_engine/client.py` | ok (locked to官方文档) |
| 3. 分镜 — 多角色群戏 | Volcengine Seedance 2.0 Pro | `src/shell3_skylark_engine/seedance_fallback.py` | **drift** (stub only) |
| 3. 分镜 — 武打动作迁移 | DashScope Wan 2.2-Animate | _not implemented_ | **gap** |
| 4. 质检 — 7-dim VLM | Volcengine Doubao Seed 1.6 Vision | `src/shell4_qa_repair/vlm_per_shot.py` | **drift** (model id) |
| 4. 质检 — ArcFace | InsightFace buffalo_l (local) | `src/shell4_qa_repair/arcface_check.py` | ok |
| 4. 质检 — 多 VLM ensemble | Claude + Pixtral + Qwen-VL | `tools/multi_provider_vlm.py` | ok |
| 4. 修复 — 面部漂移 | FAL Wan 2.7-FLF | `src/shell4_qa_repair/repair_wan_flf.py` | ok |
| 4. 修复 — 近景对白唇形 | Hedra Character-3 | `src/shell4_qa_repair/repair_hedra.py` | **drift** (handler name) |
| 4. 修复 — 服装/局部 | FAL FLUX Kontext (frame-by-frame) | `src/shell4_qa_repair/repair_flux_kontext.py` | **drift** (handler name) |
| 4. 修复 — 风格统一 | Runway Aleph V2V | `src/shell4_qa_repair/repair_aleph.py` | **drift** (handler name) |
| 4. 修复 — 越轴/动作错位 | Volcengine Seedance Standard | _via Seedance fallback_ | **gap** (handler not registered) |
| 4. 修复 — 高光集精修 | Google Veo 3.1 Fast/Standard | `src/shell4_qa_repair/repair_veo31.py` | **drift** (handler name) |
| 4. 修复 — 封神镜头 | OpenAI Sora 2 Pro | `src/shell4_qa_repair/repair_sora2.py` | **drift** (handler name) |
| 5. 后期 — 主路 TTS | Volcengine Doubao Seed-TTS 2.0 ICL | `src/shell5_post_production/tts_doubao_icl.py` | ok |
| 5. 后期 — 情感配音 | MiniMax Speech 2.5 HD | _not implemented_ | **gap** (config only) |
| 5. 后期 — 海外 TTS | ElevenLabs Multilingual v3 | `src/shell5_post_production/tts_elevenlabs_intl.py` | ok |
| 5. 后期 — 主 BGM | ElevenLabs Music v1 | `src/shell5_post_production/bgm_elevenlabs.py` | ok |
| 5. 后期 — 中文古风 BGM | 网易天音 | _not implemented_ | **gap** (no public API) |
| 5. 后期 — 主题曲 | Suno Chirp Premier v5.5 | _not implemented_ | **gap** (config only) |
| 5. 后期 — SFX | ElevenLabs Sound Effects | `src/shell5_post_production/sfx_elevenlabs.py` | ok |
| 5. 后期 — 双语字幕翻译 | Gemini 2.5 Pro / Claude | `src/shell5_post_production/subtitle_translate.py` | **drift** (model id) |
| 5. 后期 — 中文封面 | Volcengine Seedream 4.0 | `src/shell5_post_production/cover_seedream.py` | ok (not invoked from orchestrator) |
| 5. 后期 — 英文封面 | Ideogram 3.0 | _not implemented_ | **gap** |
| 5. 后期 — 4K 上采 | Google Veo 3.1 Upscaler | `src/shell5_post_production/upscale_veo31.py` | ok (not invoked from orchestrator) |
| 5. 后期 — AIGC 隐式标识 | Volcengine 小云雀 `req_json` | `src/shell3_skylark_engine/client.py` `AigcMeta` | ok |
| 5. 后期 — SynthID + C2PA | (none) | _not implemented_ | **gap** |
| 6. 合规 — 广电备案 auto-fill | (none) | _not implemented_ | **gap** |

Total: **19 providers**, of which 11 are working (`ok`), 6 have drift (`drift`), 8 have gap (`gap`). Phase B closes drift; Phase C closes gap.

---

## 1. Volcengine 小云雀 Agent 2.0 — Pippit IV2V vinput  ★ 核心引擎

- **Official doc** · <https://www.volcengine.com/docs/85621/2359610?lang=zh>
- **req_key** · `pippit_iv2v_v20_cvtob_with_vinput` _(single canonical, no fallback)_
- **Endpoint** · `POST https://visual.volcengineapi.com`
- **Auth** · HMAC-SHA256 V4 (Region=`cn-north-1`, Service=`cv`)
- **Action** · `CVSync2AsyncSubmitTask` (submit) / `CVSync2AsyncGetResult` (poll)
- **API version** · `2022-08-31`
- **Submit body** ·
  ```json
  {
    "req_key": "pippit_iv2v_v20_cvtob_with_vinput",
    "prompt": "≤ 2000 chars，含人物设定块",
    "img_url_list": ["..."],        // 角色 + 场景 + 风格锚定
    "video_url_list": ["..."],      // 动作迁移参考视频（可选）
    "ratio": "9:16",                // ★ enum: 16:9 | 9:16 | 4:3 | 3:4
    "duration": "40～60s",          // ★ enum: ～15s | ～30s | 40～60s  (max 60s)
    "language": "Chinese",
    "enable_watermark": false       // 商用关掉双水印
  }
  ```
- **Query body** ·
  ```json
  { "req_key": "...", "task_id": "...",
    "req_json": "{\"aigc_meta\":{\"content_producer\":\"...\",\"producer_id\":\"...\",\"content_propagator\":\"...\",\"propagate_id\":\"...\"}}" }
  ```
- **Response** · `data.status ∈ {processing, in_queue, generating, done, not_found, expired}` · `data.video_url` (TTL **1 h**) · `task_id` TTL **12 h** · `data.aigc_meta_tagged: bool`
- **Constraints** · `len(img_url_list) + len(video_url_list) ≤ 50` · single image ≤ 20 MB / 4096² · single video ≤ 3 min / 200 MB · prompt ≤ 2000 chars · output **≤ 60 s/次** (>60s 集走 `chunk_renderer.py` 2-chunk 拼接)
- **Pricing** · 11 积分/秒；39 元 / 1200 积分 → **¥0.36 / 秒**；计费基数 = `(InputVideoDurationSum + Duration) × 单价`
- **Retryable codes** · `{50429, 50430, 50500, 50501, 50511}`
- **Audit fatal codes** · `{50411, 50412, 50413, 50512, 50513, 50514}`
- **config/production.yaml** · `shell3_video_generation.primary_engine`
- **Code** · [src/shell3_skylark_engine/client.py](../src/shell3_skylark_engine/client.py)
- **STATUS: ok** — client is faithful to官方文档 2026-05.

## 2. Volcengine Seedream 5.0 Lite + 即梦 4.6  ★ 人物图主图 + 变体

- **Official doc** · `https://www.volcengine.com/docs/6791` (Visual OpenAPI)
- **req_key** · Seedream 5.0 Lite = `jimeng_t2i_v50_lite` · 即梦 4.6 = `jimeng_t2i_v46` · Seedream 4.0 (封面) = `jimeng_t2i_v40`
- **Endpoint** · `POST https://visual.volcengineapi.com`
- **Auth** · 同 §1 (HMAC V4)
- **Action** · `CVProcess`
- **Submit body (Seedream)** ·
  ```json
  {
    "req_key": "jimeng_t2i_v50_lite",
    "prompt": "...",
    "num_images": 8,
    "aspect_ratio": "3:4",
    "deep_thinking": true,
    "reference_images": ["..."]      // 即梦 4.6 → 同字段
  }
  ```
- **Response** · `data.image_urls: [str]` (Seedream) / `data.images: [str]` (即梦)
- **Pricing** · Seedream ≈ ¥0.10/张；即梦 ≈ ¥0.05/张
- **Code** · [src/shell2_character_assets/gen_seedream.py](../src/shell2_character_assets/gen_seedream.py) · [src/shell2_character_assets/gen_jimeng.py](../src/shell2_character_assets/gen_jimeng.py)
- **STATUS: ok**.

## 3. Volcengine Doubao Seed 1.6 Vision  ★ 7-dim 每镜质检

- **Official doc** · <https://www.volcengine.com/docs/82379>  (Ark v3)
- **Endpoint** · `POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- **Model id** · `doubao-seed-1-6-vision-250815`  _← 注意：API 用连字符（**不是** `.1.6.`）_
- **Auth** · `Authorization: Bearer ${DOUBAO_API_KEY or VOLC_ARK_API_KEY}`
- **Body** · OpenAI-compatible `messages[]`, 支持 `{"type":"video_url","video_url":{"url":...}}` + `{"type":"image_url","image_url":{"url":...}}` 混合输入
- **Response** · OpenAI 兼容 `choices[0].message.content` (JSON 字符串)
- **Pricing** · ¥0.8/M input · ¥8/M output
- **Code** · [src/shell4_qa_repair/vlm_per_shot.py](../src/shell4_qa_repair/vlm_per_shot.py)
- **STATUS: drift** — `config/production.yaml` 写的是 `doubao-seed-1.6-vision-250815`（点号），而真正的 API id 是 `doubao-seed-1-6-vision-250815`（连字符）。代码用对了，YAML 是文档值，写为注释保留，不需改动；但要在 [docs/api-contracts-2026-05.md](api-contracts-2026-05.md) 中明确两种命名约定的关系。

## 4. Volcengine Doubao Seed-TTS 2.0 + ICL  ★ 主路配音

- **Official doc** · <https://www.volcengine.com/docs/6561>
- **Endpoint** · `POST https://openspeech.bytedance.com/api/v1/tts`
- **Auth** · `Authorization: Bearer; ${access_token}` _(注意分号)_  + `app.appid` + `app.token` + `app.cluster=volcano_icl`
- **Body** ·
  ```json
  {
    "app": {"appid":"...", "token":"...", "cluster":"volcano_icl"},
    "user": {"uid":"skylark_pipeline"},
    "audio": {"voice_type":"...", "encoding":"mp3", "rate":24000,
              "speed_ratio":1.0, "volume_ratio":1.0, "pitch_ratio":1.0,
              "emotion":"neutral|happy|sad|angry|fear"},
    "request": {"reqid":"...", "text":"...", "operation":"query"}
  }
  ```
- **Response** · `{"code":3000, "data":"<base64>"}`
- **Pricing** · ¥4.9-6.5 / 万字 · 复刻音色年订阅 ¥150
- **Code** · [src/shell5_post_production/tts_doubao_icl.py](../src/shell5_post_production/tts_doubao_icl.py)
- **STATUS: ok**.

## 5. Anthropic Claude Opus 4.7  ★ 编剧主笔 + 营销文案 + 字幕翻译

- **Official doc** · <https://docs.anthropic.com/en/api/messages>
- **Endpoint** · `POST https://api.anthropic.com/v1/messages` (官方) · 代理走 `ANTHROPIC_BASE_URL`
- **Model id (canonical 2026-05)** · `claude-opus-4-7-20260413`
- **Auth** · `x-api-key: ${ANTHROPIC_API_KEY}` (官方) · `Authorization: Bearer ${ANTHROPIC_AUTH_TOKEN}` (代理)
- **Body** · `{model, max_tokens, system, messages: [{role, content}], temperature}`
- **Pricing** · $5 / M input · $25 / M output · prompt-cache –90% · batch –50%
- **Code** · [src/shell1_screenwriter/write_episodes.py](../src/shell1_screenwriter/write_episodes.py) (uses 4.7) · [src/shell5_post_production/subtitle_translate.py](../src/shell5_post_production/subtitle_translate.py) (uses 4.5) · [src/shell5_post_production/marketing_copy.py](../src/shell5_post_production/marketing_copy.py) (uses 4.5) · [src/shell1_screenwriter/theme_to_novel.py](../src/shell1_screenwriter/theme_to_novel.py) (uses 4.5) · [src/compliance/copyright_novelty.py](../src/compliance/copyright_novelty.py) (uses 4.5) · [src/advanced/continuation.py](../src/advanced/continuation.py)
- **STATUS: drift** — 主笔已用 `claude-opus-4-7-20260413`，但 5 处副笔仍默认 `claude-opus-4-5-20250929`。**Phase B** 统一改为 `claude-opus-4-7-20260413`（可被 `ANTHROPIC_MODEL` env 覆盖）。

## 6. DeepSeek V4-Pro  ★ 事件抽取 (1M 上下文)

- **Official doc** · <https://api-docs.deepseek.com>
- **Endpoint** · `POST https://api.deepseek.com/v1/chat/completions`
- **Model id** · `deepseek-v4-pro` (event-extraction), `deepseek-chat` (general)
- **Auth** · `Authorization: Bearer ${DEEPSEEK_API_KEY}`
- **Body** · OpenAI-compatible, `response_format: {type: json_object}` 支持
- **Pricing** · $1.74 / M input · $3.48 / M output (2026-05 折扣价 0.25×)
- **Code** · [src/shell1_screenwriter/extract_events.py](../src/shell1_screenwriter/extract_events.py)
- **STATUS: ok**.

## 7. Google Gemini 2.5 Pro  ★ JSON schema 校验 + 字幕翻译

- **Official doc** · <https://ai.google.dev/api/rest/v1beta/models/generateContent>
- **Endpoint** · `POST https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`
- **Model id** · `gemini-2.5-pro`
- **Body** · `{contents:[{role,parts:[{text}]}], generationConfig:{temperature, maxOutputTokens, responseMimeType:"application/json", responseSchema:{...}}}`
- **Pricing** · ≤200k input $1.25/M · >200k $2.50/M
- **Code** · [src/shell1_screenwriter/schema_validate.py](../src/shell1_screenwriter/schema_validate.py) · [src/shell5_post_production/subtitle_translate.py](../src/shell5_post_production/subtitle_translate.py)
- **STATUS: ok**.

## 8. Google Veo 3.1 (Fast / Standard / Upscaler)  ★ 高光精修 + 4K 上采

- **Official doc** · <https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo>
- **Endpoint** · `POST https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${LOCATION}/publishers/google/models/${model}:predictLongRunning`
- **Model id** · `veo-3.1-fast-generate-001` · `veo-3.1-generate-001` (Standard) · `veo-3.1-upscaler`
- **Auth** · `Authorization: Bearer ${GOOGLE_ACCESS_TOKEN}` (OAuth2 from service account)
- **Body** · `{instances:[{prompt, referenceImages:[{image:{gcsUri}}], aspectRatio:"9:16", durationSeconds, resolution:"1080p", generateAudio:true}], parameters:{sampleCount:1}}`
- **Polling** · `GET https://${LOCATION}-aiplatform.googleapis.com/v1/${operation_name}` until `done:true`
- **Pricing** · Fast $0.15/s · Standard $0.40/s · Upscaler $0.10/s
- **Code** · [src/shell4_qa_repair/repair_veo31.py](../src/shell4_qa_repair/repair_veo31.py) · [src/shell5_post_production/upscale_veo31.py](../src/shell5_post_production/upscale_veo31.py)
- **STATUS: ok client / gap orchestrator** — Upscaler module exists but `orchestrator_v2._step6_fine_cut` does not invoke it for `ep01/ep04/ep09`. **Phase C** wires it.

## 9. OpenAI Sora 2 Pro  ★ ep09 封神镜头 (only)

- **Official doc** · <https://platform.openai.com/docs/api-reference/videos>
- **Endpoint** · `POST https://api.openai.com/v1/videos/generations`
- **Model id** · `sora-2-pro`
- **Auth** · `Authorization: Bearer ${OPENAI_API_KEY}`
- **Body** · `{model, prompt, size:"1080x1920", n_seconds:8}`
- **Polling** · `GET /v1/videos/generations/{id}` until `status=succeeded`
- **Pricing** · ~$0.75 / s 1080p
- **Restriction (硬红线)** · 禁上传任何他人脸照（含动漫风）；本管线只对 ep09 "革囊苍白手伸出" 等无脸镜头使用。
- **Code** · [src/shell4_qa_repair/repair_sora2.py](../src/shell4_qa_repair/repair_sora2.py)
- **STATUS: ok**.

## 10. Runway Aleph (V2V)  ★ 跨集风格统一

- **Official doc** · <https://docs.dev.runwayml.com>
- **Endpoint** · `POST https://api.dev.runwayml.com/v1/video_to_video`
- **Model** · `aleph`
- **Auth** · `Authorization: Bearer ${RUNWAY_API_KEY}` + `X-Runway-Version: 2024-11-06`
- **Body** · `{model:"aleph", videoUri, promptText, referenceImages:[{uri}], duration, ratio:"1080:1920"}`
- **Polling** · `GET /v1/tasks/{id}` until `status=SUCCEEDED`
- **Pricing** · ~$0.10 / s
- **Code** · [src/shell4_qa_repair/repair_aleph.py](../src/shell4_qa_repair/repair_aleph.py)
- **STATUS: ok**.

## 11. FAL — FLUX Kontext Pro / InfiniteYou / Wan 2.7-FLF

- **Official doc** · <https://fal.ai/models>
- **Endpoints** ·
  - FLUX Kontext Pro · `POST https://fal.run/fal-ai/flux-kontext/pro`
  - InfiniteYou · `POST https://fal.run/fal-ai/infinite-you`
  - Wan 2.7-FLF · `POST https://fal.run/fal-ai/wan-2.7-flf`
- **Auth** · `Authorization: Key ${FAL_API_KEY}`
- **Body / Response** · see each model page (image edit / id-embedding / video FLF)
- **Pricing** · FLUX Kontext Pro $0.04/edit · InfiniteYou $0.05/id · Wan FLF $0.10/s
- **Code** · [src/shell2_character_assets/edit_flux_kontext.py](../src/shell2_character_assets/edit_flux_kontext.py) · [src/shell2_character_assets/id_lock_infiniteyou.py](../src/shell2_character_assets/id_lock_infiniteyou.py) · [src/shell4_qa_repair/repair_wan_flf.py](../src/shell4_qa_repair/repair_wan_flf.py) · [src/shell4_qa_repair/repair_flux_kontext.py](../src/shell4_qa_repair/repair_flux_kontext.py)
- **STATUS: ok**.

## 12. Replicate PuLID  ★ 多角色 ID 锁

- **Official doc** · <https://replicate.com/fofr/pulid>
- **Endpoint** · `POST https://api.replicate.com/v1/predictions`
- **Model version** · `fofr/pulid` (latest published)
- **Auth** · `Authorization: Token ${REPLICATE_API_TOKEN}`
- **Body** · `{version, input:{prompt, id_images:[...], id_weights:[...], aspect_ratio:"9:16", seed}}`
- **Pricing** · ~$0.012 / gen on Nvidia A100
- **Code** · [src/shell2_character_assets/multi_id_pulid.py](../src/shell2_character_assets/multi_id_pulid.py)
- **STATUS: gap orchestrator** — class is ready, but `CharacterAssetBuilder._gen_seedream/_gen_jimeng` doesn't call PuLID when shots have ≥ 2 主角. **Phase C** adds a `multi_id_pulid_lock(asset, others=...)` path to `build_asset.py`.

## 13. Hedra Character-3 (lip-sync)

- **Official doc** · <https://docs.hedra.com>
- **Endpoint** · `POST https://api.hedra.com/web-app/public/generations`
- **Model** · `character-3`
- **Auth** · `Authorization: Bearer ${HEDRA_API_KEY}`
- **Body** · `{model, image_url, audio_url, aspect_ratio:"9:16", resolution:"720p", lipsync_quality:"high"}`
- **Polling** · `GET /generations/{id}` until `status=complete`
- **Pricing** · $0.15 / generation (720p)
- **Code** · [src/shell4_qa_repair/repair_hedra.py](../src/shell4_qa_repair/repair_hedra.py)
- **STATUS: drift handler-name** — `run_qa._build_default_router` imports `HedraLipsyncRepair`, but actual class is `HedraRepair`. **Phase B** fixes import.

## 14. ElevenLabs — Multilingual v3 TTS + Music v1 + Sound Effects

- **Official doc** · <https://elevenlabs.io/docs/api-reference>
- **Endpoints** ·
  - TTS · `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` (header `Accept: audio/mpeg`)
  - Music · `POST https://api.elevenlabs.io/v1/music/compose`
  - SFX · `POST https://api.elevenlabs.io/v1/sound-generation`
- **Auth** · `xi-api-key: ${ELEVENLABS_API_KEY}`
- **Body (TTS)** · `{text, model_id:"eleven_multilingual_v3", voice_settings:{stability, similarity_boost}}`
- **Body (Music)** · `{prompt, music_length_ms, instrumental}`
- **Body (SFX)** · `{text, duration_seconds}`
- **Pricing** · TTS $0.10/1k chars (multilingual v3) · Music $0.30/min · SFX $0.12/clip
- **Code** · [src/shell5_post_production/tts_elevenlabs_intl.py](../src/shell5_post_production/tts_elevenlabs_intl.py) · [src/shell5_post_production/bgm_elevenlabs.py](../src/shell5_post_production/bgm_elevenlabs.py) · [src/shell5_post_production/sfx_elevenlabs.py](../src/shell5_post_production/sfx_elevenlabs.py)
- **STATUS: ok**.

## 15. MiniMax Speech 2.5 HD  ★ 高情感张力配音

- **Official doc** · <https://www.minimax.io/api>
- **Endpoint** · `POST https://api.minimax.chat/v1/t2a_v2`
- **Model id** · `speech-2.5-hd`
- **Auth** · `Authorization: Bearer ${MINIMAX_API_KEY}`
- **Body** · `{model:"speech-2.5-hd", text, voice_id, audio_setting:{format:"mp3", sample_rate:32000}, emotion:"happy|sad|angry|fearful|surprised|disgusted"}`
- **Pricing** · $0.08 / 1k chars
- **Code** · _not implemented_
- **STATUS: gap** — Phase C adds `src/shell5_post_production/tts_minimax.py` for `voice_emotion_boost` route used on 小倩泣诉 / 燕赤霞慷慨等张力高的镜头.

## 16. Suno Chirp Premier v5.5  ★ 主题曲

- **Official doc** · <https://docs.suno.com>
- **Endpoint** · `POST https://api.suno.com/v1/generations` (Premier tier only)
- **Model id** · `chirp-fenix-v5.5`
- **Auth** · `Authorization: Bearer ${SUNO_API_KEY}` (Premier subscription required)
- **Body** · `{model, prompt, lyrics, duration_seconds, with_vocals:true}`
- **Pricing** · $30 / month Premier subscription
- **Code** · _not implemented_
- **STATUS: gap (optional)** — Phase C adds `src/shell5_post_production/theme_song_suno.py` as the theme-song generator. Not blocking core SaaS launch; defaults to skip if `SUNO_API_KEY` absent.

## 17. DashScope (阿里通义) Wan 2.2-Animate  ★ 武打动作迁移

- **Official doc** · <https://help.aliyun.com/zh/dashscope>
- **Endpoint** · `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`
- **Model id** · `wan-2.2-animate`
- **Auth** · `Authorization: Bearer ${DASHSCOPE_API_KEY}`
- **Body** · `{model, input:{character_image_url, action_video_url, prompt}, parameters:{aspect_ratio:"9:16", duration:6, resolution:"720p"}}`
- **Polling** · `GET /api/v1/tasks/{task_id}` until `task_status=SUCCEEDED`
- **Pricing** · $0.0717 / s (480p) · $0.12 / s (720p)
- **Code** · _not implemented_
- **STATUS: gap** — Phase C adds `src/shell3_skylark_engine/wan_animate.py` + dispatches it for `shot_type=fight` shots in `orchestrator_v2._step4_render`.

## 18. Ideogram 3.0 (English cover poster)

- **Official doc** · <https://developer.ideogram.ai/api-reference>
- **Endpoint** · `POST https://api.ideogram.ai/generate`
- **Model id** · `V_3` (Quality)
- **Auth** · `Api-Key: ${IDEOGRAM_API_KEY}`
- **Body** · `{image_request:{prompt, aspect_ratio:"ASPECT_9_16", model:"V_3", style_type:"DESIGN", magic_prompt_option:"AUTO"}}`
- **Pricing** · $0.08 / image (V_3 Quality)
- **Code** · _not implemented_
- **STATUS: gap (optional)** — Phase C adds `src/shell5_post_production/cover_ideogram.py` for English market covers (海外发行).

## 19. 网易天音 (Chinese 古风 BGM, enterprise only)

- **Doc** · 仅企业合作；无公开 REST API
- **Code** · _not implemented_
- **STATUS: gap (documented fallback)** — Phase E documents in `RUNBOOK.md` 如何对接企业账号；运行时回落 ElevenLabs Music + 自带古风风格 prompt.

---

## Drift summary (Phase B targets)

| # | File | Drift |
|---|---|---|
| B-1 | `src/shell4_qa_repair/run_qa.py` `_build_default_router` | imports `HedraLipsyncRepair / FluxKontextRepair / AlephStyleRepair / Veo31ClimaxRepair / Sora2GodTierRepair` which don't exist → all handlers silently unwired. Patch: import actual classes `HedraRepair / FluxKontextShotRepair / AlephRepair / Veo31Repair / Sora2ProRepair`. |
| B-2 | `src/shell5_post_production/subtitle_translate.py` | default `claude-opus-4-5-20250929` → `claude-opus-4-7-20260413`. |
| B-3 | `src/shell5_post_production/marketing_copy.py` | same. |
| B-4 | `src/shell1_screenwriter/theme_to_novel.py` | same. |
| B-5 | `src/compliance/copyright_novelty.py` | same. |
| B-6 | `src/advanced/continuation.py` | same. |
| B-7 | `.env.example` + `backend/.env.example` | `ANTHROPIC_MODEL` default → `claude-opus-4-7-20260413`. |

## Gap summary (Phase C targets)

| # | Provider | New / wire-in file | Trigger |
|---|---|---|---|
| C-1 | DashScope Wan 2.2-Animate | `src/shell3_skylark_engine/wan_animate.py` (new) + dispatch in `orchestrator_v2._step4_render` | `shot.shot_type == "fight"` |
| C-2 | Volcengine Seedance 2.0 Pro | `src/shell3_skylark_engine/seedance_fallback.py` (实现 generate + poll) + dispatch | `len(shot.subject_chars) >= 3` |
| C-3 | Replicate PuLID | `src/shell2_character_assets/build_asset.py` (add `multi_lock` helper) | shot has ≥ 2 主角 |
| C-4 | Hedra Character-3 | `src/pipeline/orchestrator_v2.py` register `lipsync_repair=HedraRepair()` | per-shot QA flags `lipsync` |
| C-5 | Veo 3.1 Upscaler | `src/pipeline/orchestrator_v2._step6_fine_cut` invoke `Veo31Upscaler` | episode in `{1, 4, 9}` and `USE_REAL_UPSCALER=1` |
| C-6 | Seedream 4.0 cover | `src/pipeline/orchestrator_v2._step6_fine_cut` invoke `build_cover` when `USE_REAL_COVER=1` | always (replaces ffmpeg frame) |
| C-7 | MiniMax Speech 2.5 HD | `src/shell5_post_production/tts_minimax.py` (new) | emotion ∈ `{cry, fury, plea}` |
| C-8 | C2PA + SynthID sidecar | `src/shell5_post_production/aigc_sidecar.py` (new) + invoke in `_step6_fine_cut` | always |
| C-9 | 广电备案 auto-fill | `src/compliance/filing_autogen.py` (new) + API endpoint `/api/jobs/{id}/filing` | on-demand |
| C-10 | Bilingual subtitle | `src/pipeline/orchestrator_v2._step6_fine_cut` translate ASS when `language != "Chinese"` | per job-config |

Total new code surface ≤ 10 files, ≤ 500 lines.

---

## Pricing roll-up (per episode, 1080p × 80s, ancient genre)

| Component | Provider | Approx CNY |
|---|---|---|
| Storyboard render | Skylark Agent 2.0 | 80s × ¥0.36 = ¥29 |
| Char asset (one-time, amortised 10 集) | Seedream + Jimeng + InfiniteYou | ¥3 / 集 |
| 7-d QA × 25 shots | Doubao Vision | ¥4 |
| Repair (avg 3 shots/集) | Veo Fast + Aleph + FLUX | ¥10 |
| TTS (avg 1200 字) | Doubao Seed-TTS 2.0 | ¥0.6 |
| BGM | ElevenLabs Music | ¥1.5 |
| SFX (avg 4 cues) | ElevenLabs SFX | ¥3.5 |
| Subtitle translate (if 海外) | Gemini | ¥0.3 |
| Cover | Seedream 4.0 | ¥0.1 |
| **Total** | | **≈ ¥52 / 集** |
| Top-tier 加价 (ep01/04/09: Veo Standard + Sora 2 Pro + Upscaler) | | +¥16-30 |

Aligns with `config/production.yaml` budget (¥56-72/集, ¥866/10 集).
