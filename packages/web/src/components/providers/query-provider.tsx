'use client'

import { QueryClientProvider } from '@tanstack/react-query'
import { getQueryClient } from '../../lib/query-client'
import { ReactNode, lazy, Suspense } from 'react'

// 动态导入开发工具，避免生产环境加载
const ReactQueryDevtools = process.env.NODE_ENV === 'development' 
  ? lazy(() => import('@tanstack/react-query-devtools').then(mod => ({ default: mod.ReactQueryDevtools })))
  : () => null

export default function QueryProvider({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <Suspense fallback={null}>
          <ReactQueryDevtools initialIsOpen={false} />
        </Suspense>
      )}
    </QueryClientProvider>
  )
}