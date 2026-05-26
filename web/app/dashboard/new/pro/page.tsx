'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { Crown, ArrowLeft, Sliders } from 'lucide-react';

const ASPECTS = ['9:16', '16:9', '1:1'];
const RESOLUTIONS = ['1080p', '2K', '4K'];
const FPS_OPTIONS = [24, 25, 30];
const SUBTITLE_STYLES = [
  'modern_sans', 'modern_round',
  'ancient_kai', 'ancient_seal',
  'voiceover', 'danmu_top', 'danmu_roll',
];
const CONFIRM_STEPS = [
  'novel', 'screenplay', 'characters', 'scenes',
  'storyboard', 'frames', 'qa', 'tts', 'compose',
];

export default function ProModePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [aspect, setAspect] = useState('9:16');
  const [resolution, setResolution] = useState('1080p');
  const [fps, setFps] = useState(24);
  const [duration, setDuration] = useState(80);
  const [subtitleStyle, setSubtitleStyle] = useState('modern_sans');
  const [confirmSteps, setConfirmSteps] = useState<string[]>([
    'screenplay', 'storyboard', 'compose',
  ]);
  const [customStyleId, setCustomStyleId] = useState('');
  const [bgmQuery, setBgmQuery] = useState('');
  const [hook, setHook] = useState('');

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login?next=/dashboard/new/pro');
  }, [authLoading, user, router]);

  if (authLoading) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="text-center text-gray-500">加载中…</div>
      </main>
    );
  }

  const toggleStep = (step: string) =>
    setConfirmSteps((cur) =>
      cur.includes(step) ? cur.filter((s) => s !== step) : [...cur, step],
    );

  const buildQuery = () => {
    const p = new URLSearchParams({
      aspect_ratio: aspect,
      resolution,
      fps: String(fps),
      duration_per_episode_s: String(duration),
      subtitle_style: subtitleStyle,
      confirm_required_at_steps: confirmSteps.join(','),
    });
    if (customStyleId) p.set('custom_style_id', customStyleId);
    if (bgmQuery) p.set('bgm_query', bgmQuery);
    if (hook) p.set('hook', hook);
    return p.toString();
  };

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold">
            <Crown className="text-amber-500" />
            专业模式
          </h1>
          <p className="mt-2 text-gray-600">
            完整参数面板，逐项可调；高级用户与团队推荐使用。
          </p>
        </div>
        <Link
          href="/dashboard/new/wizard"
          className="flex items-center gap-1 rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          <ArrowLeft size={16} />
          返回简易模式
        </Link>
      </div>

      <section className="mb-8 rounded-lg border border-gray-200 p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Sliders size={18} />
          产出规格
        </h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Pick label="画幅比" value={aspect} options={ASPECTS} onChange={setAspect} />
          <Pick label="分辨率" value={resolution} options={RESOLUTIONS} onChange={setResolution} />
          <Pick label="帧率" value={String(fps)} options={FPS_OPTIONS.map(String)} onChange={(v) => setFps(parseInt(v))} />
          <NumInput label="每集时长 (s)" value={duration} onChange={setDuration} min={30} max={180} />
        </div>
      </section>

      <section className="mb-8 rounded-lg border border-gray-200 p-6">
        <h2 className="mb-4 text-lg font-semibold">画风与字幕</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700">自定义画风 ID（可选）</label>
            <input
              type="text"
              value={customStyleId}
              onChange={(e) => setCustomStyleId(e.target.value)}
              placeholder="例：style_a1b2c3"
              className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2"
            />
          </div>
          <Pick label="字幕样式" value={subtitleStyle} options={SUBTITLE_STYLES} onChange={setSubtitleStyle} />
        </div>
      </section>

      <section className="mb-8 rounded-lg border border-gray-200 p-6">
        <h2 className="mb-4 text-lg font-semibold">叙事与配乐</h2>
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">前 3 秒钩子文案</label>
            <textarea
              value={hook}
              onChange={(e) => setHook(e.target.value)}
              placeholder="例：重生归来的林夕睁眼便已是被害前夜……"
              rows={2}
              className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">BGM 描述 / 关键词</label>
            <input
              type="text"
              value={bgmQuery}
              onChange={(e) => setBgmQuery(e.target.value)}
              placeholder="古风宫斗，紧张高潮"
              className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2"
            />
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-lg border border-gray-200 p-6">
        <h2 className="mb-4 text-lg font-semibold">每步暂停确认</h2>
        <p className="mb-3 text-sm text-gray-600">
          勾选需要人工审核的环节，系统将在该步骤生成后暂停，等待你 approve / modify / reject。
        </p>
        <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
          {CONFIRM_STEPS.map((step) => {
            const isOn = confirmSteps.includes(step);
            return (
              <button
                key={step}
                onClick={() => toggleStep(step)}
                className={`rounded-md border px-3 py-2 text-sm transition ${
                  isOn
                    ? 'border-purple-500 bg-purple-50 text-purple-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {step}
              </button>
            );
          })}
        </div>
      </section>

      <div className="flex justify-end">
        <Link
          href={`/dashboard/new?${buildQuery()}`}
          className="rounded-md bg-purple-600 px-6 py-3 text-white shadow hover:bg-purple-700"
        >
          下一步：填写剧本来源
        </Link>
      </div>
    </main>
  );
}

function Pick({
  label, value, options, onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function NumInput({
  label, value, onChange, min, max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(parseInt(e.target.value || '0'))}
        className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2"
      />
    </div>
  );
}
