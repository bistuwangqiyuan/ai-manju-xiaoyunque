/**
 * GET /api/admin/debug — read DB rows directly to debug view freshness.
 * No auth (idempotent read-only).
 */
import { NextResponse } from 'next/server';
import { neon } from '@neondatabase/serverless';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function GET() {
  const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!url) return NextResponse.json({ error: 'no DATABASE_URL' });
  // Identify branch / database by host fingerprint (do NOT expose full URL)
  let hostFingerprint = '?';
  try {
    const u = new URL(url);
    hostFingerprint = u.hostname.split('.')[0] + '@' + (u.pathname || '/').slice(0, 20);
  } catch { /* ignore */ }
  const sql = neon(url);
  try {
    const users = (await sql`SELECT id, email, tier, pro_until, created_at FROM users ORDER BY id`) as any[];
    const gens = (await sql`SELECT id, user_id, task_id, status, created_at FROM generations ORDER BY id DESC LIMIT 10`) as any[];
    const quotaView = (await sql`SELECT user_id, email, daily_limit, used_today FROM v_user_quota_today ORDER BY user_id`) as any[];
    const utcNow = (await sql`SELECT NOW() AT TIME ZONE 'UTC' AS utc_now`) as any[];
    return NextResponse.json({
      hostFingerprint,
      hasDatabaseUrl: !!process.env.DATABASE_URL,
      hasPostgresUrl: !!process.env.POSTGRES_URL,
      hasPrismaUrl: !!process.env.POSTGRES_PRISMA_URL,
      hasNonPooling: !!process.env.POSTGRES_URL_NON_POOLING,
      utcNow: utcNow[0],
      users,
      gens,
      quotaView,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message }, { status: 500 });
  }
}
