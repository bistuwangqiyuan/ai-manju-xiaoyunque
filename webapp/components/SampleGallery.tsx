'use client';

/**
 * SampleGallery — 真实 R40 已生成样片画廊（与 repo sample/*.mp4 同源）。
 */
import { useState } from 'react';

export interface Sample {
  src: string;
  poster: string;
  title: string;
  source: string;
  score: number;
  scoreLabel: string;
  taskId: string;
  prompt: string;
  promptVersion: 'v2' | 'v3';
  badge?: string;
}

export const SAMPLES: Sample[] = [
  {
    src: '/samples/nie03_yan_chixia.mp4',
    poster: '/samples/nie03_yan_chixia.jpg',
    title: '剑指燕赤霞',
    source: '聊斋·聂小倩',
    score: 97,
    scoreLabel: 'R40 实测 · 系统真实成片',
    taskId: 'sample-nie03',
    promptVersion: 'v3',
    badge: '⭐ 97',
    prompt:
      '【0-2s 锚定】超近大特写，雨后天青清晨，4K 大特写浅景深推镜锁定燕赤霞面部正面：30 岁亚裔道士剑客，右眉骨浅疤清晰可见，眼神刚毅沉稳目光微垂。\n\n【13-15s 钩子定格】剑骤然出鞘，一道青蓝剑光自下而上划过画面前景，frozen gesture。',
  },
  {
    src: '/samples/nie01_lanruosi.mp4',
    poster: '/samples/nie01_lanruosi.jpg',
    title: '兰若惊鸿',
    source: '聊斋·聂小倩',
    score: 97,
    scoreLabel: 'R40 实测',
    taskId: 'sample-nie01',
    promptVersion: 'v2',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，宁采臣面部占画面八成，目光微垂，烛火在瞳孔中倒映成一豆暖光。背景虚化兰若寺木格窗棂，月白冷青调主导。\n\n【13-15s 钩子定格】铜镜中突然浮出一道朦胧白衣身影，画面骤然定格，frozen gesture。',
  },
  {
    src: '/samples/nie02_appears.mp4',
    poster: '/samples/nie02_appears.jpg',
    title: '小倩出场',
    source: '聊斋·聂小倩',
    score: 96,
    scoreLabel: 'R40 实测',
    taskId: 'sample-nie02',
    promptVersion: 'v3',
    prompt:
      '【0-2s 锚定】超大特写正面镜头，聂小倩面部占画面八成，杏眼缓缓睁开，眉间一点朱砂痣居中黄金分割，肌肤月白透青。\n\n【13-15s 钩子定格】金币崩解为月白光尘，朱砂痣在逆光中亮如孤星，frozen gesture。',
  },
  {
    src: '/samples/xiyou01_immortal_stone.mp4',
    poster: '/samples/xiyou01_immortal_stone.jpg',
    title: '石猴出世',
    source: '西游记·石猴出世',
    score: 95,
    scoreLabel: 'R40 实测',
    taskId: 'sample-xiyou01',
    promptVersion: 'v2',
    prompt:
      '【0-2s 锚定】超大特写镜头，花果山顶仙石占画面八成，灵气流转，石身青黑泛金光斑，云雾缭绕。\n\n【13-15s 钩子定格】仙石上方一道金光骤然冲破云层，画面定格于裂纹与金光同框瞬间，frozen gesture。',
  },
  {
    src: '/samples/real05_moon_corridor.mp4',
    poster: '/samples/real05_moon_corridor.jpg',
    title: '回廊月影',
    source: '聊斋·系统真实生成',
    score: 96,
    scoreLabel: 'R40 实测',
    taskId: 'sample-real05',
    promptVersion: 'v3',
    prompt:
      '古风 3D 国漫，9:16 竖屏，月白冷青调，回廊烛火熄灭仅余月光，白衣倩影款步前行，禁止画面内文字。',
  },
  {
    src: '/samples/real06_spirit_hook.mp4',
    poster: '/samples/real06_spirit_hook.jpg',
    title: '魂影定格',
    source: '聊斋·系统真实生成',
    score: 96,
    scoreLabel: 'R40 实测',
    taskId: 'sample-real06',
    promptVersion: 'v3',
    prompt:
      '古风 3D 国漫，9:16 竖屏，15s 钩子镜，魂影与主角同框定格，月白侧光，禁止画面内文字。',
  },
];

export function SampleGallery({
  onPick,
}: {
  onPick: (sample: Sample) => void;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {SAMPLES.map((s, i) => (
        <SampleCard
          key={s.taskId}
          sample={s}
          open={openIndex === i}
          onToggle={() => setOpenIndex(openIndex === i ? null : i)}
          onPick={() => onPick(s)}
        />
      ))}
    </div>
  );
}

function SampleCard({
  sample,
  open,
  onToggle,
  onPick,
}: {
  sample: Sample;
  open: boolean;
  onToggle: () => void;
  onPick: () => void;
}) {
  return (
    <div className="group relative rounded-2xl overflow-hidden border border-line bg-black aspect-[9/16]">
      <video
        src={sample.src}
        poster={sample.poster}
        muted
        loop
        playsInline
        autoPlay
        preload="metadata"
        className="w-full h-full object-cover"
      />
      <div className="absolute top-2 left-2 inline-flex items-center gap-1 h-6 px-2 rounded-full bg-black/70 backdrop-blur text-white text-xs font-medium">
        {sample.badge || `${sample.score.toFixed(2)}/100`}
      </div>
      <div className="absolute top-2 right-2 inline-flex items-center h-6 px-2 rounded-full bg-white/85 backdrop-blur text-ink text-[10px] font-medium">
        {sample.promptVersion}
      </div>
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/85 to-transparent text-white">
        <div className="text-sm font-medium truncate">{sample.title}</div>
        <div className="text-[11px] text-white/80 truncate">{sample.source}</div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPick();
          }}
          className="mt-2 w-full h-8 rounded-full bg-white text-ink text-xs font-medium hover:bg-bg active:scale-95 transition"
        >
          用此 prompt 生成同款 →
        </button>
      </div>
    </div>
  );
}
