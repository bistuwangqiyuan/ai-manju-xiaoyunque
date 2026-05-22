'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, Genre } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { Sparkles, ArrowRight } from 'lucide-react';

export default function TemplatesPage() {
  const { t, locale } = useI18n();
  const [genres, setGenres] = useState<Genre[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listGenres().then(setGenres).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-cinnabar-700 text-sm font-medium mb-2">
          <Sparkles className="w-4 h-4" />
          {t('nav.templates')}
        </div>
        <h1 className="font-serif text-4xl text-ink-900 mb-2">5 大题材，一键开剧</h1>
        <p className="text-ink-600 max-w-2xl">
          {locale === 'en'
            ? 'Pick a genre template, give a theme, AI generates the novel + 10 episodes + master + cover for you.'
            : '选择题材模板，输入主题，AI 自动生成小说 + 10 集分镜 + 母带 + 海报。'}
        </p>
      </div>

      {err && (
        <div className="card p-4 mb-6 text-red-700 bg-red-50">{err}</div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        {genres.map((g) => (
          <div key={g.id} className="card p-6 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="badge bg-cinnabar-100 text-cinnabar-800">{g.aspect_ratio}</div>
              <div className="text-xs text-ink-500 font-mono">{g.style_id}</div>
            </div>
            <h2 className="font-serif text-2xl text-ink-900 mb-1">
              {locale === 'en' ? g.name_en : g.name_zh}
            </h2>
            <div className="text-xs text-ink-500 mb-2">{g.name_en} · {g.name_zh}</div>
            <p className="text-sm text-ink-700 mb-4 line-clamp-3">{g.description}</p>
            <div className="text-xs text-ink-600 mb-4">
              <div className="font-semibold mb-1">{locale === 'en' ? 'Sample themes' : '示例主题'}</div>
              <ul className="space-y-1">
                {g.sample_themes.slice(0, 3).map((th, i) => (
                  <li key={i} className="text-ink-700">· {th}</li>
                ))}
              </ul>
            </div>
            <Link
              href={`/dashboard/new?genre=${encodeURIComponent(g.id)}`}
              className="mt-auto inline-flex items-center justify-center gap-1 btn-primary text-sm"
            >
              {locale === 'en' ? 'Start with this template' : '用此模板开剧'}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ))}
        {genres.length === 0 && !err && (
          <div className="col-span-full text-center text-ink-500 py-12">{t('common.loading')}</div>
        )}
      </div>
    </div>
  );
}
