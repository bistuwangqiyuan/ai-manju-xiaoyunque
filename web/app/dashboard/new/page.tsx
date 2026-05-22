'use client';

import { useEffect, useState, FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api, Quota, Genre } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { formatYuan } from '@/lib/utils';
import { Sparkles, ArrowLeft, Crown, AlertTriangle, FileText, Type, Wand2 } from 'lucide-react';
import Link from 'next/link';

const STYLES = [
  { id: 'ancient_3d_guoman', label: '古风 3D 国漫', desc: '60/30/10 复合风格锚点' },
  { id: 'modern_cinematic', label: '现代电影感', desc: '写实 + teal-orange 调色' },
  { id: 'sweet_anime_3d', label: '甜宠半二次元', desc: '糖色调 + 高饱和柔光' },
  { id: 'noir_cinematic', label: '黑色 noir', desc: '强光影对比 + 阴影构图' },
  { id: 'xuanhuan_epic', label: '玄幻史诗', desc: '灵气粒子 + 撞色打斗' },
];

const LANGUAGES = [
  { code: 'Chinese', label: '中文' },
  { code: 'English', label: 'English' },
  { code: 'Japanese', label: '日本語' },
  { code: 'Korean', label: '한국어' },
];

type Mode = 'excerpt' | 'theme' | 'novel';

