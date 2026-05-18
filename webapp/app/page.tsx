import { GeneratorForm } from '@/components/GeneratorForm';

export default function HomePage() {
  return (
    <main className="min-h-screen pb-24">
      <Header />
      <section className="pt-12 md:pt-20 pb-12 px-6">
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
            R40 实测 <strong className="text-ink">96.81/100</strong> 评分基线 ·
            基于火山方舟 Skylark Agent 2.0。
          </p>
        </div>
      </section>

      <section className="px-6">
        <GeneratorForm />
      </section>

      <Footer />
    </main>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-20 glass border-b border-line/50">
      <div className="max-w-6xl mx-auto px-6 h-12 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-accent" />
          云雀漫剧
        </div>
        <nav className="flex items-center gap-6 text-sm text-ink2">
          <a href="#about" className="hover:text-ink">关于</a>
          <a
            href="https://github.com/bistuwangqiyuan/ai-manju-xiaoyunque"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-ink"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
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
