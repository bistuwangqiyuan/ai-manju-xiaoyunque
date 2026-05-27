/** Backend origin for API + /storage assets.
 *
 * All-in-one (Caddy :8080): leave NEXT_PUBLIC_BACKEND_URL empty → same-origin /api/*
 * Local dev: set NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 in web/.env.local
 */
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

export function assetUrl(path: string | null | undefined): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${BACKEND_URL}${path}`;
}
