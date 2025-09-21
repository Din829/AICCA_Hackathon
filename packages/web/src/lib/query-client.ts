import { QueryClient } from '@tanstack/react-query'

// 创建QueryClient实例
// 保持灵活配置，可以根据需要调整
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // 数据缓存时间（5分钟）
        gcTime: 5 * 60 * 1000,
        // 数据过期时间（1分钟）
        staleTime: 60 * 1000,
        // 失败重试次数
        retry: 1,
        // 重试延迟
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
        // 窗口聚焦时不自动重新获取
        refetchOnWindowFocus: false,
      },
      mutations: {
        // 突变失败重试
        retry: 0,
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

// 获取客户端QueryClient（单例模式）
export function getQueryClient() {
  if (typeof window === 'undefined') {
    // 服务器端：总是创建新实例
    return makeQueryClient()
  } else {
    // 客户端：使用单例
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}