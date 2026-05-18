'use client';

import { Play, Award } from 'lucide-react';
import { useState } from 'react';

const SAMPLE_VIDEO =
  'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4';

interface Episode {
  no: string;
  title: string;
  subtitle: string;
  seal: string;
  score: number;
  duration: string;
  gradient: string;
  characterName: string;
  characterRole: string;
}

const EPISODES: Episode[] = [
  {
    no: 'EP 01',
    title: '兰若惊鸿',
    subtitle: '夜投兰若寺，初见小倩魂',
    seal: '倩',
    score: 94,
    duration: '88s',
    gradient: 'from-cinnabar-700 via-cinnabar-500 to-ink-300',
    characterName: '聂小倩',
    characterRole: '女主 · 善鬼',
  },
  {
    no: 'EP 02',
    title: '剑指姥姥',
    subtitle: '燕赤霞夜斗千年树妖',
    seal: '霞',
    score: 92,
    duration: '85s',
    gradient: 'from-ink-700 via-ink-400 to-cinnabar-200',
    characterName: '燕赤霞',
    characterRole: '剑客 · 道长',
  },
  {
    no: 'EP 03',
    title: '书生赤心',
    subtitle: '宁采臣不为色诱所动',
    seal: '采',
    score: 91,
    duration: '82s',
    gradient: 'from-ink-300 via-cinnabar-100 to-ink-200',
    characterName: '宁采臣',
    characterRole: '男主 · 书生',
  },
  {
    no: 'EP 05',
    title: '骨匣秘藏',
    subtitle: '小倩枯骨随风返乡',
    seal: '骨',
    score: 95,
    duration: '90s',
    gradient: 'from-purple-900 via-ink-700 to-cinnabar-300',
    characterName: '聂小倩',
    characterRole: '魂归故里',
  },
  {
    no: 'EP 08',
    title: '千年之约',
    subtitle: '人鬼殊途之约 (Veo 精修)',
    seal: '诀',
    score: 96,
    duration: '90s',
    gradient: 'from-cinnabar-900 via-cinnabar-600 to-ink-200',
    characterName: '宁 × 倩',
    characterRole: '高光集',
  },
  {
    no: 'EP 10',
    title: '终破阴司',
    subtitle: '终章 · 三人破阵 (Sora 2 1080P)',
    seal: '终',
    score: 97,
    duration: '90s',
    gradient: 'from-ink-900 via-cinnabar-700 to-yellow-300/40',
    characterName: '终局',
    characterRole: 'Sora 2 旗舰精修',
  },
];

export function ShowcaseGallery() {
  const [playingIdx, setPlayingIdx] = useState<number | null>(null);

  return (
    <section className="mx-auto max-w-6xl px-6 py-20">
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cinnabar-100 text-cinnabar-800 text-xs font-medium mb-4">
          <Award className="w-3.5 h-3.5" />
          已生成成片 · 平均评分 94/100
        </div>
        <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-3">
          聊斋·聂小倩 十集预览
        </h2>
        <p className="text-ink-600">
          全集 9:16 古风 3D 国漫 · 跨集 ArcFace ≥ 0.80 · 五道质检防线
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {EPISODES.map((ep, idx) => (
          <button
            key={ep.no}
            onClick={() => setPlayingIdx(idx)}
            className="group relative aspect-[9/16] rounded-2xl overflow-hidden shadow-ink hover:shadow-2xl transition-all hover:-translate-y-1 hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-cinnabar-500"
          >
            {/* Background gradient (古风渐变) */}
            <div className={`absolute inset-0 bg-gradient-to-br ${ep.gradient}`} />

            {/* 山水墨晕效果 */}
            <div className="absolute inset-0 mix-blend-overlay opacity-40"
                 style={{
                   backgroundImage: 'radial-gradient(circle at 30% 20%, rgba(255,255,255,0.4) 0%, transparent 50%), radial-gradient(circle at 70% 80%, rgba(0,0,0,0.3) 0%, transparent 50%)',
                 }}
            />

            {/* 印章 */}
            <div className="absolute top-3 right-3 w-8 h-8 rounded bg-cinnabar-700 text-white font-serif text-base flex items-center justify-center rotate-[-6deg] shadow-lg">
              {ep.seal}
            </div>

            {/* 集数 + 时长 */}
            <div className="absolute top-3 left-3 text-white/90 text-[10px] font-mono tracking-wider">
              {ep.no} · {ep.duration}
            </div>

            {/* 标题 */}
            <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
              <div className="font-serif text-white text-lg leading-tight mb-0.5">
                {ep.title}
              </div>
              <div className="text-[10px] text-white/70 leading-tight mb-1">
                {ep.subtitle}
              </div>
              <div className="flex items-center justify-between text-[10px] text-white/80">
                <span>{ep.characterName} · {ep.characterRole}</span>
                <span className={`font-semibold ${ep.score >= 95 ? 'text-emerald-300' : 'text-amber-300'}`}>
                  {ep.score}
                </span>
              </div>
            </div>

            {/* Play overlay on hover */}
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
              <div className="w-14 h-14 rounded-full bg-cinnabar-600/90 flex items-center justify-center shadow-2xl">
                <Play className="w-7 h-7 text-white fill-white ml-1" />
              </div>
            </div>
          </button>
        ))}
      </div>

      <p className="text-center text-xs text-ink-500 mt-6">
        点击任意集预览样片 · 全部由小云雀 v2 流水线自动生成 · 平均渲染时间 7-9 小时/集
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
            <video
              src={SAMPLE_VIDEO}
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
            <button
              onClick={() => setPlayingIdx(null)}
              className="absolute top-3 right-3 w-9 h-9 rounded-full bg-black/60 text-white hover:bg-black flex items-center justify-center"
            >
              ✕
            </button>
            <div className="absolute bottom-3 left-3 right-3 text-white text-sm bg-black/60 rounded p-2 backdrop-blur">
              <div className="font-serif text-base">
                {EPISODES[playingIdx].no} · {EPISODES[playingIdx].title}
              </div>
              <div className="text-xs text-white/70">
                示例占位视频 · 真实成片由小云雀 v2 渲染生成
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
