/** Backend origin for API + /storage assets.
 *
 * 优先级：
 *   1. NEXT_PUBLIC_BACKEND_URL 显式设置（构建/运行时注入）
 *   2. 本地开发模式 → http://localhost:8000
 *   3. 生产默认 → CloudBase BaaS HTTP 访问服务（/api/* 路由到 SCF 云函数 xyq-api）
 */
const PRODUCTION_FALLBACK_BACKEND =
  'https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com';

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  (process.env.NODE_ENV === 'development'
    ? 'http://localhost:8000'
    : PRODUCTION_FALLBACK_BACKEND);

export function assetUrl(path: string | null | undefined): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${BACKEND_URL}${path}`;
}

/** Video/cover URL: /storage needs API origin; /samples stay same-origin. */
export function mediaUrl(path: string | null | undefined): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  if (path.startsWith('/storage/')) return assetUrl(path);
  return path;
}
