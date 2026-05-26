'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { Sparkles, ArrowRight, Crown } from 'lucide-react';

type HotTemplate = {
  id: string;
  label: string;
  genre: string;
  sub_genre?: string;
  aspect_ratio: string;
  resolution: string;
  duration_per_episode_s: number;
  hook_template: string;
  bgm_query: string;
  subtitle_style: string;
  cover_prompt: string;
};

export default function WizardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [templates, setTemplates] = useState<HotTemplate[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [lead, setLead] = useState('主角');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/new/wizard');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    fetch('/api/templates', { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => {
        setTemplates(d.templates || []);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [user]);

  if (authLoading || loading) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="text-center text-gray-500">加载中…</div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold">
            <Sparkles className="text-purple-500" />
            爆款模板 · 简易模式
          </h1>
          <p className="mt-2 text-gray-600">
            选一个模板，输入主角名，剩下交给 AI ——
            画风 / 镜头节奏 / 字幕 / 配乐自动套用。
          </p>
        </div>
        <Link
          href="/dashboard/new/pro"
          className="flex items-center gap-1 rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          <Crown size={16} />
          切到专业模式
        </Link>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700">主角名字</label>
        <input
          type="text"
          value={lead}
          onChange={(e) => setLead(e.target.value)}
          className="mt-2 w-64 rounded-md border border-gray-300 px-3 py-2"
          placeholder="主角"
        />
      </div>

      {error && (
        <div className="mb-6 rounded-md bg-red-50 p-4 text-red-700">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {templates.map((t) => {
          const isPicked = picked === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setPicked(t.id)}
              className={`flex flex-col rounded-lg border p-5 text-left transition-all ${
                isPicked
                  ? 'border-purple-500 bg-purple-50 shadow-md'
                  : 'border-gray-200 hover:border-gray-400'
              }`}
            >
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">{t.label}</h3>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                  {t.aspect_ratio} · {t.resolution} · {t.duration_per_episode_s}s
                </span>
              </div>
              <p className="mb-3 text-sm text-gray-600 line-clamp-3">
                {t.hook_template.replace('{lead}', lead)}
              </p>
              <div className="mt-auto flex flex-wrap gap-2 text-xs text-gray-500">
                <span className="rounded bg-gray-100 px-2 py-0.5">{t.genre}</span>
                {t.sub_genre && (
                  <span className="rounded bg-gray-100 px-2 py-0.5">
                    {t.sub_genre}
                  </span>
                )}
                <span className="rounded bg-gray-100 px-2 py-0.5">
                  {t.subtitle_style}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {picked && (
        <div className="mt-8 flex justify-end">
          <Link
            href={`/dashboard/new?template=${picked}&lead=${encodeURIComponent(lead)}`}
            className="flex items-center gap-2 rounded-md bg-purple-600 px-6 py-3 text-white shadow hover:bg-purple-700"
          >
            下一步：确认并生成
            <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </main>
  );
}
