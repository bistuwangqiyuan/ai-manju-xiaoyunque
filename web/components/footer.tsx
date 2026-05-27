export function Footer() {
  return (
    <footer className="mt-24 border-t border-ink-200/60 bg-ink-50/40">
      <div className="mx-auto max-w-6xl px-6 py-10 grid gap-8 md:grid-cols-3 text-sm text-ink-700">
        <div>
          <div className="font-serif text-lg text-ink-900 mb-2">小云雀 · 漫剧产线</div>
          <p className="text-ink-600 leading-relaxed">
            世界级 AI 漫剧工业流水线，将公版小说一键化为
            9:16 古风 3D 国漫。
          </p>
        </div>
        <div>
          <div className="font-semibold mb-2">产品</div>
          <ul className="space-y-1">
            <li><a href="/guide">使用说明</a></li>
            <li><a href="/pricing">定价方案</a></li>
            <li><a href="/dashboard">控制台</a></li>
            <li><a href="/quality">评分方法</a></li>
          </ul>
        </div>
        <div>
          <div className="font-semibold mb-2">合规</div>
          <ul className="space-y-1 text-ink-600">
            <li>所有产出 AIGC 双标识</li>
            <li>广电备案模板内置</li>
            <li>仅用公版 / 授权素材</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-ink-200/60 py-4 text-center text-xs text-ink-500">
        © {new Date().getFullYear()} 小云雀 AI 漫剧 · 由 Vercel + Railway 驱动
      </div>
    </footer>
  );
}
