'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, Shot, assetUrl } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useI18n } from '@/lib/i18n';
import { Scores7DPanel } from '@/components/WorkflowStepper';
import { ArrowLeft, RefreshCw, RotateCcw, Wrench, Check } from 'lucide-react';

function ShotsInner() {
  const { user, loading: authLoading } = useAuth();
  const { t, locale } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const jobId = Number(search.get('id') || '0');
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/job/shots?id=' + jobId);
  }, [authLoading, user, jobId, router]);

  const load = async () => {
    try {
      const rows = await api.listShots(jobId);
      setShots(rows);
      setErr(null);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    if (!user || !jobId) return;
    load();
  }, [user, jobId]);

  const onAction = async (sid: number, kind: 'reroll' | 'repair' | 'approve') => {
    setBusy(sid);
    try {
      let updated: Shot;
      if (kind === 'reroll') updated = await api.rerollShot(jobId, sid);
      else if (kind === 'repair') updated = await api.repairShot(jobId, sid, 'auto');
      else updated = await api.approveShot(jobId, sid);
      setShots((prev) => prev.map((s) => (s.id === sid ? updated : s)));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link href={`/dashboard/job?id=${jobId}`} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> {locale === 'en' ? 'Back' : '返回作品'}
      </Link>
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-serif text-3xl text-ink-900">{t('job_detail.shots')}</h1>
        <button onClick={load} className="btn-ghost text-sm"><RefreshCw className="w-4 h-4" /></button>
      </div>

      {err && <div className="card p-4 mb-4 bg-red-50 text-red-800">{err}</div>}

      {shots.length === 0 ? (
        <div className="card p-12 text-center text-ink-500">
          {locale === 'en'
            ? 'No shots yet — they appear once Step 4 (gacha render) starts.'
            : '还没有镜头 — Step 4「抽卡生视频」开始后这里会出现。'}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {shots.map((s) => (
            <div key={s.id} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-mono text-ink-600">{s.episode_id} · 镜 {s.shot_id}</div>
                <span className={`badge ${s.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                  {s.overall_score?.toFixed(1) ?? '—'} / 10
                </span>
              </div>
              {s.description && (
                <p className="text-xs text-ink-700 mb-3 line-clamp-2">{s.description}</p>
              )}
              {s.result_url && (
                <video
                  src={assetUrl(s.result_url)}
                  className="w-full aspect-[9/16] rounded mb-2 bg-black object-contain"
                  controls
                />
              )}
              {s.score_7d && <Scores7DPanel scores={s.score_7d} />}
              {s.repair_iters > 0 && (
                <div className="text-xs text-ink-500 mt-2">
                  {locale === 'en' ? `Auto-repair ×${s.repair_iters}` : `已自动修复 ${s.repair_iters} 次`}
                  {s.repair_routes?.length ? ` (${s.repair_routes.join('→')})` : ''}
                </div>
              )}
              <div className="flex gap-2 mt-3">
                <button
                  disabled={busy === s.id}
                  onClick={() => onAction(s.id, 'reroll')}
                  className="btn-ghost text-xs flex-1"
                >
                  <RotateCcw className="w-3.5 h-3.5 mr-1" />{t('job_detail.reroll')}
                </button>
                <button
                  disabled={busy === s.id}
                  onClick={() => onAction(s.id, 'repair')}
                  className="btn-ghost text-xs flex-1"
                >
                  <Wrench className="w-3.5 h-3.5 mr-1" />{t('job_detail.repair')}
                </button>
                <button
                  disabled={busy === s.id}
                  onClick={() => onAction(s.id, 'approve')}
                  className="btn-secondary text-xs flex-1"
                >
                  <Check className="w-3.5 h-3.5 mr-1" />{t('common.passed')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ShotsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-6 py-16 text-center text-ink-600">…</div>}>
      <ShotsInner />
    </Suspense>
  );
}
