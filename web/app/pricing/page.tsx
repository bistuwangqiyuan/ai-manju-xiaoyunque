'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Check, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';

const PLANS = [
  {
    id: 'starter',
    name: '试看版',
    price: '¥99',
    period: '/单集',
    description: '单集试水，先看效果再决定',
    features: [
      '1 集 75-90s 古风国漫',
      '小云雀 v2 标准画质',
      'ASS 字幕 + 1 条 BGM',
      'AIGC 双标识合规',
      'MP4 1080p 永久下载',
    ],
    cta: '购买单集',
    highlight: false,
  },
  {
    id: 'series',
    name: '十集套装',
    price: '¥1,299',
    period: '/十集',
    description: '完整一部短剧，热推上线',
    features: [
      '10 集 × 90s 古风国漫',
      '跨集 ArcFace ≥ 0.80 锁定',
      '高光集走 Veo / Sora 精修',
      '4K 上扫 + 主题曲(可选)',
      '7-10 天交付',
      '广电备案模板',
    ],
    cta: '购买十集',
    highlight: true,
  },
  {
    id: 'studio',
    name: '工作室版',
    price: '¥定制',
    period: '',
    description: '多部并行 / 私有部署',
    features: [
      '不限部数月度套餐',
      'IP / 风格定制锚点',
      '专属客户成功',
      'API 接入 / Webhook',
      'SLA 99.9% 优先队列',
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
            ['交付周期多久？', '单集 6-12 小时，十集套装 7-10 天。'],
            ['可以指定小说吗？', '可以上传任意公版或你拥有版权的文本。'],
            ['费用包含哪些？', '所有渲染、TTS、BGM、字幕、合规标识。'],
            ['失败可以退款吗？', '支持 3 次免费修复，仍不通过全额退款。'],
            ['支持哪些风格？', '当前主推古风 3D 国漫，更多风格陆续开放。'],
            ['用 Vercel + Railway 部署？', '是的，前端 Vercel，渲染 Worker 在 Railway。'],
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
