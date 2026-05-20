/**
 * POST /api/generate
 *
 * Authenticated endpoint. Requires session cookie.
 * Free tier: 1 video/day. Pro tier: 100 videos/day.
 * Quota: per UTC calendar day (resets at 00:00 UTC).
 *
 * Body: { prompt, ratio?, duration?, language?, imgUrls?, videoUrls? }
 * Response:
 *   200 { taskId, dailyLimit, usedToday }
 *   401 { error: '未登录, 请先注册或登录' }
 *   429 { error: '今日额度已用完', dailyLimit, usedToday, tier }
 *   503 { error: '数据库未配置' }
 */
import { NextRequest, NextResponse } from 'next/server';
import {
  submitGenerate,
  SkylarkError,
  SkylarkAuditError,
  SkylarkRetryable,
  type Ratio,
  type Duration,
  type Language,
} from '@/lib/skylark';
import { readSessionFromRequest } from '@/lib/auth';
import {
  getQuota,
  recordGeneration,
  debitCredits,
  isDbReady,
  COST_PER_VIDEO_FEN,
  FREE_TIER_DAILY,
} from '@/lib/db';
import crypto from 'node:crypto';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function POST(req: NextRequest) {
  try {
    // ----- 1. 鉴权 -----
    const session = await readSessionFromRequest(req);
    if (!session) {
      return NextResponse.json(
        { error: '未登录, 请先注册或登录', requireAuth: true },
        { status: 401 },
      );
    }

    if (!isDbReady()) {
      return NextResponse.json(
        { error: '数据库未配置 — 请管理员先在 Vercel 启用 Neon' },
        { status: 503 },
      );
    }

    // ----- 2. 额度/余额检查 -----
    const quota = await getQuota(session.uid);
    if (!quota) {
      return NextResponse.json({ error: '用户不存在', requireAuth: true }, { status: 401 });
    }
    if (quota.tier === 'free') {
      // Free: enforce daily limit (default 3)
      if (quota.used_today >= quota.daily_limit) {
        return NextResponse.json(
          {
            error: `今日免费额度已用完 (${quota.used_today}/${quota.daily_limit})。明日 UTC 00:00 重置，或充值升级 Pro 享无限生成（按 ¥5.50/视频 扣费）`,
            tier: 'free',
            dailyLimit: quota.daily_limit,
            usedToday: quota.used_today,
            quotaExhausted: true,
          },
          { status: 429 },
        );
      }
    } else {
      // Pro: check credit balance
      if (quota.credit_balance_fen < COST_PER_VIDEO_FEN) {
        return NextResponse.json(
          {
            error: `余额不足: 当前余额 ¥${(quota.credit_balance_fen / 100).toFixed(2)}, 单次生成需 ¥${(COST_PER_VIDEO_FEN / 100).toFixed(2)}。请充值后再生成`,
            tier: 'pro',
            creditBalance: quota.credit_balance_fen / 100,
            costPerVideo: COST_PER_VIDEO_FEN / 100,
            balanceInsufficient: true,
          },
          { status: 402 },   // Payment Required
        );
      }
    }

    // ----- 3. 请求参数 -----
    const body = await req.json();
    const prompt: string = String(body.prompt ?? '').trim();
    if (!prompt) {
      return NextResponse.json({ error: 'prompt required' }, { status: 400 });
    }

    const ratio = (body.ratio ?? '9:16') as Ratio;
    const duration = (body.duration ?? '～15s') as Duration;
    const language = (body.language ?? 'Chinese') as Language;

    const aigcProducerId =
      'yunque_' + crypto.randomBytes(8).toString('hex');

    // ----- 4. 提交 Skylark -----
    const result = await submitGenerate({
      prompt,
      ratio,
      duration,
      language,
      enableWatermark: false,
      imgUrls: Array.isArray(body.imgUrls) ? body.imgUrls : undefined,
      videoUrls: Array.isArray(body.videoUrls) ? body.videoUrls : undefined,
      aigcMeta: {
        contentProducer: process.env.AIGC_CONTENT_PRODUCER || 'yunque-manhua',
        producerId: aigcProducerId,
        contentPropagator: process.env.AIGC_CONTENT_PROPAGATOR || 'yunque-web',
        propagateId: aigcProducerId,
      },
    });

    // ----- 5. 写库 + 扣费 (pro tier) -----
    const costFen = quota.tier === 'pro' ? COST_PER_VIDEO_FEN : 0;
    await recordGeneration({
      userId: session.uid,
      taskId: result.taskId,
      prompt,
      ratio,
      duration,
      status: 'submitted',
      costFen: costFen || undefined,
    });
    let newBalance = quota.credit_balance_fen;
    if (quota.tier === 'pro') {
      try {
        newBalance = await debitCredits(session.uid, COST_PER_VIDEO_FEN, result.taskId);
      } catch (e: any) {
        // race condition: balance went insufficient between check and debit
        return NextResponse.json(
          { error: '余额不足 (并发扣费失败)', balanceInsufficient: true },
          { status: 402 },
        );
      }
    }

    return NextResponse.json(
      {
        taskId: result.taskId,
        tier: quota.tier,
        dailyLimit: quota.daily_limit,
        usedToday: quota.used_today + 1,
        creditBalance: newBalance / 100,
        chargedFen: costFen,
      },
      { status: 200 },
    );
  } catch (e: any) {
    if (e instanceof SkylarkAuditError) {
      return NextResponse.json(
        {
          error: 'content审核未通过 — 请尝试更柔和的表达',
          code: e.code,
          requestId: e.requestId,
        },
        { status: 422 },
      );
    }
    if (e instanceof SkylarkRetryable) {
      return NextResponse.json(
        { error: '火山方舟当前并发饱和，请 1 分钟后重试', code: e.code },
        { status: 503 },
      );
    }
    if (e instanceof SkylarkError) {
      return NextResponse.json(
        { error: e.message, code: e.code, requestId: e.requestId },
        { status: 500 },
      );
    }
    return NextResponse.json(
      { error: e?.message || String(e) },
      { status: 500 },
    );
  }
}
