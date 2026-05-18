/**
 * GET /api/proxy-video?url=<encodedVideoUrl>
 *
 * Streams a Skylark-generated video through our server so:
 *   1. Browser doesn't see the raw volcengine.cn URL (cleaner UX)
 *   2. No CORS issues (we control the Content-Type/Disposition)
 *   3. Allows direct <video src> playback + Save-As download
 *
 * Note: Skylark video URLs expire after 1h. Client should download or
 * play within that window after seeing status=done.
 */
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

// Whitelist only trusted Volcengine CDN hosts to prevent SSRF
const ALLOWED_HOSTS = [
  'tos-cn-i-',           // volc tos cn
  'volcengine.com',
  'volccdn.com',
  '.tos.cn-',
  'volc-image-i-',
];

function isAllowed(url: string): boolean {
  try {
    const u = new URL(url);
    if (u.protocol !== 'https:') return false;
    return ALLOWED_HOSTS.some((p) => u.hostname.includes(p));
  } catch {
    return false;
  }
}

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get('url');
  if (!url) return NextResponse.json({ error: 'url required' }, { status: 400 });
  if (!isAllowed(url)) {
    return NextResponse.json({ error: 'url host not allowed' }, { status: 403 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      signal: AbortSignal.timeout(55_000),
      headers: { 'User-Agent': 'YunqueManhua/1.0' },
    });
  } catch (e: any) {
    return NextResponse.json(
      { error: `upstream fetch failed: ${e?.message || e}` },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { error: `upstream ${upstream.status}` },
      { status: 502 },
    );
  }

  const headers = new Headers();
  headers.set('Content-Type', upstream.headers.get('content-type') || 'video/mp4');
  const len = upstream.headers.get('content-length');
  if (len) headers.set('Content-Length', len);
  headers.set('Cache-Control', 'public, max-age=300');
  headers.set('Content-Disposition', 'inline; filename="yunque.mp4"');

  return new Response(upstream.body, { status: 200, headers });
}
