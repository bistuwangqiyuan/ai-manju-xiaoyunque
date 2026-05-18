/**
 * Skylark Agent 2.0 = Seedance 2.0 fast 720p with reference — TypeScript client.
 *
 * 端口自 src/shell3_skylark_engine/client.py (Python production-verified, R1-R40 实测).
 *
 * 提供:
 *   submitGenerate(prompt, opts) → task_id   (~1s, fits Vercel 60s budget)
 *   queryStatus(task_id)         → status/data/video_url
 *   isTerminalDone, isTerminalError, isRunning   状态判断辅助
 *
 * 不做的:
 *   - 不做 wait_and_archive（轮询移到客户端）
 *   - 不做 storage archive（video_url 直接返给客户端，1h 有效）
 *   - 不做 Shell 5 master（webapp 仅展示 raw mp4）
 */
import { signRequest } from './volc-signer';

const SKYLARK_REQ_KEY = 'pippit_iv2v_v20_cvtob_with_vinput';
const API_VERSION = '2022-08-31';
const ACTION_SUBMIT = 'CVSync2AsyncSubmitTask';
const ACTION_QUERY = 'CVSync2AsyncGetResult';

export const RATIO_VALUES = ['16:9', '9:16', '4:3', '3:4'] as const;
export const DURATION_VALUES = ['～15s', '～30s', '40～60s'] as const;
export const LANGUAGE_VALUES = ['Chinese', 'English'] as const;
export const MAX_PROMPT_CHARS = 2000;
export const MAX_REFS_PER_REQUEST = 50;

export type Ratio = typeof RATIO_VALUES[number];
export type Duration = typeof DURATION_VALUES[number];
export type Language = typeof LANGUAGE_VALUES[number];

// retryable Volcengine error codes
const RETRYABLE_CODES = new Set([50429, 50430, 50500, 50501, 50511]);
// audit-fatal codes (don't retry, surface to user)
const AUDIT_FATAL_CODES = new Set([50411, 50412, 50413, 50512, 50513, 50514]);

export interface SubmitOptions {
  prompt: string;
  ratio?: Ratio;
  duration?: Duration;
  language?: Language;
  enableWatermark?: boolean;
  imgUrls?: string[];
  videoUrls?: string[];
  aigcMeta?: {
    contentProducer?: string;
    producerId?: string;
    contentPropagator?: string;
    propagateId?: string;
  };
}

export class SkylarkError extends Error {
  public code: number;
  public requestId?: string;
  constructor(message: string, code: number, requestId?: string) {
    super(message);
    this.name = 'SkylarkError';
    this.code = code;
    this.requestId = requestId;
  }
}

export class SkylarkAuditError extends SkylarkError {
  constructor(message: string, code: number, requestId?: string) {
    super(message, code, requestId);
    this.name = 'SkylarkAuditError';
  }
}

export class SkylarkRetryable extends SkylarkError {
  constructor(message: string, code: number) {
    super(message, code);
    this.name = 'SkylarkRetryable';
  }
}

interface VolcResponse<T = any> {
  code?: number;
  message?: string;
  request_id?: string;
  status?: number;
  data?: T;
}

async function httpPost(opts: {
  accessKey: string;
  secretKey: string;
  action: string;
  body: Record<string, unknown>;
}): Promise<VolcResponse> {
  const bodyJson = JSON.stringify(opts.body);
  const signed = signRequest({
    accessKey: opts.accessKey,
    secretKey: opts.secretKey,
    action: opts.action,
    version: API_VERSION,
    body: bodyJson,
  });

  let res: Response;
  try {
    res = await fetch(signed.url, {
      method: signed.method,
      headers: signed.headers,
      body: signed.body,
      // Vercel serverless edge timeout safety
      signal: AbortSignal.timeout(55_000),
      cache: 'no-store',
    });
  } catch (e: any) {
    throw new SkylarkError(`network error: ${e?.message || e}`, -1);
  }

  const text = await res.text();
  let parsed: VolcResponse = {};
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new SkylarkError(`non-JSON response (status ${res.status}): ${text.slice(0, 256)}`, res.status);
  }

  if (!res.ok || (parsed.code && parsed.code !== 10000)) {
    const code = parsed.code ?? res.status;
    const message = parsed.message || `HTTP ${res.status}`;
    if (RETRYABLE_CODES.has(code)) throw new SkylarkRetryable(message, code);
    if (AUDIT_FATAL_CODES.has(code)) throw new SkylarkAuditError(message, code, parsed.request_id);
    throw new SkylarkError(`[${code}] ${message}`, code, parsed.request_id);
  }
  return parsed;
}

export interface SubmitResult {
  taskId: string;
  reqJson?: string;
}

/**
 * Submit a generation job. Returns task_id (~1s).
 * Caller polls via queryStatus until done, then displays video_url.
 */
