import Link from 'next/link';
import { BookOpen, ArrowRight } from 'lucide-react';

type GuideBannerProps = {
  variant?: 'default' | 'compact';
  className?: string;
};

/** 引导普通用户阅读 /guide 使用说明 */
export function GuideBanner({ variant = 'default', className = '' }: GuideBannerProps) {
  if (variant === 'compact') {
    return (
      <Link
        href="/guide"
        className={`inline-flex items-center gap-1.5 text-sm text-cinnabar-700 hover:underline ${className}`}
      >
        <BookOpen className="w-4 h-4" />
        新手？查看使用说明
      </Link>
    );
  }

  return (
    <div
      className={`rounded-xl border border-cinnabar-200/70 bg-gradient-to-r from-cinnabar-50/80 to-amber-50/60 px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${className}`}
    >
      <div className="flex items-start gap-3">
        <BookOpen className="w-6 h-6 text-cinnabar-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-ink-900">第一次使用？</p>
          <p className="text-sm text-ink-600 mt-0.5 leading-relaxed">
            《使用说明》手把手教您注册、粘贴小说、下载成片，含 Free/Pro 配额与常见问题。
          </p>
        </div>
      </div>
      <Link href="/guide" className="btn-secondary text-sm whitespace-nowrap shrink-0">
        打开使用说明 <ArrowRight className="w-4 h-4 ml-1" />
      </Link>
    </div>
  );
}
