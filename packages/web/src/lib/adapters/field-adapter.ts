/**
 * 字段名适配器
 * 处理不同工具返回的字段名不一致问题
 * 保持灵活性，避免硬编码
 */

// 统一的分析结果接口
export interface UnifiedAnalysisResult {
  // 风险分数（0-100）
  riskScore: number
  
  // AI检测相关
  aiDetection: {
    score: number  // 0-1或0-100，需要标准化
    type: 'deepfake' | 'ai_generated' | 'mixed' | 'unknown'
    confidence: number
  }
  
  // 详细分数（如句子级分析）
  detailScores?: Array<{
    index: number
    score: number
    text?: string
  }>
  
  // C2PA验证
  c2paValidation?: {
    valid: boolean
    hasCredential: boolean
    tampering?: boolean
    trustStatus?: string
  }
  
  // 元数据
  metadata?: {
    anomalies: number
    details: Record<string, any>
  }
  
  // 原始数据（保留原始响应）
  rawData: any
}

// 字段映射配置（可从配置文件加载）
const FIELD_MAPPINGS = {
  deepfake: {
    score: ['deepfake_score', 'score', 'probability'],
    confidence: ['confidence', 'certainty']
  },
  ai_generated: {
    score: ['ai_generated_score', 'ai_score', 'score'],
    confidence: ['confidence', 'certainty']
  },
  text: {
    score: ['score', 'ai_probability'],
    sentences: ['sentence_scores', 'sentences', 'details']
  },
  c2pa: {
    valid: ['is_valid', 'valid', 'validation_status'],
    tampering: ['tampering_detected', 'tampered', 'modified']
  }
}

/**
 * 从原始数据中提取字段值
 * 支持多个可能的字段名
 */
function extractField(data: any, possibleFields: string[]): any {
  if (!data) return undefined
  
  for (const field of possibleFields) {
    // 支持嵌套字段访问（如 'result.score'）
    const parts = field.split('.')
    let value = data
    
    for (const part of parts) {
      value = value?.[part]
      if (value === undefined) break
    }
    
    if (value !== undefined) {
      return value
    }
  }
  
  return undefined
}

/**
 * 标准化分数到0-100范围
 */
function normalizeScore(score: number | undefined, originalRange: [number, number] = [0, 1]): number {
  if (score === undefined || score === null) return 0
  
  const [min, max] = originalRange
  const normalized = ((score - min) / (max - min)) * 100
  
  return Math.max(0, Math.min(100, normalized))
}

/**
 * 适配Deepfake检测结果
 */
export function adaptDeepfakeResult(data: any): Partial<UnifiedAnalysisResult> {
  // 处理视频分析的嵌套结构
  if (data?.video_analysis) {
    const videoAnalysis = data.video_analysis
    
    // 综合模式
    if (videoAnalysis.comprehensive_mode) {
      const facialScore = videoAnalysis.facial_analysis?.average_deepfake_score || 
                         videoAnalysis.facial_analysis?.error ? 0 : 50
      const aiScore = videoAnalysis.general_ai_analysis?.average_ai_score || 
                     videoAnalysis.general_ai_analysis?.error ? 0 : 50
      
      return {
        aiDetection: {
          score: normalizeScore(Math.max(facialScore, aiScore), [0, 1]),
          type: 'mixed',
          confidence: 0.7
        },
        metadata: {
          anomalies: videoAnalysis.facial_analysis?.error ? 1 : 0,
          details: {
            facial: videoAnalysis.facial_analysis,
            ai: videoAnalysis.general_ai_analysis,
            model: videoAnalysis.model_used || 'comprehensive'
          }
        },
        rawData: data
      }
    }
    
    // 单一模式
    const score = extractField(videoAnalysis, ['average_deepfake_score', 'average_ai_score', 'deepfake_score'])
    return {
      aiDetection: {
        score: normalizeScore(score, [0, 1]),
        type: videoAnalysis.model_used === 'genai' ? 'ai_generated' : 'deepfake',
        confidence: 0.8
      },
      rawData: data
    }
  }
  
  // 处理图片分析
  if (data?.sightengine_analysis) {
    const analysis = data.sightengine_analysis
    const score = analysis.deepfake_score || analysis.ai_generated_score || 0
    
    return {
      aiDetection: {
        score: normalizeScore(score, [0, 1]),
        type: analysis.deepfake_score ? 'deepfake' : 'ai_generated',
        confidence: 0.9
      },
      rawData: data
    }
  }
  
  // 处理错误情况
  if (data?.error) {
    return {
      aiDetection: {
        score: 0,
        type: 'unknown',
        confidence: 0
      },
      metadata: {
        anomalies: 1,
        details: { error: data.error }
      },
      rawData: data
    }
  }
  
  // 默认处理
  const score = extractField(data, FIELD_MAPPINGS.deepfake.score)
  const confidence = extractField(data, FIELD_MAPPINGS.deepfake.confidence)
  
  return {
    aiDetection: {
      score: normalizeScore(score),
      type: 'deepfake',
      confidence: confidence || 0
    },
    rawData: data
  }
}

