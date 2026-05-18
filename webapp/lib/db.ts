/**
 * Neon Postgres client (Vercel-Neon integration).
 *
 * Vercel auto-injects these env vars when the Neon integration is connected:
 *   DATABASE_URL                       (pooled, recommended)
 *   DATABASE_URL_UNPOOLED              (direct connection, for migrations)
 *   POSTGRES_URL / POSTGRES_PRISMA_URL ( aliases)
 *
 * We use @neondatabase/serverless because it works on Vercel Edge & Node runtimes.
 */
import { neon } from '@neondatabase/serverless';

/**
 * Fresh neon() per call to avoid module-cached state issues that surfaced
 * during E2E (reads stale after writes, even on same connection string).
 * Reads always re-resolve env vars too (Vercel may rotate them).
 */
function getUrl(): string {
  // Prefer NON_POOLING for reads — pgbouncer/pooler can return stale snapshots
  // across pooled connections. Direct connection guarantees latest commit.
  return (
    process.env.POSTGRES_URL_NON_POOLING ||
    process.env.DATABASE_URL_UNPOOLED ||
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL ||
    process.env.POSTGRES_PRISMA_URL ||
    ''
  );
}

export function isDbReady(): boolean {
  return Boolean(getUrl());
}

// Dynamic proxy: each tagged-template call creates a new neon() instance.
// Type matches @neondatabase/serverless's NeonQueryFunction signature.
export const sql: any = (strings: TemplateStringsArray, ...values: any[]) => {
  const url = getUrl();
  if (!url) throw new Error('db not configured');
  return (neon(url) as any)(strings, ...values);
};

// ----- Pricing constants -----
// Cost from Volcengine Skylark Agent 2.0 (fast 720p) ~ ¥5 per 15s video.
// We charge 1.1× = ¥5.5 = 550 fen per video.
export const COST_PER_VIDEO_FEN = 550;          // ¥5.50 charged
export const ACTUAL_COST_PER_VIDEO_FEN = 500;   // ¥5.00 our cost
export const MARKUP = 1.10;
export const FREE_TIER_DAILY = 3;

// ----- DTOs -----
export interface UserRow {
  id: number;
  email: string;
  password_hash: string;
  tier: 'free' | 'pro';
  credit_balance_fen: number;
  created_at: string;
  last_login_at: string | null;
}

export interface UserQuotaRow {
  user_id: number;
  email: string;
  tier: 'free' | 'pro';
  credit_balance_fen: number;
  daily_limit: number;             // -1 means unlimited (pro)
  used_today: number;
}

// ----- Queries -----
export async function findUserByEmail(email: string): Promise<UserRow | null> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    SELECT id, email, password_hash, tier, credit_balance_fen::bigint AS credit_balance_fen, created_at, last_login_at
    FROM users WHERE lower(email) = lower(${email}) LIMIT 1
  `) as unknown as UserRow[];
  if (rows[0]) rows[0].credit_balance_fen = Number(rows[0].credit_balance_fen) || 0;
  return rows[0] || null;
}

export async function findUserById(id: number): Promise<UserRow | null> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    SELECT id, email, password_hash, tier, credit_balance_fen::bigint AS credit_balance_fen, created_at, last_login_at
    FROM users WHERE id = ${id} LIMIT 1
  `) as unknown as UserRow[];
  if (rows[0]) rows[0].credit_balance_fen = Number(rows[0].credit_balance_fen) || 0;
  return rows[0] || null;
}

export async function createUser(email: string, passwordHash: string): Promise<UserRow> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    INSERT INTO users (email, password_hash) VALUES (${email}, ${passwordHash})
    RETURNING id, email, password_hash, tier, credit_balance_fen::bigint AS credit_balance_fen, created_at, last_login_at
  `) as unknown as UserRow[];
  rows[0].credit_balance_fen = Number(rows[0].credit_balance_fen) || 0;
  return rows[0];
}

export async function touchLastLogin(userId: number): Promise<void> {
  if (!isDbReady()) return;
  await sql`UPDATE users SET last_login_at = NOW() WHERE id = ${userId}`;
}

export async function getQuota(userId: number): Promise<UserQuotaRow> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    SELECT
      u.id AS user_id,
      u.email,
      u.tier,
      u.credit_balance_fen::bigint AS credit_balance_fen,
      CASE WHEN u.tier = 'pro' THEN -1 ELSE ${FREE_TIER_DAILY} END::int AS daily_limit,
      (SELECT COUNT(*)::int FROM generations g
       WHERE g.user_id = u.id
         AND g.created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
         AND g.status IN ('submitted','generating','done')) AS used_today
    FROM users u WHERE u.id = ${userId} LIMIT 1
  `) as unknown as UserQuotaRow[];
  if (!rows[0]) return null as unknown as UserQuotaRow;
  const row = rows[0];
  row.used_today = Number(row.used_today) || 0;
  row.daily_limit = Number(row.daily_limit) || FREE_TIER_DAILY;
  row.credit_balance_fen = Number(row.credit_balance_fen) || 0;
  return row;
}

