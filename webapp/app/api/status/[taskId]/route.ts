/**
 * GET /api/status/[taskId]
 *
 * Query Skylark task status. Cheap (~1-3s).
 * Response statuses:
 *   { status: 'in_queue'|'processing'|'generating', ... }   keep polling
 *   { status: 'done', videoUrl, outputDurationSeconds }     ready to play
 *   { status: 'expired'|'not_found' }                       hard error
 */
import { NextResponse } from 'next/server';
import { queryStatus, SkylarkError } from '@/lib/skylark';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

export async function GET(
  _req: Request,
  { params }: { params: { taskId: string } },
) {
  try {
    const taskId = params.taskId;
    if (!taskId || taskId.length < 8) {
      return NextResponse.json({ error: 'invalid taskId' }, { status: 400 });
    }
    const result = await queryStatus(taskId);
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
