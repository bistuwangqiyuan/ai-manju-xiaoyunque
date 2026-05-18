'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api, Job } from '@/lib/api';
import { formatDate, formatYuan } from '@/lib/utils';
import { Plus, Sparkles, RefreshCw } from 'lucide-react';

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

export default function DashboardPage() {
  const { user, loading: authLoading, refresh } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login?next=/dashboard');
    }
  }, [authLoading, user, router]);

  const load = async () => {
    try {
      setLoading(true);
      const data = await api.listJobs();
      setJobs(data);
      setErr(null);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!user) return;
    load();
    const t = setInterval(() => {
      load();
      refresh();
    }, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16 text-center text-ink-600">
        加载中…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-serif text-3xl text-ink-900 mb-1">仪表盘</h1>
          <p className="text-ink-600 text-sm">
            欢迎，{user.email} · 余额{' '}
            <span className="text-cinnabar-700 font-semibold">
              {formatYuan(user.credits_cents)}
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/pricing" className="btn-secondary">
            <Sparkles className="w-4 h-4 mr-1" /> 充值
          </Link>
          <Link href="/dashboard/new" className="btn-primary">
            <Plus className="w-4 h-4 mr-1" /> 新建漫剧
          </Link>
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-ink-900">我的任务</h2>
          <button onClick={load} className="btn-ghost text-sm">
            <RefreshCw className="w-4 h-4 mr-1" /> 刷新
          </button>
        </div>
        {err && (
          <div className="p-3 mb-4 rounded-lg bg-red-100 text-red-700 text-sm">
            {err}
          </div>
        )}
        {loading && jobs.length === 0 ? (
          <div className="py-12 text-center text-ink-500">加载中…</div>
        ) : jobs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-ink-600 mb-4">还没有任务，开始你的第一部漫剧吧。</p>
            <Link href="/dashboard/new" className="btn-primary">
              <Plus className="w-4 h-4 mr-1" /> 新建漫剧
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-ink-200">
                  <th className="py-3 pr-2">标题</th>
                  <th className="py-3 pr-2">集数</th>
                  <th className="py-3 pr-2">状态</th>
                  <th className="py-3 pr-2">进度</th>
                  <th className="py-3 pr-2">花费</th>
                  <th className="py-3 pr-2">创建</th>
                  <th className="py-3"></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr
                    key={j.id}
                    className="border-b border-ink-100 hover:bg-ink-50/50"
                  >
                    <td className="py-3 pr-2">
                      <Link
                        href={`/dashboard/jobs/${j.id}`}
                        className="text-ink-900 font-medium hover:text-cinnabar-700"
                      >
                        {j.title}
                      </Link>
                    </td>
                    <td className="py-3 pr-2 text-ink-700">{j.episodes}</td>
                    <td className="py-3 pr-2">
                      <span className={`badge ${STATUS_COLOR[j.status]}`}>
                        {STATUS_TEXT[j.status]}
                      </span>
                    </td>
                    <td className="py-3 pr-2 w-32">
                      <div className="h-2 bg-ink-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cinnabar-500 transition-all"
                          style={{ width: `${j.progress}%` }}
                        />
                      </div>
                      <div className="text-xs text-ink-500 mt-1">
                        {j.progress}%
                      </div>
                    </td>
                    <td className="py-3 pr-2 text-ink-700">
                      {formatYuan(j.cost_cents)}
                    </td>
                    <td className="py-3 pr-2 text-ink-600 text-xs">
                      {formatDate(j.created_at)}
                    </td>
                    <td className="py-3 text-right">
                      <Link
                        href={`/dashboard/jobs/${j.id}`}
                        className="text-cinnabar-700 hover:underline text-sm"
                      >
                        查看
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
