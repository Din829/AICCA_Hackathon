'use client'

import { useEffect, useState } from 'react'
import useAppStore from '../../store/useAppStore'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Progress } from '../ui/progress'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { Badge } from '../ui/badge'
import { ScrollArea } from '../ui/scroll-area'
import { Separator } from '../ui/separator'
import { Button } from '../ui/button'
import { Skeleton } from '../ui/skeleton'
import { 
  FileSearch, 
  AlertCircle,
  CheckCircle,
  XCircle,
  Info,
  ChevronLeft,
  ChevronRight,
  Image,
  Video,
  FileText,
  Shield,
  Cpu,
  Eye,
  Lock
} from 'lucide-react'

// 工具类型映射
const TOOL_INFO: Record<string, { name: string; icon: any; color: string }> = {
  'image_verify': { 
    name: 'イメージ検証', 
    icon: Eye,
    color: 'text-blue-600'
  },
  'deepfake_detector': { 
    name: 'ディープフェイク検出', 
    icon: Cpu,
    color: 'text-purple-600'
  },
  'ai_content_detector': { 
    name: 'AIコンテンツ検出', 
    icon: FileText,
    color: 'text-green-600'
  },
  'ai_detector': {  // 添加ai_detector映射
    name: 'AIコンテンツ検出', 
    icon: FileText,
    color: 'text-green-600'
  },
  'c2pa_credential_tool': { 
    name: 'C2PA認証', 
    icon: Lock,
    color: 'text-orange-600'
  },
  'c2pa_verify': {  // 添加c2pa_verify映射
    name: 'C2PA認証', 
    icon: Lock,
    color: 'text-orange-600'
  }
}

