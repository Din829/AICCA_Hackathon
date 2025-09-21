'use client'

import { useEffect, useState } from 'react'
import useAppStore from '../../store/useAppStore'
import { Badge } from '../ui/badge'
import { Wifi, WifiOff, Loader2, AlertCircle } from 'lucide-react'

export default function ConnectionStatus() {
  const connectionStatus = useAppStore((state) => state.connectionStatus)
  const [show, setShow] = useState(false)

  useEffect(() => {
    // 显示状态变化
    if (connectionStatus !== 'connected') {
      setShow(true)
    } else {
      // 连接成功后延迟隐藏
      const timer = setTimeout(() => setShow(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [connectionStatus])

  if (!show && connectionStatus === 'connected') {
    return null
  }

  const getStatusConfig = () => {
    switch (connectionStatus) {
      case 'connecting':
        return {
          icon: <Loader2 className="h-3 w-3 animate-spin" />,
          text: '接続中...',
          variant: 'secondary' as const
        }
      case 'connected':
        return {
          icon: <Wifi className="h-3 w-3" />,
          text: '接続済み',
          variant: 'default' as const
        }
      case 'disconnected':
        return {
          icon: <WifiOff className="h-3 w-3" />,
          text: '未接続',
          variant: 'secondary' as const
        }
      case 'error':
        return {
          icon: <AlertCircle className="h-3 w-3" />,
          text: 'エラー',
          variant: 'destructive' as const
        }
      default:
        return {
          icon: <WifiOff className="h-3 w-3" />,
          text: '未接続',
          variant: 'secondary' as const
        }
    }
  }

  const config = getStatusConfig()

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Badge variant={config.variant} className="flex items-center gap-1 px-3 py-1">
        {config.icon}
        <span>{config.text}</span>
      </Badge>
    </div>
  )
}