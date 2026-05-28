'use client';

import { useEffect, useRef, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, Job, JobLog, assetUrl, BACKEND_URL } from '@/lib/api';
import { WorkflowStepper, Scores7DPanel } from '@/components/WorkflowStepper';
import { formatDate, formatYuan } from '@/lib/utils';
import { ArrowLeft, Download, XCircle, RefreshCw, Award } from 'lucide-react';

/**
 * Smooth progress interpolation.
 *
 * 后端按阶段跳变（0/25/50/85/99/100），单阶段可耗时 5-10 分钟。
 * 这里每 10 秒钟把显示值向阶段天花板（next milestone - 1）漂移 1%，
 * 后端推回新进度时直接 snap 到更高值，让用户视觉上感受到「一直在进展」。
 */
function useSmoothProgress(rawProgress: number, status: Job['status']): number {
  const [display, setDisplay] = useState<number>(Math.max(0, rawProgress || 0));
  const baseRef = useRef<number>(rawProgress || 0);

  const ceilOf = (p: number): number => {
    if (p >= 99) return 100;
    if (p >= 85) return 98;
    if (p >= 50) return 84;
    if (p >= 25) return 49;
    return 24;
  };

  useEffect(() => {
    setDisplay((d) => {
      const next = Math.max(d, rawProgress || 0);
      baseRef.current = next;
      return next;
    });
  }, [rawProgress]);

  useEffect(() => {
    if (status === 'succeeded') {
      setDisplay(100);
      return;
    }
    if (status === 'failed' || status === 'cancelled') return;
    const id = setInterval(() => {
      setDisplay((d) => {
        const ceiling = ceilOf(rawProgress || 0);
        if (d >= ceiling - 1) return d;
        return Math.min(ceiling - 1, d + 1);
      });
    }, 10_000);
    return () => clearInterval(id);
  }, [status, rawProgress]);

  return Math.round(display);
}

function ProgressBar({
  progress,
  status,
  pipelineVersion,
}: {
  progress: number;
  status: Job['status'];
  pipelineVersion: string;
}) {
  const display = useSmoothProgress(progress, status);
  return (
    <div className="mb-6">
      <div className="flex justify-between text-sm text-ink-700 mb-1">
        <span>渲染进度 · {pipelineVersion}</span>
        <span>{display}%</span>
      </div>
      <div className="h-2 bg-ink-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cinnabar-500 to-cinnabar-700 transition-all duration-1000 ease-linear"
          style={{ width: `${display}%` }}
        />
      </div>
      {status === 'running' && display > progress && (
        <div className="text-[10px] text-ink-400 mt-0.5">
          已完成 {progress}%（火山真实管线），预估进度自动按 10s 平滑递增
        </div>
      )}
    </div>
  );
}

const STATUS_TEXT: Record<Job['status'], string> = {
  queued: '排队中',
  running: '渲染中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
};
const STATUS_COLOR: Record<Job['status'], string> = {
  queued: 'bg-ink-200 text-ink-700',
  running: 'bg-cinnabar-100 text-cinnabar-700',
  succeeded: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-ink-100 text-ink-500',
};

