import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Message } from '../components/chat/MessageList'

interface AnalysisResult {
  id: string
  type: string  // tool name
  content: any
  timestamp: Date
  fileName?: string
  fileId?: string
}

interface AppState {
  // 消息相关
  messages: Message[]
  addMessage: (message: Message) => void
  updateMessage: (id: string, updatedMessage: Message) => void
  clearMessages: () => void
  
  // 分析结果相关 - 支持多文件多工具
  currentAnalysis: AnalysisResult | null
  analysisHistory: AnalysisResult[]
  analysisResultsByFile: Map<string, AnalysisResult[]>  // fileId/fileName -> results
  currentFileKey: string | null  // 当前选中的文件标识
  currentToolType: string | null  // 当前选中的工具类型
  setCurrentAnalysis: (analysis: AnalysisResult | null) => void
  addAnalysisHistory: (analysis: AnalysisResult) => void
  setCurrentFileKey: (key: string | null) => void
  setCurrentToolType: (type: string | null) => void
  getAnalysisForFile: (fileKey: string) => AnalysisResult[]
  getCurrentFileAnalysis: () => AnalysisResult[]
  
  // WebSocket连接状态
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  setConnectionStatus: (status: AppState['connectionStatus']) => void
  
  // 当前选中的文件
  selectedFiles: File[]
  setSelectedFiles: (files: File[]) => void
  
  // 文件ID映射
  fileIdMap: Map<string, string>  // filename -> file_id
  addFileMapping: (filename: string, fileId: string) => void
  
  // 工具执行状态
  activeTools: Map<string, { name: string; status: string; progress?: number }>
  updateToolStatus: (toolId: string, status: any) => void
  
  // 重置所有数据
  resetAll: () => void
}

const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // 消息相关
      messages: [],
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
        })),
      updateMessage: (id, updatedMessage) =>
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? updatedMessage : msg
          ),
        })),
      clearMessages: () => set({ messages: [] }),
      
      // 分析结果相关
      currentAnalysis: null,
      analysisHistory: [],
      analysisResultsByFile: new Map(),
      currentFileKey: null,
      currentToolType: null,
      setCurrentAnalysis: (analysis) => {
        set({ currentAnalysis: analysis })
        // 同时添加到按文件分组的结果中
        if (analysis) {
          const fileKey = analysis.fileId || analysis.fileName || 'unknown'
          set((state) => {
            const newMap = new Map(state.analysisResultsByFile)
            const existing = newMap.get(fileKey) || []
            // 检查是否已存在相同工具的结果，如果存在则替换
            const filteredExisting = existing.filter(r => r.type !== analysis.type)
            newMap.set(fileKey, [...filteredExisting, analysis])
            return { analysisResultsByFile: newMap }
          })
        }
      },
      addAnalysisHistory: (analysis) =>
        set((state) => ({
          analysisHistory: [...state.analysisHistory, analysis],
        })),
      setCurrentFileKey: (key) => set({ currentFileKey: key }),
      setCurrentToolType: (type) => set({ currentToolType: type }),
      getAnalysisForFile: (fileKey) => {
        const state = useAppStore.getState()
        return state.analysisResultsByFile.get(fileKey) || []
      },
      getCurrentFileAnalysis: () => {
        const state = useAppStore.getState()
        if (!state.currentFileKey) return []
        return state.analysisResultsByFile.get(state.currentFileKey) || []
      },
      
      // WebSocket连接状态
      connectionStatus: 'disconnected',
      setConnectionStatus: (status) => set({ connectionStatus: status }),
      
      // 当前选中的文件
      selectedFiles: [],
      setSelectedFiles: (files) => set({ selectedFiles: files }),
      
      // 文件ID映射
      fileIdMap: new Map(),
      addFileMapping: (filename, fileId) =>
        set((state) => {
          const newMap = new Map(state.fileIdMap)
          newMap.set(filename, fileId)
          return { fileIdMap: newMap }
        }),
      
      // 工具执行状态
      activeTools: new Map(),
      updateToolStatus: (toolId, status) =>
        set((state) => {
          const newTools = new Map(state.activeTools)
          if (status === null) {
            newTools.delete(toolId)
          } else {
            newTools.set(toolId, status)
          }
          return { activeTools: newTools }
        }),
      
      // 重置所有数据
      resetAll: () => set({
        messages: [],
        currentAnalysis: null,
        analysisHistory: [],
        analysisResultsByFile: new Map(),
        currentFileKey: null,
        currentToolType: null,
        connectionStatus: 'disconnected',
        selectedFiles: [],
        fileIdMap: new Map(),
        activeTools: new Map()
      }),
    }),
    {
      name: 'aicca-storage',
      partialize: (state) => ({
        // 刷新页面时不保存任何对话和分析数据
        // 可以在这里添加需要持久化的配置项（如语言设置等）
      }),
      // 确保刷新页面时重置所有数据
      onRehydrateStorage: () => (state) => {
        if (state) {
          // 重置所有对话和分析相关数据
          state.messages = []
          state.currentAnalysis = null
          state.analysisHistory = []
          state.analysisResultsByFile = new Map()
          state.currentFileKey = null
          state.currentToolType = null
          state.connectionStatus = 'disconnected'
          state.selectedFiles = []
          state.fileIdMap = new Map()
          state.activeTools = new Map()
        }
      },
    }
  )
)

export default useAppStore