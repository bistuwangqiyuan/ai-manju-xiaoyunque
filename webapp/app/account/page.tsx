'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface MeData {
  authenticated: boolean;
  email?: string;
  tier?: 'free' | 'pro';
  dailyLimit?: number;       // -1 = unlimited (pro)
  usedToday?: number;
  creditBalance?: number;    // ¥
  costPerVideo?: number;     // ¥ per video for pro
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

  const isPro = me.tier === 'pro';
  const balance = me.creditBalance ?? 0;
  const costPerVideo = me.costPerVideo ?? 5.5;
  const videosRemaining = isPro ? Math.floor(balance / costPerVideo) : (me.dailyLimit ?? 3) - (me.usedToday ?? 0);

  return (
    <div className="max-w-2xl mx-auto pt-16 px-6">
      <Link href="/" className="text-sm text-ink2 hover:text-ink">
        ← 返回首页
      </Link>
      <h1 className="mt-6 text-3xl font-semibold">账户中心</h1>

      <div className="mt-8 rounded-2xl border border-line bg-white p-6 space-y-4">
        <Row label="邮箱" value={me.email!} />
        <Row label="套餐" value={isPro ? '⭐ Pro 充值用户' : '免费用户'} />
        {isPro ? (
          <>
            <Row label="账户余额" value={`¥${balance.toFixed(2)}`} highlight />
            <Row label="单次扣费" value={`¥${costPerVideo.toFixed(2)} / 视频`} hint="按火山方舟成本 1.1× 计费" />
            <Row label="今日已生成" value={`${me.usedToday} 条（无上限）`} />
            <Row label="剩余可生成" value={`约 ${videosRemaining} 条`} />
          </>
        ) : (
          <>
            <Row label="每日免费额度" value={`${me.usedToday}/${me.dailyLimit}（UTC 日历日重置）`} />
            <Row label="今日剩余" value={`${videosRemaining} 条`} highlight={videosRemaining > 0} />
          </>
        )}
      </div>

      <div className="mt-6 rounded-2xl border border-accent/20 bg-accent/5 p-6">
        <h2 className="text-lg font-medium text-ink">
          {isPro ? '继续充值' : '充值升级 Pro'}
        </h2>
        <p className="mt-2 text-sm text-ink2 leading-relaxed">
          {isPro
            ? '余额低于单次成本时会被拦截。建议保持 ≥ ¥50 余额。'
            : '充值即升级 Pro（自动），按 ¥5.50/视频 扣费，无每日上限。'}
        </p>
        <ul className="mt-3 text-sm text-ink2 space-y-1">
          <li>· 1 视频 = 15 秒 1080×1920 竖屏国漫</li>
          <li>· 实际成本：火山方舟 Skylark 2.0 ¥5/视频</li>
          <li>· 平台服务费：1.1× 成本 = <strong>¥5.50/视频</strong></li>
          <li>· 推荐充值：¥55 (10 条) / ¥110 (20 条) / ¥550 (100 条)</li>
        </ul>
        <p className="mt-4 text-sm text-ink2">
          暂未对接 Stripe/Alipay，请发邮件申请充值：
        </p>
        <a
          href={`mailto:hello@yunque-manhua.com?subject=申请充值&body=邮箱: ${encodeURIComponent(me.email!)}%0A充值金额: ¥`}
          className="mt-3 inline-flex items-center px-5 h-11 rounded-full bg-ink text-white text-sm font-medium hover:bg-black"
        >
          发邮件申请充值
        </a>
      </div>

      <button
        onClick={logout}
        className="mt-8 text-sm text-ink2 hover:text-ink underline"
      >
        退出登录
      </button>
    </div>
  );
}

function Row({ label, value, highlight, hint }: { label: string; value: string; highlight?: boolean; hint?: string }) {
  return (
    <div className="flex items-start justify-between text-sm">
      <div>
        <div className="text-ink2">{label}</div>
        {hint && <div className="text-xs text-ink2/70 mt-0.5">{hint}</div>}
      </div>
      <span className={`font-medium ${highlight ? 'text-accent' : 'text-ink'}`}>{value}</span>
    </div>
  );
}
