'use client'

import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '../ui/resizable'
import ChatPanel from '../chat/ChatPanel'
import ContentPanel from '../content/ContentPanel'
import LanguageSwitcher from '../common/LanguageSwitcher'
import ConnectionStatus from '../common/ConnectionStatus'
import CommandMenu from '../common/CommandMenu'
import { Shield } from 'lucide-react'

export default function MainLayout() {
  return (
    <div className="h-screen w-full flex flex-col bg-background">
      {/* 顶部导航栏 */}
      <header className="h-14 border-b bg-card flex items-center justify-between px-6 shadow-sm">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">
            AICCA - AI Content Credibility Agent
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
            <span className="text-xs">⌘</span>K
          </kbd>
          <LanguageSwitcher />
        </div>
      </header>

      {/* 主体区域 - 双栏布局 */}
      <div className="flex-1 overflow-hidden">
        <ResizablePanelGroup
          direction="horizontal"
          className="h-full"
        >
          {/* 左侧对话区 - 30% */}
          <ResizablePanel 
            defaultSize={30} 
            minSize={25} 
            maxSize={40}
            className="min-w-[300px]"
          >
            <ChatPanel />
          </ResizablePanel>

          {/* 可拖动分隔线 */}
          <ResizableHandle withHandle className="bg-border hover:bg-primary/10 transition-colors" />

          {/* 右侧展示区 - 70% */}
          <ResizablePanel 
            defaultSize={70} 
            minSize={60}
            className="min-w-[500px]"
          >
            <ContentPanel />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
      
      {/* WebSocket连接状态指示器 */}
      <ConnectionStatus />
      
      {/* Command Menu (Cmd+K) */}
      <CommandMenu />
    </div>
  )
}