import { useMutation, useQuery } from '@tanstack/react-query'
import { getQueryClient } from '../lib/query-client'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// API请求的通用函数
async function fetchAPI(endpoint: string, options?: RequestInit) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }
  
  return response.json()
}

// 获取服务信息
export function useServiceInfo() {
  return useQuery({
    queryKey: ['service-info'],
    queryFn: () => fetchAPI('/api/info'),
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 获取可用工具列表
export function useAvailableTools() {
  return useQuery({
    queryKey: ['tools'],
    queryFn: () => fetchAPI('/api/tools'),
    staleTime: 10 * 60 * 1000, // 10分钟
  })
}

// 分析内容
export function useAnalyzeContent() {
  const queryClient = getQueryClient()
  
  return useMutation({
    mutationFn: (data: {
      content: string
      content_type?: string
      options?: Record<string, any>
    }) => fetchAPI('/api/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    onSuccess: (data) => {
      // 更新相关查询缓存
      queryClient.invalidateQueries({ queryKey: ['analysis-history'] })
    },
  })
}

// 上传文件
export function useUploadFile() {
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      })
      
      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`)
      }
      
      return response.json()
    },
  })
}

// 批量分析
export function useBatchAnalyze() {
  return useMutation({
    mutationFn: (data: {
      files: string[]
      options?: Record<string, any>
    }) => fetchAPI('/api/batch/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  })
}

// 直接执行工具
export function useExecuteTool() {
  return useMutation({
    mutationFn: (data: {
      tool_name: string
      args: Record<string, any>
    }) => fetchAPI('/api/tools/execute', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  })
}