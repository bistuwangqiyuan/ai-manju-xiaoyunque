'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, JobVersion, assetUrl } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useI18n } from '@/lib/i18n';
import { Scores7DPanel } from '@/components/WorkflowStepper';
import { ArrowLeft, RotateCcw, Award } from 'lucide-react';

function VersionsInner() {
  const { user, loading: authLoading } = useAuth();
  const { t, locale } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const jobId = Number(search.get('id') || '0');
  const [versions, setVersions] = useState<JobVersion[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/job/versions?id=' + jobId);
  }, [authLoading, user, jobId, router]);

  const load = async () => {
    try {
      const rows = await api.getJobVersions(jobId);
      setVersions(rows);
      setErr(null);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    if (!user || !jobId) return;
    load();
  }, [user, jobId]);

  const onRollback = async (v: number) => {
    if (!confirm(locale === 'en' ? `Rollback to v${v}?` : `回滚到 v${v}？`)) return;
    setBusy(v);
    try {
      await api.rollbackVersion(jobId, v);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Link href={`/dashboard/job?id=${jobId}`} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> {locale === 'en' ? 'Back' : '返回作品'}
      </Link>
      <h1 className="font-serif text-3xl text-ink-900 mb-2">{t('job_detail.versions')}</h1>
      <p className="text-ink-600 mb-6 text-sm">
        {locale === 'en'
          ? 'Every render run snapshots a version. You can rollback or compare scores.'
          : '每次渲染都会自动归档一个版本。可以一键回滚或对比 7 维评分。'}
      </p>

      {err && <div className="card p-4 mb-4 bg-red-50 text-red-800">{err}</div>}

      {versions.length === 0 ? (
        <div className="card p-12 text-center text-ink-500">
          {locale === 'en' ? 'No versions yet.' : '还没有版本记录。'}
        </div>
      ) : (
        <div className="space-y-4">
          {versions.map((v) => (
            <div key={v.id} className="card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Award className="w-4 h-4 text-cinnabar-600" />
                    <span className="font-serif text-xl text-ink-900">v{v.version_no}</span>
                    {v.quality_score != null && (
                      <span className={`badge ${v.quality_score >= 95 ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                        {v.quality_score}/100
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-ink-500 font-mono">
                    {new Date(v.created_at).toLocaleString()}
                  </div>
                </div>
                <button
                  disabled={busy === v.version_no}
                  onClick={() => onRollback(v.version_no)}
                  className="btn-secondary text-xs"
                >
                  <RotateCcw className="w-3.5 h-3.5 mr-1" />
                  {locale === 'en' ? 'Rollback' : '回滚到此版本'}
                </button>
              </div>
              {v.scores_7d && <Scores7DPanel scores={v.scores_7d} />}
              {v.notes && (
                <details className="text-xs text-ink-600 mt-3">
                  <summary className="cursor-pointer">{locale === 'en' ? 'Notes' : '备注'}</summary>
                  <pre className="whitespace-pre-wrap mt-2 bg-ink-50 p-2 rounded">{v.notes}</pre>
                </details>
              )}
              {v.result_url && (
                <a
                  href={assetUrl(v.result_url)}
                  download
                  className="btn-ghost text-xs mt-3 inline-block"
                >
                  ↓ master.mp4
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function VersionsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-6 py-16 text-center text-ink-600">…</div>}>
      <VersionsInner />
    </Suspense>
  );
}
