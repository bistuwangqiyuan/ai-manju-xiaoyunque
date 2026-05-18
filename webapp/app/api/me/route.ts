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
    return NextResponse.json({
      authenticated: true,
      email: session.email,
      tier: 'free',
      dailyLimit: 3,
      usedToday: 0,
      creditBalance: 0,
      costPerVideo: 5.50,
      dbReady: false,
    });
  }
  const quota = await getQuota(session.uid);
  if (!quota) {
    return NextResponse.json({ authenticated: false });
  }
  const usedToday = Number(quota.used_today) || 0;
  const dailyLimit = Number(quota.daily_limit) || 3;
  const creditBalanceFen = Number(quota.credit_balance_fen) || 0;
  return NextResponse.json({
    authenticated: true,
    email: quota.email,
    tier: quota.tier,
    dailyLimit,                                  // -1 means unlimited (pro)
    usedToday,
    creditBalance: creditBalanceFen / 100,       // ¥
    costPerVideo: 5.50,                          // ¥ per video for pro tier
  });
}
