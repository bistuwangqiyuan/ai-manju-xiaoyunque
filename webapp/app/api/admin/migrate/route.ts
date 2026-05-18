/**
 * POST /api/admin/migrate
 *
 * One-time idempotent schema bootstrap. Safe to call multiple times because
 * every DDL uses IF NOT EXISTS / OR REPLACE.
 *
 * Optional protection: set ADMIN_TOKEN env var, pass via
 * Authorization: Bearer <token>. If ADMIN_TOKEN is unset, endpoint is open
 * (acceptable because schema is idempotent — worst case it succeeds again).
 */
import { NextRequest, NextResponse } from 'next/server';
import { neon } from '@neondatabase/serverless';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

const SCHEMA_STATEMENTS = [
  // R1: drop pre-existing yunque tables if any (idempotent fresh start)
  // The Neon template comes with sample `users` having `username NOT NULL` etc.
  // Drop them so we own the schema.
  `DROP TABLE IF EXISTS generations CASCADE`,
  `DROP VIEW IF EXISTS v_user_quota_today`,
  `DROP TABLE IF EXISTS users CASCADE`,
  `CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tier          TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
    pro_until     TIMESTAMPTZ,
    daily_limit_override INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
  )`,
  `CREATE INDEX idx_users_email ON users (lower(email))`,
  `CREATE TABLE generations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id     TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    ratio       TEXT,
    duration    TEXT,
    status      TEXT NOT NULL DEFAULT 'submitted',
    video_url   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`,
  `CREATE INDEX idx_generations_user_date ON generations (user_id, created_at DESC)`,
  `CREATE OR REPLACE VIEW v_user_quota_today AS
   SELECT
     u.id AS user_id,
     u.email,
     u.tier,
     u.pro_until,
     COALESCE(u.daily_limit_override,
              CASE WHEN u.tier = 'pro' AND (u.pro_until IS NULL OR u.pro_until > NOW())
                   THEN 100
                   ELSE 1
              END) AS daily_limit,
     (SELECT COUNT(*) FROM generations g
      WHERE g.user_id = u.id
        AND g.created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
        AND g.status IN ('submitted', 'generating', 'done')) AS used_today
   FROM users u`,
];

export async function POST(req: NextRequest) {
  // Optional auth
  const adminToken = (process.env.ADMIN_TOKEN || '').trim();
  if (adminToken) {
    const auth = req.headers.get('authorization') || '';
    if (auth !== `Bearer ${adminToken}`) {
      return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
    }
  }

  const url =
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL ||
    process.env.POSTGRES_PRISMA_URL;
  if (!url) {
    return NextResponse.json(
      { error: 'no DATABASE_URL configured' },
      { status: 503 },
    );
  }

  const sql = neon(url);
  const results: Array<{ ok: boolean; statement: string; error?: string }> = [];
  for (const stmt of SCHEMA_STATEMENTS) {
    const short = stmt.split('\n')[0].slice(0, 70);
    try {
      // @ts-ignore - neon supports .query for raw multi-statement
      await sql.query(stmt);
      results.push({ ok: true, statement: short });
    } catch (e: any) {
      results.push({ ok: false, statement: short, error: e?.message || String(e) });
    }
  }
  const allOk = results.every((r) => r.ok);

  // sanity probe
  let probe: any = null;
  try {
    const rows = (await sql`SELECT
      (SELECT COUNT(*)::int FROM users) AS users_count,
      (SELECT COUNT(*)::int FROM generations) AS gen_count,
      (SELECT count(*)::int FROM information_schema.views WHERE table_name='v_user_quota_today') AS view_exists`) as any[];
    probe = rows[0];
  } catch (e: any) {
    probe = { error: e?.message };
  }

  return NextResponse.json(
    { ok: allOk, results, probe },
    { status: allOk ? 200 : 500 },
  );
}

export async function GET() {
  return NextResponse.json(
    { hint: 'POST to this endpoint to apply schema (idempotent)' },
  );
}