export async function submitGenerate(opts: SubmitOptions): Promise<SubmitResult> {
  const accessKey = process.env.VOLC_ACCESS_KEY;
  const secretKey = process.env.VOLC_SECRET_KEY;
  if (!accessKey || !secretKey) {
    throw new SkylarkError(
      'Volcengine credentials missing — set VOLC_ACCESS_KEY and VOLC_SECRET_KEY env vars',
      -1,
    );
  }

  // Validation
  if (!opts.prompt || opts.prompt.length === 0) {
    throw new SkylarkError('prompt required', -1);
  }
  if (opts.prompt.length > MAX_PROMPT_CHARS) {
    throw new SkylarkError(`prompt ${opts.prompt.length} chars > ${MAX_PROMPT_CHARS} max`, -1);
  }
  const ratio = opts.ratio ?? '9:16';
  const duration = opts.duration ?? '～15s';
  const language = opts.language ?? 'Chinese';
  if (!RATIO_VALUES.includes(ratio)) throw new SkylarkError(`bad ratio: ${ratio}`, -1);
  if (!DURATION_VALUES.includes(duration)) throw new SkylarkError(`bad duration: ${duration}`, -1);
  if (!LANGUAGE_VALUES.includes(language)) throw new SkylarkError(`bad language: ${language}`, -1);

  const imgUrls = opts.imgUrls ?? [];
  const videoUrls = opts.videoUrls ?? [];
  if (imgUrls.length + videoUrls.length > MAX_REFS_PER_REQUEST) {
    throw new SkylarkError(`img+video refs > ${MAX_REFS_PER_REQUEST} max`, -1);
  }

  // AIGC meta (optional)
  let reqJson: string | undefined;
  if (opts.aigcMeta) {
    reqJson = JSON.stringify({
      aigc_meta: {
        content_producer: opts.aigcMeta.contentProducer ?? '',
        producer_id: opts.aigcMeta.producerId ?? '',
        content_propagator: opts.aigcMeta.contentPropagator ?? '',
        propagate_id: opts.aigcMeta.propagateId ?? '',
      },
    });
  }

  const payload: Record<string, unknown> = {
    req_key: SKYLARK_REQ_KEY,
    prompt: opts.prompt,
    ratio,
    duration,
    language,
    enable_watermark: opts.enableWatermark ?? false,
  };
  if (imgUrls.length) payload.img_url_list = imgUrls;
  if (videoUrls.length) payload.video_url_list = videoUrls;
  if (reqJson) payload.req_json = reqJson;

  const response = await httpPost({
    accessKey,
    secretKey,
    action: ACTION_SUBMIT,
    body: payload,
  });
  const taskId = response.data?.task_id;
  if (!taskId) throw new SkylarkError('missing task_id in response', -1);
  return { taskId: String(taskId), reqJson };
}

export type TaskStatus =
  | 'in_queue'
  | 'processing'
  | 'generating'
  | 'done'
  | 'expired'
  | 'not_found'
  | 'unknown';

export interface QueryResult {
  taskId: string;
  status: TaskStatus;
  videoUrl?: string;
  outputDurationSeconds?: number;
  raw: Record<string, unknown>;
}

const STATUS_RUNNING: TaskStatus[] = ['in_queue', 'processing', 'generating'];

export function isTerminalDone(s: TaskStatus): boolean {
  return s === 'done';
}
export function isTerminalError(s: TaskStatus): boolean {
  return s === 'expired' || s === 'not_found';
}
export function isRunning(s: TaskStatus): boolean {
  return STATUS_RUNNING.includes(s);
}

/**
 * Query task status. Cheap (~1s) — client should poll every 10-15s.
 */
export async function queryStatus(taskId: string): Promise<QueryResult> {
  const accessKey = process.env.VOLC_ACCESS_KEY;
  const secretKey = process.env.VOLC_SECRET_KEY;
  if (!accessKey || !secretKey) throw new SkylarkError('credentials missing', -1);
  if (!taskId) throw new SkylarkError('taskId required', -1);

  const response = await httpPost({
    accessKey,
    secretKey,
    action: ACTION_QUERY,
    body: { req_key: SKYLARK_REQ_KEY, task_id: taskId },
  });
  const data = (response.data ?? {}) as Record<string, any>;
  const status = (data.status as TaskStatus) ?? 'unknown';
  const videoUrl =
    typeof data.video_url === 'string'
      ? data.video_url
      : Array.isArray(data.video_url_list) && data.video_url_list.length > 0
        ? data.video_url_list[0]
        : undefined;
  const outputDurationSeconds = typeof data.output_video_duration === 'number'
    ? data.output_video_duration
    : typeof data.output_duration === 'number'
      ? data.output_duration
      : undefined;
  return { taskId, status, videoUrl, outputDurationSeconds, raw: data };
}
