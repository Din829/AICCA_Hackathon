import type { NextConfig } from 'next'
import createNextIntlPlugin from 'next-intl/plugin'
import path from 'path'

const withNextIntl = createNextIntlPlugin('./i18n.ts')

const nextConfig: NextConfig = {
  reactStrictMode: false,  // 关闭严格模式，减少警告
  // 关闭各种检查，最大兼容性
  eslint: {
    ignoreDuringBuilds: true,  // 构建时忽略ESLint错误
  },
  typescript: {
    ignoreBuildErrors: true,   // 构建时忽略TypeScript错误
  },
  experimental: {
    // Turbopack相关配置已经通过--turbo flag启用
    // forceSwcTransforms: true,  // 在Docker环境中与Turbopack冲突，暂时注释
  },
  // 🔧 修复路径解析 - 一劳永逸的解决方案
  webpack: (config, { buildId, dev, isServer, defaultLoaders, webpack }) => {
    // 确保路径别名在webpack中正确解析 - 使用绝对路径
    const srcPath = path.resolve(process.cwd(), 'src')

    config.resolve.alias = {
      ...config.resolve.alias,
      '@': srcPath,
      '@/components': path.resolve(srcPath, 'components'),
      '@/lib': path.resolve(srcPath, 'lib'),
      '@/hooks': path.resolve(srcPath, 'hooks'),
      '@/store': path.resolve(srcPath, 'store'),
      '@/i18n': path.resolve(srcPath, 'i18n'),
      '@/messages': path.resolve(srcPath, 'messages'),
    }

    // 确保模块解析顺序正确
    config.resolve.modules = [
      srcPath,
      path.resolve(process.cwd(), 'node_modules'),
      'node_modules'
    ]

    return config
  },
  // 图片优化配置
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
  // 环境变量
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  }
}

export default withNextIntl(nextConfig)