/**
 * 适配AI生成检测结果
 */
export function adaptAIGeneratedResult(data: any): Partial<UnifiedAnalysisResult> {
  const score = extractField(data, FIELD_MAPPINGS.ai_generated.score)
  const confidence = extractField(data, FIELD_MAPPINGS.ai_generated.confidence)
  
  return {
    aiDetection: {
      score: normalizeScore(score),
      type: 'ai_generated',
      confidence: confidence || 0
    },
    rawData: data
  }
}

/**
 * 适配文本检测结果
 */
export function adaptTextResult(data: any): Partial<UnifiedAnalysisResult> {
  const score = extractField(data, FIELD_MAPPINGS.text.score)
  const sentences = extractField(data, FIELD_MAPPINGS.text.sentences)
  
  const detailScores = sentences?.map((item: any, index: number) => ({
    index,
    score: typeof item === 'number' ? item : item?.score || 0,
    text: item?.text
  }))
  
  return {
    aiDetection: {
      score: normalizeScore(score),
      type: 'ai_generated',
      confidence: 0
    },
    detailScores,
    rawData: data
  }
}

/**
 * 适配C2PA验证结果
 */
export function adaptC2PAResult(data: any): Partial<UnifiedAnalysisResult> {
  // 处理C2PA结果的多种格式
  if (data?.validation_report) {
    const report = data.validation_report
    const hasCredential = report.manifest_store !== undefined || data.has_manifest
    const isValid = report.is_valid || (hasCredential && !report.validation_errors)
    
    return {
      c2paValidation: {
        valid: isValid,
        hasCredential: hasCredential,
        tampering: report.tampering_detected || false,
        trustStatus: report.trust_status || 'unknown'
      },
      metadata: {
        anomalies: report.validation_errors?.length || 0,
        details: {
          manifest_id: report.manifest_id,
          errors: report.validation_errors
        }
      },
      rawData: data
    }
  }
  
  // 处理错误情况
  if (data?.error || data?.status === 'error') {
    return {
      c2paValidation: {
        valid: false,
        hasCredential: false,
        tampering: false,
        trustStatus: 'error'
      },
      metadata: {
        anomalies: 1,
        details: { error: data.error || data.message }
      },
      rawData: data
    }
  }
  
  // 默认处理
  const valid = extractField(data, FIELD_MAPPINGS.c2pa.valid)
  const tampering = extractField(data, FIELD_MAPPINGS.c2pa.tampering)
  
  return {
    c2paValidation: {
      valid: Boolean(valid),
      hasCredential: data?.manifest_store !== undefined || data?.has_manifest,
      tampering: Boolean(tampering),
      trustStatus: data?.validation_analysis?.trust_status
    },
    rawData: data
  }
}

/**
 * 通用适配器
 * 根据工具类型自动选择适配策略
 */
export function adaptToolResult(toolName: string, data: any): UnifiedAnalysisResult {
  let result: Partial<UnifiedAnalysisResult> = { rawData: data }
  
  // 根据工具名称选择适配策略（保持灵活，不硬编码）
  const toolNameLower = toolName.toLowerCase()
  
  if (toolNameLower.includes('deepfake')) {
    result = { ...result, ...adaptDeepfakeResult(data) }
  } else if (toolNameLower.includes('ai') || toolNameLower.includes('detect')) {
    result = { ...result, ...adaptAIGeneratedResult(data) }
  } else if (toolNameLower.includes('text')) {
    result = { ...result, ...adaptTextResult(data) }
  } else if (toolNameLower.includes('c2pa')) {
    result = { ...result, ...adaptC2PAResult(data) }
  }
  
  // 计算综合风险分数
  result.riskScore = calculateRiskScore(result)
  
  return result as UnifiedAnalysisResult
}

/**
 * 计算综合风险分数
 * 可根据业务需求调整权重
 */
function calculateRiskScore(result: Partial<UnifiedAnalysisResult>): number {
  const scores: number[] = []
  
  if (result.aiDetection?.score !== undefined) {
    scores.push(result.aiDetection.score)
  }
  
  if (result.c2paValidation !== undefined) {
    // C2PA无效或被篡改增加风险
    if (!result.c2paValidation.valid || result.c2paValidation.tampering) {
      scores.push(80)
    } else if (result.c2paValidation.hasCredential && result.c2paValidation.valid) {
      scores.push(20)
    }
  }
  
  if (result.metadata?.anomalies) {
    // 每个异常增加10分风险
    scores.push(Math.min(100, result.metadata.anomalies * 10))
  }
  
  // 返回平均分或最高分（根据需求调整）
  return scores.length > 0 
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
    : 50 // 默认中等风险
}