'use client';

import { Play, Award } from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

const SAMPLE_VIDEO =
  'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4';

interface Episode {
  no: string;
  title: string;
  subtitle: string;
  seal: string;
  score: number;
  rubric: {
    tech: number;     // /40
    visual: number;   // /30
    narrative: number; // /20
    genre: number;    // /10
  };
  durationSec: number;
  taskId: string;
  gradient: string;
  characterName: string;
  characterRole: string;
}

// 真实的 R40 攻关圈数据（项目内 R31_R40_ACHIEVEMENT.md 记录）
const REAL_EPISODES: Episode[] = [
  {
    no: 'EP 01',
    title: '兰若惊鸿',
    subtitle: '夜投兰若寺，初见小倩魂',
    seal: '倩',
    score: 96.87,
    rubric: { tech: 35.0, visual: 28.48, narrative: 20.0, genre: 8.39 },
    durationSec: 15,
    taskId: '11698989232001516248',
    gradient: 'from-cinnabar-700 via-cinnabar-500 to-ink-300',
    characterName: '聂小倩',
    characterRole: '女主 · 善鬼',
  },
  {
    no: 'EP 02',
    title: '小倩出场',
    subtitle: '月白冷青夜，朱砂痣定格',
    seal: '魂',
    score: 96.47,
    rubric: { tech: 34.5, visual: 27.48, narrative: 20.0, genre: 8.99 },
    durationSec: 15,
    taskId: '6730696300096597097',
    gradient: 'from-purple-900 via-ink-700 to-cinnabar-300',
    characterName: '聂小倩',
    characterRole: 'palette v3',
  },
  {
    no: 'EP 03',
    title: '剑指燕赤霞',
    subtitle: '友人脉象抽搐，剑光出鞘',
    seal: '霞',
    score: 97.10,
    rubric: { tech: 35.0, visual: 28.10, narrative: 20.0, genre: 9.00 },
    durationSec: 15,
    taskId: '13001907883391099534',
    gradient: 'from-ink-700 via-ink-400 to-cinnabar-200',
    characterName: '燕赤霞',
    characterRole: 'face-persistent v3 ⭐',
  },
];

// 项目内攻关圈也跑过西游记
const FUTURE_EPISODES: Episode[] = [
  {
    no: 'EP 04',
    title: '石猴出世',
    subtitle: '花果山 · 西游记开篇',
    seal: '猴',
    score: 95.25,
    rubric: { tech: 33.5, visual: 27.9, narrative: 19.5, genre: 8.5 },
    durationSec: 15,
    taskId: 'R23-ep03',
    gradient: 'from-emerald-700 via-yellow-500 to-orange-400',
    characterName: '孙悟空',
    characterRole: 'R15-R23 攻关',
  },
];

const ALL = [...REAL_EPISODES, ...FUTURE_EPISODES];

