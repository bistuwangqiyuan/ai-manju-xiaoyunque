'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || `${mode === 'login' ? '登录' : '注册'}失败`);
        return;
      }
      router.push('/');
      router.refresh();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto pt-16 md:pt-24 px-6">
      <Link href="/" className="text-sm text-ink2 hover:text-ink">
        ← 返回首页
      </Link>
      <h1 className="mt-6 text-3xl font-semibold">
        {mode === 'login' ? '登录' : '注册账号'}
      </h1>
      <p className="mt-2 text-sm text-ink2">
        {mode === 'login'
          ? '已有账号请登录使用每日生成额度'
          : '新用户注册即享每日 1 条免费生成额度'}
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1.5 text-ink">邮箱</label>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full h-11 px-4 rounded-xl border border-line bg-white text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5 text-ink">密码</label>
          <input
            type="password"
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={6}
            maxLength={256}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="至少 6 位"
            className="w-full h-11 px-4 rounded-xl border border-line bg-white text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl p-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full h-12 rounded-full bg-ink text-white text-base font-medium hover:bg-black disabled:bg-ink2 disabled:cursor-not-allowed transition-colors"
        >
          {loading
            ? '处理中…'
            : mode === 'login'
              ? '登录'
              : '注册并登录'}
        </button>
      </form>

      <div className="mt-6 text-center text-sm text-ink2">
        {mode === 'login' ? (
          <>
            还没有账号？{' '}
            <Link href="/register" className="text-accent hover:underline">
              立即注册
            </Link>
          </>
        ) : (
          <>
            已有账号？{' '}
            <Link href="/login" className="text-accent hover:underline">
              直接登录
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
