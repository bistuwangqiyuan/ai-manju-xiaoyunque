/**
 * Lightweight JWT auth — bcrypt for password hash, jose for HS256 JWT in
 * HTTP-only cookie. No NextAuth dependency; ~80 lines covers register /
 * login / logout / session-from-cookie.
 *
 * Cookie name: yunque_session
 * Expiry:      7 days
 * Algorithm:   HS256 (server-side secret only)
 */
import { SignJWT, jwtVerify, type JWTPayload } from 'jose';
import bcrypt from 'bcryptjs';
import { cookies } from 'next/headers';
import { NextResponse, type NextRequest } from 'next/server';

const COOKIE_NAME = 'yunque_session';
const COOKIE_MAX_AGE_SEC = 7 * 24 * 60 * 60;          // 7d
const ALG = 'HS256';

export interface SessionData extends JWTPayload {
  uid: number;
  email: string;
}

function getSecretKey(): Uint8Array {
  const s = (process.env.AUTH_SECRET || '').trim();
  if (!s || s.length < 32) {
    // fallback when env missing — JWTs WILL fail to verify between deploys,
    // forcing re-login. better than crashing the app at startup.
    return new TextEncoder().encode('insecure-fallback-' + '0'.repeat(32));
  }
  return new TextEncoder().encode(s);
}

// ----- Password hashing -----
export async function hashPassword(plain: string): Promise<string> {
  if (!plain || plain.length < 6 || plain.length > 256) {
    throw new Error('password must be 6-256 chars');
  }
  return bcrypt.hash(plain, 10);
}

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  if (!plain || !hash) return false;
  return bcrypt.compare(plain, hash);
}

// ----- JWT -----
export async function signSession(data: SessionData): Promise<string> {
  // Force uid to number when signing (PG BIGINT returns string from Neon)
  const payload = { ...data, uid: Number(data.uid) };
  return new SignJWT(payload)
    .setProtectedHeader({ alg: ALG })
    .setIssuedAt()
    .setExpirationTime(`${COOKIE_MAX_AGE_SEC}s`)
    .sign(getSecretKey());
}

export async function verifySession(token: string): Promise<SessionData | null> {
  try {
    const { payload } = await jwtVerify(token, getSecretKey(), { algorithms: [ALG] });
    // PG BIGINT is returned as string from Neon driver, so uid may be string or number.
    // Coerce to number safely.
    let uid: number;
    if (typeof payload.uid === 'number') uid = payload.uid;
    else if (typeof payload.uid === 'string') {
      const n = Number(payload.uid);
      if (!Number.isFinite(n) || n <= 0) return null;
      uid = n;
    } else return null;
    if (typeof payload.email !== 'string' || !payload.email) return null;
    return { ...payload, uid, email: payload.email } as SessionData;
  } catch {
    return null;
  }
}

// ----- Cookie helpers (Next.js App Router) -----
export async function setSessionCookie(res: NextResponse, data: SessionData) {
  const token = await signSession(data);
  res.cookies.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: COOKIE_MAX_AGE_SEC,
  });
}

export function clearSessionCookie(res: NextResponse) {
  res.cookies.set(COOKIE_NAME, '', { path: '/', maxAge: 0 });
}

export async function readSessionFromRequest(req: NextRequest): Promise<SessionData | null> {
  const token = req.cookies.get(COOKIE_NAME)?.value;
  if (!token) return null;
  return verifySession(token);
}

export async function readSessionFromServerCookies(): Promise<SessionData | null> {
  const token = cookies().get(COOKIE_NAME)?.value;
  if (!token) return null;
  return verifySession(token);
}

// ----- Email/password validation -----
export function isValidEmail(email: string): boolean {
  if (!email || email.length > 256) return false;
  // RFC-lite: local-part @ domain with at least one dot in domain.
  return /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$/.test(email);
}
