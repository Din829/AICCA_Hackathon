'use client'

import * as React from 'react'
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '../ui/command'
import {
  FileSearch,
  Upload,
  MessageSquare,
  RotateCcw,
  ShieldCheck,
  ScanSearch,
  FileType,
  Settings,
} from 'lucide-react'
import { toast } from 'sonner'
import useAppStore from '../../store/useAppStore'
import socketManager from '../../lib/socket'

export default function CommandMenu() {
  const [open, setOpen] = React.useState(false)
  const resetAll = useAppStore((state) => state.resetAll)

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((open) => !open)
      }
    }

    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [])

  const handleAction = (action: string) => {
    setOpen(false)
    
    switch (action) {
      case 'reset':
        resetAll()
        socketManager.reconnect()
        toast.success('リセット完了', {
          description: '新しいセッションを開始しました'
        })
        break
      case 'ai-detect':
        socketManager.sendChat('アップロードされたコンテンツのAI生成検出を実行してください')
        toast('AI検出を開始', {
          description: 'エージェントが分析を開始します'
        })
        break
      case 'deepfake':
        socketManager.sendChat('ディープフェイク検出を実行してください')
        toast('ディープフェイク検出を開始', {
          description: 'エージェントが分析を開始します'
        })
        break
      case 'c2pa':
        socketManager.sendChat('C2PA検証を実行してください')
        toast('C2PA検証を開始', {
          description: 'デジタル証明を確認します'
        })
        break
      case 'comprehensive':
        socketManager.sendChat('総合的な信頼性分析を実行してください')
        toast('総合分析を開始', {
          description: '全ての検出ツールを実行します'
        })
        break
      default:
        break
    }
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="コマンドを検索..." />
      <CommandList>
        <CommandEmpty>該当するコマンドがありません</CommandEmpty>
        
        <CommandGroup heading="クイックアクション">
          <CommandItem onSelect={() => handleAction('reset')}>
            <RotateCcw className="mr-2 h-4 w-4" />
            <span>セッションをリセット</span>
          </CommandItem>
          <CommandItem onSelect={() => document.getElementById('file-upload')?.click()}>
            <Upload className="mr-2 h-4 w-4" />
            <span>ファイルをアップロード</span>
          </CommandItem>
        </CommandGroup>
        
        <CommandSeparator />
        
        <CommandGroup heading="分析ツール">
          <CommandItem onSelect={() => handleAction('ai-detect')}>
            <FileSearch className="mr-2 h-4 w-4" />
            <span>AI生成コンテンツ検出</span>
          </CommandItem>
          <CommandItem onSelect={() => handleAction('deepfake')}>
            <ScanSearch className="mr-2 h-4 w-4" />
            <span>ディープフェイク検出</span>
          </CommandItem>
          <CommandItem onSelect={() => handleAction('c2pa')}>
            <ShieldCheck className="mr-2 h-4 w-4" />
            <span>C2PA証明検証</span>
          </CommandItem>
          <CommandItem onSelect={() => handleAction('comprehensive')}>
            <FileType className="mr-2 h-4 w-4" />
            <span>総合信頼性分析</span>
          </CommandItem>
        </CommandGroup>
        
        <CommandSeparator />
        
        <CommandGroup heading="設定">
          <CommandItem onSelect={() => toast('設定画面は準備中です')}>
            <Settings className="mr-2 h-4 w-4" />
            <span>設定</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}