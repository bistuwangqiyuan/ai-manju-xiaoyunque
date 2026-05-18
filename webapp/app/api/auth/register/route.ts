/**
 * POST /api/auth/register
 * Body: { email, password }
 * Effect: insert user, set session cookie, return { email, tier, quota }.
 */
import { NextRequest, NextResponse } from 'next/server';
import { hashPassword, isValidEmail, setSessionCookie } from '@/lib/auth';
import { findUserByEmail, createUser, getQuota, isDbReady } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function POST(req: NextRequest) {
  try {
    if (!isDbReady()) {
      return NextResponse.json(
        { error: '数据库未配置 — 请管理员先在 Vercel Storage 启用 Neon' },
        { status: 503 },
      );
    }
    const body = await req.json();
    const email = String(body.email ?? '').trim().toLowerCase();
    const password = String(body.password ?? '');

    if (!isValidEmail(email)) {
      return NextResponse.json({ error: '邮箱格式无效' }, { status: 400 });
    }
    if (password.length < 6) {
      return NextResponse.json({ error: '密码至少 6 位' }, { status: 400 });
    }
    if (password.length > 256) {
      return NextResponse.json({ error: '密码过长' }, { status: 400 });
    }

    const existing = await findUserByEmail(email);
    if (existing) {
      return NextResponse.json({ error: '邮箱已注册，请直接登录' }, { status: 409 });
    }

    const passwordHash = await hashPassword(password);
    const user = await createUser(email, passwordHash);
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
      { error: e?.message || 'register failed' },
      { status: 500 },
    );
  }
}
