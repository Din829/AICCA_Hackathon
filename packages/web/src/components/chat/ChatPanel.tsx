'use client'

import { useState, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { Input } from '../ui/input'
import { Button } from '../ui/button'
import MessageList from './MessageList'
import useAppStore from '../../store/useAppStore'
import socketManager from '../../lib/socket'
import { Send, RotateCcw } from 'lucide-react'
import { Card } from '../ui/card'

export default function ChatPanel() {
  const t = useTranslations('chat')
  const tFiles = useTranslations('files')
  const [message, setMessage] = useState('')
  
  const addMessage = useAppStore((state) => state.addMessage)
  const setSelectedFiles = useAppStore((state) => state.setSelectedFiles)
  const fileIdMap = useAppStore((state) => state.fileIdMap)
  const resetAll = useAppStore((state) => state.resetAll)

  const handleSend = () => {
    if (message.trim()) {
      // 添加用户消息到状态 - 确保唯一ID
      addMessage({
        id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        type: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      })
      
      // 发送消息到后端
      socketManager.sendChat(message)
      
      // 清空输入
      setMessage('')
    }
  }


  return (
    <div className="h-full flex flex-col bg-muted/30">
      {/* 已上传文件状态栏 */}
      {fileIdMap.size > 0 && (
        <div className="px-4 py-2 border-b bg-background/50">
          <div className="text-xs text-muted-foreground">
            <span>{tFiles('agentAccessibleFiles')} ({fileIdMap.size})</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {Array.from(fileIdMap.entries()).map(([filename, fileId]) => (
                <span key={fileId} className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 rounded-sm text-xs">
                  <span className="w-2 h-2 bg-green-500 rounded-full inline-block"></span>
                  {filename}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
      
      {/* 消息列表区域 */}
      <div className="flex-1 overflow-hidden">
        <MessageList />
      </div>


      {/* 输入区域 */}
      <div className="border-t bg-card p-4">
        <div className="flex gap-2">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => {
              // 重置所有数据
              resetAll()
              setMessage('')
              // 重新连接WebSocket以获取新的会话
              socketManager.reconnect()
            }}
            title="リセット"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Input
            placeholder={t('placeholder')}
            className="flex-1"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          <Button 
            size="icon"
            onClick={handleSend}
            disabled={!message.trim()}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        
      </div>
    </div>
  )
}