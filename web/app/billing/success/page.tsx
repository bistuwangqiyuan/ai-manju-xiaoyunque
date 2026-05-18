'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { CheckCircle2 } from 'lucide-react';

export default function BillingSuccess() {
  const { refresh } = useAuth();
  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="mx-auto max-w-md px-6 py-20 text-center">
      <CheckCircle2 className="w-16 h-16 text-emerald-600 mx-auto mb-4" />
      <h1 className="font-serif text-3xl text-ink-900 mb-2">支付成功</h1>
      <p className="text-ink-600 mb-6">余额已到账，可立即新建漫剧。</p>
      <div className="flex gap-3 justify-center">
        <Link href="/dashboard" className="btn-primary">前往仪表盘</Link>
        <Link href="/dashboard/new" className="btn-secondary">立即开始</Link>
      </div>
    </div>
  );
}
