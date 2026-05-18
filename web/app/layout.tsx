import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { Nav } from '@/components/nav';
import { Footer } from '@/components/footer';

export const metadata: Metadata = {
  title: '小云雀 · AI 漫剧产线',
  description:
    '世界级 AI 漫剧工业流水线：将公版小说一键转化为 9:16 古风 3D 国漫，跨集人物锁定，单集 ¥56-72。',
  keywords: ['AI 漫剧', '小云雀', 'AI 视频', '9:16 短剧', '国漫', '聊斋'],
  openGraph: {
    title: '小云雀 · AI 漫剧产线',
    description: '一键将小说转为古风国漫短剧',
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
        <AuthProvider>
          <Nav />
          <main className="min-h-[calc(100vh-4rem)]">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
