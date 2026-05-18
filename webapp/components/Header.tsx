'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';

interface MeData {
  authenticated: boolean;
  email?: string;
  tier?: 'free' | 'pro';
  dailyLimit?: number;
  usedToday?: number;
}

export function Header() {
  const [me, setMe] = useState<MeData | null>(null);

  useEffect(() => {
    fetch('/api/me', { cache: 'no-store' })
      .then((r) => r.json())
      .then(setMe)
      .catch(() => setMe({ authenticated: false }));
  }, []);

  return (
    <header className="sticky top-0 z-20 glass border-b border-line/50">
      <div className="max-w-6xl mx-auto px-6 h-12 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-sm font-medium">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-accent" />
          云雀漫剧
        </Link>
        <nav className="flex items-center gap-4 text-sm text-ink2">
          <a href="#about" className="hover:text-ink hidden md:inline">关于</a>
          <a
            href="https://github.com/bistuwangqiyuan/ai-manju-xiaoyunque"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-ink hidden md:inline"
          >
            GitHub
          </a>
          {me === null ? (
            <span className="h-7 w-20 rounded-full shimmer" />
          ) : me.authenticated ? (
            <Link
              href="/account"
              className="inline-flex items-center gap-2 h-8 px-3 rounded-full border border-line bg-white hover:border-ink2 text-ink"
            >
              {me.tier === 'pro' ? (
                <span className="text-yellow-600">⭐</span>
              ) : null}
              <span className="max-w-[180px] truncate text-xs">{me.email}</span>
              <span className="text-xs text-ink2">
                {me.usedToday}/{me.dailyLimit}
              </span>
            </Link>
          ) : (
            <>
              <Link href="/login" className="hover:text-ink">登录</Link>
              <Link
                href="/register"
                className="inline-flex items-center h-8 px-4 rounded-full bg-ink text-white text-xs font-medium hover:bg-black"
              >
                注册
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
