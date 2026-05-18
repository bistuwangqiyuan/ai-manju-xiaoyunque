'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, Job, JobLog } from '@/lib/api';
import { formatDate, formatYuan } from '@/lib/utils';
import { ArrowLeft, Download, XCircle, RefreshCw } from 'lucide-react';

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

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const id = Number(params?.id);

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?next=/dashboard/jobs/${id}`);
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
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const fullVideoUrl = job.result_url
    ? job.result_url.startsWith('http')
      ? job.result_url
      : `${backendUrl}${job.result_url}`
    : null;

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

        <div className="mb-6">
          <div className="flex justify-between text-sm text-ink-700 mb-1">
            <span>渲染进度</span>
            <span>{job.progress}%</span>
          </div>
          <div className="h-2 bg-ink-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cinnabar-500 to-cinnabar-700 transition-all duration-500"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>

        {job.error && (
          <div className="p-4 rounded-lg bg-red-100 text-red-800 text-sm mb-4">
            <div className="font-semibold mb-1">错误</div>
            {job.error}
          </div>
        )}

        {fullVideoUrl && (
          <div className="space-y-3">
            <div className="card !shadow-none p-2 aspect-[9/16] max-w-sm mx-auto bg-black overflow-hidden">
              <video
                controls
                src={fullVideoUrl}
                poster={
                  job.cover_url
                    ? job.cover_url.startsWith('http')
                      ? job.cover_url
                      : `${backendUrl}${job.cover_url}`
                    : undefined
                }
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
