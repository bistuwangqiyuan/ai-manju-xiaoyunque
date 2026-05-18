'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface MeData {
  authenticated: boolean;
  email?: string;
  tier?: 'free' | 'pro';
  dailyLimit?: number;
  usedToday?: number;
  proUntil?: string | null;
}

export default function AccountPage() {
  const [me, setMe] = useState<MeData | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    fetch('/api/me', { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        setMe(d);
        setLoading(false);
        if (!d.authenticated) router.replace('/login');
      });
  }, [router]);

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/');
    router.refresh();
  }

  if (loading || !me) {
    return <div className="pt-32 text-center text-ink2">加载中…</div>;
  }
  if (!me.authenticated) return null;

  const tierLabel = me.tier === 'pro' ? '⭐ Pro' : '免费';
  const remaining = (me.dailyLimit ?? 0) - (me.usedToday ?? 0);

  return (
    <div className="max-w-2xl mx-auto pt-16 px-6">
      <Link href="/" className="text-sm text-ink2 hover:text-ink">
        ← 返回首页
      </Link>
      <h1 className="mt-6 text-3xl font-semibold">账户中心</h1>

      <div className="mt-8 rounded-2xl border border-line bg-white p-6 space-y-4">
        <Row label="邮箱" value={me.email!} />
        <Row label="套餐" value={tierLabel} />
        <Row label="每日额度" value={`${me.usedToday}/${me.dailyLimit}（剩余 ${remaining}）`} />
        {me.proUntil && (
          <Row label="Pro 有效期" value={new Date(me.proUntil).toLocaleString('zh-CN')} />
        )}
      </div>

      {me.tier === 'free' && (
        <div className="mt-6 rounded-2xl border border-accent/20 bg-accent/5 p-6">
          <h2 className="text-lg font-medium text-ink">升级到 Pro</h2>
          <p className="mt-2 text-sm text-ink2 leading-relaxed">
            Pro 用户每日 <strong className="text-ink">100 条</strong> 生成额度（免费版 1 条/天）。
            <br />
            目前支付通道尚未开通，请发邮件申请：
          </p>
          <a
            href={`mailto:hello@yunque-manhua.com?subject=申请升级 Pro&body=邮箱: ${encodeURIComponent(me.email!)}`}
            className="mt-4 inline-flex items-center px-5 h-11 rounded-full bg-ink text-white text-sm font-medium hover:bg-black"
          >
            发邮件申请 Pro
          </a>
        </div>
      )}

      <button
        onClick={logout}
        className="mt-8 text-sm text-ink2 hover:text-ink underline"
      >
        退出登录
      </button>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink2">{label}</span>
      <span className="text-ink font-medium">{value}</span>
    </div>
  );
}
