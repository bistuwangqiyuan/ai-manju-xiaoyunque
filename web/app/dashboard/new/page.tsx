'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api, Quota } from '@/lib/api';
import { formatYuan } from '@/lib/utils';
import { Sparkles, ArrowLeft, Crown, AlertTriangle } from 'lucide-react';
import Link from 'next/link';

const STYLES = [
  { id: 'ancient_3d_guoman', label: '古风 3D 国漫', desc: '60/30/10 复合风格锚点' },
  { id: 'wuxia_ink', label: '武侠水墨', desc: '黑白水墨 + 动态分镜' },
  { id: 'urban_drama', label: '都市悬疑', desc: '现代感 + 强光影对比' },
];

export default function NewJobPage() {
  const { user, loading: authLoading, refresh } = useAuth();
  const router = useRouter();
  const [quota, setQuota] = useState<Quota | null>(null);
  const [title, setTitle] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [style, setStyle] = useState(STYLES[0].id);
  const [episodes, setEpisodes] = useState(1);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/new');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.getQuota().then(setQuota).catch(() => {});
  }, [user]);

  const isFree = quota?.tier === 'free';
  const maxEpisodes = isFree ? 1 : 10;
  const effectiveEpisodes = Math.min(episodes, maxEpisodes);
  const costPerEpisode = quota?.cost_per_episode_cents ?? 0;
  const totalCost = effectiveEpisodes * costPerEpisode;
  const freeBlocked = isFree && (quota?.free_remaining_today ?? 0) <= 0;
  const enoughCredits = !quota || quota.tier === 'free' || quota.credits_cents >= totalCost;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (excerpt.trim().length < 50) {
      setErr('小说片段至少 50 字');
      return;
    }
    if (freeBlocked) {
      setErr('今日免费配额已用完，请充值升级 Pro');
      return;
    }
    if (!enoughCredits) {
      setErr('余额不足，请先充值');
      return;
    }
    setLoading(true);
    try {
      const job = await api.createJob({
        title: title || '未命名漫剧',
        novel_excerpt: excerpt,
        style,
        episodes: effectiveEpisodes,
      });
      await refresh();
      router.push(`/dashboard/job?id=${job.id}`);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || !user || !quota) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center text-ink-600">
        加载中…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/dashboard" className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> 返回仪表盘
      </Link>
      <div className="card p-8">
        <h1 className="font-serif text-3xl text-ink-900 mb-1">做一集漫剧</h1>
        <p className="text-ink-700 text-base mb-6">
          只要填两个东西：标题、文字内容。其他都是默认就好。
          <br />
          <span className="text-sm text-ink-500">
            （评分自动保证 95 分以上，不达标会自动重做）
          </span>
        </p>

        {/* Tier 状态条 */}
        {isFree ? (
          <div className="rounded-xl border border-ink-200 bg-ink-50/60 p-4 mb-6">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-cinnabar-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-ink-800 flex-1">
                <div className="font-semibold mb-1">
                  Free 会员 · 今日剩余 {quota.free_remaining_today}/{quota.free_daily_limit} 集
                </div>
                <div className="text-ink-600 text-xs leading-relaxed">
                  免费用户每天 3 集，每次只能生成 1 集。想生成完整 10 集套装？
                  <Link href="/pricing" className="text-cinnabar-700 underline ml-1">
                    升级 Pro
                  </Link>{' '}
                  即可不限量。
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-cinnabar-200 bg-cinnabar-50/40 p-4 mb-6">
            <div className="flex items-center gap-2 text-sm">
              <Crown className="w-4 h-4 text-cinnabar-700" />
              <span className="font-semibold text-ink-900">
                {quota.tier.toUpperCase()} 会员
              </span>
              <span className="text-ink-600">
                · 余额 {formatYuan(quota.credits_cents)}
              </span>
              <span className="text-ink-500 ml-auto text-xs">
                单集 {formatYuan(quota.cost_per_episode_cents)}
                <span className="text-ink-400">（成本×{quota.profit_multiplier}）</span>
              </span>
            </div>
          </div>
        )}

        {freeBlocked && (
          <div className="rounded-lg bg-cinnabar-100 text-cinnabar-800 p-4 mb-5 flex items-start gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold mb-1">今日免费配额已用完</div>
              <Link href="/pricing" className="underline">充值任意金额自动升级 Pro，配额无限</Link>
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label className="label">作品标题</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：聊斋·聂小倩"
              maxLength={80}
            />
          </div>

          <div>
            <label className="label">小说片段 / 大纲（≥ 50 字）</label>
            <textarea
              className="input min-h-[200px] font-serif"
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
              placeholder="粘贴你想改编的小说片段、剧情大纲或人物设定…"
              maxLength={20000}
            />
            <div className="text-xs text-ink-500 mt-1 text-right">
              {excerpt.length} / 20,000
            </div>
          </div>

          <div>
            <label className="label">风格</label>
            <div className="grid sm:grid-cols-3 gap-3">
              {STYLES.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  onClick={() => setStyle(s.id)}
                  className={`p-4 rounded-xl border text-left transition ${
                    style === s.id
                      ? 'border-cinnabar-600 bg-cinnabar-50 ring-2 ring-cinnabar-300'
                      : 'border-ink-200 hover:border-ink-400 bg-white/60'
                  }`}
                >
                  <div className="font-semibold text-ink-900 text-sm">
                    {s.label}
                  </div>
                  <div className="text-xs text-ink-600 mt-1">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="label">
              集数（1-{maxEpisodes}）
              {isFree && (
                <span className="text-xs text-ink-500 ml-2">Free 用户最多 1 集</span>
              )}
            </label>
            <input
              type="range"
              min={1}
              max={maxEpisodes}
              value={effectiveEpisodes}
              onChange={(e) => setEpisodes(Number(e.target.value))}
              className="w-full accent-cinnabar-600"
              disabled={maxEpisodes === 1}
            />
            <div className="flex justify-between text-sm">
              <span className="text-ink-700">{effectiveEpisodes} 集 × 90s</span>
              <span className="text-cinnabar-700 font-semibold">
                {totalCost === 0 ? '免费（占用日配额）' : formatYuan(totalCost)}
              </span>
            </div>
          </div>

          {err && (
            <div className="p-3 rounded-lg bg-cinnabar-100 text-cinnabar-800 text-sm">
              {err}
            </div>
          )}

          <button
            type="submit"
            className="inline-flex items-center justify-center w-full px-6 py-4 rounded-xl bg-cinnabar-600 text-white text-lg font-semibold shadow-lg hover:bg-cinnabar-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading || freeBlocked || !enoughCredits}
          >
            {loading
              ? '正在做，请等一下…'
              : freeBlocked
              ? '今天已经免费做完 3 个了'
              : !enoughCredits
              ? `余额不够，还差 ${formatYuan(totalCost - (quota?.credits_cents || 0))}`
              : totalCost === 0
              ? '✨ 开始做漫剧（免费）'
              : `✨ 开始做漫剧（${formatYuan(totalCost)}）`}
          </button>
        </form>
      </div>
    </div>
  );
}
