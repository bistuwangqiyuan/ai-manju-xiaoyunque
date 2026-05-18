'use client';

import Link from 'next/link';
import { useState, FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

function SignupForm() {
  const { signUp } = useAuth();
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
    if (password.length < 8) {
      setErr('密码至少 8 位');
      return;
    }
    setLoading(true);
    try {
      await signUp(email, password);
      router.push(next);
    } catch (e: any) {
      setErr(e.message || '注册失败');
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
          minLength={8}
          className="input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="至少 8 位"
          autoComplete="new-password"
        />
      </div>
      {err && (
        <div className="p-3 rounded-lg bg-cinnabar-100 text-cinnabar-800 text-sm">
          {err}
        </div>
      )}
      <button type="submit" className="btn-primary w-full" disabled={loading}>
        {loading ? '注册中…' : '免费注册（送 ¥100 体验金）'}
      </button>
      <p className="text-sm text-ink-600 text-center">
        已有账号？
        <Link href="/login" className="text-cinnabar-700 hover:underline ml-1">
          登录
        </Link>
      </p>
      <p className="text-xs text-ink-500 text-center">
        注册即表示同意 <a className="underline">服务条款</a> 与 <a className="underline">隐私政策</a>
      </p>
    </form>
  );
}

export default function SignupPage() {
  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <div className="card p-8">
        <h1 className="font-serif text-2xl text-ink-900 mb-1">开启你的漫剧</h1>
        <p className="text-sm text-ink-600 mb-6">
          注册即赠 ¥100 体验金，足够生成一集试看片。
        </p>
        <Suspense>
          <SignupForm />
        </Suspense>
      </div>
    </div>
  );
}
