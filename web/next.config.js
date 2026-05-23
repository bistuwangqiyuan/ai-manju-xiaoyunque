/** @type {import('next').NextConfig} */
// 三种部署模式同时支持：
//   - GH_PAGES=1            → GitHub Pages 静态导出（basePath 修正）
//   - NEXT_OUTPUT_STANDALONE=1 → Docker 自托管（生成 .next/standalone，国内部署用）
//   - 默认                  → Vercel/EdgeOne 动态部署 + rewrites
const isGhPages = process.env.GH_PAGES === '1';
const isStandalone = process.env.NEXT_OUTPUT_STANDALONE === '1';

const nextConfig = {
  reactStrictMode: true,
  ...(isGhPages
    ? {
        output: 'export',
        basePath: '/ai-manju-xiaoyunque',
        assetPrefix: '/ai-manju-xiaoyunque',
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : isStandalone
    ? {
        // 国内 Docker 自托管模式：生成 .next/standalone/server.js
        output: 'standalone',
        async rewrites() {
          const backend =
            process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL;
          if (!backend) return [];
          return [
            {
              source: '/api/backend/:path*',
              destination: `${backend}/api/:path*`,
            },
          ];
        },
        images: { remotePatterns: [{ protocol: 'https', hostname: '**' }] },
      }
    : {
        // Vercel / EdgeOne 动态模式
        async rewrites() {
          const backend =
            process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL;
          if (!backend) return [];
          return [
            {
              source: '/api/backend/:path*',
              destination: `${backend}/api/:path*`,
            },
          ];
        },
        images: { remotePatterns: [{ protocol: 'https', hostname: '**' }] },
      }),
};

module.exports = nextConfig;
