/**
 * GET /api/me — current session + quota.
 *
 * Response 200: { authenticated: true, email, tier, dailyLimit, usedToday, proUntil }
 * Response 200 (no session): { authenticated: false }
 */
import { NextRequest, NextResponse } from 'next/server';
import { readSessionFromRequest } from '@/lib/auth';
import { getQuota, isDbReady } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function GET(req: NextRequest) {
  const session = await readSessionFromRequest(req);
  if (!session) {
    return NextResponse.json({ authenticated: false });
  }
  if (!isDbReady()) {
    // session valid but db missing — degrade gracefully
    return NextResponse.json({
      authenticated: true,
      email: session.email,
      tier: 'free',
      dailyLimit: 1,
      usedToday: 0,
      dbReady: false,
    });
  }
  const quota = await getQuota(session.uid);
  if (!quota) {
    // user row vanished (e.g. admin deleted)
    return NextResponse.json({ authenticated: false });
  }
  // Coerce PG bigint -> number (Neon serverless returns bigint as string).
  const usedToday = Number(quota.used_today) || 0;
  const dailyLimit = Number(quota.daily_limit) || 1;
  return NextResponse.json({
    authenticated: true,
    email: quota.email,
    tier: quota.tier,
    dailyLimit,
    usedToday,
    proUntil: quota.pro_until,
  });
}
