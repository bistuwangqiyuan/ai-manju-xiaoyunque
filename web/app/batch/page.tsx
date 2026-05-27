'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, Batch, BatchItem, assetUrl, BACKEND_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useI18n } from '@/lib/i18n';
import { Upload, Play, RefreshCw, Download, Image as ImageIcon } from 'lucide-react';

export default function BatchPage() {
  const { user, loading: authLoading } = useAuth();
  const { t, locale } = useI18n();
  const router = useRouter();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/batch');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.listBatches().then(setBatches).catch((e) => setErr(e.message));
  }, [user]);

  const onUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      const created = await api.uploadBatchFiles(Array.from(files));
      const rows = await api.listBatches();
      setBatches(rows);
      // Auto-run the new batch
      await api.runBatch(created.id);
      const refreshed = await api.listBatches();
      setBatches(refreshed);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="font-serif text-4xl text-ink-900 mb-1">{t('batch.title')}</h1>
          <p className="text-ink-600 max-w-2xl">
            {locale === 'en'
              ? 'Upload images, choose style + genre, AI auto-redraws + scores + exports a ZIP.'
              : '上传图片，选择风格 + 题材，AI 自动转绘 + 7 维评分 + 一键 ZIP 导出。'}
          </p>
        </div>
        <div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden"
            onChange={(e) => onUpload(e.target.files)}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            {busy ? t('common.loading') : t('batch.upload')}
          </button>
        </div>
      </div>

      {err && (
        <div className="card p-4 mb-4 bg-red-50 text-red-800">{err}</div>
      )}

      {batches.length === 0 ? (
        <div className="card p-12 text-center">
          <ImageIcon className="w-12 h-12 mx-auto text-ink-300 mb-4" />
          <div className="text-ink-700 mb-2 font-semibold">
            {locale === 'en' ? 'No batches yet' : '还没有批次'}
          </div>
          <div className="text-sm text-ink-500 mb-4">
            {locale === 'en' ? 'Click "Upload files" to create your first batch.' : '点击「上传文件」创建第一个批次。'}
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          {batches.map((b) => (
            <BatchCard key={b.id} batch={b} onRefresh={() => api.listBatches().then(setBatches)} />
          ))}
        </div>
      )}
    </div>
  );
}

function BatchCard({ batch, onRefresh }: { batch: Batch; onRefresh: () => void }) {
  const { t } = useI18n();
  const [items, setItems] = useState<BatchItem[]>(batch.items);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setItems(batch.items);
  }, [batch.items]);

  const onRunAgain = async () => {
    await api.runBatch(batch.id);
    onRefresh();
  };

  const onExport = async () => {
    setExporting(true);
    try {
      const { url } = await api.exportBatch(batch.id);
      const backend = BACKEND_URL;
      window.open(`${backend}${url}`, '_blank');
    } finally {
      setExporting(false);
    }
  };

  const onItemRedraw = async (itemId: number) => {
    const it = await api.redrawBatchItem(batch.id, itemId);
    setItems((prev) => prev.map((p) => (p.id === itemId ? it : p)));
  };

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <div className="font-serif text-xl text-ink-900">{batch.name}</div>
          <div className="text-xs text-ink-500 font-mono">#{batch.id} · {batch.style} · {batch.genre} · {batch.aspect_ratio}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge bg-ink-100 text-ink-700">{batch.finished_items}/{batch.total_items}</span>
          <span className={`badge ${batch.status === 'succeeded' ? 'bg-emerald-100 text-emerald-800' : batch.status === 'running' ? 'bg-cinnabar-100 text-cinnabar-800' : 'bg-ink-100 text-ink-600'}`}>
            {t(`common.${batch.status}`, batch.status)}
          </span>
          <button onClick={onRunAgain} className="btn-ghost text-xs"><RefreshCw className="w-3.5 h-3.5 mr-1" />{t('batch.run')}</button>
          <button disabled={exporting} onClick={onExport} className="btn-secondary text-xs">
            <Download className="w-3.5 h-3.5 mr-1" />{t('batch.export_zip')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 mt-3">
        {items.map((it) => (
          <div key={it.id} className="border border-ink-200 rounded-lg overflow-hidden bg-ink-50/40">
            <div className="aspect-[3/4] bg-ink-100 overflow-hidden">
              {it.result_url ? (
                <img
                  src={assetUrl(it.result_url)}
                  alt={`item ${it.id}`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-ink-400 text-xs">
                  {it.status}
                </div>
              )}
            </div>
            <div className="p-2 text-xs">
              <div className="flex justify-between mb-1">
                <span className="text-ink-500">#{it.id}</span>
                <span className={it.passed ? 'text-emerald-700 font-mono' : 'text-amber-700 font-mono'}>
                  {it.overall_score != null ? it.overall_score.toFixed(1) : '—'}
                </span>
              </div>
              <button onClick={() => onItemRedraw(it.id)} className="text-cinnabar-700 hover:text-cinnabar-900 text-[11px]">
                ↻ {t('batch.redraw_item')}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
