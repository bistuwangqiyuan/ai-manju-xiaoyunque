'use client';

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export type Tier = 'free' | 'pro' | 'studio' | 'admin';

export interface User {
  id: number;
  email: string;
  credits_cents: number;
  tier: Tier;
  created_at: string;
}

export interface QualityBreakdown {
  // 四大主项（100-Pt Rubric）
  tech: number;        // / 40
  visual: number;      // / 30
  narrative: number;   // / 20
  genre: number;       // / 10
  // 工业指标子项
  arcface?: number;    // / 10 - 人物一致性
  clip_align?: number; // / 10 - 文图对齐
  aesthetic?: number;  // / 10 - LAION 美学
  hsv_color?: number;  // / 10 - 色彩
  motion?: number;     // / 10 - 运动 sweet-spot
}

export interface Job {
  id: number;
  title: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  progress: number;
  cost_cents: number;
  episodes: number;
  novel_excerpt: string;
  style: string;
  result_url: string | null;
  cover_url: string | null;
  error: string | null;
  quality_score: number | null;
  quality_breakdown: QualityBreakdown | null;
  quality_retries: number;
  created_at: string;
  updated_at: string;
}

export interface Quota {
  tier: Tier;
  credits_cents: number;
  free_daily_limit: number;
  free_used_today: number;
  free_remaining_today: number | null;
  cost_per_episode_cents: number;
  episode_base_cost_cents: number;
  profit_multiplier: number;
}

export interface JobLog {
  ts: string;
  level: string;
  message: string;
}

const TOKEN_KEY = 'xyq_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === 'undefined') return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(`${BACKEND_URL}/api${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || data.message || detail;
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  signup: (email: string, password: string) =>
    request<{ token: string; user: User }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>('/auth/me'),

  listJobs: () => request<Job[]>('/jobs'),
  getQuota: () => request<Quota>('/jobs/quota'),
  getJob: (id: number) => request<Job>(`/jobs/${id}`),
  getJobLogs: (id: number) => request<JobLog[]>(`/jobs/${id}/logs`),
  createJob: (payload: {
    title: string;
    novel_excerpt: string;
    style: string;
    episodes: number;
  }) =>
    request<Job>('/jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  cancelJob: (id: number) =>
    request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),

  createCheckout: (plan: string) =>
    request<{ url: string; mocked: boolean }>('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ plan }),
    }),
  topUp: (amount_cents: number) =>
    request<User>('/billing/topup', {
      method: 'POST',
      body: JSON.stringify({ amount_cents }),
    }),
};
