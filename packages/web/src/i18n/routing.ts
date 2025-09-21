import { defineRouting } from 'next-intl/routing'
import { createNavigation } from 'next-intl/navigation'

export const routing = defineRouting({
  // 支持的语言列表（日语优先）
  locales: ['ja', 'en', 'zh'],
  // 默认语言设为日语
  defaultLocale: 'ja',
  // 路径名映射（可选）
  pathnames: {
    '/': '/',
    '/chat': {
      ja: '/chat',
      en: '/chat',
      zh: '/chat'
    }
  }
})

// 导出导航hooks
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing)