'use client'

import { Message } from '../MessageList'
import { Wrench, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface ToolCallProps {
  message: Message
}

export default function ToolCall({ message }: ToolCallProps) {
  const { tool, status } = message.metadata || {}
  
  // 根据状态决定显示的图标和颜色
  const getStatusIndicator = () => {
    switch (status) {
      case 'success':
      case 'completed':
        return <CheckCircle className="h-3 w-3 text-green-500" />
      case 'error':
      case 'failed':
        return <XCircle className="h-3 w-3 text-red-500" />
      case 'executing':
      case 'running':
        return <Loader2 className="h-3 w-3 text-blue-500 animate-spin" />
      default: // pending
        return <div className="h-3 w-3 rounded-full border-2 border-muted-foreground/40" />
    }
  }

  return (
    <div className="flex justify-start">
      <div className="inline-flex min-w-0 max-w-[80%] rounded-lg bg-card border px-3 py-1.5 items-center gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Wrench className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
          <span className="text-sm text-muted-foreground truncate">
            {message.content}
          </span>
        </div>
        <div className="flex-shrink-0">
          {getStatusIndicator()}
        </div>
      </div>
    </div>
  )
}