function NewJobInner() {
  const { user, loading: authLoading, refresh } = useAuth();
  const { t, locale } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const initialGenre = search.get('genre') || 'ancient';

  const [quota, setQuota] = useState<Quota | null>(null);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [genre, setGenre] = useState(initialGenre);
  const [mode, setMode] = useState<Mode>('excerpt');
  const [title, setTitle] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [theme, setTheme] = useState('');
  const [style, setStyle] = useState(STYLES[0].id);
  const [language, setLanguage] = useState('Chinese');
  const [episodes, setEpisodes] = useState(1);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/new');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.getQuota().then(setQuota).catch(() => {});
    api.listGenres().then(setGenres).catch(() => {});
  }, [user]);

  // Sync genre → style + episodes defaults
  useEffect(() => {
    const g = genres.find((gg) => gg.id === genre);
    if (g) {
      setStyle(g.style_id);
      if (mode !== 'excerpt') {
        setEpisodes(Math.min(quota?.tier === 'free' ? 1 : 10, g.default_episodes));
      }
    }
  }, [genre, genres, mode, quota?.tier]);

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
    if (mode === 'theme') {
      if (theme.trim().length < 4) {
        setErr(locale === 'en' ? 'Theme needs at least 4 characters.' : '请输入至少 4 字的主题。');
        return;
      }
    } else if (excerpt.trim().length < 50) {
      setErr(locale === 'en' ? 'Novel text needs at least 50 characters.' : '小说片段至少 50 字。');
      return;
    }
    if (freeBlocked) {
      setErr(locale === 'en' ? 'Free quota exhausted.' : '今日免费配额已用完，请充值升级 Pro。');
      return;
    }
    if (!enoughCredits) {
      setErr(locale === 'en' ? 'Insufficient credits.' : '余额不足，请先充值。');
      return;
    }
    setLoading(true);
    try {
      const job = await api.createJob({
        title: title || (mode === 'theme' ? `主题：${theme.slice(0, 12)}` : '未命名漫剧'),
        novel_excerpt: mode === 'theme' ? '' : excerpt,
        style,
        episodes: effectiveEpisodes,
        genre,
        mode,
        theme: mode === 'theme' ? theme : null,
        language,
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
    return <div className="mx-auto max-w-2xl px-6 py-16 text-center text-ink-600">{t('common.loading')}</div>;
  }

  const TABS: { id: Mode; icon: any; label: string }[] = [
    { id: 'excerpt', icon: FileText, label: t('new_job.tab_excerpt') },
    { id: 'novel',   icon: Type,     label: t('new_job.tab_novel') },
    { id: 'theme',   icon: Wand2,    label: t('new_job.tab_theme') },
  ];

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <Link href="/dashboard" className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> {locale === 'en' ? 'Back' : '返回仪表盘'}
      </Link>
      <div className="card p-8">
        <h1 className="font-serif text-3xl text-ink-900 mb-1">{t('new_job.title')}</h1>
        <p className="text-ink-700 text-base mb-6">
          {t('new_job.subtitle')}
        </p>

        {isFree ? (
          <div className="rounded-xl border border-ink-200 bg-ink-50/60 p-4 mb-6">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-cinnabar-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-ink-800 flex-1">
                <div className="font-semibold mb-1">
                  Free · 今日剩余 {quota.free_remaining_today}/{quota.free_daily_limit} 集
                </div>
                <div className="text-ink-600 text-xs leading-relaxed">
                  <Link href="/pricing" className="text-cinnabar-700 underline">升级 Pro</Link> 解锁多集 + 多题材 + 多语言。
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-cinnabar-200 bg-cinnabar-50/40 p-4 mb-6">
            <div className="flex items-center gap-2 text-sm">
              <Crown className="w-4 h-4 text-cinnabar-700" />
              <span className="font-semibold text-ink-900">{quota.tier.toUpperCase()}</span>
              <span className="text-ink-600">· 余额 {formatYuan(quota.credits_cents)}</span>
              <span className="text-ink-500 ml-auto text-xs">单集 {formatYuan(quota.cost_per_episode_cents)}</span>
            </div>
          </div>
        )}

        {/* Genre picker */}
        <div className="mb-5">
          <label className="label">{t('new_job.field_genre')}</label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {genres.map((g) => (
              <button
                type="button"
                key={g.id}
                onClick={() => setGenre(g.id)}
                className={`p-3 rounded-lg border text-left transition ${
                  genre === g.id
                    ? 'border-cinnabar-600 bg-cinnabar-50 ring-2 ring-cinnabar-300'
                    : 'border-ink-200 hover:border-ink-400 bg-white/60'
                }`}
              >
                <div className="text-xs font-semibold text-ink-900">
                  {locale === 'en' ? g.name_en : g.name_zh}
                </div>
                <div className="text-[10px] text-ink-500 truncate">{g.aspect_ratio}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Mode tabs */}
        <div className="mb-5">
          <div className="inline-flex rounded-lg border border-ink-200 overflow-hidden">
            {TABS.map((tab) => {
              const active = mode === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setMode(tab.id)}
                  className={`inline-flex items-center gap-1 px-4 py-2 text-sm border-r last:border-r-0 border-ink-200 ${
                    active
                      ? 'bg-cinnabar-50 text-cinnabar-800 font-semibold'
                      : 'bg-white text-ink-700 hover:bg-ink-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label className="label">{t('new_job.field_title')}</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={locale === 'en' ? 'e.g. Liaozhai · Nie Xiaoqian' : '例如：聊斋·聂小倩'}
              maxLength={80}
            />
          </div>

          {mode === 'theme' ? (
            <div>
              <label className="label">{t('new_job.field_theme')}</label>
              <textarea
                className="input min-h-[100px]"
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                placeholder={
                  locale === 'en'
                    ? 'e.g. "A young man encounters a mysterious girl on a moonlit night, uncovering a thousand-year mystery."'
                    : '例如：少年在月夜邂逅神秘少女，揭开千年前的一桩悬案。'
                }
                maxLength={400}
              />
              <div className="text-xs text-ink-500 mt-1">
                {locale === 'en' ? 'AI auto-generates the full novel for you.' : 'AI 会自动写出完整小说草稿。'}
              </div>
            </div>
          ) : (
            <div>
              <label className="label">{t('new_job.field_excerpt')}</label>
              <textarea
                className="input min-h-[200px] font-serif"
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
                placeholder={
                  locale === 'en'
                    ? 'Paste your novel / excerpt / outline (≥ 50 chars)…'
                    : '粘贴你想改编的小说片段、剧情大纲或人物设定…'
                }
                maxLength={mode === 'novel' ? 200000 : 20000}
              />
              <div className="text-xs text-ink-500 mt-1 text-right">
                {excerpt.length} / {mode === 'novel' ? 200000 : 20000}
              </div>
            </div>
          )}

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="label">{t('new_job.field_style')}</label>
              <select className="input" value={style} onChange={(e) => setStyle(e.target.value)}>
                {STYLES.map((s) => (
                  <option key={s.id} value={s.id}>{s.label} — {s.desc}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t('new_job.field_language')}</label>
              <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="label">
              {t('new_job.field_episodes')}（1-{maxEpisodes}）
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
              <span className="text-ink-700">{effectiveEpisodes} 集 × ~90s</span>
              <span className="text-cinnabar-700 font-semibold">
                {totalCost === 0
                  ? (locale === 'en' ? 'Free (uses daily quota)' : '免费（占用日配额）')
                  : formatYuan(totalCost)}
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
            {loading ? t('new_job.btn_loading') : t('new_job.btn_submit')}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function NewJobPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-2xl px-6 py-16 text-center text-ink-600">…</div>}>
      <NewJobInner />
    </Suspense>
  );
}
