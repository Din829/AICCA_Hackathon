import useAppStore from '../store/useAppStore'
import { toast } from 'sonner'

// WebSocket消息类型定义
export interface ServerMessage {
  type: 'connection' | 'chat_start' | 'chat_content' | 'chat_complete' |
        'tool_call' | 'tool_result' | 'analysis_start' | 'analysis_progress' |
        'analysis_tool_result' | 'analysis_complete' | 'error' | 'pong' |
        'upload_progress' | 'upload_complete'
  [key: string]: any
}

export interface ClientMessage {
  type: 'chat' | 'analyze' | 'file_chunk' | 'tool_execute' | 'ping'
  [key: string]: any
}

class SocketManager {
  private socket: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelays = [1000, 2000, 4000, 8000, 16000]
  private clientId: string = ''
  private messageQueue: ClientMessage[] = []
  private connected = false
  private currentStreamingMessageId: string | null = null

  connect(clientId?: string) {
    // 生成或使用提供的clientId
    this.clientId = clientId || `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // 获取WebSocket URL - 支持运行时环境变量（部署环境修复）
    let wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

    // 部署环境动态检测：如果在生产环境且URL仍是localhost，则使用当前域名
    if (typeof window !== 'undefined' && wsUrl.includes('localhost') && window.location.hostname !== 'localhost') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const hostname = window.location.hostname
      // 检查是否是前端域名，如果是则推断后端域名
      if (hostname.includes('aicca-frontend')) {
        const backendHostname = hostname.replace('aicca-frontend', 'aicca-backend')
        wsUrl = `${protocol}//${backendHostname}`
      } else {
        wsUrl = `${protocol}//${hostname}:8000`
      }
      console.log('🔄 Auto-detected WebSocket URL for production:', wsUrl)
    }

    const fullUrl = `${wsUrl}/ws/enhanced/${this.clientId}`

    console.log('🔗 WebSocket Connection Info:')
    console.log('  - NEXT_PUBLIC_WS_URL:', process.env.NEXT_PUBLIC_WS_URL)
    console.log('  - Resolved wsUrl:', wsUrl)
    console.log('  - Full URL:', fullUrl)
    console.log('  - Client ID:', this.clientId)
    
    // 创建WebSocket连接
    this.socket = new WebSocket(fullUrl)
    
    // 设置连接状态
    useAppStore.getState().setConnectionStatus('connecting')
    
    // 设置事件处理器
    this.setupEventHandlers()
  }

  private setupEventHandlers() {
    if (!this.socket) return

    // 连接打开
    this.socket.onopen = () => {
      console.log('✅ WebSocket connected successfully')
      console.log('  - Connection URL:', this.socket?.url)
      console.log('  - Ready State:', this.socket?.readyState)
      this.connected = true
      this.reconnectAttempts = 0
      useAppStore.getState().setConnectionStatus('connected')

      // 发送队列中的消息
      this.flushMessageQueue()
    }

    // 接收消息
    this.socket.onmessage = (event) => {
      try {
        const data: ServerMessage = JSON.parse(event.data)
        this.handleServerMessage(data)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    // 连接关闭
    this.socket.onclose = () => {
      console.log('WebSocket disconnected')
      this.connected = false
      useAppStore.getState().setConnectionStatus('disconnected')
      this.handleReconnect()
    }

    // 连接错误
    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error)
      useAppStore.getState().setConnectionStatus('error')
    }
  }

  private handleServerMessage(data: ServerMessage) {
    const store = useAppStore.getState()

    console.log('📨 Received WebSocket message:', data.type, data)

    switch (data.type) {
      case 'connection':
        console.log('Connection confirmed:', data)
        break
        
      case 'chat_start':
        // 生成唯一的消息ID，不使用session_id避免重复
        const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        this.currentStreamingMessageId = messageId
        store.addMessage({
          id: messageId,
          type: 'agent-thinking',
          content: '考え中...',
          timestamp: new Date().toISOString()
        })
        break
        
      case 'chat_content':
        // 流式更新消息内容 - 累积而不是替换
        if (this.currentStreamingMessageId) {
          const messages = store.messages
          const targetMessage = messages.find(m => m.id === this.currentStreamingMessageId)
          
          if (targetMessage) {
            // 累积内容，第一次时转换类型
            const isFirstContent = targetMessage.type === 'agent-thinking'
            store.updateMessage(this.currentStreamingMessageId, {
              ...targetMessage,
              type: 'agent-reply',
              content: isFirstContent ? data.content : targetMessage.content + data.content
            })
          } else {
            // 如果没有找到目标消息（比如工具调用后），创建新消息
            store.addMessage({
              id: this.currentStreamingMessageId,
              type: 'agent-reply',
              content: data.content,
              timestamp: new Date().toISOString()
            })
          }
        }
        break
        
      case 'chat_complete':
        // 聊天完成，清除流式消息ID
        this.currentStreamingMessageId = null
        
        // 检查是否有未完成的工具调用，如有则标记为成功
        const messages = store.messages
        const pendingTools = messages.filter(m => 
          m.type === 'tool-call' && 
          (m.metadata?.status === 'executing' || m.metadata?.status === 'pending')
        )
        
        pendingTools.forEach(toolMessage => {
          store.updateMessage(toolMessage.id, {
            ...toolMessage,
            metadata: {
              ...toolMessage.metadata,
              status: 'success'
            }
          })
        })
        break
        
      case 'tool_call':
        // 工具调用时，需要结束当前流式消息，创建新的消息流
        // 完成当前的流式消息
        if (this.currentStreamingMessageId) {
          this.currentStreamingMessageId = null
        }
        
        // 添加工具调用消息
        store.addMessage({
          id: `tool-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: 'tool-call',
          content: `ツール実行: ${data.tool_name}`,
          metadata: { 
            status: 'executing', 
            tool: data.tool_name,
            args: data.parameters 
          },
          timestamp: new Date().toISOString()
        })
        
        // 添加Sonner通知
        toast(`${data.tool_name} を実行中...`, {
          description: '分析処理を開始しました'
        })
        
        // 为工具调用后的内容创建新的流式消息ID
        const newMessageId = `msg-after-tool-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        this.currentStreamingMessageId = newMessageId
        break
        
      case 'tool_result':
        // 更新分析结果 - 增加文件关联
        console.log('[DEBUG] Tool result received:', data)
        
        // 尝试从原始参数和结果中提取文件信息
        let fileName = 'unknown'
        let fileId = null
        
        // 首先从原始参数中提取（最可靠）
        if (data.original_args) {
          // image_path, media_path, file_path 等参数
          const possiblePaths = [
            data.original_args.image_path,
            data.original_args.media_path,
            data.original_args.file_path,
            data.original_args.content  // 有时候文件路径在content参数中
          ]
          
          for (const path of possiblePaths) {
            if (path && typeof path === 'string') {
              // 处理file:ID格式
              if (path.startsWith('file:')) {
                fileId = path.substring(5)
                // 从fileIdMap反向查找文件名
                const fileIdMap = store.fileIdMap
                for (const [name, id] of fileIdMap.entries()) {
                  if (id === fileId) {
                    fileName = name
                    break
                  }
                }
                break
              } else {
                // 普通文件路径，提取文件名
                fileName = path.split('/').pop() || path.split('\\').pop() || path
                break
              }
            }
          }
        }
        
        // 如果还是没找到，尝试从结果中提取
        if (fileName === 'unknown') {
          if (data.result?.file_name) {
            fileName = data.result.file_name
          } else if (data.result?.media_path) {
            fileName = data.result.media_path
          } else if (data.result?.local_analysis?.file_path) {
            fileName = data.result.local_analysis.file_path
          }
        }
        
        // 如果有文件名但没有fileId，尝试从fileIdMap找到对应的fileId
        const fileIdMap = store.fileIdMap
        if (!fileId && fileName !== 'unknown' && fileIdMap.has(fileName)) {
          fileId = fileIdMap.get(fileName)
        }
        
        const analysisResult = {
          id: `analysis-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: data.tool_name,
          content: data.result,
          timestamp: new Date(),
          fileName: fileName,
          fileId: fileId || fileName  // 使用fileId或fileName作为标识
        }
        console.log('[DEBUG] Setting current analysis:', analysisResult)
        store.setCurrentAnalysis(analysisResult)
        
        // 设置当前文件标识
        if (fileId || fileName !== 'unknown') {
          store.setCurrentFileKey(fileId || fileName)
        }
        
        // 如果是检测类工具，添加到历史
        if (data.tool_name?.toLowerCase().includes('detect') || 
            data.tool_name?.toLowerCase().includes('verify') ||
            data.tool_name?.toLowerCase().includes('c2pa')) {
          store.addAnalysisHistory(analysisResult)
        }
        
        // 更新工具调用状态为成功
        const currentMessages = store.messages
        const toolMessage = currentMessages.findLast(m => 
          m.type === 'tool-call' && 
          m.metadata?.tool === data.tool_name &&
          (m.metadata?.status === 'pending' || m.metadata?.status === 'executing')
        )
        
        if (toolMessage) {
          store.updateMessage(toolMessage.id, {
            ...toolMessage,
            metadata: {
              ...toolMessage.metadata,
              status: 'success'
            }
          })
        }
        
        // 工具完成通知
        toast.success(`${data.tool_name} 完了`, {
          description: '分析結果を表示しています'
        })
        break
        
      case 'analysis_start':
        // 显示思考状态
        const analysisMessageId = data.request_id || `analysis-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        this.currentStreamingMessageId = analysisMessageId
        store.addMessage({
          id: analysisMessageId,
          type: 'agent-thinking',
          content: '分析中...',
          timestamp: new Date().toISOString()
        })
        break
        
      case 'analysis_progress':
        // 更新分析进度
        store.addMessage({
          id: `progress-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: 'system-alert',
          content: data.status,
          metadata: { level: 'info' },
          timestamp: new Date().toISOString()
        })
        break
        
      case 'analysis_tool_result':
        // 工具结果
        console.log('[DEBUG] Analysis tool result received:', data)
        const toolAnalysisResult = {
          id: `result-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: data.tool_name,
          content: data.result,
          timestamp: new Date()
        }
        console.log('[DEBUG] Setting analysis from tool:', toolAnalysisResult)
        store.setCurrentAnalysis(toolAnalysisResult)
        
        // 添加到历史
        if (data.tool_name?.toLowerCase().includes('detect') || 
            data.tool_name?.toLowerCase().includes('verify') ||
            data.tool_name?.toLowerCase().includes('c2pa')) {
          store.addAnalysisHistory(toolAnalysisResult)
        }
        break
        
      case 'analysis_complete':
        // 将思考状态转换为完成消息
        if (this.currentStreamingMessageId) {
          const messages = store.messages
          const targetMessage = messages.find(m => m.id === this.currentStreamingMessageId)

          if (targetMessage && targetMessage.type === 'agent-thinking') {
            store.updateMessage(this.currentStreamingMessageId, {
              ...targetMessage,
              type: 'agent-reply',
              content: '分析が完了しました。結果をご確認ください。'
            })
          }
          this.currentStreamingMessageId = null
        }

        const completeResult = {
          id: data.request_id || `analysis-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: 'complete',
          content: data.result,
          timestamp: new Date()
        }
        store.setCurrentAnalysis(completeResult)
        store.addAnalysisHistory(completeResult)

        // 分析完成通知
        toast.success('分析完了', {
          description: '全ての分析処理が正常に完了しました'
        })
        break
        
      case 'error':
        store.addMessage({
          id: `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type: 'system-alert',
          content: `エラー: ${data.message}`,
          metadata: { level: 'error' },
          timestamp: new Date().toISOString()
        })
        
        // エラー通知
        toast.error('エラーが発生しました', {
          description: data.message
        })
        
        // 如果错误与工具调用相关，更新工具状态为失败
        if (data.tool_name) {
          const errorMessages = store.messages
          const toolMessage = errorMessages.findLast(m => 
            m.type === 'tool-call' && 
            m.metadata?.tool === data.tool_name &&
            (m.metadata?.status === 'pending' || m.metadata?.status === 'executing')
          )
          
          if (toolMessage) {
            store.updateMessage(toolMessage.id, {
              ...toolMessage,
              metadata: {
                ...toolMessage.metadata,
                status: 'error'
              }
            })
          }
        }
        break
        
      case 'upload_progress':
        // ファイルアップロード進捗更新
        console.log(`Upload progress: ${data.progress}%`)
        break
        
      case 'upload_complete':
        // ファイルアップロード完了 - file_idマッピングを保存
        console.log('File upload completed:', data.upload_id, data.file_id)
        if (data.file_id && data.file_info && data.file_info.name) {
          const store = useAppStore.getState()
          store.addFileMapping(data.file_info.name, data.file_id)
          
          // アップロード完了通知
          toast.success('アップロード完了', {
            description: `${data.file_info.name} が正常にアップロードされました`
          })
        }
        break
        
      case 'pong':
        console.log('Pong received')
        break
        
      default:
        console.log('Unknown message type:', data.type, data)
    }
  }

  private handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached')
      useAppStore.getState().setConnectionStatus('error')
      return
    }

    const delay = this.reconnectDelays[this.reconnectAttempts]
    this.reconnectAttempts++

    console.log(`Reconnecting in ${delay / 1000} seconds... (attempt ${this.reconnectAttempts})`)
    
    setTimeout(() => {
      this.connect(this.clientId)
    }, delay)
  }

  private flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.connected) {
      const message = this.messageQueue.shift()
      if (message) {
        this.send(message)
      }
    }
  }

  // 公开的重连方法
  public reconnect() {
    console.log('Manual reconnect requested')
    this.disconnect()
    this.reconnectAttempts = 0
    setTimeout(() => {
      this.connect()
    }, 100)
  }

  private send(message: ClientMessage) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message))
    } else {
      // 如果未连接，加入队列
      this.messageQueue.push(message)
    }
  }

  // 公共方法
  disconnect() {
    if (this.socket) {
      this.socket.close()
      this.socket = null
      this.connected = false
      useAppStore.getState().setConnectionStatus('disconnected')
    }
  }

  // 发送聊天消息
  sendChat(message: string) {
    this.send({
      type: 'chat',
      message: message,
      session_id: `session_${this.clientId}`
    })
  }

  // 发送分析请求
  sendAnalysis(content: string, sourceType: 'image' | 'video' | 'text' | 'auto' = 'auto') {
    this.send({
      type: 'analyze',
      content: content,
      source_type: sourceType,
      options: {}
    })
  }

  // 发送文件（自动分块）
  async sendFile(file: File): Promise<string> {
    const CHUNK_SIZE = 1024 * 1024 // 1MB chunks
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    
    return new Promise((resolve, reject) => {
      // 监听上传结果
      const handleUploadResult = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'upload_complete' && data.upload_id === uploadId) {
            this.socket?.removeEventListener('message', handleUploadResult)
            resolve(data.file_id)
          } else if (data.type === 'error' && data.upload_id === uploadId) {
            this.socket?.removeEventListener('message', handleUploadResult)
            reject(new Error(data.message))
          }
        } catch (e) {
          // 忽略非 JSON 消息
        }
      }
      
      this.socket?.addEventListener('message', handleUploadResult)
      
      // 发送文件分块
      const sendChunks = async () => {
        try {
          for (let i = 0; i < totalChunks; i++) {
            const start = i * CHUNK_SIZE
            const end = Math.min(start + CHUNK_SIZE, file.size)
            const chunk = file.slice(start, end)
            
            const reader = new FileReader()
            const base64Chunk = await new Promise<string>((resolve) => {
              reader.onload = (e) => {
                const result = e.target?.result as string
                resolve(result.split(',')[1]) // Remove data:type;base64, prefix
              }
              reader.readAsDataURL(chunk)
            })
            
            this.send({
              type: 'file_chunk',
              upload_id: uploadId,
              chunk_index: i,
              total_chunks: totalChunks,
              data: base64Chunk,
              file_info: {
                name: file.name,
                size: file.size,
                type: file.type
              }
            })
            
            // 等待一小段时间避免过载
            await new Promise(resolve => setTimeout(resolve, 100))
          }
        } catch (error) {
          this.socket?.removeEventListener('message', handleUploadResult)
          reject(error)
        }
      }
      
      sendChunks()
      
      // 超时处理
      setTimeout(() => {
        this.socket?.removeEventListener('message', handleUploadResult)
        reject(new Error('ファイルアップロードタイムアウト'))
      }, 30000) // 30秒超时
    })
  }

  // 直接执行工具
  executeToolDirectly(toolName: string, args: any) {
    this.send({
      type: 'tool_execute',
      tool_name: toolName,
      args: args
    })
  }

  // 发送心跳
  sendPing() {
    this.send({ type: 'ping' })
  }

  // 获取连接状态
  isConnected() {
    return this.connected
  }
}

// 单例模式
const socketManager = new SocketManager()
export default socketManager