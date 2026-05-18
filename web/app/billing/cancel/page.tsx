import Link from 'next/link';
import { XCircle } from 'lucide-react';

export default function BillingCancel() {
  return (
    <div className="mx-auto max-w-md px-6 py-20 text-center">
      <XCircle className="w-16 h-16 text-ink-400 mx-auto mb-4" />
      <h1 className="font-serif text-3xl text-ink-900 mb-2">已取消支付</h1>
      <p className="text-ink-600 mb-6">没关系，随时可以回来。</p>
      <div className="flex gap-3 justify-center">
        <Link href="/pricing" className="btn-primary">查看定价</Link>
        <Link href="/dashboard" className="btn-secondary">返回仪表盘</Link>
      </div>
    </div>
  );
}
