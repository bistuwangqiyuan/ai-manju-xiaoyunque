'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { formatYuan } from '@/lib/utils';
import { Sparkles, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const STYLES = [
  { id: 'ancient_3d_guoman', label: '古风 3D 国漫', desc: '60/30/10 复合风格锚点' },
  { id: 'wuxia_ink', label: '武侠水墨', desc: '黑白水墨 + 动态分镜' },
  { id: 'urban_drama', label: '都市悬疑', desc: '现代感 + 强光影对比' },
];

const PER_EPISODE_CENTS = 9900; // ¥99/集

export default function NewJobPage() {
  const { user, loading: authLoading, refresh } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [style, setStyle] = useState(STYLES[0].id);
  const [episodes, setEpisodes] = useState(1);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/new');
  }, [authLoading, user, router]);

  const cost = episodes * PER_EPISODE_CENTS;
  const enough = user ? user.credits_cents >= cost : false;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (excerpt.trim().length < 50) {
      setErr('小说片段至少 50 字');
      return;
    }
    if (!enough) {
      setErr('余额不足，请先充值');
      return;
    }
    setLoading(true);
    try {
      const job = await api.createJob({
        title: title || '未命名漫剧',
        novel_excerpt: excerpt,
        style,
        episodes,
      });
      await refresh();
      router.push(`/dashboard/jobs/${job.id}`);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || !user) {
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
        <h1 className="font-serif text-3xl text-ink-900 mb-1">新建漫剧</h1>
        <p className="text-ink-600 text-sm mb-8">
          填写文本与风格，提交后流水线自动启动。
        </p>

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
            <label className="label">集数（1-10）</label>
            <input
              type="range"
              min={1}
              max={10}
              value={episodes}
              onChange={(e) => setEpisodes(Number(e.target.value))}
              className="w-full accent-cinnabar-600"
            />
            <div className="flex justify-between text-sm">
              <span className="text-ink-700">{episodes} 集 × 90s</span>
              <span className="text-cinnabar-700 font-semibold">
                {formatYuan(cost)}
              </span>
            </div>
          </div>

          <div className="card !shadow-none p-4 bg-ink-50/60">
            <div className="flex items-start gap-3 text-sm">
              <Sparkles className="w-5 h-5 text-cinnabar-600 flex-shrink-0 mt-0.5" />
              <div className="text-ink-700">
                当前余额{' '}
                <span className="font-semibold text-ink-900">
                  {formatYuan(user.credits_cents)}
                </span>
                ，本任务预计花费{' '}
                <span className="font-semibold text-cinnabar-700">
                  {formatYuan(cost)}
                </span>
                。
                {!enough && (
                  <Link
                    href="/pricing"
                    className="ml-2 text-cinnabar-700 underline"
                  >
                    去充值
                  </Link>
                )}
              </div>
            </div>
          </div>

          {err && (
            <div className="p-3 rounded-lg bg-cinnabar-100 text-cinnabar-800 text-sm">
              {err}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={loading || !enough}
          >
            {loading ? '提交中…' : `提交渲染任务（${formatYuan(cost)}）`}
          </button>
        </form>
      </div>
    </div>
  );
}