function JobDetailInner() {
  const search = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const id = Number(search.get('id') || '0');

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?next=/dashboard/job?id=${id}`);
  }, [authLoading, user, id, router]);

  const load = async () => {
    try {
      const [j, l] = await Promise.all([api.getJob(id), api.getJobLogs(id)]);
      setJob(j);
      setLogs(l);
      setErr(null);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    if (!user || !id) return;
    load();
    const t = setInterval(() => {
      if (job && ['succeeded', 'failed', 'cancelled'].includes(job.status)) return;
      load();
    }, 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, id, job?.status]);

  const onCancel = async () => {
    if (!job || !confirm('确定取消该任务？已扣额度按比例退回。')) return;
    try {
      const j = await api.cancelJob(job.id);
      setJob(j);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  if (authLoading || !user) return null;
  if (!job) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        {err ? (
          <div className="card p-8 text-center">
            <p className="text-red-700 mb-4">{err}</p>
            <Link href="/dashboard" className="btn-secondary">返回</Link>
          </div>
        ) : (
          <div className="text-center text-ink-600 py-16">加载中…</div>
        )}
      </div>
    );
  }

  const canCancel = job.status === 'queued' || job.status === 'running';
  const backendUrl = BACKEND_URL;
  // /samples/... 是 Vercel 自己的静态文件（项目内真实 R40 样片，跟首页 Showcase 同源）
  // /storage/... 是 Railway 后端运行时落地（接入真实流水线后使用）
  // http... 是外链
  const resolveUrl = (u: string | null): string | null => {
    if (!u) return null;
    if (u.startsWith('http')) return u;
    if (u.startsWith('/samples/')) return u; // 让浏览器相对 Vercel 域名解析
    return `${backendUrl}${u}`;
  };
  const fullVideoUrl = resolveUrl(job.result_url);

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <Link href="/dashboard" className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> 返回仪表盘
      </Link>

      <div className="card p-8 mb-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="font-serif text-3xl text-ink-900 mb-1">{job.title}</h1>
            <div className="text-sm text-ink-600">
              #{job.id} · {job.episodes} 集 · 风格 {job.style}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`badge ${STATUS_COLOR[job.status]}`}>
              {STATUS_TEXT[job.status]}
            </span>
            {canCancel && (
              <button onClick={onCancel} className="btn-ghost text-sm">
                <XCircle className="w-4 h-4 mr-1" /> 取消
              </button>
            )}
            <button onClick={load} className="btn-ghost text-sm">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 mb-6 text-sm">
          <div>
            <div className="text-ink-500">花费</div>
            <div className="font-semibold text-ink-900">{formatYuan(job.cost_cents)}</div>
          </div>
          <div>
            <div className="text-ink-500">创建</div>
            <div className="text-ink-700">{formatDate(job.created_at)}</div>
          </div>
          <div>
            <div className="text-ink-500">更新</div>
            <div className="text-ink-700">{formatDate(job.updated_at)}</div>
          </div>
        </div>

        <WorkflowStepper currentStep={job.current_step || (job.status === 'succeeded' ? 6 : 0)} />

        {/* Sub-pages (per-shot / versions / export) */}
        <div className="flex flex-wrap gap-2 mb-4">
          <Link href={`/dashboard/job/shots?id=${job.id}`} className="btn-ghost text-xs">
            🎬 镜头与 7 维评分
          </Link>
          <Link href={`/dashboard/job/versions?id=${job.id}`} className="btn-ghost text-xs">
            🗂 版本中心
          </Link>
          <Link href={`/dashboard/job/export?id=${job.id}`} className="btn-ghost text-xs">
            📤 多平台导出
          </Link>
        </div>

        <ProgressBar progress={job.progress} status={job.status} pipelineVersion={job.pipeline_version} />

        {job.error && (
          <div className="p-4 rounded-lg bg-red-100 text-red-800 text-sm mb-4">
            <div className="font-semibold mb-1">错误</div>
            {job.error}
          </div>
        )}

        {/* 质量评分 — 100-Pt Rubric */}
        {job.quality_score !== null && (
          <div className="card !shadow-none p-5 mb-4 border-2 border-cinnabar-200/60 bg-gradient-to-br from-ink-50 to-cinnabar-50/30">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Award className={`w-5 h-5 ${job.quality_score >= 95 ? 'text-emerald-600' : 'text-amber-600'}`} />
                <span className="font-semibold text-ink-900">100-Pt Rubric 工业评分</span>
                {job.quality_retries > 0 && (
                  <span className="badge bg-ink-100 text-ink-600 text-xs">
                    Multi-VLM Ensemble 自动修复 {job.quality_retries} 次
                  </span>
                )}
              </div>
              <div className="text-right">
                <div className={`font-serif text-4xl ${job.quality_score >= 95 ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {job.quality_score}
                  <span className="text-base text-ink-400">/100</span>
                </div>
                <div className="text-xs text-ink-500">
                  {job.quality_score >= 95 ? '✓ 已达 95 分工业标准' : '< 95 分'}
                </div>
              </div>
            </div>

            {/* 主项（Tech / Visual / Narrative / Genre） */}
            {job.quality_breakdown && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 mb-4">
                  {[
                    ['tech', 'Tech', 40, '技术质量'],
                    ['visual', 'Visual', 30, '视觉美学'],
                    ['narrative', 'Narrative', 20, '叙事完整'],
                    ['genre', 'Genre', 10, '题材契合'],
                  ].map(([key, label, max, desc]) => {
                    const v = (job.quality_breakdown as any)?.[key] ?? 0;
                    const pct = (v / (max as number)) * 100;
                    return (
                      <div key={key as string} className="bg-white/60 rounded-lg p-3">
                        <div className="flex justify-between items-baseline">
                          <span className="text-sm font-semibold text-ink-900">{label}</span>
                          <span className={`font-mono text-base ${pct >= 90 ? 'text-emerald-700' : 'text-ink-700'}`}>
                            {typeof v === 'number' ? v.toFixed(1) : v}
                            <span className="text-xs text-ink-400">/{max}</span>
                          </span>
                        </div>
                        <div className="text-[10px] text-ink-500 mb-1.5">{desc}</div>
                        <div className="h-1 bg-ink-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all ${pct >= 90 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* 工业子项指标 */}
                <details className="text-xs">
                  <summary className="cursor-pointer text-ink-600 hover:text-ink-900 mb-2">
                    工业指标细节（ArcFace / CLIP / LAION-Aesthetic …）
                  </summary>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-2">
                    {[
                      ['arcface', 'ArcFace', '人物一致性'],
                      ['clip_align', 'CLIP', '文图对齐'],
                      ['aesthetic', 'LAION-Aes', '美学评分'],
                      ['hsv_color', 'HSV', '色彩一致'],
                      ['motion', 'OptFlow', '运动评分'],
                    ].map(([key, label, desc]) => {
                      const v = (job.quality_breakdown as any)?.[key];
                      if (v === undefined) return null;
                      return (
                        <div key={key as string}>
                          <div className="flex justify-between text-[11px] text-ink-600">
                            <span title={desc as string}>{label}</span>
                            <span className={v >= 9 ? 'text-emerald-700 font-mono' : 'text-ink-700 font-mono'}>
                              {typeof v === 'number' ? v.toFixed(2) : v}
                            </span>
                          </div>
                          <div className="h-1 bg-ink-100 rounded-full overflow-hidden mt-0.5">
                            <div
                              className={`h-full ${v >= 9 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                              style={{ width: `${(v / 10) * 100}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-[10px] text-ink-500 mt-3 leading-relaxed">
                    评分基于业界公认模型：ArcFace (InsightFace 5M-IDs)、CLIP ViT-B-32、
                    LAION-Aesthetic v2。叙事/类型由 Claude + Qwen-VL + Pixtral 三厂 VLM cross-vendor
                    ensemble 投票。详见 <Link href="/quality" className="text-cinnabar-700 underline">评分方法</Link>。
                  </div>
                </details>
              </>
            )}

            {job.scores_7d && (
              <div className="mt-4 pt-4 border-t border-ink-200/60">
                <div className="text-sm font-semibold text-ink-900 mb-1">7 维质量诊断（0–10）</div>
                <Scores7DPanel scores={job.scores_7d} />
              </div>
            )}
          </div>
        )}

        {job.status === 'succeeded' && (
          <div className="flex flex-wrap gap-2 mb-4">
            {!job.human_approved && (
              <button
                type="button"
                className="btn-primary text-sm"
                onClick={async () => {
                  const j = await api.approveJob(job.id);
                  setJob(j);
                }}
              >
                人工确认放行
              </button>
            )}
            {job.human_approved && (
              <span className="badge bg-emerald-100 text-emerald-800">已人工确认</span>
            )}
            <button
              type="button"
              className="btn-secondary text-sm"
              onClick={async () => {
                if (!confirm('重新排队渲染？将消耗配额/余额。')) return;
                const j = await api.rerollJob(job.id);
                setJob(j);
                router.push(`/dashboard/job?id=${j.id}`);
              }}
            >
              一键重绘
            </button>
          </div>
        )}

        {fullVideoUrl && (
          <div className="space-y-3">
            <div className="card !shadow-none p-2 aspect-[9/16] max-w-sm mx-auto bg-black overflow-hidden">
              <video
                controls
                src={fullVideoUrl}
                poster={resolveUrl(job.cover_url) || undefined}
                className="w-full h-full object-contain"
              />
            </div>
            <div className="text-center">
              <a
                href={fullVideoUrl}
                download
                className="btn-primary"
              >
                <Download className="w-4 h-4 mr-2" /> 下载 MP4
              </a>
            </div>
          </div>
        )}
      </div>

      <div className="card p-6">
        <h2 className="font-semibold text-ink-900 mb-3">原文片段</h2>
        <pre className="whitespace-pre-wrap font-serif text-sm text-ink-700 leading-relaxed max-h-48 overflow-auto">
          {job.novel_excerpt}
        </pre>
      </div>

      <div className="card p-6 mt-6">
        <h2 className="font-semibold text-ink-900 mb-3">渲染日志</h2>
        <div className="font-mono text-xs bg-ink-950/95 text-ink-100 rounded-lg p-4 max-h-80 overflow-auto">
          {logs.length === 0 ? (
            <div className="text-ink-500">暂无日志</div>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="flex gap-3">
                <span className="text-ink-500 flex-shrink-0">
                  {new Date(l.ts).toLocaleTimeString('zh-CN')}
                </span>
                <span
                  className={
                    l.level === 'ERROR'
                      ? 'text-red-300'
                      : l.level === 'WARN'
                      ? 'text-yellow-300'
                      : 'text-ink-100'
                  }
                >
                  [{l.level}]
                </span>
                <span className="text-ink-200">{l.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-6 py-16 text-center text-ink-600">加载中…</div>}>
      <JobDetailInner />
    </Suspense>
  );
}
