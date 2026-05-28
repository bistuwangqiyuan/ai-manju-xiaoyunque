'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Check, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: '¥0',
    period: '',
    description: '每日 20 集免费，零成本试用',
    features: [
      '✅ 每日 20 集 免费生成',
      '✅ 全部古风 / 武侠 / 都市风格',
      '✅ 1080p MP4 永久下载',
      '✅ 跨集 ArcFace ≥ 0.80 一致性',
      '✅ 质量评分 ≥ 90 才放行',
      '⚠️ 单次只能 1 集（不可批量）',
    ],
    cta: '立即注册',
    highlight: false,
  },
  {
    id: 'starter',
    name: 'Pro',
    price: '¥0.72',
    period: '/集起',
    description: '按成本×1.1 计费 · 充值即用',
    features: [
      '✅ 不限每日生成数',
      '✅ 一次最多 10 集套装',
      '✅ 高光集走 Veo / Sora 精修',
      '✅ 4K 上扫 + 主题曲',
      '✅ 优先队列（≤ 3 并发）',
      '✅ 充值任意金额自动升级',
      '✅ 透明计费：成本 ¥0.65 × 1.10',
    ],
    cta: '充值升级',
    highlight: true,
  },
  {
    id: 'studio',
    name: 'Studio',
    price: '定制',
    period: '',
    description: '企业版 / API / 私有部署',
    features: [
      '🏢 不限部数月度套餐',
      '🏢 IP / 风格定制锚点',
      '🏢 API 接入 / Webhook',
      '🏢 SLA 99.9% 优先队列',
      '🏢 私有部署 / 数据不出域',
      '🏢 专属客户成功',
    ],
    cta: '联系销售',
    highlight: false,
  },
];

export default function PricingPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const onBuy = async (planId: string) => {
    setErr(null);
    if (!user) {
      router.push(`/signup?next=/pricing`);
      return;
    }
    if (planId === 'free') {
      router.push('/dashboard');
      return;
    }
    if (planId === 'studio') {
      window.location.href = 'mailto:sales@example.com?subject=小云雀工作室版咨询';
      return;
    }
    setLoading(planId);
    try {
      const { url } = await api.createCheckout(planId);
      window.location.href = url;
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-20">
      <div className="text-center mb-12">
        <h1 className="font-serif text-4xl md:text-5xl text-ink-900 mb-3">
          定价方案
        </h1>
        <p className="text-ink-600">
          透明计费，按集结算。注册即赠 ¥100 体验金。
        </p>
      </div>
      {err && (
        <div className="max-w-md mx-auto mb-6 p-3 rounded-lg bg-cinnabar-100 text-cinnabar-800 text-sm">
          {err}
        </div>
      )}
      <div className="grid md:grid-cols-3 gap-6">
        {PLANS.map((p) => (
          <div
            key={p.id}
            className={`card p-8 flex flex-col ${
              p.highlight ? 'ring-2 ring-cinnabar-600 scale-[1.02]' : ''
            }`}
          >
            {p.highlight && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge bg-cinnabar-600 text-white">
                <Sparkles className="w-3 h-3 mr-1" /> 热门
              </div>
            )}
            <div className="font-serif text-2xl text-ink-900 mb-1">{p.name}</div>
            <div className="text-ink-600 text-sm mb-5">{p.description}</div>
            <div className="mb-6">
              <span className="font-serif text-4xl text-cinnabar-700">
                {p.price}
              </span>
              <span className="text-ink-500 ml-1">{p.period}</span>
            </div>
            <ul className="space-y-3 mb-8 flex-1">
              {p.features.map((f) => (
                <li key={f} className="flex text-sm text-ink-700">
                  <Check className="w-4 h-4 text-cinnabar-600 mr-2 flex-shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => onBuy(p.id)}
              disabled={loading === p.id}
              className={p.highlight ? 'btn-primary' : 'btn-secondary'}
            >
              {loading === p.id ? '跳转中…' : p.cta}
            </button>
          </div>
        ))}
      </div>

      <div className="mt-16 card p-8">
        <h2 className="font-serif text-2xl text-ink-900 mb-4">常见问题</h2>
        <dl className="grid md:grid-cols-2 gap-x-10 gap-y-6 text-sm">
          {[
            ['Free 怎么算配额？', '按 UTC 0:00 重置；已取消的任务不占用配额。'],
            ['Pro 怎么计费？', '每集成本 ¥0.65 × 1.10 = ¥0.72。10 集 = ¥7.15。'],
            ['充值即升 Pro 吗？', '是。首次任意金额充值，账户自动从 Free 升 Pro，无年费。'],
            ['质量怎么保证？', '内置 5 维评分（一致性/美学/贴合/字幕/节奏），低于 90 自动修复重试。'],
            ['失败可以退款吗？', '渲染失败按已完成进度比例退款；3 次自动修复后仍 < 90 分仍交付当前最优版本。'],
            ['可以并行渲染吗？', 'Pro/Studio 可同时排队多任务，3 个 worker 并发执行。'],
            ['支持哪些风格？', '当前古风 3D 国漫主推，武侠水墨/都市悬疑可选。Studio 可定制。'],
            ['用什么部署？', '前端 Vercel，后端 Railway，数据库 Neon Postgres。全球低延迟。'],
          ].map(([q, a]) => (
            <div key={q}>
              <dt className="font-semibold text-ink-900 mb-1">{q}</dt>
              <dd className="text-ink-600">{a}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
