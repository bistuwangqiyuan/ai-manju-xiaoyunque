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

// SCHEMA: free tier = 3 video/day, pro tier = unlimited as long as
// credit_balance_fen >= COST_PER_VIDEO_FEN. Charge 1.1× cost on submit.
// (1 fen = 0.01 yuan = 0.01 RMB)
const SCHEMA_STATEMENTS = [
  // Idempotent CREATE
  `CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tier          TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
    credit_balance_fen BIGINT NOT NULL DEFAULT 0,  -- in fen (0.01 RMB)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
  )`,
  // ALTERs for existing tables (idempotent column add)
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS credit_balance_fen BIGINT NOT NULL DEFAULT 0`,
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'free'`,
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ`,
  // Drop legacy columns we no longer use (if they exist)
  `ALTER TABLE users DROP COLUMN IF EXISTS pro_until`,
  `ALTER TABLE users DROP COLUMN IF EXISTS daily_limit_override`,
  `CREATE INDEX IF NOT EXISTS idx_users_email ON users (lower(email))`,
  `CREATE TABLE IF NOT EXISTS generations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id     TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    ratio       TEXT,
    duration    TEXT,
    status      TEXT NOT NULL DEFAULT 'submitted',
    video_url   TEXT,
    cost_fen    BIGINT,            -- charged amount (only for pro tier deductions)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`,
  `ALTER TABLE generations ADD COLUMN IF NOT EXISTS cost_fen BIGINT`,
  `CREATE INDEX IF NOT EXISTS idx_generations_user_date ON generations (user_id, created_at DESC)`,
  // Credit history (audit trail of recharges + deductions)
  `CREATE TABLE IF NOT EXISTS credit_ledger (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta_fen   BIGINT NOT NULL,      -- positive = recharge, negative = consumption
    balance_after_fen BIGINT NOT NULL,
    reason      TEXT NOT NULL,        -- 'recharge' | 'video_submit' | 'refund' | 'admin_adjust'
    task_id     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`,
  `CREATE INDEX IF NOT EXISTS idx_credit_ledger_user ON credit_ledger (user_id, created_at DESC)`,
  // Updated quota view: separate free-tier daily counter from pro credit_balance
  `DROP VIEW IF EXISTS v_user_quota_today`,
  `CREATE VIEW v_user_quota_today AS
   SELECT
     u.id AS user_id,
     u.email,
     u.tier,
     u.credit_balance_fen,
     CASE WHEN u.tier = 'pro' THEN -1 ELSE 3 END AS daily_limit,  -- -1 = unlimited (pro)
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
