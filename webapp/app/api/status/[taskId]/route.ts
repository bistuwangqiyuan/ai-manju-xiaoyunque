/**
 * GET /api/status/[taskId]
 *
 * Query Skylark task status. Cheap (~1-3s).
 * Response statuses:
 *   { status: 'in_queue'|'processing'|'generating', ... }   keep polling
 *   { status: 'done', videoUrl, outputDurationSeconds }     ready to play
 *   { status: 'expired'|'not_found' }                       hard error
 */
import { NextRequest, NextResponse } from 'next/server';
import { queryStatus, SkylarkError } from '@/lib/skylark';
import { readSessionFromRequest } from '@/lib/auth';
import { updateGenerationStatus } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 10;

export async function GET(
  req: NextRequest,
  { params }: { params: { taskId: string } },
) {
  try {
    // require auth to prevent open status enumeration
    const session = await readSessionFromRequest(req);
    if (!session) {
      return NextResponse.json(
        { error: '未登录', requireAuth: true },
        { status: 401 },
      );
    }
    const taskId = params.taskId;
    if (!taskId || taskId.length < 8) {
      return NextResponse.json({ error: 'invalid taskId' }, { status: 400 });
    }
    const result = await queryStatus(taskId);
    // best-effort persist status into DB (don't fail user if DB hiccups)
    try {
      await updateGenerationStatus(taskId, result.status, result.videoUrl ?? null);
    } catch {/* ignore */}
    return NextResponse.json(
      {
        taskId: result.taskId,
        status: result.status,
        videoUrl: result.videoUrl,
        outputDurationSeconds: result.outputDurationSeconds,
      },
      { status: 200 },
    );
  } catch (e: any) {
    if (e instanceof SkylarkError) {
      return NextResponse.json(
        { error: e.message, code: e.code },
        { status: 500 },
      );
    }
    return NextResponse.json(
      { error: e?.message || String(e) },
      { status: 500 },
    );
  }
}
