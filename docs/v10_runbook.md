# Xiaoyunque V10 Runbook

This runbook covers day-2 operations for the V10 production pipeline:
deploy, scale, monitor, debug, recover.

---

## 1. Architecture (1-pager)

```
                   ┌──────────────────────────┐
                   │  Next.js Frontend (web/) │
                   │  /dashboard/new/{wizard, │
                   │     pro}, /jobs, /flow   │
                   └─────────────┬────────────┘
                                 ▼ HTTPS
       ┌─────────────────────────────────────────────┐
       │ FastAPI API (backend/app/main.py)           │
       │   /api/*       — UI                         │
       │   /api/v1/*    — Public API (X-API-Key)     │
       │   /api/flow/ws — Pause-gate WebSocket       │
       │   /api/internal/worker/tick — Cron entry    │
       └─────────────────────────────────────────────┘
              │                                │
              │ embedded asyncio worker        │ public_v1
              ▼                                ▼
   ┌────────────────┐                ┌──────────────────┐
   │ Pipeline jobs  │  produces      │ Per-org rate     │
   │ (worker.py)    ├───────────────▶│ limits + usage   │
   │ • text_layer   │                │ rollups          │
   │ • visual asset │                └──────────────────┘
   │ • frame_gen    │
   │ • qa loop      │      provider fan-out:
   │ • av_synth     │   ┌──────────────────────────┐
   │ • derivative   │──▶│ Volcengine, Doubao,      │
   │ • export       │   │ FAL, ElevenLabs, Skylark │
   └────────────────┘   │ Manju Agent, Wan, etc.   │
                        └──────────────────────────┘
              │                                │
              ▼                                ▼
       ┌──────────────┐               ┌──────────────────┐
       │ PostgreSQL   │               │ TOS object store │
       │ (xyq_* tabl.)│               │ orgs/{id}/jobs/  │
       └──────────────┘               └──────────────────┘
```

Five enterprise tables (`xyq_organizations`, `xyq_org_members`,
`xyq_api_keys`, `xyq_org_usage`, `xyq_org_invites`) isolate every
asset by `org_id`.

---

## 2. First-time deploy

### 2.1 Self-hosted (docker-compose)

```bash
cd deploy/cn
cp .env.example .env
# edit DATABASE_URL, ANTHROPIC_API_KEY, FAL_API_KEY, VOLC_ACCESS_KEY, …
./install.sh
```

Health check: `curl http://localhost:8000/api/health`

### 2.2 Volcengine veFaaS (serverless)

```bash
cd deploy/cn-volc-vefaas
cp config.yaml.example config.yaml
# fill in function_name, image, env vars (EMBEDDED_WORKER=0 here)
python deploy.py up
# wire a Volcengine timer trigger → /api/internal/worker/tick (every 30s)
# wire another timer trigger → /api/schedules/poll  (every 60s)
```

### 2.3 K8s / private deploy (Helm)

```bash
cd deploy/enterprise/helm
helm install xyq ./xyq -f my-values.yaml
helm upgrade --install xyq ./xyq -f my-values.yaml
```

Required values:
- `image.repository`, `image.tag`
- `env.DATABASE_URL`
- `secrets.ANTHROPIC_API_KEY`, `secrets.FAL_API_KEY`, …
- `ingress.host`, `ingress.tlsSecretName`

---

## 3. Run database migrations

```bash
# inside the API container or any host with access to DB:
alembic -c backend/alembic.ini upgrade head
```

The `_apply_simple_migrations` helper in `db.py` keeps dev DBs current
automatically; production should use Alembic.

---

## 4. Operate

### 4.1 Cron triggers
- `POST /api/internal/worker/tick`  — pipeline tick (every 30s)
- `POST /api/schedules/poll`        — fire due `/schedules` (every 60s)

