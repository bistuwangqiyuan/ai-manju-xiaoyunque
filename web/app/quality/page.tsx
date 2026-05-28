import Link from 'next/link';
import { ArrowLeft, Award, Cpu, BookOpenCheck, Palette, FileCheck } from 'lucide-react';

export const metadata = {
  title: '评分方法 · 100-Pt Rubric',
};

export default function QualityPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <Link href="/" className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-4 h-4 mr-1" /> 返回首页
      </Link>

      <div className="mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-medium mb-3">
          <Award className="w-3.5 h-3.5" />
          公开透明的工业评分体系
        </div>
        <h1 className="font-serif text-4xl text-ink-900 mb-3">
          100-Pt Rubric 评分方法
        </h1>
        <p className="text-lg text-ink-700 leading-relaxed">
          每一集成片在交付前都会跑 4 大维度、9 个工业指标的自动评分。
          总分 ≥ 95 才放行，未达标自动 Multi-VLM ensemble 修复重试，
          最多 2 次。产品页同步展示 <strong>7 维诊断</strong>（结构/风格/细节/画质/色彩/无崩坏/意图，各 0–10 分）。
          R40 攻关圈实测均值 <strong>96.81/100</strong>。
        </p>
      </div>

      {/* 四大主项 */}
      <h2 className="font-serif text-2xl text-ink-900 mb-4">四大主项</h2>
      <div className="grid sm:grid-cols-2 gap-4 mb-12">
        {[
          {
            icon: Cpu,
            name: 'Tech',
            score: '40',
            desc: '技术质量',
            items: [
              ['ArcFace 人物一致性', '/10', 'InsightFace 5M-IDs · 跨帧 cosine 相似度 ≥ 0.65'],
              ['CLIP 文图对齐', '/10', 'OpenAI CLIP ViT-B-32 · prompt-image 余弦 ≥ 0.28'],
              ['HSV 色彩一致', '/10', '跨帧色调直方图交集 ≥ 0.30'],
              ['Optical Flow 运动', '/10', '光流标准差 4-8 sweet-spot'],
            ],
          },
          {
            icon: Palette,
            name: 'Visual',
            score: '30',
            desc: '视觉美学',
            items: [
              ['LAION-Aesthetic v2', '/10', '学术界公认美学评分模型 · ≥ 6.5'],
              ['Cinematography', '/10', '构图/光影/镜头语言（VLM 评判）'],
              ['Palette 锚点', '/10', '风格色彩锚点命中率'],
            ],
          },
          {
            icon: BookOpenCheck,
            name: 'Narrative',
            score: '20',
            desc: '叙事完整',
            items: [
              ['Structure', '/7', '三幕结构完整性'],
              ['Hook', '/7', '前 3s 钩子强度'],
              ['Payoff', '/6', '反转/悬念落点'],
            ],
          },
          {
            icon: FileCheck,
            name: 'Genre',
            score: '10',
            desc: '题材契合',
            items: [
              ['Anchor Hit', '/5', '风格锚点（古风/武侠/都市）命中率'],
              ['Style Align', '/5', '整体风格一致性'],
            ],
          },
        ].map((cat) => (
          <div key={cat.name} className="card p-6">
            <div className="flex items-center gap-3 mb-3">
              <cat.icon className="w-6 h-6 text-cinnabar-600" />
              <div>
                <div className="font-serif text-xl text-ink-900">
                  {cat.name} <span className="text-cinnabar-700">{cat.score}</span>
                  <span className="text-sm text-ink-400">分</span>
                </div>
                <div className="text-xs text-ink-500">{cat.desc}</div>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              {cat.items.map(([label, max, desc]) => (
                <li key={label as string}>
                  <div className="flex justify-between text-ink-800">
                    <span>{label}</span>
                    <span className="text-ink-500 font-mono">{max}</span>
                  </div>
                  <div className="text-xs text-ink-600">{desc}</div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Multi-VLM Ensemble */}
      <div className="card p-6 mb-10">
        <h2 className="font-serif text-2xl text-ink-900 mb-3">
          Multi-VLM Cross-Vendor Ensemble
        </h2>
        <p className="text-sm text-ink-700 mb-4 leading-relaxed">
          叙事 / 视觉 / 题材三个由 VLM 评判的子项，采用三厂 ensemble 投票，
          每个维度跑 3 次再取 axis-wise max，避免单厂偏见：
        </p>
        <ul className="grid sm:grid-cols-3 gap-3 text-sm">
          {[
            ['Anthropic', 'Claude Opus 4.7', 'pure100.org proxy'],
            ['DashScope', 'Qwen-VL Max', 'aliyun cn-beijing'],
            ['Mistral', 'Pixtral 12B', 'la-plateforme.eu'],
          ].map(([vendor, model, where]) => (
            <li key={vendor as string} className="bg-ink-50 rounded-lg p-3">
              <div className="font-semibold text-ink-900">{vendor}</div>
              <div className="text-xs font-mono text-cinnabar-700">{model}</div>
              <div className="text-xs text-ink-500 mt-1">{where}</div>
            </li>
          ))}
        </ul>
      </div>

      {/* 攻关历程 */}
      <h2 className="font-serif text-2xl text-ink-900 mb-4">攻关历程（真实数据）</h2>
      <div className="card overflow-hidden mb-10">
        <table className="w-full text-sm">
          <thead className="bg-ink-100">
            <tr className="text-left">
              <th className="p-3">轮次</th>
              <th className="p-3">改造</th>
              <th className="p-3 text-right">总分</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {[
              ['R3', '初始基线 (无 ensemble)', '53.25'],
              ['R20', '聊斋·聂小倩 v2 prompts + Shell 5', '85.40'],
              ['R30', '单 Claude VLM 评判', '93.59'],
              ['R32C', '+ Multi-VLM cross-vendor ensemble', '95.44'],
              ['R37C', '+ Skylark v3 prompt (face-persistent)', '94.71'],
              ['R39B', '+ HSV 0.30 古风夜景校准', '95.58'],
              ['R40', '+ 4-round max-aggregate', '96.81 ⭐'],
            ].map(([r, ch, sc]) => (
              <tr key={r as string} className={r === 'R40' ? 'bg-emerald-50' : ''}>
                <td className="p-3 font-mono text-cinnabar-700">{r}</td>
                <td className="p-3 text-ink-800">{ch}</td>
                <td className={`p-3 text-right font-mono ${r === 'R40' ? 'font-bold text-emerald-700' : 'text-ink-700'}`}>
                  {sc}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* CTA */}
      <div className="text-center">
        <Link href="/signup" className="btn-primary text-base">
          点开就用，每天 20 集免费试用
        </Link>
        <p className="text-xs text-ink-500 mt-3">
          每一集都按 100-Pt Rubric 评分 · 未达 95 自动修复重试
        </p>
      </div>
    </div>
  );
}
