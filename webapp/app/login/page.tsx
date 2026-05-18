import { AuthForm } from '@/components/AuthForm';

export const metadata = { title: '登录 — 云雀漫剧' };

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
