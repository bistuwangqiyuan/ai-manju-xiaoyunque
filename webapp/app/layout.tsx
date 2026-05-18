import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '云雀漫剧 — AI 国漫一键生成',
  description:
    '基于火山方舟 Skylark Agent 2.0 (Seedance 2.0 fast 720p) 的 AI 漫剧生成。输入提示词，约 5 分钟收到一段 15 秒竖屏国漫短片。',
  keywords: 'AI 漫剧, AI 国漫, Skylark, Seedance, 火山方舟, AI 短视频, 一键生成',
  authors: [{ name: '云雀漫剧' }],
  openGraph: {
    title: '云雀漫剧 — AI 国漫一键生成',
    description: '输入提示词，AI 帮你生成 15 秒 1080×1920 国漫短片',
    type: 'website',
    locale: 'zh_CN',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#fbfbfd',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="font-sans antialiased bg-bg text-ink">
        {children}
      </body>
    </html>
  );
}
