'use client';

import { BACKEND_URL, assetUrl } from './backend-url';

export { BACKEND_URL, assetUrl };

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
  genre?: string;
  mode?: 'excerpt' | 'theme' | 'novel';
  theme?: string | null;
  language?: string;
  result_url: string | null;
  cover_url: string | null;
  error: string | null;
  quality_score: number | null;
  quality_breakdown: QualityBreakdown | null;
  quality_retries: number;
  current_step: number;
  step_artifacts: Record<string, unknown> | null;
  pipeline_version: string;
  scores_7d: Record<string, number> | null;
  human_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface Shot {
  id: number;
  job_id: number;
  episode_id: string;
  shot_id: number;
  duration_s: number;
  description: string | null;
  shot_type: string;
  status: string;
  result_url: string | null;
  canonical_image_url: string | null;
  score_7d: Record<string, number> | null;
  overall_score: number | null;
  passed: boolean;
  repair_iters: number;
  repair_routes: string[] | null;
  feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface Genre {
  id: string;
  name_zh: string;
  name_en: string;
  description: string;
  style_id: string;
  aspect_ratio: string;
  default_episodes: number;
  sample_themes: string[];
  preview_video_url?: string | null;
  preview_cover_url?: string | null;
}

export interface BatchItem {
  id: number;
  batch_id: number;
  source_url: string;
  result_url: string | null;
  params: Record<string, unknown> | null;
  status: string;
  score_7d: Record<string, number> | null;
  overall_score: number | null;
  passed: boolean;
  repair_iters: number;
  feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface Batch {
  id: number;
  name: string;
  style: string;
  genre: string;
  aspect_ratio: string;
  status: string;
  total_items: number;
  finished_items: number;
  params: Record<string, unknown> | null;
  items: BatchItem[];
  created_at: string;
  updated_at: string;
}

export interface ExportResult {
  platform: string;
  url: string;
  cover_url: string | null;
  caption: string | null;
  hashtags: string[];
  duration_s: number | null;
  width: number | null;
  height: number | null;
}

export interface MarketingCopy {
  title: string;
  summary: string;
  hook_copy: string;
  hashtags: string[];
  language: string;
}

export interface JobVersion {
  id: number;
  version_no: number;
  quality_score: number | null;
  scores_7d: Record<string, number> | null;
  result_url: string | null;
  cover_url: string | null;
  notes: string | null;
  created_at: string;
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
    novel_excerpt?: string;
    style: string;
    episodes: number;
    genre?: string;
    mode?: 'excerpt' | 'theme' | 'novel';
    theme?: string | null;
    language?: string;
  }) =>
    request<Job>('/jobs', {
      method: 'POST',
      body: JSON.stringify({
        novel_excerpt: '',
        ...payload,
      }),
    }),
  cancelJob: (id: number) =>
    request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
  approveJob: (id: number) =>
    request<Job>(`/jobs/${id}/approve`, { method: 'POST' }),
  rerollJob: (id: number, shotId?: string) =>
    request<Job>(`/jobs/${id}/reroll`, {
      method: 'POST',
      body: JSON.stringify({ shot_id: shotId ?? null }),
    }),
  getJobVersions: (id: number) =>
    request<JobVersion[]>(`/jobs/${id}/versions`),
  rollbackVersion: (id: number, targetVersionNo: number, notes?: string) =>
    request<Job>(`/jobs/${id}/versions/rollback`, {
      method: 'POST',
      body: JSON.stringify({ target_version_no: targetVersionNo, notes: notes ?? null }),
    }),

  // ---- Shots (per-shot QA & repair) ----
  listShots: (jobId: number) =>
    request<Shot[]>(`/jobs/${jobId}/shots`),
  getShot: (jobId: number, shotId: number) =>
    request<Shot>(`/jobs/${jobId}/shots/${shotId}`),
  rerollShot: (jobId: number, shotId: number) =>
    request<Shot>(`/jobs/${jobId}/shots/${shotId}/reroll`, { method: 'POST' }),
  repairShot: (jobId: number, shotId: number, route?: string, feedback?: string) =>
    request<Shot>(`/jobs/${jobId}/shots/${shotId}/repair`, {
      method: 'POST',
      body: JSON.stringify({ route: route ?? null, feedback: feedback ?? null }),
    }),
  approveShot: (jobId: number, shotId: number) =>
    request<Shot>(`/jobs/${jobId}/shots/${shotId}/approve`, { method: 'POST' }),

  // ---- Genres / templates ----
  listGenres: () => request<Genre[]>('/genres'),
  getGenre: (id: string) => request<Genre>(`/genres/${id}`),

  // ---- Library ----
  listLibraryCharacters: () => request<any[]>('/library/characters'),
  getLibraryCharacter: (charId: string) =>
    request<any>(`/library/characters/${charId}`),
  listLibraryScenes: (category?: string) =>
    request<any[]>(`/library/scenes${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  getLibraryScene: (sceneId: string) =>
    request<any>(`/library/scenes/${sceneId}`),
  listExpressionKeys: () => request<any[]>('/library/expressions'),
  listActionKeys: () => request<any[]>('/library/actions'),
  listWardrobeKeys: () => request<any[]>('/library/wardrobe'),

  // ---- Batch redraw ----
  listBatches: () => request<Batch[]>('/batch'),
  getBatch: (id: number) => request<Batch>(`/batch/${id}`),
  createBatch: (payload: {
    name: string;
    style: string;
    genre: string;
    aspect_ratio: string;
    source_urls: string[];
    params?: Record<string, unknown>;
  }) =>
    request<Batch>('/batch', { method: 'POST', body: JSON.stringify(payload) }),
  runBatch: (id: number) =>
    request<Batch>(`/batch/${id}/run`, { method: 'POST' }),
  redrawBatchItem: (batchId: number, itemId: number) =>
    request<BatchItem>(`/batch/${batchId}/items/${itemId}/redraw`, { method: 'POST' }),
  exportBatch: (id: number) =>
    request<{ url: string; items: number }>(`/batch/${id}/export`),
  uploadBatchFiles: async (files: File[]) => {
    const token = getToken();
    const form = new FormData();
    for (const f of files) form.append('files', f);
    const res = await fetch(`${BACKEND_URL}/api/batch/upload`, {
      method: 'POST',
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error(`上传失败 (${res.status})`);
    return (await res.json()) as Batch;
  },

  // ---- Advanced (continuation / restyle / translate / export / marketing) ----
  exportPlatforms: (
    jobId: number,
    platforms: string[],
    options?: { add_watermark?: boolean; account_handle?: string }
  ) =>
    request<ExportResult[]>(`/jobs/${jobId}/export`, {
      method: 'POST',
      body: JSON.stringify({
        platforms,
        add_watermark: options?.add_watermark ?? true,
        account_handle: options?.account_handle ?? null,
      }),
    }),
  getMarketingCopy: (jobId: number) =>
    request<MarketingCopy>(`/jobs/${jobId}/marketing`),
  continueJob: (jobId: number, extraEpisodes: number, direction?: string) =>
    request<Job>(`/jobs/${jobId}/continue`, {
      method: 'POST',
      body: JSON.stringify({ extra_episodes: extraEpisodes, direction: direction ?? null }),
    }),
  restyleJob: (jobId: number, target: 'jpn_anime' | 'guoman' | 'realistic' | 'manhwa') =>
    request<Job>(`/jobs/${jobId}/restyle`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    }),
  translateJob: (jobId: number, target_lang: string, burn_subtitle = true) =>
    request<Job>(`/jobs/${jobId}/translate`, {
      method: 'POST',
      body: JSON.stringify({ target_lang, burn_subtitle }),
    }),
  getInteractionGraph: (jobId: number) =>
    request<{ nodes: string[]; edges: any[] }>(`/jobs/${jobId}/interaction-graph`),

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
