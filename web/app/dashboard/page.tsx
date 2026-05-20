'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api, Job, Quota } from '@/lib/api';
import { formatDate, formatYuan } from '@/lib/utils';
import { Plus, Sparkles, RefreshCw, Crown, AlertTriangle, Zap } from 'lucide-react';

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
  const [quota, setQuota] = useState<Quota | null>(null);
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
      const [j, q] = await Promise.all([api.listJobs(), api.getQuota()]);
      setJobs(j);
      setQuota(q);
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
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-serif text-3xl text-ink-900 mb-1">我的作品</h1>
          <p className="text-ink-600 text-sm">欢迎，{user.email}</p>
        </div>
        <div className="flex gap-2">
          <Link href="/pricing" className="btn-secondary">
            <Sparkles className="w-4 h-4 mr-1" /> 充值
          </Link>
          <Link
            href="/dashboard/new"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-cinnabar-600 text-white text-base font-semibold shadow-lg hover:bg-cinnabar-700 transition"
          >
            <Plus className="w-5 h-5 mr-1.5" /> 做一集新的
          </Link>
        </div>
      </div>

      {/* Tier 信息卡片 */}
      {quota && (
        <div className="grid sm:grid-cols-3 gap-4 mb-6">
          <div className="card p-5">
            <div className="text-xs text-ink-500 mb-1">当前等级</div>
            <div className="flex items-center gap-2 mb-1">
              {quota.tier === 'free' ? (
                <span className="font-serif text-2xl text-ink-900">Free</span>
              ) : quota.tier === 'pro' ? (
                <span className="font-serif text-2xl text-cinnabar-700 flex items-center gap-1.5">
                  <Crown className="w-5 h-5" /> Pro
                </span>
              ) : (
                <span className="font-serif text-2xl text-emerald-700">
                  {quota.tier.toUpperCase()}
                </span>
              )}
            </div>
            {quota.tier === 'free' ? (
              <Link href="/pricing" className="text-xs text-cinnabar-700 hover:underline">
                升级 Pro → 配额无限 →
              </Link>
            ) : (
              <div className="text-xs text-emerald-700">✓ 无每日配额限制</div>
            )}
          </div>

          {quota.tier === 'free' ? (
            <div className="card p-5">
              <div className="text-xs text-ink-500 mb-1">今日免费配额</div>
              <div className="font-serif text-2xl text-ink-900">
                {quota.free_remaining_today} <span className="text-base text-ink-500">/ {quota.free_daily_limit}</span>
              </div>
              <div className="mt-2 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cinnabar-500 transition-all"
                  style={{
                    width: `${((quota.free_used_today) / quota.free_daily_limit) * 100}%`,
                  }}
                />
              </div>
              {quota.free_remaining_today === 0 && (
                <div className="mt-2 text-xs text-cinnabar-700 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> 今日额度已用完
                </div>
              )}
            </div>
          ) : (
            <div className="card p-5">
              <div className="text-xs text-ink-500 mb-1">余额</div>
              <div className="font-serif text-2xl text-ink-900">
                {formatYuan(quota.credits_cents)}
              </div>
              <Link href="/pricing" className="text-xs text-cinnabar-700 hover:underline">
                充值 →
              </Link>
            </div>
          )}

          <div className="card p-5">
            <div className="text-xs text-ink-500 mb-1">单集费用</div>
            <div className="font-serif text-2xl text-ink-900">
              {quota.tier === 'free' ? '免费' : formatYuan(quota.cost_per_episode_cents)}
            </div>
            <div className="text-xs text-ink-500 mt-1">
              {quota.tier === 'free'
                ? `${quota.free_daily_limit} 集/日`
                : `成本 ${formatYuan(quota.episode_base_cost_cents)} × ${quota.profit_multiplier}`}
            </div>
          </div>
        </div>
      )}

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
            <p className="text-lg text-ink-700 mb-6">
              你还没做过漫剧。点下面的按钮试试看 👇
            </p>
            <Link
              href="/dashboard/new"
              className="inline-flex items-center justify-center px-8 py-4 rounded-xl bg-cinnabar-600 text-white text-lg font-semibold shadow-xl hover:bg-cinnabar-700 hover:scale-105 transition"
            >
              <Plus className="w-6 h-6 mr-2" /> 做我的第一集漫剧
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
                        href={`/dashboard/job?id=${j.id}`}
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
                        href={`/dashboard/job?id=${j.id}`}
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
