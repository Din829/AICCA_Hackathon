# AICCA前端项目结构文档

## 技术栈
- Next.js 15 (使用Turbopack)
- React 19
- TypeScript 5.5
- Tailwind CSS v4 (CSS-first配置)
- shadcn/ui组件库
- Zustand状态管理
- Socket.io-client v4
- next-intl国际化
- TanStack Query v5

## 目录结构
```
packages/web/
├── src/
│   ├── app/
│   │   ├── [locale]/
│   │   │   ├── layout.tsx          # 国际化布局
│   │   │   └── page.tsx            # 主页面
│   │   ├── layout.tsx              # 根布局
│   │   └── globals.css             # Tailwind v4全局样式
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx       # 左侧对话面板
│   │   │   ├── MessageList.tsx     # 消息列表容器
│   │   │   └── messages/           # 5种消息类型组件
│   │   │       ├── UserMessage.tsx     # 用户消息
│   │   │       ├── AgentThinking.tsx   # Agent思考
│   │   │       ├── ToolCall.tsx        # 工具调用
│   │   │       ├── AgentReply.tsx      # Agent回复
│   │   │       └── SystemAlert.tsx     # 系统提示
│   │   ├── content/
│   │   │   ├── ContentPanel.tsx    # 右侧内容面板
│   │   │   ├── ContentPreview.tsx  # 内容预览(上50%)
│   │   │   └── AnalysisResults.tsx # 分析结果(下50%)
│   │   ├── layout/
│   │   │   └── MainLayout.tsx      # 主布局(双栏)
│   │   ├── common/
│   │   │   └── LanguageSwitcher.tsx # 语言切换器
│   │   └── ui/                     # shadcn/ui组件
│   │       ├── resizable.tsx       # 可调整面板
│   │       ├── card.tsx            # 卡片
│   │       ├── tabs.tsx            # 标签页
│   │       ├── progress.tsx        # 进度条
│   │       ├── skeleton.tsx        # 骨架屏
│   │       ├── alert.tsx           # 警告提示
│   │       ├── button.tsx          # 按钮
│   │       └── input.tsx           # 输入框
│   ├── i18n/
│   │   ├── routing.ts              # 路由配置
│   │   └── request.ts              # 请求配置
│   ├── messages/                   # 国际化文件
│   │   ├── ja.json                 # 日语(默认)
│   │   ├── en.json                 # 英语
│   │   └── zh.json                 # 中文
│   ├── lib/
│   │   ├── utils.ts                # 工具函数
│   │   └── socket.ts               # WebSocket管理
│   ├── store/
│   │   └── useAppStore.ts          # Zustand全局状态
│   └── middleware.ts               # Next.js中间件
├── package.json                    # 依赖配置
├── tsconfig.json                   # TypeScript配置
├── next.config.ts                  # Next.js配置
├── postcss.config.js              # PostCSS配置
├── components.json                # shadcn/ui配置
└── .env.local                     # 环境变量
```

## 核心功能实现

### 1. 双栏布局
- 使用ResizablePanel组件实现可调整宽度
- 左侧30%: 对话区(ChatPanel)
- 右侧70%: 内容展示区(ContentPanel)
- 右侧上下分割: 内容预览50% + 分析结果50%

### 2. 消息类型系统
定义5种消息类型:
- user: 用户消息(右对齐,主色背景)
- agent-thinking: Agent思考(灰色斜体,Skeleton动画)
- tool-call: 工具调用(Card展示,Progress进度条)
- agent-reply: Agent回复(左对齐,包含风险评分)
- system-alert: 系统提示(Alert组件,支持不同级别)

### 3. 国际化配置
- 默认语言: 日语(ja)
- 支持语言: ja/en/zh
- URL路径: /ja/chat, /en/chat, /zh/chat
- 动态切换: LanguageSwitcher组件

### 4. 状态管理(Zustand)
```typescript
interface AppState {
  messages: Message[]              // 消息列表
  currentAnalysis: AnalysisResult  // 当前分析
  analysisHistory: AnalysisResult[] // 历史记录
  connectionStatus: string          // 连接状态
  selectedFiles: File[]            // 选中文件
  activeTools: Map                // 工具状态
}
```

### 5. WebSocket连接
- 自动重连机制: 1/2/4/8/16秒间隔
- 最大重连次数: 5次
- 消息类型:
  - 对话: chat_start, chat_content, chat_complete
  - 工具: tool_call, tool_execution_*, tool_result
  - 分析: analysis_start, analysis_progress, analysis_complete
  - 系统: connection, error, pong

### 6. 内容展示
- 多文件支持: Tabs组件切换
- 三种视图模式: 原图/热力图/对比
- 文件类型: 图片/视频/文本
- 懒加载: 只渲染当前激活tab

### 7. 分析结果展示
- 风险评分: 0-100分值,颜色渐变
- 检测结果: deepfake_score, ai_generated_score
- 多标签页: 概要/证据/详情/建议
- 进度显示: Progress组件

## 关键配置

### Tailwind CSS v4
- 使用@import "tailwindcss"单行导入
- CSS-first配置,无需tailwind.config.js
- 颜色系统: OKLCH色彩空间
- 主题变量: 通过@theme定义

### TypeScript配置
- strict模式启用
- 路径别名: @/*, @/components/*, @/lib/*
- 目标: ES2022
- JSX: preserve

### Next.js配置
- Turbopack: 通过--turbo flag启用
- React严格模式: true
- 图片优化: 支持远程图片
- 环境变量: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL

## 开发注意事项

1. 不使用emoji
2. 严格遵循shadcn/ui 2025规范
3. 工具返回字段名不统一,需要适配处理
4. Agent自主选择工具,前端只展示结果
5. 保持灵活性,避免硬编码
6. 小侵入性开发原则
7. 日语作为默认语言,确保日语界面完整

## 代码优化完成

### 已修正的问题
1. **移除硬编码数据**
   - MessageList: 从Zustand store获取消息
   - ContentPreview: 从store获取文件列表
   - AnalysisResults: 使用字段适配器处理动态数据

2. **字段名适配**
   - 创建field-adapter.ts统一处理不同工具返回的字段
   - 支持deepfake_score/ai_generated_score等字段自动映射
   - 提供UnifiedAnalysisResult统一接口

3. **补充缺失组件**
   - Collapsible组件
   - Dialog组件
   - Toast组件

4. **TanStack Query集成**
   - 配置QueryClient
   - 创建QueryProvider
   - 实现API hooks(useAnalyzeContent等)

5. **灵活性改进**
   - 字段映射可配置化
   - 避免硬编码工具名称
   - 支持动态数据源