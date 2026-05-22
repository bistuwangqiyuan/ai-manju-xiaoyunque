'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, ExportResult, MarketingCopy } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useI18n } from '@/lib/i18n';
import { ArrowLeft, Download, Megaphone } from 'lucide-react';

const PLATFORMS = [
  { id: 'douyin', name_zh: '抖音', name_en: 'Douyin', aspect: '9:16' },
  { id: 'kuaishou', name_zh: '快手', name_en: 'Kuaishou', aspect: '9:16' },
  { id: 'wechat_video', name_zh: '视频号', name_en: 'WeChat Video', aspect: '9:16' },
  { id: 'xiaohongshu', name_zh: '小红书', name_en: 'Little Red Book', aspect: '3:4' },
  { id: 'bilibili', name_zh: 'B 站', name_en: 'Bilibili', aspect: '16:9' },
  { id: 'youtube_shorts', name_zh: 'YouTube Shorts', name_en: 'YouTube Shorts', aspect: '9:16' },
];

function ExportInner() {
  const { user, loading: authLoading } = useAuth();
  const { t, locale } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const jobId = Number(search.get('id') || '0');
  const [selected, setSelected] = useState<string[]>(['douyin', 'wechat_video', 'youtube_shorts']);
  const [watermark, setWatermark] = useState(true);
  const [handle, setHandle] = useState('');
  const [results, setResults] = useState<ExportResult[]>([]);
  const [marketing, setMarketing] = useState<MarketingCopy | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/job/export?id=' + jobId);
  }, [authLoading, user, jobId, router]);

  useEffect(() => {
    if (!user || !jobId) return;
    api.getMarketingCopy(jobId).then(setMarketing).catch(() => {});
  }, [user, jobId]);

  const toggle = (id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  };

  const onExport = async () => {
    setBusy(true);
    setErr(null);
    try {
      const out = await api.exportPlatforms(jobId, selected, {
        add_watermark: watermark,
        account_handle: handle || undefined,
      });
      setResults(out);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Link href={`/dashboard/job?id=${jobId}`} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> {locale === 'en' ? 'Back' : '返回作品'}
      </Link>
      <h1 className="font-serif text-3xl text-ink-900 mb-1">{t('export.title')}</h1>
      <p className="text-ink-600 text-sm mb-6">
        {locale === 'en'
          ? 'Re-encode the master once per platform with the correct aspect ratio + watermark.'
          : '一次精剪母带 → 自动按各平台尺寸 + 水印重导，配套引流文案。'}
      </p>

      {marketing && (
        <div className="card p-5 mb-6 bg-cinnabar-50/30">
          <div className="flex items-center gap-2 text-cinnabar-800 font-semibold mb-2">
            <Megaphone className="w-4 h-4" />
            {t('job_detail.marketing')}
          </div>
          <div className="text-sm text-ink-900 font-semibold mb-1">{marketing.title}</div>
          <div className="text-sm text-ink-700 mb-2">{marketing.summary}</div>
          <div className="text-sm text-cinnabar-700 mb-2">🔥 {marketing.hook_copy}</div>
          <div className="flex flex-wrap gap-1">
            {marketing.hashtags.map((h, i) => (
              <span key={i} className="badge bg-ink-100 text-ink-700 text-xs">{h}</span>
            ))}
          </div>
        </div>
      )}

      <div className="card p-5 mb-6">
        <div className="font-semibold mb-3 text-ink-900">
          {locale === 'en' ? 'Choose platforms' : '选择平台'}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
          {PLATFORMS.map((p) => {
            const active = selected.includes(p.id);
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => toggle(p.id)}
                className={`p-3 rounded-lg border text-left transition ${
                  active
                    ? 'border-cinnabar-600 bg-cinnabar-50 ring-2 ring-cinnabar-300'
                    : 'border-ink-200 hover:border-ink-400'
                }`}
              >
                <div className="font-semibold text-sm text-ink-900">
                  {locale === 'en' ? p.name_en : p.name_zh}
                </div>
                <div className="text-xs text-ink-500">{p.aspect}</div>
              </button>
            );
          })}
        </div>

        <div className="grid sm:grid-cols-2 gap-3 mb-4">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={watermark}
              onChange={(e) => setWatermark(e.target.checked)}
            />
            <span>{t('export.watermark')}</span>
          </label>
          <input
            className="input text-sm"
            placeholder={locale === 'en' ? '@your-handle (optional)' : '账号 @ 名（可选）'}
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
          />
        </div>

        <button
          onClick={onExport}
          disabled={busy || selected.length === 0}
          className="btn-primary text-sm"
        >
          <Download className="w-4 h-4 mr-1" />
          {busy ? t('common.loading') : (locale === 'en' ? 'Generate exports' : '一键生成各平台版本')}
        </button>
      </div>

      {err && <div className="card p-4 mb-4 bg-red-50 text-red-800">{err}</div>}

      {results.length > 0 && (
        <div className="grid sm:grid-cols-2 gap-4">
          {results.map((r) => (
            <div key={r.platform} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold text-ink-900">{r.platform}</div>
                {r.width && r.height && (
                  <div className="badge bg-ink-100 text-ink-700 text-xs">{r.width}×{r.height}</div>
                )}
              </div>
              {r.caption && <div className="text-sm text-ink-700 mb-2">{r.caption}</div>}
              <div className="flex flex-wrap gap-1 mb-3">
                {r.hashtags?.map((h, i) => (
                  <span key={i} className="badge bg-ink-100 text-ink-700 text-xs">{h}</span>
                ))}
              </div>
              <a
                href={(process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000') + r.url}
                download
                className="btn-secondary text-xs inline-flex items-center"
              >
                <Download className="w-3.5 h-3.5 mr-1" />
                {locale === 'en' ? 'Download' : '下载'}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExportPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-6 py-16 text-center text-ink-600">…</div>}>
      <ExportInner />
    </Suspense>
  );
}
