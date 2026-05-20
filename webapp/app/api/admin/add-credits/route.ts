/**
 * POST /api/admin/add-credits
 * Body: { email, amountYuan }
 * Auth: Bearer ADMIN_TOKEN
 *
 * Adds credits to user balance (and auto-flips to 'pro' tier).
 * 1 yuan = 100 fen. amountYuan can be fractional (e.g. 55 → 5500 fen).
 */
import { NextRequest, NextResponse } from 'next/server';
import { addCreditsByEmail, isDbReady } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function POST(req: NextRequest) {
  const adminToken = (process.env.ADMIN_TOKEN || '').trim();
  if (!adminToken) {
    return NextResponse.json({ error: 'ADMIN_TOKEN env var not set' }, { status: 503 });
  }
  const auth = req.headers.get('authorization') || '';
  if (auth !== `Bearer ${adminToken}`) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  if (!isDbReady()) {
    return NextResponse.json({ error: 'no DATABASE_URL' }, { status: 503 });
  }
  const body = await req.json();
  const email = String(body.email ?? '').trim().toLowerCase();
  const amountYuan = Number(body.amountYuan ?? 0);
  if (!email || !Number.isFinite(amountYuan) || amountYuan <= 0) {
    return NextResponse.json({ error: 'email + amountYuan (>0) required' }, { status: 400 });
  }
  const amountFen = Math.round(amountYuan * 100);
  const reason = String(body.reason ?? 'admin_recharge').slice(0, 64);
  try {
    const r = await addCreditsByEmail(email, amountFen, reason);
    if (!r) return NextResponse.json({ error: 'user not found' }, { status: 404 });
    return NextResponse.json({
      ok: true,
      userId: r.userId,
      email,
      newBalance: r.balance / 100,
      addedYuan: amountYuan,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message }, { status: 500 });
  }
}
