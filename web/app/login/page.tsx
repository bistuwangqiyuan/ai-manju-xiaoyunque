'use client';

import Link from 'next/link';
import { useState, FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

function LoginForm() {
  const { signIn } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get('next') || '/dashboard';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await signIn(email, password);
      router.push(next);
    } catch (e: any) {
      setErr(e.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label className="label">邮箱</label>
        <input
          type="email"
          required
          className="input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
        />
      </div>
      <div>
        <label className="label">密码</label>
        <input
          type="password"
          required
          className="input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="至少 8 位"
          autoComplete="current-password"
        />
      </div>
      {err && (
        <div className="p-3 rounded-lg bg-cinnabar-100 text-cinnabar-800 text-sm">
          {err}
        </div>
      )}
      <button type="submit" className="btn-primary w-full" disabled={loading}>
        {loading ? '登录中…' : '登录'}
      </button>
      <p className="text-sm text-ink-600 text-center">
        还没有账号？
        <Link href="/signup" className="text-cinnabar-700 hover:underline ml-1">
          免费注册
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <div className="card p-8">
        <h1 className="font-serif text-2xl text-ink-900 mb-1">欢迎回来</h1>
        <p className="text-sm text-ink-600 mb-6">登录小云雀，继续你的漫剧创作。</p>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
    </div>
  );
}
