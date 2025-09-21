'use client'

import { Message } from '../MessageList'
import { Alert, AlertDescription } from '../../ui/alert'
import { AlertCircle, AlertTriangle, Info, CheckCircle } from 'lucide-react'

interface SystemAlertProps {
  message: Message
}

export default function SystemAlert({ message }: SystemAlertProps) {
  const level = message.metadata?.level || 'info'
  
  const getIcon = () => {
    switch (level) {
      case 'error':
        return <AlertCircle className="h-4 w-4" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4" />
      case 'success':
        return <CheckCircle className="h-4 w-4" />
      default:
        return <Info className="h-4 w-4" />
    }
  }
  
  const getVariant = () => {
    switch (level) {
      case 'error':
        return 'destructive'
      case 'success':
        return 'default' // 使用默认样式显示成功
      default:
        return 'default'
    }
  }

  return (
    <Alert 
      variant={getVariant()}
      className={`my-2 ${level === 'success' ? 'border-green-200 text-green-800 bg-green-50' : ''}`}
    >
      {getIcon()}
      <AlertDescription>{message.content}</AlertDescription>
    </Alert>
  )
}