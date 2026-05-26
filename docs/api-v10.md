# Xiaoyunque · Public API v10

Public RESTful interface under `/api/v1/*` authenticated by
`X-API-Key`. The OpenAPI/Swagger UI is auto-generated and lives at
`/docs` (login required for dashboard scopes; public-v1 endpoints
are documented anonymously).

## Authentication

Send the raw token from `POST /api/orgs/{org_id}/keys` as the
`X-API-Key` header:

```http
GET /api/v1/me
X-API-Key: xyq_live_o9Iks2EvT3wM_cZw8fI5UrA8hPx9JNqB
```

Every response includes:

| Header                  | Description                                |
|-------------------------|--------------------------------------------|
| `X-Org-Id`              | The org this key belongs to                |
| `X-RateLimit-Limit`     | Per-minute request cap                     |
| `X-Quota-Monthly`       | Total monthly request quota                |
| `X-Quota-Used`          | Monthly usage so far                       |
| `Retry-After` (on 429)  | Seconds until the bucket refills           |

## Endpoints

### `POST /api/v1/jobs` — Create a job

Body (subset of `JobCreateIn`):

```json
{
  "title": "First episode from API",
  "genre": "ancient",
  "mode": "excerpt",
  "novel_excerpt": "林辰穿越到唐朝……",
  "episodes": 1,
  "language": "Chinese",
  "aspect_ratio": "9:16",
  "resolution": "1080p",
  "fps": 24,
  "duration_per_episode_s": 80
}
```

→ `202 Accepted`, returns the `JobOut` payload (id, status,
created_at, …).

### `GET /api/v1/jobs/{id}`

Returns the same `JobOut` shape. 404 if not in your org.

### `GET /api/v1/jobs/{id}/shots`

Per-shot status (re-roll candidates, scores, urls).

### `POST /api/v1/jobs/{id}/cancel`

Soft-cancel; idempotent.

### `GET /api/v1/usage`

30-day rolling usage rollup for the calling org.

```json
{
  "org_id": 7,
  "days": 30,
  "jobs": 142,
  "episodes": 248,
  "minutes": 312.6,
  "cost_cents": 18420,
  "api_calls": 9420,
  "api_4xx": 24,
  "api_5xx": 0
}
```

### `GET /api/v1/me`

Identify the calling key without exposing the secret.

## SDK snippets

### Python

```python
import httpx

client = httpx.Client(
    base_url="https://xyq.example.com",
    headers={"X-API-Key": os.environ["XYQ_API_KEY"]},
    timeout=30,
)

r = client.post("/api/v1/jobs", json={
    "title": "API-generated episode",
    "mode": "theme",
    "theme": "唐朝穿越宫斗",
    "episodes": 1,
})
job = r.json()
print("job id:", job["id"])

while True:
    j = client.get(f"/api/v1/jobs/{job['id']}").json()
    if j["status"] in ("succeeded", "failed", "cancelled"):
        break
    time.sleep(5)
```

### Node.js

```js
import axios from "axios";

const xyq = axios.create({
  baseURL: "https://xyq.example.com",
  headers: { "X-API-Key": process.env.XYQ_API_KEY },
  timeout: 30000,
});

const { data: job } = await xyq.post("/api/v1/jobs", {
  title: "API-generated episode",
  mode: "theme",
  theme: "都市重生",
  episodes: 1,
});
```

### cURL

```bash
curl -X POST https://xyq.example.com/api/v1/jobs \
     -H "X-API-Key: $XYQ_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"mode":"theme","theme":"现代悬疑","episodes":1}'
```

## Error model

```json
{ "detail": "<human-readable message>" }
```

Common HTTP codes:

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 401  | Missing or invalid `X-API-Key`                       |
| 403  | Key disabled or scopes insufficient                  |
| 404  | Resource not in your org                             |
| 422  | Body validation failed (`detail.errors`)             |
| 429  | Rate limit exceeded — see `Retry-After`              |
| 5xx  | Server error — retry with exponential backoff        |

## Rate limits & quotas

Per key:
- `rate_per_min` — sliding-window cap (default 60/min, configurable).
- `monthly_quota_calls` — hard monthly cap (default 10 000).

Per org:
- `seats_max` — paid seats.
- `monthly_credits_cents` — render budget.

Exceeding any of the above returns 402 / 429 with a clear `detail`.

## Webhooks (preview)

Coming in v10.1:

- `POST {your-url}` body=`{event: "job.succeeded", id, ...}`

Configure via `POST /api/orgs/{org_id}/webhooks`.

## Compatibility

- v1 endpoints are stable. Additive changes (new optional fields)
  are released without a version bump; breaking changes will be
  shipped under `/api/v2/`.
- Deprecation policy: 90-day notice published in `docs/changelog.md`.
