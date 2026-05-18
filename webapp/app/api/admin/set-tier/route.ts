/**
 * POST /api/admin/set-tier
 * Body: { email, tier: 'free'|'pro', proUntilDays?: number }
 * Protected: requires ADMIN_TOKEN env (sent as Authorization: Bearer <token>).
 * If ADMIN_TOKEN unset, endpoint refuses (more dangerous than schema migrate).
 */
import { NextRequest, NextResponse } from 'next/server';
import { neon } from '@neondatabase/serverless';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function POST(req: NextRequest) {
  const adminToken = (process.env.ADMIN_TOKEN || '').trim();
  if (!adminToken) {
    return NextResponse.json(
      { error: 'ADMIN_TOKEN env var not set — endpoint disabled for safety' },
      { status: 503 },
    );
  }
  const auth = req.headers.get('authorization') || '';
  if (auth !== `Bearer ${adminToken}`) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!url) return NextResponse.json({ error: 'no DATABASE_URL' }, { status: 503 });
  let hostFingerprint = '?';
  try {
    const u = new URL(url);
    hostFingerprint = u.hostname.split('.')[0] + '@' + (u.pathname || '/').slice(0, 20);
  } catch { /* ignore */ }

  const body = await req.json();
  const email = String(body.email ?? '').trim().toLowerCase();
  const tier = String(body.tier ?? '').trim();
  const proUntilDays = Number(body.proUntilDays ?? 30);
  if (!email || !['free', 'pro'].includes(tier)) {
    return NextResponse.json({ error: 'email + tier ∈ {free, pro} required' }, { status: 400 });
  }

  const sql = neon(url);
  if (tier === 'pro') {
    const rows = (await sql`
      UPDATE users
      SET tier = 'pro',
          pro_until = NOW() + (${proUntilDays}::int * INTERVAL '1 day')
      WHERE lower(email) = ${email}
      RETURNING id, email, tier, pro_until
    `) as any[];
    if (rows.length === 0) {
      return NextResponse.json({ error: 'user not found', hostFingerprint }, { status: 404 });
    }
    return NextResponse.json({ ok: true, user: rows[0], hostFingerprint });
  } else {
    const rows = (await sql`
      UPDATE users
      SET tier = 'free', pro_until = NULL
      WHERE lower(email) = ${email}
      RETURNING id, email, tier, pro_until
    `) as any[];
    if (rows.length === 0) {
      return NextResponse.json({ error: 'user not found' }, { status: 404 });
    }
    return NextResponse.json({ ok: true, user: rows[0] });
  }
}
