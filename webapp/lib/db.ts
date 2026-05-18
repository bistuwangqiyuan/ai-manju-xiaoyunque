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

// ----- DTOs -----
export interface UserRow {
  id: number;
  email: string;
  password_hash: string;
  tier: 'free' | 'pro';
  pro_until: string | null;
  daily_limit_override: number | null;
  created_at: string;
  last_login_at: string | null;
}

export interface UserQuotaRow {
  user_id: number;
  email: string;
  tier: 'free' | 'pro';
  pro_until: string | null;
  daily_limit: number;
  used_today: number;
}

// ----- Queries -----
export async function findUserByEmail(email: string): Promise<UserRow | null> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    SELECT id, email, password_hash, tier, pro_until, daily_limit_override, created_at, last_login_at
    FROM users WHERE lower(email) = lower(${email}) LIMIT 1
  `) as unknown as UserRow[];
  return rows[0] || null;
}

export async function findUserById(id: number): Promise<UserRow | null> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    SELECT id, email, password_hash, tier, pro_until, daily_limit_override, created_at, last_login_at
    FROM users WHERE id = ${id} LIMIT 1
  `) as unknown as UserRow[];
  return rows[0] || null;
}

export async function createUser(email: string, passwordHash: string): Promise<UserRow> {
  if (!isDbReady()) throw new Error('db not configured');
  const rows = (await sql`
    INSERT INTO users (email, password_hash) VALUES (${email}, ${passwordHash})
    RETURNING id, email, password_hash, tier, pro_until, daily_limit_override, created_at, last_login_at
  `) as unknown as UserRow[];
  return rows[0];
}

export async function touchLastLogin(userId: number): Promise<void> {
  if (!isDbReady()) return;
  await sql`UPDATE users SET last_login_at = NOW() WHERE id = ${userId}`;
}

export async function getQuota(userId: number): Promise<UserQuotaRow> {
  if (!isDbReady()) throw new Error('db not configured');
  // Bypass view due to suspected planner issue with correlated subquery
  // when filtered by WHERE — query users + count generations explicitly.
  const rows = (await sql`
    SELECT
      u.id AS user_id,
      u.email,
      u.tier,
      u.pro_until,
      COALESCE(u.daily_limit_override,
               CASE WHEN u.tier = 'pro' AND (u.pro_until IS NULL OR u.pro_until > NOW())
                    THEN 100
                    ELSE 1
               END)::int AS daily_limit,
      (SELECT COUNT(*)::int FROM generations g
       WHERE g.user_id = u.id
         AND g.created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
         AND g.status IN ('submitted','generating','done')) AS used_today
    FROM users u WHERE u.id = ${userId} LIMIT 1
  `) as unknown as UserQuotaRow[];
  if (!rows[0]) return null as unknown as UserQuotaRow;
  // Coerce bigint→number defensively
  const row = rows[0];
  row.used_today = Number(row.used_today) || 0;
  row.daily_limit = Number(row.daily_limit) || 1;
  return row;
}

export async function recordGeneration(opts: {
  userId: number;
  taskId: string;
  prompt: string;
  ratio?: string;
  duration?: string;
  status?: string;
}): Promise<void> {
  if (!isDbReady()) throw new Error('db not configured');
  await sql`
    INSERT INTO generations (user_id, task_id, prompt, ratio, duration, status)
    VALUES (${opts.userId}, ${opts.taskId}, ${opts.prompt},
            ${opts.ratio || null}, ${opts.duration || null},
            ${opts.status || 'submitted'})
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
