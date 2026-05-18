/**
 * POST /api/auth/login
 * Body: { email, password }
 * Effect: verify password, set session cookie, return { email, tier, quota }.
 */
import { NextRequest, NextResponse } from 'next/server';
import { verifyPassword, isValidEmail, setSessionCookie } from '@/lib/auth';
import { findUserByEmail, touchLastLogin, getQuota, isDbReady } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function POST(req: NextRequest) {
  try {
    if (!isDbReady()) {
      return NextResponse.json(
        { error: '数据库未配置' },
        { status: 503 },
      );
    }
    const body = await req.json();
    const email = String(body.email ?? '').trim().toLowerCase();
    const password = String(body.password ?? '');

    if (!isValidEmail(email) || password.length < 6) {
      return NextResponse.json({ error: '邮箱或密码错误' }, { status: 401 });
    }

    const user = await findUserByEmail(email);
    if (!user) {
      return NextResponse.json({ error: '邮箱或密码错误' }, { status: 401 });
    }
    const ok = await verifyPassword(password, user.password_hash);
    if (!ok) {
      return NextResponse.json({ error: '邮箱或密码错误' }, { status: 401 });
    }

    await touchLastLogin(user.id);
    const quota = await getQuota(user.id);

    const res = NextResponse.json({
      email: user.email,
      tier: user.tier,
      dailyLimit: quota?.daily_limit ?? 1,
      usedToday: quota?.used_today ?? 0,
    });
    await setSessionCookie(res, { uid: user.id, email: user.email });
    return res;
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message || 'login failed' },
      { status: 500 },
    );
  }
}
