'use client';

/**
 * 主表单：prompt 输入 → 提交 → 轮询 → 视频展示
 *
 * 流程:
 *   1. 用户输入 prompt + 选 ratio/duration
 *   2. POST /api/generate → 拿 taskId
 *   3. setInterval 轮询 GET /api/status/[taskId]，每 12s 一次
 *   4. status='done' 拿 videoUrl → 通过 /api/proxy-video 播放
 */
import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import Link from 'next/link';
import { ExamplePrompts, type ExamplePrompt } from './ExamplePrompts';
import type { Sample } from './SampleGallery';

interface MeData {
  authenticated: boolean;
  email?: string;
  tier?: 'free' | 'pro';
  dailyLimit?: number;
  usedToday?: number;
}

type Stage =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'polling'; taskId: string; status: string; secondsElapsed: number }
  | { kind: 'done'; taskId: string; videoUrl: string; secondsElapsed: number }
  | { kind: 'error'; message: string; code?: number };

const POLL_INTERVAL_MS = 12_000;
const MAX_POLL_MINUTES = 15;

export interface GeneratorFormHandle {
  setPromptFromSample: (sample: Sample) => void;
  scrollIntoView: () => void;
}

export const GeneratorForm = forwardRef<GeneratorFormHandle>(function GeneratorForm(_, ref) {
  const [prompt, setPrompt] = useState('');
  const [ratio, setRatio] = useState<'9:16' | '16:9'>('9:16');
  const [duration, setDuration] = useState<'～15s' | '～30s'>('～15s');
  const [stage, setStage] = useState<Stage>({ kind: 'idle' });
  const [me, setMe] = useState<MeData | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startRef = useRef<number>(0);
  const rootRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    setPromptFromSample: (s: Sample) => {
      setPrompt(s.prompt);
      rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
    scrollIntoView: () => {
      rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
  }), []);

  useEffect(() => {
    fetch('/api/me', { cache: 'no-store' })
      .then((r) => r.json())
      .then(setMe)
      .catch(() => setMe({ authenticated: false }));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function refreshMe() {
    try {
      const r = await fetch('/api/me', { cache: 'no-store' });
      setMe(await r.json());
    } catch {/* ignore */}
  }

  const promptLen = prompt.length;
  const isLoggedIn = me?.authenticated === true;
  const quotaExhausted =
    isLoggedIn && (me?.usedToday ?? 0) >= (me?.dailyLimit ?? 0);
  const canSubmit =
    promptLen >= 20 &&
    promptLen <= 2000 &&
    stage.kind === 'idle' &&
    isLoggedIn &&
    !quotaExhausted;

  function pickExample(ex: ExamplePrompt) {
    setPrompt(ex.prompt);
    if (ex.ratio) setRatio(ex.ratio);
    if (ex.durationPreset) setDuration(ex.durationPreset);
  }

  async function submit() {
    setStage({ kind: 'submitting' });
    startRef.current = Date.now();
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, ratio, duration, language: 'Chinese' }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStage({
          kind: 'error',
          message: data.error || `提交失败 (${res.status})`,
          code: data.code,
        });
        return;
      }
      const taskId = data.taskId as string;
      // immediately reflect quota decrement
      if (typeof data.usedToday === 'number') {
        setMe((prev) => prev ? { ...prev, usedToday: data.usedToday } : prev);
      }
      setStage({ kind: 'polling', taskId, status: 'in_queue', secondsElapsed: 0 });
      startPolling(taskId);
    } catch (e: any) {
      setStage({ kind: 'error', message: e?.message || String(e) });
    }
  }

  function startPolling(taskId: string) {
    let tries = 0;
    const maxTries = Math.ceil((MAX_POLL_MINUTES * 60_000) / POLL_INTERVAL_MS);
    const tick = async () => {
      tries += 1;
      const secondsElapsed = Math.floor((Date.now() - startRef.current) / 1000);
      if (tries > maxTries) {
        if (pollRef.current) clearInterval(pollRef.current);
        setStage({
          kind: 'error',
          message: `生成超时（>${MAX_POLL_MINUTES} min）。任务 ${taskId} 仍可能在队列中，可稍后通过 task_id 查询。`,
        });
        return;
      }
      try {
        const r = await fetch(`/api/status/${taskId}`, { cache: 'no-store' });
        const d = await r.json();
        if (!r.ok) {
          // soft-fail: keep polling
          setStage({ kind: 'polling', taskId, status: 'unknown', secondsElapsed });
          return;
        }
        if (d.status === 'done' && d.videoUrl) {
          if (pollRef.current) clearInterval(pollRef.current);
          setStage({
            kind: 'done',
            taskId,
            videoUrl: d.videoUrl,
            secondsElapsed,
          });
          return;
        }
        if (d.status === 'expired' || d.status === 'not_found') {
          if (pollRef.current) clearInterval(pollRef.current);
          setStage({
            kind: 'error',
            message: `任务已 ${d.status}，请重新提交`,
          });
          return;
        }
        setStage({ kind: 'polling', taskId, status: d.status, secondsElapsed });
      } catch (e: any) {
        // network blip — keep polling
        console.warn('poll error', e);
      }
    };
    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
  }

  function reset() {
    if (pollRef.current) clearInterval(pollRef.current);
    setStage({ kind: 'idle' });
  }

  return (
    <div ref={rootRef} className="w-full max-w-4xl mx-auto">
      {/* NOT-LOGGED-IN BANNER */}
      {(stage.kind === 'idle' || stage.kind === 'submitting') && me && !isLoggedIn && (
        <div className="mb-6 rounded-2xl border border-line bg-white p-6 text-center">
          <h2 className="text-lg font-medium text-ink">登录后即可开始生成</h2>
          <p className="mt-2 text-sm text-ink2 leading-relaxed">
            注册免费账号 → 每天 1 条免费生成额度；升级 Pro → 每天 100 条。
          </p>
          <div className="mt-5 flex gap-3 justify-center">
            <Link
              href="/register"
              className="inline-flex items-center px-6 h-11 rounded-full bg-ink text-white text-sm font-medium hover:bg-black"
            >
              立即注册
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center px-6 h-11 rounded-full border border-line text-ink text-sm font-medium hover:bg-white"
            >
              已有账号 登录
            </Link>
          </div>
        </div>
      )}

      {/* QUOTA BANNER (logged in) */}
      {(stage.kind === 'idle' || stage.kind === 'submitting') && isLoggedIn && (
        <div className="mb-6 rounded-2xl border border-line bg-white p-4 flex items-center justify-between text-sm">
          <div className="flex items-center gap-3">
            <span className="text-ink2">{me?.email}</span>
            <span className={`px-2 py-0.5 rounded-full text-xs ${
              me?.tier === 'pro' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-700'
            }`}>
              {me?.tier === 'pro' ? '⭐ Pro' : '免费'}
            </span>
          </div>
          <div className={`font-medium ${quotaExhausted ? 'text-red-600' : 'text-ink'}`}>
            今日额度 {me?.usedToday}/{me?.dailyLimit}
          </div>
        </div>
      )}

      {/* INPUT FORM */}
      {(stage.kind === 'idle' || stage.kind === 'submitting') && isLoggedIn && (
        <div className="space-y-6">
          {quotaExhausted && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <strong>今日额度已用完。</strong>
              {' '}免费用户每天 1 条；
              <Link href="/account" className="underline hover:text-red-900">
                升级 Pro
              </Link>{' '}享每天 100 条。明日 UTC 00:00 后重置。
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-2 text-ink">
              提示词
              <span className="ml-2 text-ink2 font-normal">
                {promptLen}/2000 字
              </span>
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="试着描述一段 15 秒的镜头序列：开场 0-2s 锚定一个面部超大特写，2-6s 中景主体动作，6-10s 浅景深推近，10-13s 悬念铺垫，13-15s frozen gesture 钩子定格。色板锁定冷青+月白+朱砂红三调，cel-shading 描边贯穿..."
              rows={10}
              maxLength={2000}
              disabled={stage.kind === 'submitting'}
              className="w-full p-4 rounded-2xl border border-line bg-white text-ink placeholder:text-ink2 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 resize-y min-h-[240px] text-[15px] leading-relaxed"
            />
          </div>

          <div className="flex flex-wrap gap-4 items-center">
            <SegmentedControl
              label="画幅"
              value={ratio}
              options={[
                { value: '9:16', label: '竖屏 9:16' },
                { value: '16:9', label: '横屏 16:9' },
              ]}
              onChange={(v) => setRatio(v as '9:16' | '16:9')}
            />
            <SegmentedControl
              label="时长"
              value={duration}
              options={[
                { value: '～15s', label: '15 秒' },
                { value: '～30s', label: '30 秒' },
              ]}
              onChange={(v) => setDuration(v as '～15s' | '～30s')}
            />
          </div>

          <div>
            <div className="text-xs text-ink2 mb-2">示例（点击填入）</div>
            <ExamplePrompts onPick={pickExample} />
          </div>

          <button
            onClick={submit}
            disabled={!canSubmit}
            className="w-full h-14 rounded-full bg-ink text-white text-base font-medium hover:bg-black disabled:bg-ink2 disabled:cursor-not-allowed transition-colors"
          >
            {stage.kind === 'submitting' ? '提交中…' : '开始生成'}
          </button>
          <p className="text-xs text-ink2 text-center">
            生成约需 3-8 分钟。Skylark Agent 2.0 (Seedance 2.0 fast 720p) + AIGC 双合规标识。
          </p>
        </div>
      )}

      {/* POLLING */}
      {stage.kind === 'polling' && (
        <div className="text-center py-16">
          <div className="inline-block">
            <div className="w-16 h-16 rounded-full border-4 border-line border-t-accent animate-spin mx-auto"></div>
          </div>
          <div className="mt-6 space-y-2">
            <div className="text-lg font-medium text-ink">
              {stageLabel(stage.status)}
            </div>
            <div className="text-sm text-ink2">
              已用时 {formatDuration(stage.secondsElapsed)}（预计还需 {estimateRemaining(stage.secondsElapsed)}）
            </div>
            <div className="text-xs text-ink2 font-mono">
              task_id: {stage.taskId}
            </div>
          </div>
          <button onClick={reset} className="mt-8 text-sm text-ink2 underline hover:text-ink">
            放弃这一轮，返回输入
          </button>
        </div>
      )}

      {/* DONE */}
      {stage.kind === 'done' && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/10">
              <svg viewBox="0 0 24 24" className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2 className="text-2xl font-medium mt-4">生成完成</h2>
            <p className="text-sm text-ink2 mt-1">
              用时 {formatDuration(stage.secondsElapsed)}
            </p>
          </div>

          <VideoPlayer videoUrl={stage.videoUrl} taskId={stage.taskId} />

          <div className="flex gap-3 justify-center pt-2">
            <a
              href={stage.videoUrl}
              download="yunque-manhua.mp4"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 h-11 inline-flex items-center rounded-full bg-ink text-white text-sm font-medium hover:bg-black"
            >
              下载 mp4
            </a>
            <button
              onClick={reset}
              className="px-6 h-11 rounded-full border border-line text-ink text-sm font-medium hover:bg-white"
            >
              再生成一段
            </button>
          </div>
          <p className="text-xs text-ink2 text-center max-w-xl mx-auto">
            视频包含 GB/T 45438-2025 AIGC 隐式标识。
            原始 video_url 1 小时后过期，请尽快下载。
          </p>
        </div>
      )}

      {/* ERROR */}
      {stage.kind === 'error' && (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10">
            <svg viewBox="0 0 24 24" className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </div>
          <h2 className="text-xl font-medium mt-4">出错了</h2>
          <p className="text-sm text-ink2 mt-2 max-w-xl mx-auto">{stage.message}</p>
          {stage.code && (
            <p className="text-xs text-ink2 mt-1 font-mono">code: {stage.code}</p>
          )}
          <button
            onClick={reset}
            className="mt-6 px-6 h-11 rounded-full bg-ink text-white text-sm font-medium hover:bg-black"
          >
            返回重试
          </button>
        </div>
      )}
    </div>
  );
});

function SegmentedControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <div className="text-xs text-ink2 mb-2">{label}</div>
      <div className="inline-flex rounded-full bg-white border border-line p-1">
        {options.map((o) => (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            className={`px-4 h-9 rounded-full text-sm transition-colors ${
              value === o.value
                ? 'bg-ink text-white'
                : 'text-ink hover:bg-bg'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function VideoPlayer({ videoUrl, taskId }: { videoUrl: string; taskId: string }) {
  // Direct Volcengine CDN URL is best for playback (zero CORS issue for <video> tag,
  // bypasses our 10s serverless function limit on Hobby tier).
  return (
    <div className="rounded-3xl overflow-hidden border border-line bg-black mx-auto" style={{ maxWidth: 480 }}>
      <video
        src={videoUrl}
        controls
        autoPlay
        loop
        playsInline
        crossOrigin="anonymous"
        className="w-full h-auto block"
      />
    </div>
  );
}

function stageLabel(status: string): string {
  switch (status) {
    case 'in_queue':
      return '已入队，等待 GPU 资源中…';
    case 'processing':
      return '模型处理中…';
    case 'generating':
      return '正在生成画面…';
    default:
      return '处理中…';
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s} 秒`;
  return `${m} 分 ${s} 秒`;
}

function estimateRemaining(elapsed: number): string {
  // empirically R30-R40 took 200-900s; budget 8 min nominal
  const remaining = Math.max(60, 8 * 60 - elapsed);
  return formatDuration(remaining);
}
