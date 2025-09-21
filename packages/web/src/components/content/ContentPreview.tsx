'use client'

import React, { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import useAppStore from '../../store/useAppStore'
import socketManager from '../../lib/socket'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { Button } from '../ui/button'
import { Card } from '../ui/card'
import { AspectRatio } from '../ui/aspect-ratio'
import { ScrollArea } from '../ui/scroll-area'
import { Badge } from '../ui/badge'
import { FileImage, FileVideo, FileText, FileAudio, File as FileIcon, Upload, X, CloudUpload, Plus, Type } from 'lucide-react'

export default function ContentPreview() {
  const t = useTranslations('analysis')
  const tFiles = useTranslations('files')
  const [activeFile, setActiveFile] = useState<string>('')
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set())
  const [contentMode, setContentMode] = useState<'file' | 'text'>('file')  // 内容模式：文件或文字
  const [textContent, setTextContent] = useState('')
  
  // 从store获取文件
  const selectedFiles = useAppStore((state) => state.selectedFiles)
  const setSelectedFiles = useAppStore((state) => state.setSelectedFiles)
  const fileIdMap = useAppStore((state) => state.fileIdMap)
  
  // 灵活的文件类型判断
  const getFileType = (file: File) => {
    const mimeType = file.type.toLowerCase()
    const extension = file.name.split('.').pop()?.toLowerCase() || ''
    
    // 基于MIME类型判断
    if (mimeType.startsWith('image/')) return 'image'
    if (mimeType.startsWith('video/')) return 'video'
    if (mimeType.startsWith('audio/')) return 'audio'
    if (mimeType.startsWith('text/')) return 'document'
    if (mimeType.includes('pdf')) return 'document'
    
    // 基于扩展名判断（作为备选）
    const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']
    const videoExts = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']
    const docExts = ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt']
    const audioExts = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']
    
    if (imageExts.includes(extension)) return 'image'
    if (videoExts.includes(extension)) return 'video'
    if (audioExts.includes(extension)) return 'audio'
    if (docExts.includes(extension)) return 'document'
    
    return 'file'
  }
  
  // 将File对象转换为显示用的格式
  const files = selectedFiles.map((file, index) => ({
    id: `file-${index}`,
    name: file.name,
    type: getFileType(file),
    file: file,
    url: URL.createObjectURL(file),
    uploaded: fileIdMap.has(file.name),
    uploading: uploadingFiles.has(file.name)
  }))
  
  // 清理URL对象防止内存泄漏
  useEffect(() => {
    return () => {
      files.forEach(file => {
        if (file.url) {
          URL.revokeObjectURL(file.url)
        }
      })
    }
  }, [files])
  
  // 清理所有文件
  const clearAllFiles = () => {
    files.forEach(file => {
      if (file.url) {
        URL.revokeObjectURL(file.url)
      }
    })
    setSelectedFiles([])
    setActiveFile('')
  }
  
  // 清理文字内容
  const clearTextContent = () => {
    setTextContent('')
  }
  
  // 处理文本内容提交（添加到会话上下文，但不立即分析）
  const handleTextSubmit = async () => {
    if (!textContent.trim()) return
    
    try {
      // 显示文本预览
      const addMessage = useAppStore.getState().addMessage
      addMessage({
        id: `text-preview-${Date.now()}`,
        type: 'system-alert',
        content: `テキストコンテンツ (${textContent.length}文字) が準備されました`,
        metadata: { level: 'info' },
        timestamp: new Date().toISOString(),
      })
      
      // 发送给Agent但明确说明只是提供内容，不要立即分析
      const textPreview = textContent.length > 100 
        ? textContent.substring(0, 100) + '...' 
        : textContent
      
      socketManager.sendChat(
        `[テキストコンテンツが提供されました]\n` +
        `文字数: ${textContent.length}\n` +
        `プレビュー: ${textPreview}\n\n` +
        `--- 完全なテキスト ---\n${textContent}\n--- テキスト終了 ---\n\n` +
        `このテキストについて何か分析が必要でしょうか？`
      )
      
      // 清空输入但保持在文本模式
      setTextContent('')
      
      // 成功提示
      addMessage({
        id: `text-ready-${Date.now()}`,
        type: 'system-alert',
        content: 'テキストがAgentに共有されました。指示をお待ちしています。',
        metadata: { level: 'success' },
        timestamp: new Date().toISOString(),
      })
    } catch (error) {
      console.error('Failed to send text:', error)
      const addMessage = useAppStore.getState().addMessage
      addMessage({
        id: `text-error-${Date.now()}`,
        type: 'system-alert',
        content: 'テキストの送信に失敗しました',
        metadata: { level: 'error' },
        timestamp: new Date().toISOString(),
      })
    }
  }
  
  // 处理继续添加文件
  const handleAddMoreFiles = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx'
    input.onchange = async (e) => {
      const newFiles = Array.from((e.target as HTMLInputElement).files || [])
      if (newFiles.length > 0) {
        const currentFiles = useAppStore.getState().selectedFiles
        setSelectedFiles([...currentFiles, ...newFiles])
        // 自动上传新文件
        for (const file of newFiles) {
          try {
            await socketManager.sendFile(file)
          } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error)
          }
        }
      }
    }
    input.click()
  }
  
  // アップロードされていないファイルをアップロード
  const uploadFiles = async () => {
    const filesToUpload = files.filter(f => !f.uploaded && !f.uploading)
    
    if (filesToUpload.length === 0) {
      const addMessage = useAppStore.getState().addMessage
      addMessage({
        id: `upload-info-${Date.now()}`,
        type: 'system-alert',
        content: tFiles('allFilesUploaded'),
        metadata: { level: 'success' },
        timestamp: new Date().toISOString(),
      })
      return
    }
    
    let successCount = 0
    for (const fileInfo of filesToUpload) {
      setUploadingFiles(prev => new Set(prev).add(fileInfo.name))
      try {
        await socketManager.sendFile(fileInfo.file)
        successCount++
      } catch (error) {
        console.error(`Failed to upload ${fileInfo.name}:`, error)
      } finally {
        setUploadingFiles(prev => {
          const next = new Set(prev)
          next.delete(fileInfo.name)
          return next
        })
      }
    }
    
    if (successCount > 0) {
      const addMessage = useAppStore.getState().addMessage
      addMessage({
        id: `upload-success-${Date.now()}`,
        type: 'system-alert',
        content: tFiles('uploadSuccessMessage', { count: successCount }),
        metadata: { level: 'success' },
        timestamp: new Date().toISOString(),
      })
    }
  }
  
  // 设置默认激活文件
  React.useEffect(() => {
    if (files.length > 0 && !activeFile) {
      setActiveFile(files[0].id)
    }
  }, [files, activeFile])

  return (
    <div className="h-full flex flex-col">
      {/* 内容模式切换 */}
      <div className="border-b px-4 py-2">
        <div className="flex items-center justify-between">
          <Tabs value={contentMode} onValueChange={(v) => setContentMode(v as 'file' | 'text')}>
            <TabsList className="h-8">
              <TabsTrigger value="file" className="text-xs px-3">
                <FileImage className="h-3.5 w-3.5 mr-1" />
                ファイル
              </TabsTrigger>
              <TabsTrigger value="text" className="text-xs px-3">
                <Type className="h-3.5 w-3.5 mr-1" />
                テキスト
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>
      
      {/* 内容区域 */}
      {contentMode === 'text' ? (
        /* 文字输入模式 */
        <div className="flex-1 p-4">
          <Card className="h-full flex flex-col">
            <div className="flex-1 p-4">
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="分析したいテキストをここに入力またはペースト..."
                className="w-full h-full min-h-[300px] p-4 border-0 resize-none focus:outline-none text-sm"
              />
            </div>
            <div className="p-4 border-t flex justify-between items-center">
              <span className="text-xs text-muted-foreground">
                {textContent.length} 文字
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={clearTextContent}
                  disabled={!textContent}
                >
                  クリア
                </Button>
                <Button
                  size="sm"
                  onClick={handleTextSubmit}
                  disabled={!textContent.trim()}
                >
                  <Upload className="h-3.5 w-3.5 mr-1" />
                  分析
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : files.length > 0 ? (
        /* 文件模式 */
        <div className="flex-1 flex flex-col">
          <div className="border-b px-4 py-2">
            <div className="flex items-center justify-between gap-2">
              <ScrollArea className="flex-1">
                <Tabs value={activeFile} onValueChange={setActiveFile}>
                  <TabsList className="h-9">
                    {files.map((file) => (
                      <TabsTrigger key={file.id} value={file.id} className="flex items-center gap-1.5 px-3 text-xs">
                        {file.type === 'image' && <FileImage className="h-3.5 w-3.5" />}
                        {file.type === 'video' && <FileVideo className="h-3.5 w-3.5" />}
                        {file.type === 'document' && <FileText className="h-3.5 w-3.5" />}
                        {file.type === 'audio' && <FileAudio className="h-3.5 w-3.5" />}
                        {file.type === 'file' && <FileIcon className="h-3.5 w-3.5" />}
                        <span className="max-w-[120px] truncate">{file.name}</span>
                        {file.uploaded && (
                          <Badge variant="outline" className="ml-1 h-4 px-1 text-[10px] bg-green-50 text-green-700 border-green-300">
                            アップロード済み
                          </Badge>
                        )}
                        {file.uploading && (
                          <Badge variant="outline" className="ml-1 h-4 px-1 text-[10px] bg-yellow-50 text-yellow-700 border-yellow-300 animate-pulse">
                            アップロード中
                          </Badge>
                        )}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </ScrollArea>
              
              {/* 操作按钮 */}
              <div className="flex items-center gap-1 ml-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleAddMoreFiles}
                  className="h-7 w-7 p-0 hover:bg-primary/10"
                  title="ファイルを追加"
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
                {files.some(f => !f.uploaded && !f.uploading) && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={uploadFiles}
                    className="h-7 px-2 text-xs text-green-700 hover:bg-green-50 hover:text-green-800"
                  >
                    <CloudUpload className="h-3.5 w-3.5 mr-1" />
                    アップロード
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={clearAllFiles}
                  className="h-7 w-7 p-0 hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>

          {/* 文件内容展示 */}
          <div className="flex-1 overflow-hidden">
            {files.map((file) => (
              <div key={file.id} className={`h-full ${activeFile === file.id ? 'block' : 'hidden'}`}>
                <ScrollArea className="h-full">
                  <div className="p-6 flex items-center justify-center min-h-full">
                    {file.type === 'image' && (
                      <div className="w-full max-w-4xl">
                        <AspectRatio ratio={16 / 9} className="bg-muted rounded-lg overflow-hidden">
                          <img 
                            src={file.url} 
                            alt={file.name}
                            className="w-full h-full object-contain"
                          />
                        </AspectRatio>
                        <div className="mt-3 text-center">
                          <p className="text-sm font-medium">{file.name}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {file.file.size ? `${(file.file.size / 1024 / 1024).toFixed(2)} MB` : ''}
                          </p>
                        </div>
                      </div>
                    )}
                    
                    {file.type === 'video' && (
                      <div className="w-full max-w-4xl">
                        <AspectRatio ratio={16 / 9} className="bg-black rounded-lg overflow-hidden">
                          <video 
                            src={file.url} 
                            controls
                            className="w-full h-full"
                          />
                        </AspectRatio>
                        <div className="mt-3 text-center">
                          <p className="text-sm font-medium">{file.name}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {file.file.size ? `${(file.file.size / 1024 / 1024).toFixed(2)} MB` : ''}
                          </p>
                        </div>
                      </div>
                    )}
                    
                    {file.type === 'audio' && (
                      <div className="w-full max-w-2xl">
                        <Card className="p-8">
                          <div className="flex flex-col items-center">
                            <FileAudio className="h-16 w-16 mb-4 text-muted-foreground" />
                            <audio 
                              src={file.url} 
                              controls
                              className="w-full"
                            />
                            <div className="mt-4 text-center">
                              <p className="text-sm font-medium">{file.name}</p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {file.file.size ? `${(file.file.size / 1024 / 1024).toFixed(2)} MB` : ''}
                              </p>
                            </div>
                          </div>
                        </Card>
                      </div>
                    )}
                    
                    {file.type === 'document' && (
                      <Card className="p-8 max-w-md">
                        <div className="flex flex-col items-center">
                          <FileText className="h-16 w-16 mb-4 text-muted-foreground" />
                          <p className="text-sm font-medium">{file.name}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {file.file.size ? `${(file.file.size / 1024 / 1024).toFixed(2)} MB` : ''}
                          </p>
                          <p className="text-xs text-muted-foreground mt-3">
                            ドキュメントプレビューは利用できません
                          </p>
                        </div>
                      </Card>
                    )}
                    
                    {file.type === 'file' && (
                      <Card className="p-8 max-w-md">
                        <div className="flex flex-col items-center">
                          <FileIcon className="h-16 w-16 mb-4 text-muted-foreground" />
                          <p className="text-sm font-medium">{file.name}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {file.file.size ? `${(file.file.size / 1024 / 1024).toFixed(2)} MB` : ''}
                          </p>
                        </div>
                      </Card>
                    )}
                  </div>
                </ScrollArea>
              </div>
            ))}
          </div>
        </div>
      ) : contentMode === 'file' ? (
        /* 文件模式空状態 - ファイルアップロードエリア */
        <div className="flex-1 p-4">
          <Card 
            className="h-full flex items-center justify-center border-2 border-dashed border-muted-foreground/20 hover:border-muted-foreground/30 transition-colors cursor-pointer bg-muted/5"
            onDragOver={(e) => {
              e.preventDefault()
              e.currentTarget.classList.add('border-primary/50', 'bg-primary/5')
            }}
            onDragLeave={(e) => {
              e.preventDefault()
              e.currentTarget.classList.remove('border-primary/50', 'bg-primary/5')
            }}
            onDrop={async (e) => {
              e.preventDefault()
              e.currentTarget.classList.remove('border-primary/50', 'bg-primary/5')
              const droppedFiles = Array.from(e.dataTransfer.files)
              if (droppedFiles.length > 0) {
                const setSelectedFiles = useAppStore.getState().setSelectedFiles
                setSelectedFiles(droppedFiles)
                // 自動アップロード
                for (const file of droppedFiles) {
                  try {
                    await socketManager.sendFile(file)
                  } catch (error) {
                    console.error(`Failed to upload ${file.name}:`, error)
                  }
                }
              }
            }}
            onClick={() => {
              const input = document.createElement('input')
              input.type = 'file'
              input.multiple = true
              input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx'
              input.onchange = async (e) => {
                const files = Array.from((e.target as HTMLInputElement).files || [])
                if (files.length > 0) {
                  const setSelectedFiles = useAppStore.getState().setSelectedFiles
                  setSelectedFiles(files)
                  // 自動アップロード
                  for (const file of files) {
                    try {
                      await socketManager.sendFile(file)
                    } catch (error) {
                      console.error(`Failed to upload ${file.name}:`, error)
                    }
                  }
                }
              }
              input.click()
            }}
          >
            <div className="text-center p-8">
              <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground/50" />
              <p className="text-base font-medium mb-1">
                ここにファイルをドロップ
              </p>
              <p className="text-sm text-muted-foreground mb-4">
                またはクリックしてファイルを選択
              </p>
              <p className="text-xs text-muted-foreground">
                画像、動画、音声、ドキュメント形式に対応
              </p>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}