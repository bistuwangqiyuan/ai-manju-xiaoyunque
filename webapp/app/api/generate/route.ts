/**
 * POST /api/generate
 *
 * Submit a new Skylark generation job. Returns task_id (~1-3s).
 * Client should then poll GET /api/status/[taskId] every 10-15s.
 *
 * Body: { prompt, ratio?, duration?, language?, imgUrls?, videoUrls? }
 * Response: 200 { taskId } | 400/429/500 { error, code? }
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
import crypto from 'node:crypto';

export const runtime = 'nodejs';      // need node crypto for HMAC
export const dynamic = 'force-dynamic';
// Vercel Hobby tier caps at 10s; submit only takes 1-3s so this is enough
export const maxDuration = 10;

// ----- in-memory rate limiter (per-IP per-day) -----
// 注意: serverless 冷启动会重置；生产建议接 Upstash Redis。
// 这里只做基础防护。
const RATE_BUCKET = new Map<string, { count: number; resetAt: number }>();
const DAY_MS = 24 * 60 * 60 * 1000;

function checkRateLimit(ip: string): { ok: boolean; remaining: number } {
  const limit = parseInt(process.env.DAILY_GENERATION_LIMIT || '0', 10);
  if (limit <= 0) return { ok: true, remaining: -1 };
  const now = Date.now();
  const entry = RATE_BUCKET.get(ip);
  if (!entry || entry.resetAt < now) {
    RATE_BUCKET.set(ip, { count: 1, resetAt: now + DAY_MS });
    return { ok: true, remaining: limit - 1 };
  }
  if (entry.count >= limit) return { ok: false, remaining: 0 };
  entry.count += 1;
  return { ok: true, remaining: limit - entry.count };
}

function getClientIp(req: NextRequest): string {
  const fwd = req.headers.get('x-forwarded-for');
  if (fwd) return fwd.split(',')[0].trim();
  return req.headers.get('x-real-ip') || 'unknown';
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const prompt: string = String(body.prompt ?? '').trim();
    if (!prompt) {
      return NextResponse.json({ error: 'prompt required' }, { status: 400 });
    }

    const ip = getClientIp(req);
    const rl = checkRateLimit(ip);
    if (!rl.ok) {
      return NextResponse.json(
        { error: 'daily generation limit reached', remaining: 0 },
        { status: 429 },
      );
    }

    const aigcProducerId =
      'yunque_' + crypto.randomBytes(8).toString('hex');

    const result = await submitGenerate({
      prompt,
      ratio: (body.ratio ?? '9:16') as Ratio,
      duration: (body.duration ?? '～15s') as Duration,
      language: (body.language ?? 'Chinese') as Language,
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

    return NextResponse.json(
      { taskId: result.taskId, remainingToday: rl.remaining },
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
