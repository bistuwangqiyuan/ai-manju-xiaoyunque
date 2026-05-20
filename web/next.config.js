/** @type {import('next').NextConfig} */
// 同一份代码可以部署到 Vercel（动态）或 GitHub Pages（静态导出）。
// GitHub Pages 路径：用 GH_PAGES=1 触发 output:'export' + basePath
const isGhPages = process.env.GH_PAGES === '1';

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
    : {
        // Vercel 模式：支持 rewrites + 优化图片
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