export default function AnalysisResults() {
  const currentAnalysis = useAppStore((state) => state.currentAnalysis)
  const analysisResultsByFile = useAppStore((state) => state.analysisResultsByFile)
  const currentFileKey = useAppStore((state) => state.currentFileKey)
  const currentToolType = useAppStore((state) => state.currentToolType)
  const setCurrentFileKey = useAppStore((state) => state.setCurrentFileKey)
  const setCurrentToolType = useAppStore((state) => state.setCurrentToolType)
  const selectedFiles = useAppStore((state) => state.selectedFiles)
  const fileIdMap = useAppStore((state) => state.fileIdMap)
  const messages = useAppStore((state) => state.messages)
  
  // 检查是否有工具正在执行
  const isToolExecuting = messages.some(m => 
    m.type === 'tool-call' && 
    (m.metadata?.status === 'executing' || m.metadata?.status === 'pending')
  )
  
  // 获取所有有分析结果的文件
  const filesWithResults = Array.from(analysisResultsByFile.keys())
  
  // 获取当前文件的所有分析结果
  const currentFileAnalysis = currentFileKey 
    ? analysisResultsByFile.get(currentFileKey) || []
    : []
  
  // 获取当前显示的分析结果
  const displayAnalysis = currentToolType
    ? currentFileAnalysis.find(a => a.type === currentToolType)
    : currentAnalysis
  
  // 文件切换
  const handleFileSwitch = (direction: 'prev' | 'next') => {
    if (filesWithResults.length === 0) return
    
    const currentIndex = currentFileKey 
      ? filesWithResults.indexOf(currentFileKey)
      : -1
    
    let newIndex
    if (direction === 'prev') {
      newIndex = currentIndex <= 0 ? filesWithResults.length - 1 : currentIndex - 1
    } else {
      newIndex = currentIndex >= filesWithResults.length - 1 ? 0 : currentIndex + 1
    }
    
    setCurrentFileKey(filesWithResults[newIndex])
    setCurrentToolType(null) // 重置工具选择
  }
  
  // 自动设置当前文件
  useEffect(() => {
    if (!currentFileKey && filesWithResults.length > 0) {
      setCurrentFileKey(filesWithResults[0])
    }
  }, [filesWithResults, currentFileKey, setCurrentFileKey])
  
  // 如果工具正在执行，显示加载状态
  if (isToolExecuting && !displayAnalysis && !currentFileAnalysis.length) {
    return (
      <div className="h-full p-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-9 w-24" />
          </div>
          
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-5 rounded" />
                <Skeleton className="h-6 w-32" />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-full" />
              </div>
              
              <div className="space-y-3">
                <Skeleton className="h-4 w-32" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }
  
  // 如果没有分析结果，显示空状态
  if (!displayAnalysis && !currentFileAnalysis.length) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center">
          <FileSearch className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
          <h3 className="text-lg font-medium text-muted-foreground mb-2">
            解析結果がここに表示されます
          </h3>
          <p className="text-sm text-muted-foreground">
            ファイルをアップロードして解析を開始すると結果が表示されます
          </p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 文件切换器 */}
      {filesWithResults.length > 0 && (
        <div className="flex items-center justify-between p-3 border-b flex-shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleFileSwitch('prev')}
            disabled={filesWithResults.length <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium truncate max-w-[200px]" title={currentFileKey || 'No file selected'}>
              {(() => {
                if (!currentFileKey) return 'No file selected'
                // 如果是fileId格式，尝试找到对应的文件名
                const fileIdMap = useAppStore.getState().fileIdMap
                for (const [name, id] of fileIdMap.entries()) {
                  if (id === currentFileKey) {
                    return name
                  }
                }
                // 如果不是fileId，可能就是文件名
                return currentFileKey
              })()}
            </span>
            <Badge variant="secondary">
              {filesWithResults.indexOf(currentFileKey || '') + 1} / {filesWithResults.length}
            </Badge>
          </div>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleFileSwitch('next')}
            disabled={filesWithResults.length <= 1}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
      
      {/* 工具选择标签 */}
      {currentFileAnalysis.length > 0 && (
        <Tabs 
          value={currentToolType || currentFileAnalysis[0]?.type} 
          onValueChange={setCurrentToolType}
          className="flex-1 flex flex-col overflow-hidden"
        >
          <TabsList className="grid w-full flex-shrink-0" style={{ gridTemplateColumns: `repeat(${currentFileAnalysis.length}, 1fr)` }}>
            {currentFileAnalysis.map((analysis) => {
              const toolInfo = TOOL_INFO[analysis.type] || { 
                name: analysis.type, 
                icon: Shield, 
                color: 'text-gray-600' 
              }
              const Icon = toolInfo.icon
              
              return (
                <TabsTrigger key={analysis.id} value={analysis.type} className="flex items-center gap-1">
                  <Icon className={`h-3 w-3 ${toolInfo.color}`} />
                  <span className="text-xs">{toolInfo.name}</span>
                </TabsTrigger>
              )
            })}
          </TabsList>
          
          {/* 分析结果内容 */}
          <div className="flex-1 overflow-hidden">
            {currentFileAnalysis.map((analysis) => (
              <TabsContent key={analysis.id} value={analysis.type} className="h-full mt-0">
                <ScrollArea className="h-full">
                  <div className="p-4">
                    {renderAnalysisContent(analysis)}
                  </div>
                </ScrollArea>
              </TabsContent>
            ))}
          </div>
        </Tabs>
      )}
      
      {/* 单个结果显示（当没有标签时） */}
      {!currentFileAnalysis.length && displayAnalysis && (
        <ScrollArea className="flex-1">
          <div className="p-4">
            {renderAnalysisContent(displayAnalysis)}
          </div>
        </ScrollArea>
      )}
    </div>
  )
}

// 渲染不同工具的分析结果
function renderAnalysisContent(analysis: any) {
  const content = analysis.content || {}
  
  switch (analysis.type) {
    case 'image_verify':
      return <ImageVerifyResult content={content} />
    case 'deepfake_detector':
      return <DeepfakeResult content={content} />
    case 'ai_content_detector':
    case 'ai_detector':  // 支持两种工具名称
      return <AIContentResult content={content} />
    case 'c2pa_credential_tool':
    case 'c2pa_verify':  // 支持两种工具名称
      return <C2PAResult content={content} />
    default:
      return <GenericResult content={content} />
  }
}

// Image Verify 结果组件
function ImageVerifyResult({ content }: { content: any }) {
  const localAnalysis = content.local_analysis || {}
  const visionAnalysis = content.vision_analysis || {}
  const aiDetection = content.ai_detection || {}
  
  // 计算综合风险分数
  const aiScore = aiDetection.type?.ai_generated || 0
  const riskScore = Math.round(aiScore * 100)
  
  return (
    <div className="space-y-4">
      {/* 总体评分 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">総合リスク評価</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">AI生成確率</span>
              <Badge variant={riskScore > 70 ? "destructive" : riskScore > 30 ? "secondary" : "default"}>
                {riskScore}%
              </Badge>
            </div>
            <Progress value={riskScore} className="h-2" />
          </div>
        </CardContent>
      </Card>
      
      {/* 本地分析 */}
      {localAnalysis.image_info && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ローカル分析</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-muted-foreground">フォーマット</dt>
              <dd>{localAnalysis.image_info.format || 'N/A'}</dd>
              <dt className="text-muted-foreground">サイズ</dt>
              <dd>{localAnalysis.image_info.width}x{localAnalysis.image_info.height}</dd>
              <dt className="text-muted-foreground">モード</dt>
              <dd>{localAnalysis.image_info.mode || 'N/A'}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
      
      {/* Vision API 分析 */}
      {visionAnalysis.labels && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">検出オブジェクト</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {visionAnalysis.labels.slice(0, 5).map((label: any, idx: number) => (
                <div key={idx} className="flex items-center justify-between">
                  <span className="text-sm">{label.description}</span>
                  <Progress value={label.score * 100} className="w-24 h-1" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// Deepfake 结果组件
function DeepfakeResult({ content }: { content: any }) {
  const mediaType = content.media_type
  const sightengineAnalysis = content.sightengine_analysis || content.video_analysis || {}
  
  // 智能识别检测模式和分数
  let detectionScore = 0
  let detectionMode = 'deepfake' // 默认模式
  let scoreLabel = 'ディープフェイクスコア' // 默认标签
  let resultTitle = 'ディープフェイク検出結果' // 默认标题
  
  // 综合模式检测 - 优先处理
  const comprehensiveMode = sightengineAnalysis.comprehensive_mode || false
  const facialAnalysis = sightengineAnalysis.facial_analysis || null
  const generalAiAnalysis = sightengineAnalysis.general_ai_analysis || null
  
  if (comprehensiveMode && generalAiAnalysis) {
    // 综合模式下，优先显示AI生成检测结果
    detectionMode = 'ai_generated'
    detectionScore = Math.round((generalAiAnalysis.average_ai_score || 0) * 100)
    scoreLabel = 'AI生成確率'
    resultTitle = '総合検出結果'
  } else if (sightengineAnalysis.model === 'genai' || sightengineAnalysis.average_ai_score !== undefined) {
    // 通用AI检测模式
    detectionMode = 'ai_generated'
    detectionScore = Math.round((sightengineAnalysis.average_ai_score || 0) * 100)
    scoreLabel = 'AI生成確率'
    resultTitle = 'AIコンテンツ検出結果'
  } else if (sightengineAnalysis.type?.deepfake) {
    // Deepfake检测（图片）
    detectionScore = Math.round(sightengineAnalysis.type.deepfake * 100)
  } else if (sightengineAnalysis.average_deepfake_score) {
    // Deepfake检测（视频）
    detectionScore = Math.round(sightengineAnalysis.average_deepfake_score * 100)
  }
  
  return (
    <div className="space-y-4">
      {/* 总体评分 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{resultTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">メディアタイプ</span>
              <Badge>{mediaType}</Badge>
            </div>
            
            {/* 综合模式：显示两个分数 */}
            {comprehensiveMode ? (
              <>
                {/* AI生成分数 */}
                <div className="flex items-center justify-between">
                  <span className="text-sm">AI生成確率</span>
                  <Badge variant={detectionScore > 70 ? "destructive" : detectionScore > 30 ? "secondary" : "default"}>
                    {detectionScore}%
                  </Badge>
                </div>
                <Progress value={detectionScore} className="h-2" />
                
                {/* Deepfake分数 */}
                {facialAnalysis && (
                  <>
                    <div className="flex items-center justify-between pt-2 border-t">
                      <span className="text-sm">ディープフェイクスコア</span>
                      <Badge variant={
                        Math.round((facialAnalysis.average_deepfake_score || 0) * 100) > 70 ? "destructive" : 
                        Math.round((facialAnalysis.average_deepfake_score || 0) * 100) > 30 ? "secondary" : "default"
                      }>
                        {Math.round((facialAnalysis.average_deepfake_score || 0) * 100)}%
                      </Badge>
                    </div>
                    <Progress value={Math.round((facialAnalysis.average_deepfake_score || 0) * 100)} className="h-2" />
                  </>
                )}
              </>
            ) : (
              <>
                {/* 单一模式：显示一个分数 */}
                <div className="flex items-center justify-between">
                  <span className="text-sm">{scoreLabel}</span>
                  <Badge variant={detectionScore > 70 ? "destructive" : detectionScore > 30 ? "secondary" : "default"}>
                    {detectionScore}%
                  </Badge>
                </div>
                <Progress value={detectionScore} className="h-2" />
              </>
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* 视频分析详情 */}
      {mediaType === 'video' && (
        comprehensiveMode ? (
          // 综合模式帧分析
          (generalAiAnalysis?.frames_analyzed || facialAnalysis?.frames_analyzed) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">フレーム分析</CardTitle>
              </CardHeader>
              <CardContent>
                {generalAiAnalysis?.frames_analyzed && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">AI生成検出</p>
                    <dl className="grid grid-cols-2 gap-2 text-sm">
                      <dt className="text-muted-foreground">分析フレーム数</dt>
                      <dd>{generalAiAnalysis.frames_analyzed || 0}</dd>
                      <dt className="text-muted-foreground">最大スコア</dt>
                      <dd>{Math.round((generalAiAnalysis.max_ai_score || 0) * 100)}%</dd>
                      <dt className="text-muted-foreground">平均スコア</dt>
                      <dd>{Math.round((generalAiAnalysis.average_ai_score || 0) * 100)}%</dd>
                    </dl>
                  </div>
                )}
                {facialAnalysis?.frames_analyzed && (
                  <div className="space-y-2 mt-4 pt-4 border-t">
                    <p className="text-sm font-medium">顔面改ざん検出</p>
                    <dl className="grid grid-cols-2 gap-2 text-sm">
                      <dt className="text-muted-foreground">分析フレーム数</dt>
                      <dd>{facialAnalysis.frames_analyzed || 0}</dd>
                      <dt className="text-muted-foreground">最大スコア</dt>
                      <dd>{Math.round((facialAnalysis.max_deepfake_score || 0) * 100)}%</dd>
                      <dt className="text-muted-foreground">平均スコア</dt>
                      <dd>{Math.round((facialAnalysis.average_deepfake_score || 0) * 100)}%</dd>
                    </dl>
                  </div>
                )}
              </CardContent>
            </Card>
          )
        ) : (
          // 单一模式帧分析
          (sightengineAnalysis.frames_analyzed || sightengineAnalysis.frame_details) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">フレーム分析</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <dt className="text-muted-foreground">分析フレーム数</dt>
                  <dd>{sightengineAnalysis.frames_analyzed || 0}</dd>
                  <dt className="text-muted-foreground">最大スコア</dt>
                  <dd>{Math.round((
                    sightengineAnalysis.max_deepfake_score || 
                    sightengineAnalysis.max_ai_score || 
                    0
                  ) * 100)}%</dd>
                  <dt className="text-muted-foreground">平均スコア</dt>
                  <dd>{Math.round((
                    sightengineAnalysis.average_deepfake_score || 
                    sightengineAnalysis.average_ai_score || 
                    0
                  ) * 100)}%</dd>
                </dl>
              </CardContent>
            </Card>
          )
        )
      )}
      
      {/* 元数据分析 */}
      {content.metadata_analysis && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">メタデータ分析</CardTitle>
          </CardHeader>
          <CardContent>
            {content.metadata_analysis.metadata && (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-muted-foreground">フォーマット</dt>
                <dd className="font-mono break-all">
                  {content.metadata_analysis.metadata.format || 'unknown'}
                </dd>
                
                <dt className="text-muted-foreground">時間</dt>
                <dd>{content.metadata_analysis.metadata.duration ? `${content.metadata_analysis.metadata.duration}秒` : 'unknown'}</dd>
                
                <dt className="text-muted-foreground">解像度</dt>
                <dd>
                  {content.metadata_analysis.metadata.width && content.metadata_analysis.metadata.height 
                    ? `${content.metadata_analysis.metadata.width} × ${content.metadata_analysis.metadata.height}`
                    : 'unknown'}
                </dd>
                
                <dt className="text-muted-foreground">コーデック</dt>
                <dd>{content.metadata_analysis.metadata.codec || 'unknown'}</dd>
                
                <dt className="text-muted-foreground">フレームレート</dt>
                <dd>
                  {content.metadata_analysis.metadata.frame_rate 
                    ? `${content.metadata_analysis.metadata.frame_rate.split('/')[0]} fps`
                    : 'unknown'}
                </dd>
                
                <dt className="text-muted-foreground">ビットレート</dt>
                <dd>
                  {content.metadata_analysis.metadata.bit_rate && content.metadata_analysis.metadata.bit_rate !== 'unknown'
                    ? `${(parseInt(content.metadata_analysis.metadata.bit_rate) / 1000000).toFixed(2)} Mbps`
                    : 'unknown'}
                </dd>
                
                {content.metadata_analysis.metadata.size && (
                  <>
                    <dt className="text-muted-foreground">サイズ</dt>
                    <dd>{(parseInt(content.metadata_analysis.metadata.size) / 1048576).toFixed(2)} MB</dd>
                  </>
                )}
                
                {content.metadata_analysis.metadata.encoder && (
                  <>
                    <dt className="text-muted-foreground">エンコーダー</dt>
                    <dd>{content.metadata_analysis.metadata.encoder}</dd>
                  </>
                )}
              </dl>
            )}
            
            {/* 可疑指标 */}
            {content.metadata_analysis.suspicious_indicators && content.metadata_analysis.suspicious_indicators.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">疑わしい指標</p>
                <div className="space-y-1">
                  {content.metadata_analysis.suspicious_indicators.map((indicator: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2">
                      <span className="text-yellow-600 mt-0.5">▪</span>
                      <span className="text-sm text-muted-foreground">{indicator}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* 状态信息 */}
            {content.metadata_analysis.status && (
              <div className="mt-3 pt-3 border-t">
                <span className="text-xs text-muted-foreground">
                  ステータス: {
                    content.metadata_analysis.status === 'analyzed' ? '詳細分析完了' :
                    content.metadata_analysis.status === 'basic_analysis' ? '基本分析完了' :
                    content.metadata_analysis.status
                  }
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// AI Content 结果组件
function AIContentResult({ content }: { content: any }) {
  // データ抽出
  const overallScore = content.score || 0
  const detectionMode = content.detection_mode || 'balanced'
  const apiSource = content.api_source || 'unknown'
  const sentenceScores = content.sentence_scores || []
  const interpretationNote = content.interpretation_note || ''
  
  // スコアの解釈
  const getScoreInterpretation = (score: number) => {
    if (score < 0.01) return { label: '人間作成', variant: 'default' as const }
    if (score < 0.3) return { label: '概ね人間作成', variant: 'default' as const }
    if (score < 0.7) return { label: '混在の可能性', variant: 'secondary' as const }
    if (score < 0.9) return { label: 'AI生成の可能性高', variant: 'destructive' as const }
    return { label: 'AI生成', variant: 'destructive' as const }
  }
  
  const interpretation = getScoreInterpretation(overallScore)
  
  // 高スコア文章の検出
  const highScoreSentences = sentenceScores.filter((s: any) => s.score > 0.5)
  const suspiciousSentences = sentenceScores.filter((s: any) => s.score > 0.3 && s.score <= 0.5)
  
  return (
    <div className="space-y-4">
      {/* 総合評価 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">AI生成検出結果</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* メインスコア */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">総合スコア</span>
                <Badge variant={interpretation.variant}>
                  {interpretation.label}
                </Badge>
              </div>
              <div className="flex items-center gap-3">
                <Progress value={overallScore * 100} className="flex-1 h-2" />
                <span className="text-sm font-medium min-w-[50px] text-right">
                  {(overallScore * 100).toFixed(2)}%
                </span>
              </div>
            </div>
            
            {/* 検出詳細 */}
            <div className="grid grid-cols-2 gap-2 pt-2 border-t">
              <div className="text-sm">
                <span className="text-muted-foreground">検出モード: </span>
                <span className="font-medium">
                  {detectionMode === 'balanced' ? 'バランス' : 
                   detectionMode === 'strict' ? '厳格' : 
                   detectionMode === 'lenient' ? '寛容' : detectionMode}
                </span>
              </div>
              <div className="text-sm">
                <span className="text-muted-foreground">検出エンジン: </span>
                <span className="font-medium uppercase">{apiSource}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* 文章レベル分析 */}
      {sentenceScores.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">文章レベル分析</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              各文章のAI生成確率を個別に評価
            </p>
          </CardHeader>
          <CardContent>
            {/* サマリー統計 */}
            <div className="grid grid-cols-3 gap-2 mb-4 pb-3 border-b">
              <div className="text-center">
                <div className="text-2xl font-bold text-destructive">{highScoreSentences.length}</div>
                <div className="text-xs text-muted-foreground">高確率検出</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{suspiciousSentences.length}</div>
                <div className="text-xs text-muted-foreground">疑わしい</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {sentenceScores.length - highScoreSentences.length - suspiciousSentences.length}
                </div>
                <div className="text-xs text-muted-foreground">人間的</div>
              </div>
            </div>
            
            {/* 文章リスト */}
            <ScrollArea className="h-64">
              <div className="space-y-2">
                {sentenceScores.map((item: any, idx: number) => {
                  const scorePercent = (item.score * 100).toFixed(3)
                  const isHighScore = item.score > 0.5
                  const isSuspicious = item.score > 0.3 && item.score <= 0.5
                  
                  return (
                    <div 
                      key={idx} 
                      className={`p-3 rounded-lg border ${
                        isHighScore ? 'border-destructive/50 bg-destructive/5' :
                        isSuspicious ? 'border-yellow-600/30 bg-yellow-50/50' :
                        'border-border bg-muted/30'
                      }`}
                    >
                      <p className="text-sm leading-relaxed mb-2">{item.sentence}</p>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">
                          文章 {idx + 1} / {sentenceScores.length}
                        </span>
                        <div className="flex items-center gap-2">
                          <Progress 
                            value={item.score * 100} 
                            className="w-20 h-1"
                          />
                          <span className={`text-xs font-mono ${
                            isHighScore ? 'text-destructive' :
                            isSuspicious ? 'text-yellow-600' :
                            'text-muted-foreground'
                          }`}>
                            {scorePercent}%
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
      
      {/* 解釈ノート */}
      {interpretationNote && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">分析解釈</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {interpretationNote}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// C2PA 结果组件
function C2PAResult({ content }: { content: any }) {
  // 健壮的数据提取
  const manifestStore = content?.manifest_store || {}
  const activeManifestId = manifestStore.active_manifest
  const activeManifest = activeManifestId ? manifestStore.manifests?.[activeManifestId] : null
  
  // 使用active_manifest_details作为备选数据源（更易解析）
  const activeDetails = content?.active_manifest_details || {}
  const validationAnalysis = content?.validation_analysis || {}
  const validationResults = content?.validation_results || manifestStore.validation_results || {}
  const trustVerification = content?.trust_verification || {}
  
  // 验证状态（优先使用validation_analysis）
  const hasC2PA = validationAnalysis.has_c2pa !== undefined ? validationAnalysis.has_c2pa : !!activeManifest
  const isValid = validationAnalysis.is_valid !== undefined ? validationAnalysis.is_valid : (hasC2PA && validationAnalysis.validation_errors?.length === 0)
  const validationErrors = validationAnalysis.validation_errors || []
  
  return (
    <div className="space-y-4">
      {/* 验证状态 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">C2PA認証状態</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">認証状態</span>
              <Badge variant={hasC2PA ? "default" : "secondary"}>
                {hasC2PA ? "C2PA署名あり" : "C2PA署名なし"}
              </Badge>
            </div>
            
            {hasC2PA && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">検証結果</span>
                <Badge variant={isValid ? "default" : "destructive"}>
                  {isValid ? "有効" : validationErrors.length > 0 ? `${validationErrors.length}件のエラー` : "無効"}
                </Badge>
              </div>
            )}
            
            {hasC2PA && trustVerification.trust_status && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">信頼チェーン</span>
                <Badge variant={trustVerification.trust_status === 'valid' ? "default" : "secondary"}>
                  {trustVerification.trust_status === 'valid' ? "検証済み" : trustVerification.note || "未検証"}
                </Badge>
              </div>
            )}
            
            {hasC2PA && (
              <Progress value={isValid ? 100 : 50} className="h-2" />
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* マニフェスト情報 */}
      {(activeManifest || activeDetails.label) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">マニフェスト情報</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between py-1 border-b border-border/50">
                <dt className="text-muted-foreground">タイトル</dt>
                <dd className="text-right max-w-[60%] break-all">
                  {activeDetails.title || activeManifest?.title || 'unknown'}
                </dd>
              </div>
              
              <div className="flex justify-between py-1 border-b border-border/50">
                <dt className="text-muted-foreground">フォーマット</dt>
                <dd>{activeDetails.format || activeManifest?.format || 'unknown'}</dd>
              </div>
              
              {(activeDetails.signature || activeManifest?.signature_info) && (
                <>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <dt className="text-muted-foreground">署名者</dt>
                    <dd className="text-right max-w-[60%] break-all">
                      {activeDetails.signature?.issuer || activeManifest?.signature_info?.issuer || 'unknown'}
                    </dd>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <dt className="text-muted-foreground">署名時刻</dt>
                    <dd className="text-right max-w-[60%] break-all">
                      {activeDetails.signature?.time || activeManifest?.signature_info?.time || 'unknown'}
                    </dd>
                  </div>
                </>
              )}
              
              {(activeDetails.generator || activeManifest?.claim_generator_info?.[0]) && (
                <>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <dt className="text-muted-foreground">生成ツール</dt>
                    <dd className="text-right max-w-[60%] break-all">
                      {activeDetails.generator?.name || activeManifest?.claim_generator_info?.[0].name || activeManifest?.claim_generator || 'unknown'}
                    </dd>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <dt className="text-muted-foreground">バージョン</dt>
                    <dd>
                      {activeDetails.generator?.version || activeManifest?.claim_generator_info?.[0].version || 'unknown'}
                    </dd>
                  </div>
                </>
              )}
            </dl>
          </CardContent>
        </Card>
      )}
      
      {/* アサーション */}
      {((activeManifest?.assertions && activeManifest.assertions.length > 0) || 
        (activeDetails?.assertions?.other && activeDetails.assertions.other.length > 0)) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">アサーション</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {/* EXIFデータを特別に表示 */}
              {(activeManifest?.assertions || activeDetails?.assertions?.other || [])
                .filter((a: any) => a.label?.includes('exif'))
                .map((assertion: any, idx: number) => {
                  const exifData = assertion.data || {}
                  const cleanExifData = Object.entries(exifData)
                    .filter(([key]) => !key.startsWith('@'))
                    .reduce((acc, [key, value]) => {
                      const cleanKey = key.replace('EXIF:', '').replace('EXIFEX:', '')
                      return { ...acc, [cleanKey]: value }
                    }, {})
                  
                  return (
                    <div key={`exif-${idx}`} className="p-3 bg-muted/30 rounded-lg">
                      <div className="text-sm font-medium mb-2">EXIFメタデータ</div>
                      <div className="grid grid-cols-2 gap-1 text-xs">
                        {Object.entries(cleanExifData).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-muted-foreground">{key}:</span>
                            <span className="font-mono ml-2 truncate">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              
              {/* センサーデータを特別に表示 */}
              {(activeManifest?.assertions || activeDetails?.assertions?.other || [])
                .filter((a: any) => a.label?.includes('odometry'))
                .map((assertion: any, idx: number) => {
                  const sensorData = assertion.data || {}
                  return (
                    <div key={`sensor-${idx}`} className="p-3 bg-muted/30 rounded-lg">
                      <div className="text-sm font-medium mb-2">センサーデータ</div>
                      <div className="space-y-2 text-xs">
                        {sensorData.lens && (
                          <div>レンズ: {sensorData.lens}</div>
                        )}
                        {sensorData.attitude?.[0] && (
                          <div>
                            姿勢: 方位角 {Number(sensorData.attitude[0].azimuth).toFixed(2)}°, 
                            ピッチ {Number(sensorData.attitude[0].pitch).toFixed(2)}°, 
                            ロール {Number(sensorData.attitude[0].roll).toFixed(2)}°
                          </div>
                        )}
                        {sensorData.pressure?.[0] && (
                          <div>気圧: {sensorData.pressure[0].value} hPa</div>
                        )}
                      </div>
                    </div>
                  )
                })}
              
              {/* その他のアサーション */}
              {(activeManifest?.assertions || activeDetails?.assertions?.other || [])
                .filter((a: any) => !a.label?.includes('exif') && !a.label?.includes('odometry'))
                .map((assertion: any, idx: number) => (
                  <div key={`other-${idx}`} className="p-2 bg-muted/50 rounded">
                    <div className="text-sm font-medium">{assertion.label || `Assertion ${idx + 1}`}</div>
                    {assertion.data && (
                      <div className="mt-1 text-xs text-muted-foreground">
                        {typeof assertion.data === 'object' 
                          ? Object.entries(assertion.data).slice(0, 3).map(([key, value]) => (
                              <div key={key} className="flex gap-2">
                                <span>{key}:</span>
                                <span className="font-mono truncate">{String(value).slice(0, 50)}</span>
                              </div>
                            ))
                          : String(assertion.data).slice(0, 100)
                        }
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* 成分（来源） */}
      {activeManifest?.ingredients && activeManifest.ingredients.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">コンテンツ来源</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {activeManifest.ingredients.map((ingredient: any, idx: number) => (
                <div key={idx} className="p-2 bg-muted/50 rounded">
                  <div className="text-sm">
                    {ingredient.title || `Source ${idx + 1}`}
                  </div>
                  {ingredient.format && (
                    <div className="text-xs text-muted-foreground mt-1">
                      Format: {ingredient.format}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* 検証結果詳細 */}
      {validationResults.activeManifest && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">検証結果詳細</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {/* 成功項目 */}
              {validationResults.activeManifest.success?.length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-1 text-green-600">✓ 検証成功項目</div>
                  <div className="space-y-1 text-xs">
                    {validationResults.activeManifest.success.slice(0, 5).map((item: any, idx: number) => (
                      <div key={idx} className="pl-4 text-muted-foreground">
                        • {item.explanation || item.code}
                      </div>
                    ))}
                    {validationResults.activeManifest.success.length > 5 && (
                      <div className="pl-4 text-muted-foreground">
                        ...他{validationResults.activeManifest.success.length - 5}項目
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* エラー項目 */}
              {validationResults.activeManifest.failure?.length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-1 text-destructive">✗ 検証エラー</div>
                  <div className="space-y-1 text-xs">
                    {validationResults.activeManifest.failure.map((item: any, idx: number) => (
                      <div key={idx} className="pl-4">
                        • {item.explanation || item.code}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* 无C2PA信息 */}
      {!hasC2PA && (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              このコンテンツにはC2PA認証情報が含まれていません
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              コンテンツの出所と真正性を検証できません
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// 通用结果组件
function GenericResult({ content }: { content: any }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">分析結果</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <pre className="text-xs font-mono whitespace-pre-wrap">
            {JSON.stringify(content, null, 2)}
          </pre>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}