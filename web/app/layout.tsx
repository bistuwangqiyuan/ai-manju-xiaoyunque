import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { I18nProvider } from '@/lib/i18n';
import { Nav } from '@/components/nav';
import { Footer } from '@/components/footer';

export const metadata: Metadata = {
  title: '小云雀 · AI 漫剧产线',
  description:
    '世界级 AI 漫剧工业流水线：多题材、多语言、多平台导出。古风/现代/甜宠/悬疑/玄幻一键生成。',
  keywords: ['AI 漫剧', '小云雀', 'AI 视频', '9:16 短剧', '国漫', '聊斋', '甜宠', '悬疑', '玄幻'],
  openGraph: {
    title: '小云雀 · AI 漫剧产线',
    description: '世界级 AI 漫剧 SaaS - 多题材、多语言',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <I18nProvider>
          <AuthProvider>
            <Nav />
            <main className="min-h-[calc(100vh-4rem)]">{children}</main>
            <Footer />
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
