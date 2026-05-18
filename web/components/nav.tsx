'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { formatYuan } from '@/lib/utils';
import { Sparkles } from 'lucide-react';

export function Nav() {
  const { user, signOut, loading } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/60 bg-ink-50/80 backdrop-blur">
      <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-serif text-xl text-ink-900">
          <span className="seal text-base w-9 h-9">雀</span>
          <span className="font-semibold tracking-wide">小云雀 · 漫剧产线</span>
        </Link>
        <nav className="flex items-center gap-2">
          <Link href="/pricing" className="btn-ghost">定价</Link>
          {user ? (
            <>
              <Link href="/dashboard" className="btn-ghost">仪表盘</Link>
              <span className="hidden sm:inline-flex badge bg-ink-100 text-ink-700">
                <Sparkles className="w-3 h-3 mr-1" />
                余额 {formatYuan(user.credits_cents)}
              </span>
              <button onClick={signOut} className="btn-ghost text-sm">退出</button>
            </>
          ) : loading ? null : (
            <>
              <Link href="/login" className="btn-ghost">登录</Link>
              <Link href="/signup" className="btn-primary text-sm">免费注册</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