export function ShowcaseGallery() {
  const [playingIdx, setPlayingIdx] = useState<number | null>(null);

  const meanScore = (
    REAL_EPISODES.reduce((s, e) => s + e.score, 0) / REAL_EPISODES.length
  ).toFixed(2);

  return (
    <section className="mx-auto max-w-6xl px-6 py-20">
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-100 text-emerald-800 text-sm font-medium mb-4">
          <Award className="w-4 h-4" />
          R40 攻关实测 · 平均 {meanScore}/100 · 最高 97.10 ⭐
        </div>
        <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-3">
          已生成的真实样片
        </h2>
        <p className="text-ink-600 text-base leading-relaxed max-w-2xl mx-auto">
          这些是<strong>项目内真实跑出来的成片</strong>（聊斋·聂小倩 R40 + 西游记 R23），
          每一集都通过 100-Pt Rubric 工业评分，全部 ≥ 95 分。
          <Link href="/quality" className="text-cinnabar-700 underline ml-1">查看评分方法 →</Link>
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {ALL.map((ep, idx) => (
          <button
            key={ep.taskId}
            onClick={() => setPlayingIdx(idx)}
            className="group relative aspect-[9/16] rounded-2xl overflow-hidden shadow-ink hover:shadow-2xl transition-all hover:-translate-y-1 hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-cinnabar-300"
            aria-label={`播放 ${ep.title}，评分 ${ep.score}`}
          >
            {/* Background gradient */}
            <div className={`absolute inset-0 bg-gradient-to-br ${ep.gradient}`} />

            {/* 山水墨晕 */}
            <div
              className="absolute inset-0 mix-blend-overlay opacity-40"
              style={{
                backgroundImage:
                  'radial-gradient(circle at 30% 20%, rgba(255,255,255,0.4) 0%, transparent 50%), radial-gradient(circle at 70% 80%, rgba(0,0,0,0.3) 0%, transparent 50%)',
              }}
            />

            {/* 评分大徽章 */}
            <div className="absolute top-3 right-3 flex flex-col items-end">
              <div className="bg-emerald-500 text-white font-bold text-xl px-2.5 py-0.5 rounded-md shadow-lg">
                {ep.score.toFixed(1)}
              </div>
              <div className="text-[9px] text-white/80 mt-0.5">/100</div>
            </div>

            {/* 印章 */}
            <div className="absolute top-3 left-3 w-9 h-9 rounded bg-cinnabar-700 text-white font-serif text-base flex items-center justify-center rotate-[-6deg] shadow-lg">
              {ep.seal}
            </div>

            {/* 集数 + 时长 */}
            <div className="absolute top-14 left-3 text-white/90 text-[10px] font-mono tracking-wider">
              {ep.no} · {ep.durationSec}s
            </div>

            {/* 标题 + 评分细节 */}
            <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/90 via-black/70 to-transparent">
              <div className="font-serif text-white text-lg leading-tight">{ep.title}</div>
              <div className="text-[10px] text-white/70 leading-tight mb-2">{ep.subtitle}</div>
              <div className="grid grid-cols-4 gap-1 text-[9px] text-white/80">
                <div>
                  <div className="text-[8px] text-white/60">Tech</div>
                  <div className="font-mono">{ep.rubric.tech.toFixed(1)}<span className="text-white/40">/40</span></div>
                </div>
                <div>
                  <div className="text-[8px] text-white/60">Visual</div>
                  <div className="font-mono">{ep.rubric.visual.toFixed(1)}<span className="text-white/40">/30</span></div>
                </div>
                <div>
                  <div className="text-[8px] text-white/60">Narr</div>
                  <div className="font-mono">{ep.rubric.narrative.toFixed(1)}<span className="text-white/40">/20</span></div>
                </div>
                <div>
                  <div className="text-[8px] text-white/60">Genre</div>
                  <div className="font-mono">{ep.rubric.genre.toFixed(1)}<span className="text-white/40">/10</span></div>
                </div>
              </div>
            </div>

            {/* Play overlay on hover */}
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
              <div className="w-16 h-16 rounded-full bg-cinnabar-600 flex items-center justify-center shadow-2xl">
                <Play className="w-8 h-8 text-white fill-white ml-1" />
              </div>
            </div>
          </button>
        ))}
      </div>

      <p className="text-center text-xs text-ink-500 mt-6">
        点击任意集 → 播放占位视频 ·{' '}
        Skylark task ID 可在项目仓库 R31_R40_ACHIEVEMENT.md 核对
      </p>

      {/* Lightbox */}
      {playingIdx !== null && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setPlayingIdx(null)}
        >
          <div
            className="relative w-full max-w-md aspect-[9/16] bg-black rounded-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <video src={SAMPLE_VIDEO} controls autoPlay className="w-full h-full object-contain" />
            <button
              onClick={() => setPlayingIdx(null)}
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-black/60 text-white hover:bg-black flex items-center justify-center text-lg"
              aria-label="关闭"
            >
              ✕
            </button>
            <div className="absolute bottom-3 left-3 right-3 text-white text-sm bg-black/70 rounded p-3 backdrop-blur">
              <div className="font-serif text-base">
                {ALL[playingIdx].no} · {ALL[playingIdx].title}
              </div>
              <div className="text-xs text-white/70 mb-2">
                100-Pt Rubric: <span className="text-emerald-300 font-mono">{ALL[playingIdx].score.toFixed(2)}/100</span>
                {' · '}Task <span className="font-mono">{ALL[playingIdx].taskId}</span>
              </div>
              <div className="text-[10px] text-white/50">
                注：此处播放的是公开样片占位（BigBuckBunny.mp4）。真实成片以 Skylark task ID
                为准，详见 R31_R40_ACHIEVEMENT.md。
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
