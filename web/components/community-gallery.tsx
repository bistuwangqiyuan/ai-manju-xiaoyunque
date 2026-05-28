'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Play, Award, Users, Sparkles, RefreshCw } from 'lucide-react';
import { api, GalleryItem } from '@/lib/api';
import { mediaUrl } from '@/lib/backend-url';
import { OFFICIAL_SAMPLES } from '@/lib/sample-catalog';

const FALLBACK_OFFICIAL: GalleryItem[] = OFFICIAL_SAMPLES;

type Props = {
  showHeader?: boolean;
  compact?: boolean;
};

export function CommunityGallery({ showHeader = true, compact = false }: Props) {
  const [items, setItems] = useState<GalleryItem[]>(FALLBACK_OFFICIAL);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState<GalleryItem | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const data = await api.listGallery(80);
      if (data.length > 0) setItems(data);
    } catch {
      setItems(FALLBACK_OFFICIAL);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const official = items.filter((i) => i.kind === 'official');
  const community = items.filter((i) => i.kind === 'community');
  const scores = official
    .map((i) => i.quality_score)
    .filter((s): s is number => s != null);
  const meanScore =
    scores.length > 0
      ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2)
      : '96.81';

  const gridClass = compact
    ? 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3'
    : 'grid grid-cols-2 sm:grid-cols-4 gap-4';

  const renderCard = (item: GalleryItem) => (
    <button
      key={item.id}
      type="button"
      onClick={() => setPlaying(item)}
      className="group relative aspect-[9/16] rounded-2xl overflow-hidden shadow-ink hover:shadow-2xl transition-all hover:-translate-y-1 hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-cinnabar-300 text-left"
      aria-label={`播放 ${item.title}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-ink-700 via-cinnabar-600 to-ink-400" />
      {item.cover_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={mediaUrl(item.cover_url)}
          alt={item.title}
          loading="lazy"
          className="absolute inset-0 w-full h-full object-cover"
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
      {item.kind === 'official' ? (
        <div className="absolute top-3 left-3 badge bg-cinnabar-600 text-white text-[10px]">
          官方示例
        </div>
      ) : (
        <div className="absolute top-3 left-3 badge bg-ink-800/80 text-white text-[10px]">
          <Users className="w-3 h-3 inline mr-0.5" />
          用户作品
        </div>
      )}
      {item.quality_score != null && (
        <div className="absolute top-3 right-3 bg-emerald-500 text-white font-bold text-sm px-2 py-0.5 rounded-md shadow">
          {item.quality_score}
        </div>
      )}
      <div className="absolute bottom-0 left-0 right-0 p-3">
        <div className="font-serif text-white text-base leading-tight line-clamp-2">
          {item.title}
        </div>
        {item.subtitle && (
          <div className="text-[10px] text-white/70 line-clamp-2 mt-0.5">{item.subtitle}</div>
        )}
        <div className="text-[10px] text-white/60 mt-1 truncate">{item.author_label}</div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
        <div className="w-14 h-14 rounded-full bg-cinnabar-600 flex items-center justify-center shadow-2xl">
          <Play className="w-7 h-7 text-white fill-white ml-0.5" />
        </div>
      </div>
    </button>
  );

  return (
    <section className={compact ? '' : 'mx-auto max-w-6xl px-6 py-20'}>
      {showHeader && (
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-100 text-emerald-800 text-sm font-medium mb-4">
            <Award className="w-4 h-4" />
            官方样片均分 {meanScore}/100 · 用户作品 {community.length} 部
          </div>
          <h2 className="font-serif text-3xl md:text-4xl text-ink-900 mb-3">
            示例与用户作品广场
          </h2>
          <p className="text-ink-600 text-base leading-relaxed max-w-2xl mx-auto">
            浏览<strong>项目内真实生成的官方示例</strong>，以及<strong>所有用户成功生成的漫剧</strong>。
            每一部均可在线播放。
            <Link href="/guide" className="text-cinnabar-700 underline ml-1">
              如何使用 →
            </Link>
          </p>
          <button
            type="button"
            onClick={load}
            className="btn-ghost text-sm mt-4 inline-flex items-center gap-1"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新列表
          </button>
        </div>
      )}

      {official.length > 0 && (
        <div className="mb-10">
          {!compact && (
            <h3 className="font-serif text-xl text-ink-900 mb-4 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-cinnabar-600" />
              官方示例（本地 R40 实测成片）
            </h3>
          )}
          <div className={gridClass}>{official.map(renderCard)}</div>
        </div>
      )}

      {community.length > 0 && (
        <div>
          {!compact && (
            <h3 className="font-serif text-xl text-ink-900 mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-cinnabar-600" />
              用户生成作品（公开广场）
            </h3>
          )}
          <div className={gridClass}>{community.map(renderCard)}</div>
        </div>
      )}

      {community.length === 0 && !loading && (
        <p className="text-center text-sm text-ink-500 mt-6">
          还没有用户作品？{' '}
          <Link href="/signup" className="text-cinnabar-700 underline">
            注册
          </Link>
          后创作第一集，完成后会自动出现在这里。
        </p>
      )}

      {playing && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          onClick={() => setPlaying(null)}
          role="dialog"
          aria-modal
        >
          <div
            className="relative w-full max-w-md aspect-[9/16] bg-black rounded-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <video
              src={mediaUrl(playing.video_url)}
              poster={playing.cover_url ? mediaUrl(playing.cover_url) : undefined}
              controls
              autoPlay
              playsInline
              className="w-full h-full object-contain"
            />
            <button
              type="button"
              onClick={() => setPlaying(null)}
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-black/60 text-white hover:bg-black flex items-center justify-center"
              aria-label="关闭"
            >
              ✕
            </button>
            <div className="absolute bottom-3 left-3 right-3 text-white text-sm bg-black/70 rounded p-3 backdrop-blur">
              <div className="font-serif text-base">{playing.title}</div>
              <div className="text-xs text-white/70">{playing.author_label}</div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
