'use client';

const STEPS = [
  { no: 1, label: '剧本分析' },
  { no: 2, label: '人物/资产' },
  { no: 3, label: '分镜提示词' },
  { no: 4, label: '抽卡生视频' },
  { no: 5, label: '初期粗剪' },
  { no: 6, label: '精剪审核' },
];

export function WorkflowStepper({ currentStep }: { currentStep: number }) {
  return (
    <div className="mb-6">
      <div className="flex flex-wrap gap-2 justify-between">
        {STEPS.map((s) => {
          const done = currentStep > s.no;
          const active = currentStep === s.no;
          return (
            <div
              key={s.no}
              className={`flex-1 min-w-[4.5rem] text-center px-2 py-2 rounded-lg text-xs border transition-colors ${
                done
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : active
                  ? 'bg-cinnabar-50 border-cinnabar-300 text-cinnabar-800 font-semibold'
                  : 'bg-ink-50 border-ink-200 text-ink-500'
              }`}
            >
              <div className="font-mono text-[10px] opacity-70">Step {s.no}</div>
              <div>{s.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Scores7DPanel({ scores }: { scores: Record<string, number> }) {
  const dims = [
    ['structure', '结构正确'],
    ['style', '风格一致'],
    ['detail', '细节完整'],
    ['clarity', '画质清晰'],
    ['color', '色彩协调'],
    ['no_deform', '无崩坏'],
    ['intent', '意图匹配'],
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
      {dims.map(([key, label]) => {
        const v = scores[key] ?? 0;
        return (
          <div key={key} className="bg-white/70 rounded-lg p-2 text-xs">
            <div className="text-ink-600">{label}</div>
            <div className="font-mono text-lg text-ink-900">{v.toFixed(1)}</div>
            <div className="h-1 bg-ink-100 rounded-full mt-1">
              <div
                className={`h-full ${v >= 8 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                style={{ width: `${(v / 10) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