### 4.2 Pause-gate (per-step confirmation)
- Inspect: `GET /api/flow/pauses/{job_id}`
- Resolve: `POST /api/flow/{approve|reject|modify}/{job_id}/{step}`
- WebSocket: `wss://…/api/flow/ws/pauses/{job_id}` for live UI updates.

### 4.3 Org & API keys
- Create org:    `POST /api/orgs`         (caller becomes owner)
- Invite mem:    `POST /api/orgs/{id}/members` → email an invite token
- Issue key:     `POST /api/orgs/{id}/keys`  (returns `raw_token` ONCE)
- Public API:    `X-API-Key: xyq_live_…`

### 4.4 Scheduled publishing
- Register: `POST /api/schedules` with cron / date / interval_seconds
- List due: `GET /api/schedules/due`
- Cancel:   `DELETE /api/schedules/{schedule_id}`

---

## 5. Observability

### 5.1 SLA probe (cron)
```bash
*/1 * * * *  python tools/sla_probe.py --base-url https://xyq.example.com
```
Output: `data/observability/sla_probe.json` (consumed by Grafana via
`json_exporter` or pushed via OTLP).

### 5.2 Dashboards
- Grafana: import `deploy/observability/grafana_dashboard_v10.json`.
- Volcengine 云监控: `volc cloud-monitor apply -f
  deploy/observability/volc_cloud_monitor.yaml`.

### 5.3 Alarm severity ladder
- **critical** — page on-call: 5xx > 5/min for 3min, TOS write fail.
- **warning**  — DingTalk: api p95 > 2s, 429 spike, low 7-d score.
- **info**     — email rollup.

### 5.4 Acceptance check
```bash
python scripts/v10_acceptance.py [--strict]
```
Verifies every chapter of `need.md` against shipped artefacts. CI runs
this on every PR.

---

## 6. Recovery playbooks

| Symptom                                | First action                                                              |
|----------------------------------------|---------------------------------------------------------------------------|
| API 5xx spike                          | tail `xyq.api` logs, check provider quotas (Doubao / FAL / Manju Agent)   |
| All jobs stuck `pending`               | restart embedded worker; or re-arm SCF / OOS timer                        |
| One job stuck in `running`             | inspect `xyq_job_logs`; resume via `/flow/jobs/{id}/branches` + fork      |
| 7-dim quality avg < 7.5                | review `feedback_distill` suggestions; pin a known-good model temporarily |
| WhisperX missing → bad subs            | route `dialogue_timeline` to ``method=char_rate`` until reinstalled       |
| Repair loop runs > 30/min              | toggle `_AXIS_ROUTES` to bypass `god_tier` route via env var              |
| TOS write failure                      | manual retry from `data/artifacts/`; verify VOLC_ACCESS_KEY rotation      |
| Org over monthly_credits_cents         | `UPDATE xyq_organizations SET monthly_credits_cents = … WHERE id = …`     |
| SSO callback failing                   | re-run `OIDCProvider.discover()`; confirm IdP redirect_uri               |

---

## 7. Backup / restore

- Database: `pg_dump`; recommended schedule = 6h.
- Object storage: TOS lifecycle rule → cross-region replication.
- Pause-gate JSON store + scheduler JSON store: backed up with the
  artifact tree via `src.infra.project_archive`.

---

## 8. Canary release

1. Push image to registry.
2. veFaaS / Helm: set traffic split 10% → image:N, 90% → image:N-1.
3. Observe Grafana + sla_probe for 30 min.
4. Bump to 30% → 60 min observation → 100%.
5. Run `python scripts/v10_acceptance.py --strict` against canary URL.

---

## 9. Quick links

- `docs/api-v10.md`              — Public /api/v1 reference + SDK snippets.
- `docs/v10_runbook.md`          — (this file).
- `deploy/enterprise/helm/`      — Helm chart.
- `deploy/observability/`        — Grafana + Volcengine alarm configs.
- `scripts/v10_acceptance.py`    — 11-chapter acceptance test.
- `tools/sla_probe.py`           — Continuous SLA probe.
