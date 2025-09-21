'use client'

import { useEffect } from 'react'
import socketManager from '../../lib/socket'

export default function WebSocketProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // 应用启动时自动连接WebSocket
    socketManager.connect()
    
    // 组件卸载时断开连接
    return () => {
      socketManager.disconnect()
    }
  }, [])

  return <>{children}</>
}