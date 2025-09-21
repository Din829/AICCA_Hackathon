import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'

export default createMiddleware(routing)

export const config = {
  // 匹配除了API路由、静态文件等之外的所有路径
  matcher: ['/', '/(ja|en|zh)/:path*', '/((?!_next|_vercel|.*\\..*).*)']
}