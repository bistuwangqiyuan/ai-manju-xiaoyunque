import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { CommunityGallery } from '@/components/community-gallery';

export const metadata = {
  title: '作品广场 · 小云雀 AI 漫剧',
  description: '官方示例与用户生成的漫剧视频，全部可在线播放。',
};

export default function ShowcasePage() {
  return (
    <div>
      <div className="mx-auto max-w-6xl px-6 pt-10">
        <Link href="/" className="btn-ghost text-sm mb-2 inline-flex items-center">
          <ArrowLeft className="w-4 h-4 mr-1" /> 返回首页
        </Link>
      </div>
      <CommunityGallery />
    </div>
  );
}
