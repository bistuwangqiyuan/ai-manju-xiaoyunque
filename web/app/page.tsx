import Link from 'next/link';
import { ArrowRight, Sparkles, Film, ShieldCheck, Zap, Award, BookOpen, Play } from 'lucide-react';
import { ShowcaseGallery } from '@/components/showcase-gallery';

const STEPS = [
  {
    n: '1',
    title: '免费注册',
    desc: '只要一个邮箱，赠 100 元体验金',
    icon: Sparkles,
  },
  {
    n: '2',
    title: '粘贴小说',
    desc: '把小说片段或大纲贴进去',
    icon: BookOpen,
  },
  {
    n: '3',
    title: '点击生成',
    desc: '等几分钟，下载 9:16 古风国漫',
    icon: Film,
  },
];

const TRUST = [
  { num: '96.81', unit: '/100', label: 'R40 实测均分' },
  { num: '95+', unit: '保证', label: '不达标自动重做' },
  { num: '3', unit: '集/天', label: '每天免费用' },
  { num: '¥0.72', unit: '/集', label: '充值即用' },
];

export default function HomePage() {
  return (
    <>
      {/* Hero — 简化到极致 */}
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-5xl px-6 pt-16 pb-12 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-medium mb-6">
            <Award className="w-3.5 h-3.5" />
            R40 实测均分 96.81/100 · 自动保证 95 分以上
          </div>
          <h1 className="font-serif text-5xl md:text-7xl font-bold text-ink-900 leading-[1.1] mb-6">
            把一段小说<br />
            <span className="text-cinnabar-700">变成一集古风漫剧</span>
          </h1>
          <p className="text-xl md:text-2xl text-ink-700 mb-10 max-w-2xl mx-auto leading-relaxed">
            粘贴文字 · 点击生成 · 下载视频。
            <br className="hidden sm:block" />
            <span className="text-base md:text-lg text-ink-600">每天 3 集免费，无需信用卡。</span>
          </p>

          {/* 超大双按钮 */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-10">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center px-8 py-4 rounded-xl bg-cinnabar-600 text-white text-lg font-semibold shadow-2xl hover:bg-cinnabar-700 hover:scale-105 transition"
            >
              免费试用，立即开始 <ArrowRight className="ml-2 w-5 h-5" />
            </Link>
            <a
              href="#showcase"
              className="inline-flex items-center justify-center px-8 py-4 rounded-xl border-2 border-ink-300 bg-white/80 text-ink-900 text-lg font-semibold hover:bg-white hover:border-ink-500 transition"
            >
              <Play className="mr-2 w-5 h-5 fill-cinnabar-600 text-cinnabar-600" />
              先看几个示例
            </a>
          </div>

          {/* Trust numbers */}
          <div className="grid grid-cols-4 gap-4 max-w-2xl mx-auto">
            {TRUST.map((s) => (
              <div key={s.label} className="text-center">
                <div className="font-serif text-2xl md:text-3xl text-ink-900">
                  {s.num}
                  <span className="text-sm text-ink-500 ml-1">{s.unit}</span>
                </div>
                <div className="text-xs text-ink-600 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 三步使用 */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <div className="text-center mb-10">
          <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-2">
            就 3 步，70 岁也能用
          </h2>
          <p className="text-ink-600">
            不用学软件，不用懂技术，会用浏览器就行
            <Link href="/guide" className="text-cinnabar-700 hover:underline ml-1">
              · 查看完整使用说明
            </Link>
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {STEPS.map((step, i) => (
            <div key={step.n} className="card p-8 text-center relative">
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-12 h-12 rounded-full bg-cinnabar-600 text-white font-serif text-2xl flex items-center justify-center shadow-lg">
                {step.n}
              </div>
              <step.icon className="w-12 h-12 text-cinnabar-600 mx-auto mt-4 mb-4" />
              <h3 className="font-serif text-2xl text-ink-900 mb-2">{step.title}</h3>
              <p className="text-base text-ink-700 leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link href="/signup" className="btn-primary text-base">
            就试一下 <ArrowRight className="ml-2 w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Showcase Gallery — 真实样本 */}
      <div id="showcase">
        <ShowcaseGallery />
      </div>

      {/* 评分保证 */}
      <section className="mx-auto max-w-4xl px-6 py-16">
        <div className="card p-10 text-center">
          <Award className="w-12 h-12 text-emerald-600 mx-auto mb-4" />
          <h2 className="font-serif text-3xl text-ink-900 mb-3">
            每一集都达 95 分以上
          </h2>
          <p className="text-ink-700 text-base max-w-2xl mx-auto mb-6 leading-relaxed">
            采用业内公认的工业评分标准（ArcFace、CLIP、LAION-Aesthetic），
            分 Tech / Visual / Narrative / Genre 4 大维度共 100 分。
            <strong>达不到 95 分？系统会自动重做最多 2 次，直到达标才交给你。</strong>
          </p>
          <Link href="/quality" className="btn-secondary">
            看评分方法
          </Link>
        </div>
      </section>

      {/* 最后 CTA */}
      <section className="mx-auto max-w-3xl px-6 py-20 text-center">
        <h2 className="font-serif text-4xl text-ink-900 mb-4">
          每天 3 集免费用 · 不用付钱
        </h2>
        <p className="text-lg text-ink-600 mb-8">
          注册时送 100 元体验金，足够生成一集试看片
        </p>
        <Link
          href="/signup"
          className="inline-flex items-center justify-center px-10 py-5 rounded-xl bg-cinnabar-600 text-white text-xl font-semibold shadow-2xl hover:bg-cinnabar-700 hover:scale-105 transition"
        >
          免费注册，1 分钟搞定 <ArrowRight className="ml-2 w-6 h-6" />
        </Link>
      </section>
    </>
  );
}
