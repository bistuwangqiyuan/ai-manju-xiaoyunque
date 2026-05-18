import Link from 'next/link';
import { ArrowRight, Sparkles, Film, ShieldCheck, Zap, Globe2, BookOpen } from 'lucide-react';
import { ShowcaseGallery } from '@/components/showcase-gallery';

const FEATURES = [
  {
    icon: Sparkles,
    title: '工业级一致性',
    desc: '跨集 ArcFace ≥ 0.80 角色锁定，五道修复防线，杜绝脸漂移、风格断层。',
  },
  {
    icon: Film,
    title: '9:16 古风 3D 国漫',
    desc: '小云雀 v2 + Seedance + 海外旗舰精修，整集级渲染，最高 4K 60fps。',
  },
  {
    icon: Zap,
    title: '一集 75-90 秒',
    desc: '钩子-冲突-反转-悬念四段节拍，红果 / 听花岛已验证的爆款短剧结构。',
  },
  {
    icon: ShieldCheck,
    title: '合规绿灯',
    desc: 'AIGC 双标识 + 广电备案模板，仅用公版与已授权素材，可直接上线分发。',
  },
  {
    icon: Globe2,
    title: '7-10 天交付',
    desc: '从小说到 10 集成片，全自动流水线，单集成本 ¥56-72，10 集仅 ¥866 起。',
  },
  {
    icon: BookOpen,
    title: '小说一键改编',
    desc: '编剧四模型流水线：Claude Opus 主笔 + DeepSeek 抽取 + Gemini 校验。',
  },
];

const STATS = [
  { num: '10', unit: '集', label: '一次交付' },
  { num: '90s', unit: '', label: '单集时长' },
  { num: '¥866', unit: '起', label: '十集成本' },
  { num: '0.80+', unit: '', label: 'ArcFace 一致性' },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-6xl px-6 pt-20 pb-24 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cinnabar-100 text-cinnabar-800 text-xs font-medium mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              v5 终极方案 · 小云雀 Agent 2.0 内核
            </div>
            <h1 className="font-serif text-5xl md:text-6xl font-bold text-ink-900 leading-tight mb-6">
              把一本小说<br />
              <span className="text-cinnabar-700">变成十集古风国漫</span>
            </h1>
            <p className="text-lg text-ink-700 mb-8 leading-relaxed">
              世界级 AI 漫剧工业流水线。小云雀 v2 为核心，海外旗舰精修，
              跨集人物锁定、五道修复防线、合规绿灯一气呵成。
              7-10 天，从文字到 10 集 × 90 秒 9:16 短剧。
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary">
                立即开始 <ArrowRight className="ml-2 w-4 h-4" />
              </Link>
              <Link href="/pricing" className="btn-secondary">查看定价</Link>
            </div>
            <div className="mt-10 grid grid-cols-4 gap-4">
              {STATS.map((s) => (
                <div key={s.label} className="text-center">
                  <div className="font-serif text-2xl text-ink-900">
                    {s.num}
                    <span className="text-sm text-ink-500 ml-1">{s.unit}</span>
                  </div>
                  <div className="text-xs text-ink-600 mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right visual */}
          <div className="relative">
            <div className="card aspect-[9/16] max-w-sm mx-auto relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-ink-200 via-ink-100 to-cinnabar-100" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center px-8">
                  <div className="seal w-20 h-20 text-4xl mx-auto mb-4">雀</div>
                  <div className="font-serif text-2xl text-ink-900 mb-2">聂小倩</div>
                  <div className="text-sm text-ink-600">第一集 · 兰若惊鸿</div>
                  <div className="mt-6 text-xs text-ink-500 font-mono">
                    9:16 · 1080×1920 · 75s
                  </div>
                </div>
              </div>
              <div className="absolute top-4 right-4 badge bg-black/60 text-white text-xs">
                ▶ 示例预览
              </div>
              <div className="absolute bottom-4 left-4 right-4 text-white">
                <div className="h-1 bg-white/20 rounded-full overflow-hidden">
                  <div className="h-full w-1/3 bg-cinnabar-500" />
                </div>
                <div className="flex justify-between text-xs mt-1 text-white/80">
                  <span>00:25</span>
                  <span>01:15</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Showcase Gallery */}
      <ShowcaseGallery />

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="text-center mb-14">
          <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-3">
            为什么选择小云雀
          </h2>
          <p className="text-ink-600">六大工业级能力，对标全球最强 AI 视频流水线</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-6 hover:shadow-2xl transition">
              <f.icon className="w-8 h-8 text-cinnabar-600 mb-4" />
              <h3 className="font-semibold text-lg text-ink-900 mb-2">{f.title}</h3>
              <p className="text-sm text-ink-600 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="card p-10">
          <h2 className="font-serif text-3xl text-ink-900 mb-2">五壳工业流水线</h2>
          <p className="text-ink-600 mb-10">完整可复现的端到端架构 · 任意一壳可独立调用</p>
          <div className="grid md:grid-cols-5 gap-4">
            {[
              { n: '1', name: '编剧', desc: '四模型协同抽取节拍' },
              { n: '2', name: '角色资产', desc: '三重 ID 锁 + 14 张参考图' },
              { n: '3', name: '小云雀 v2', desc: '整集级有参考视频生成' },
              { n: '4', name: '质检修复', desc: 'ArcFace + 五道修复防线' },
              { n: '5', name: '后期', desc: 'TTS / BGM / 字幕 / 4K 上扫' },
            ].map((s) => (
              <div key={s.n} className="relative">
                <div className="font-serif text-3xl text-cinnabar-700 mb-1">
                  Shell {s.n}
                </div>
                <div className="font-semibold text-ink-900">{s.name}</div>
                <div className="text-xs text-ink-600 mt-1">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-4">
          准备好让你的小说<span className="text-cinnabar-700">活过来</span>了吗？
        </h2>
        <p className="text-ink-600 mb-8">
          注册即赠 ¥100 体验金，足够生成一集试看片。
        </p>
        <Link href="/signup" className="btn-primary text-base">
          免费注册 <ArrowRight className="ml-2 w-4 h-4" />
        </Link>
      </section>
    </>
  );
}