/**
 * Atomic credit deduction. Returns updated balance, or throws if insufficient.
 * Used by /api/generate for pro-tier users.
 */
export async function debitCredits(userId: number, amountFen: number, taskId: string): Promise<number> {
  if (!isDbReady()) throw new Error('db not configured');
  if (amountFen <= 0) throw new Error('amountFen must be positive');
  // Single-statement atomic UPDATE — fails (returns 0 rows) if balance insufficient
  const rows = (await sql`
    UPDATE users
    SET credit_balance_fen = credit_balance_fen - ${amountFen}
    WHERE id = ${userId} AND credit_balance_fen >= ${amountFen}
    RETURNING credit_balance_fen::bigint AS new_balance
  `) as any[];
  if (!rows[0]) {
    throw new Error('insufficient_credit');
  }
  const newBalance = Number(rows[0].new_balance) || 0;
  // Audit log
  await sql`
    INSERT INTO credit_ledger (user_id, delta_fen, balance_after_fen, reason, task_id)
    VALUES (${userId}, ${-amountFen}, ${newBalance}, 'video_submit', ${taskId})
  `;
  return newBalance;
}

/**
 * Admin: add credits (recharge) to a user, returns new balance.
 */
export async function addCreditsByEmail(email: string, amountFen: number, reason = 'recharge'): Promise<{balance: number; userId: number} | null> {
  if (!isDbReady()) throw new Error('db not configured');
  if (amountFen <= 0) throw new Error('amountFen must be positive');
  const rows = (await sql`
    UPDATE users
    SET credit_balance_fen = credit_balance_fen + ${amountFen},
        tier = 'pro'
    WHERE lower(email) = lower(${email})
    RETURNING id, credit_balance_fen::bigint AS new_balance
  `) as any[];
  if (!rows[0]) return null;
  const userId = Number(rows[0].id);
  const newBalance = Number(rows[0].new_balance) || 0;
  await sql`
    INSERT INTO credit_ledger (user_id, delta_fen, balance_after_fen, reason)
    VALUES (${userId}, ${amountFen}, ${newBalance}, ${reason})
  `;
  return { balance: newBalance, userId };
}

export async function recordGeneration(opts: {
  userId: number;
  taskId: string;
  prompt: string;
  ratio?: string;
  duration?: string;
  status?: string;
  costFen?: number;
}): Promise<void> {
  if (!isDbReady()) throw new Error('db not configured');
  await sql`
    INSERT INTO generations (user_id, task_id, prompt, ratio, duration, status, cost_fen)
    VALUES (${opts.userId}, ${opts.taskId}, ${opts.prompt},
            ${opts.ratio || null}, ${opts.duration || null},
            ${opts.status || 'submitted'},
            ${opts.costFen ?? null})
  `;
}

export async function updateGenerationStatus(taskId: string, status: string, videoUrl?: string | null): Promise<void> {
  if (!isDbReady()) return;
  await sql`
    UPDATE generations SET status = ${status}, video_url = ${videoUrl ?? null}
    WHERE task_id = ${taskId}
  `;
}

export async function listUserGenerations(userId: number, limit = 20): Promise<Array<{
  task_id: string;
  prompt: string;
  status: string;
  video_url: string | null;
  created_at: string;
}>> {
  if (!isDbReady()) return [];
  return (await sql`
    SELECT task_id, prompt, status, video_url, created_at
    FROM generations WHERE user_id = ${userId}
    ORDER BY created_at DESC LIMIT ${limit}
  `) as any;
}
