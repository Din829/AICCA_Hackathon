'use client'

import { useEffect, useRef } from 'react'
import useAppStore from '../../store/useAppStore'
import { ScrollArea } from '../ui/scroll-area'
import UserMessage from './messages/UserMessage'
import AgentThinking from './messages/AgentThinking'
import ToolCall from './messages/ToolCall'
import AgentReply from './messages/AgentReply'
import SystemAlert from './messages/SystemAlert'
import { MessageSquare } from 'lucide-react'

// 消息类型定义
export type MessageType = 
  | 'user'
  | 'agent-thinking'
  | 'tool-call'
  | 'agent-reply'
  | 'system-alert'

export interface Message {
  id: string
  type: MessageType
  content: string
  timestamp: Date | string
  metadata?: any
}

export default function MessageList() {
  // 从Zustand store获取消息
  const messages = useAppStore((state) => state.messages)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-3 p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-sm font-medium">会話を始めましょう</p>
            <p className="text-xs mt-1">質問やファイルをアップロードしてください</p>
            
            {/* Agent能力紹介 */}
            <div className="mt-8 space-y-4 max-w-sm">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background/60 rounded-lg p-3 border">
                  <p className="text-xs font-semibold text-foreground mb-1">AIテキスト検出</p>
                  <p className="text-xs text-muted-foreground/80">GPT/Claude生成文書を識別</p>
                </div>
                
                <div className="bg-background/60 rounded-lg p-3 border">
                  <p className="text-xs font-semibold text-foreground mb-1">AI画像検出</p>
                  <p className="text-xs text-muted-foreground/80">Stable Diffusion/DALL-E等</p>
                </div>
                
                <div className="bg-background/60 rounded-lg p-3 border">
                  <p className="text-xs font-semibold text-foreground mb-1">ディープフェイク検出</p>
                  <p className="text-xs text-muted-foreground/80">動画顔面置換・音声クローン</p>
                </div>
                
                <div className="bg-background/60 rounded-lg p-3 border">
                  <p className="text-xs font-semibold text-foreground mb-1">C2PA検証</p>
                  <p className="text-xs text-muted-foreground/80">デジタル証明・改ざん検知</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => {
            switch (message.type) {
              case 'user':
                return <UserMessage key={message.id} message={message} />
              case 'agent-thinking':
                return <AgentThinking key={message.id} message={message} />
              case 'tool-call':
                return <ToolCall key={message.id} message={message} />
              case 'agent-reply':
                return <AgentReply key={message.id} message={message} />
              case 'system-alert':
                return <SystemAlert key={message.id} message={message} />
              default:
                return null
            }
          })
        )}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  )
}