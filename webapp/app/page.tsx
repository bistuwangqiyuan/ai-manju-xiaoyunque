import { Header } from '@/components/Header';
import { HomeShell } from '@/components/HomeShell';

export default function HomePage() {
  return (
    <main className="min-h-screen pb-24">
      <Header />
      <section className="pt-10 md:pt-16 pb-8 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
            云雀漫剧
          </h1>
          <p className="mt-3 text-xl md:text-2xl text-ink2 font-normal">
            AI 国漫一键生成
          </p>
          <p className="mt-6 text-base md:text-lg text-ink2 max-w-2xl mx-auto leading-relaxed">
            输入提示词，约 5 分钟后收获一段 15 秒 1080×1920 竖屏国漫短片。
            <br className="hidden md:block" />
            R40 实测峰值 <strong className="text-ink">97.10/100</strong>，3 集平均
            <strong className="text-ink">96.81/100</strong> · 基于火山方舟 Skylark Agent 2.0。
          </p>
          <div className="mt-5 inline-flex items-center gap-3 text-xs text-ink2">
            <span className="inline-flex items-center gap-1.5 px-3 h-7 rounded-full bg-white border border-line">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              免费 1 条/天
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 h-7 rounded-full bg-white border border-line">
              <span className="text-yellow-600">⭐</span> Pro 100 条/天
            </span>
            <a
              href="#samples"
              className="inline-flex items-center px-3 h-7 rounded-full bg-ink text-white"
            >
              看示例 ↓
            </a>
          </div>
        </div>
      </section>

      <HomeShell />

      <Footer />
    </main>
  );
}

function Footer() {
  return (
    <footer id="about" className="mt-24 px-6">
      <div className="max-w-4xl mx-auto pt-12 border-t border-line">
        <div className="grid md:grid-cols-3 gap-8 text-sm text-ink2">
          <div>
            <div className="text-ink font-medium mb-2">技术栈</div>
            <ul className="space-y-1">
              <li>Skylark Agent 2.0 (Seedance 2.0 fast 720p)</li>
              <li>HMAC-SHA256 V4 签名 · cn-north-1</li>
              <li>Next.js 14 + Vercel Functions</li>
            </ul>
          </div>
          <div>
            <div className="text-ink font-medium mb-2">合规</div>
            <ul className="space-y-1">
              <li>GB/T 45438-2025 AIGC 隐式标识</li>
              <li>不含显式水印（关闭）</li>
              <li>提示词内容审核（火山方舟前置）</li>
            </ul>
          </div>
          <div>
            <div className="text-ink font-medium mb-2">指标基线</div>
            <ul className="space-y-1">
              <li>R40 mean 96.81 / min 96.47 (聊斋·聂小倩 3 集)</li>
              <li>40 轮迭代优化历程</li>
              <li>Multi-VLM 跨厂 ensemble 评判</li>
            </ul>
          </div>
        </div>
        <div className="mt-12 pb-6 text-xs text-ink2 text-center">
          © 2026 云雀漫剧 · Built with Skylark Agent 2.0 ·
          {' '}
          <a
            href="https://github.com/bistuwangqiyuan/ai-manju-xiaoyunque"
            className="underline hover:text-ink"
          >
            源码开源
          </a>
        </div>
      </div>
    </footer>
  );
}
