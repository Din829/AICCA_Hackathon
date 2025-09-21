"""
AI内容检测工具 - 识别AI生成的文本、图像和音频
AI Content Detection - 使用多种技术检测AI生成内容
"""

import asyncio
import os
from typing import Dict, Any, Optional, Union, Callable, List, Tuple
from pathlib import Path
import hashlib
from datetime import datetime
import re

# 使用成熟的dbrheo接口
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
from dbrheo.tools.base import DatabaseTool, DatabaseConfirmationDetails
from dbrheo.config.base import DatabaseConfig
from dbrheo.utils.debug_logger import log_info


class AIContentDetector(DatabaseTool):
    """
    AI内容检测工具
    检测文本、图像、音频是否由AI生成，支持GPT、Stable Diffusion、Midjourney等
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self._i18n = i18n
        super().__init__(
            name="ai_detector",
            display_name=self._('ai_detector_name', default="AI Content Detector") if i18n else "AI Content Detector",
            description="Specialized text AI detection tool using Sapling API with GPTZero fallback. Analyzes writing patterns and perplexity to identify AI-generated text. Returns confidence scores (0=human, 1=AI) with sentence-level granularity.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "content_type": {
                        "type": "string",
                        "enum": ["text", "image", "audio", "auto"],
                        "description": "内容类型: text(文本), image(图像), audio(音频), auto(自动检测)",
                        "default": "auto"
                    },
                    "content": {
                        "type": "string",
                        "description": "要检测的内容（文本内容或文件路径）"
                    },
                    "detection_mode": {
                        "type": "string",
                        "enum": ["fast", "balanced", "thorough"],
                        "description": "检测模式: fast(快速), balanced(平衡), thorough(深度)",
                        "default": "balanced"
                    },
                    "check_watermark": {
                        "type": "boolean",
                        "description": "是否检查AI水印（如SynthID）",
                        "default": True
                    },
                    "analyze_patterns": {
                        "type": "boolean",
                        "description": "是否分析生成模式",
                        "default": True
                    },
                    "known_models": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "指定要检测的AI模型列表",
                        "default": ["GPT", "Claude", "Gemini", "StableDiffusion", "Midjourney", "DALL-E"]
                    }
                },
                "required": ["content"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
        
        # ===== 灵活的API配置系统 =====
        # 优先级：环境变量 > 配置文件 > 默认值
        self.api_config = self._initialize_api_config()
        
        # 文本优化设置
        self.text_optimization = {
            "enabled": config.get("ai_detector_optimize_text", True),
            "max_chars": config.get("ai_detector_max_chars", 10000),  # 单次检测最大字符
            "smart_truncate": config.get("ai_detector_smart_truncate", True),  # 智能截取
            "remove_redundant": config.get("ai_detector_remove_redundant", True),  # 移除冗余
        }
    
    def _initialize_api_config(self) -> Dict[str, Any]:
        """初始化API配置（灵活、不硬编码）"""
        config = {}
        
        # 1. Sapling API配置
        sapling_key = (
            os.environ.get("SAPLING_API_KEY") or
            self.config.get("sapling_api_key")
        )
        
        config["sapling"] = {
            "enabled": self.config.get("ai_detector_use_sapling", True),
            "api_key": sapling_key,
            "endpoint": self.config.get("sapling_endpoint", "https://api.sapling.ai/api/v1/aidetect"),
            "timeout": self.config.get("sapling_timeout", 30),
            "max_retries": self.config.get("sapling_max_retries", 2),
            "version": self.config.get("sapling_version", "20240606"),  # 最新版本
        }
        
        # 2. 备用API配置（可扩展）
        config["fallback_apis"] = []
        
        # GPTZero作为备用（如果配置了）
        gptzero_key = os.environ.get("GPTZERO_API_KEY") or self.config.get("gptzero_api_key")
        if gptzero_key:
            config["fallback_apis"].append({
                "name": "gptzero",
                "api_key": gptzero_key,
                "endpoint": "https://api.gptzero.me/v2/predict/text",
                "enabled": self.config.get("ai_detector_use_gptzero", False)
            })
        
        # 3. 本地模型配置（可选）
        config["local_models"] = {
            "enabled": self.config.get("ai_detector_use_local", False),
            "huggingface_model": self.config.get("ai_detector_hf_model", "roberta-base-openai-detector")
        }
        
        return config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        params = self._normalize_params(params)
        
        content = params.get("content", "")
        if not content:
            return "Detection content cannot be empty"
        
        content_type = params.get("content_type", "auto")
        
        # 如果是文件路径，检查文件是否存在
        if content_type in ["image", "audio", "auto"]:
            if not content.startswith(('http://', 'https://')) and len(content) < 1000:
                # 可能是文件路径
                path = Path(content)
                if path.suffix and not path.exists():
                    return f"File not found: {content}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        content = params.get("content", "")
        content_type = params.get("content_type", "auto")
        mode = params.get("detection_mode", "balanced")
        
        # 智能识别内容类型
        if content_type == "auto":
            # 处理file:ID格式
            if content.startswith('file:'):
                # 对于file:ID，默认为text（因为这个工具主要处理文本）
                content_type = "text"
            elif not content.startswith(('http://', 'https://')) and Path(content).exists():
                if Path(content).suffix in ['.jpg', '.png', '.gif', '.webp']:
                    content_type = "image"
                elif Path(content).suffix in ['.mp3', '.wav', '.m4a']:
                    content_type = "audio"
            else:
                content_type = "text"
        
        content_preview = content[:50] + "..." if len(content) > 50 else content
        
        return f"Performing {mode} mode AI detection ({content_type}): {content_preview}"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认"""
        # AI检测通常不需要确认
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行AI内容检测"""
        params = self._normalize_params(params)
        
        content = params.get("content", "")
        content_type = params.get("content_type", "auto")
        detection_mode = params.get("detection_mode", "balanced")
        
        try:
            # 智能内容准备
            if update_output:
                update_output("Preparing content...")
            
            # 处理不同输入类型
            text_content = await self._prepare_content(content, content_type)
            
            if not text_content:
                return ToolResult(
                    error="Cannot extract text content for AI detection"
                )
            
            # 文本优化（避免字符浪费）
            optimized_text = self._optimize_text_for_detection(text_content, detection_mode)
            
            if update_output:
                char_count = len(optimized_text)
                update_output(f"Analyzing {char_count} characters...")
            
            # 调用Sapling API进行检测
            detection_result = await self._call_sapling_api(optimized_text, detection_mode)
            
            if detection_result.get("error"):
                # 如果主API失败，尝试备用方案
                if update_output:
                    update_output("Primary API failed, trying fallback...")
                detection_result = await self._fallback_detection(optimized_text)
            
            # 生成详细的分析报告
            analysis_report = self._generate_analysis_report(
                detection_result, 
                optimized_text,
                detection_mode
            )
            
            # 返回标准化结果
            return self._format_detection_result(analysis_report, optimized_text)
            
        except Exception as e:
            error_msg = f"AI detection failed: {str(e)}"
            return ToolResult(
                error=error_msg,
                llm_content=f"AI detection failed: {str(e)}",
                return_display=f"[ERROR] {error_msg}"
            )
    
    # ===== 文本优化方法（避免字符浪费） =====
    
    def _optimize_text_for_detection(self, text: str, mode: str) -> str:
        """优化文本以减少API调用字符数"""
        if not self.text_optimization["enabled"]:
            return text
        
        original_length = len(text)
        
        # 1. 移除多余空白和格式字符
        if self.text_optimization["remove_redundant"]:
            # 移除多余空行
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            # 移除行尾空白
            text = '\n'.join(line.rstrip() for line in text.split('\n'))
            # 压缩多余空格
            text = re.sub(r' {2,}', ' ', text)
        
        # 2. 智能截取策略
        max_chars = self.text_optimization["max_chars"]
        
        if len(text) > max_chars and self.text_optimization["smart_truncate"]:
            if mode == "fast":
                # 快速模式：只检测开头部分
                text = text[:max_chars]
            elif mode == "balanced":
                # 平衡模式：检测开头、中间、结尾
                chunk_size = max_chars // 3
                start = text[:chunk_size]
                middle_pos = len(text) // 2
                middle = text[middle_pos - chunk_size//2:middle_pos + chunk_size//2]
                end = text[-chunk_size:]
                text = f"{start}\n[...]\n{middle}\n[...]\n{end}"
            else:  # thorough
                # 深度模式：分段采样
                if len(text) <= max_chars * 2:
                    # 如果不是太长，检测前半部分
                    text = text[:max_chars]
                else:
                    # 多段采样
                    segments = []
                    segment_count = 5
                    segment_size = max_chars // segment_count
                    step = len(text) // segment_count
                    for i in range(segment_count):
                        start_pos = i * step
                        segments.append(text[start_pos:start_pos + segment_size])
                    text = '\n[...]\n'.join(segments)
        
        # 记录优化效果
        if original_length > len(text):
            log_info("AIDetector", f"Text optimized: {original_length} -> {len(text)} chars (saved {original_length - len(text)})")
        
        return text
    
    async def _prepare_content(self, content: str, content_type: str) -> Optional[str]:
        """准备内容，提取文本"""
        try:
            # 如果是纯文本，直接返回
            if content_type == "text" or (content_type == "auto" and len(content) < 1000 and not content.startswith(('http', '/'))):
                return content
            
            # 尝试使用ContentLoader
            try:
                from aicca.utils.content_loader import ContentLoader
                loader = ContentLoader()
                file_path, metadata = await loader.load_content(content)
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception as e:
                log_info("AIDetector", f"ContentLoader failed: {e}")
                # 降级处理
                if content.startswith('file:'):
                    # 尝试从临时目录访问
                    import tempfile
                    temp_path = Path(tempfile.gettempdir()) / "aicca_uploads" / content[5:]
                    if temp_path.exists():
                        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                            return f.read()
                elif Path(content).exists():
                    with open(content, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
                return content
                
        except Exception as e:
            log_info("AIDetector", f"Content preparation failed: {e}")
            return content if isinstance(content, str) else None
    
    # ===== Sapling API调用 =====
    
    async def _call_sapling_api(self, text: str, mode: str) -> Dict[str, Any]:
        """调用Sapling AI检测API"""
        if not self.api_config["sapling"]["enabled"]:
            return {"error": "Sapling API disabled"}
        
        try:
            # 使用标准库的urllib替代httpx
            import json
            import urllib.request
            import urllib.error
            
            # 根据模式调整参数
            sent_scores = mode != "fast"  # 快速模式不需要句子级分数
            
            request_data = {
                "key": self.api_config["sapling"]["api_key"],
                "text": text,
                "sent_scores": sent_scores,
                "version": self.api_config["sapling"]["version"]
            }
            
            log_info("AIDetector", f"Calling Sapling API with {len(text)} chars, mode={mode}")
            
            # 构建请求
            req = urllib.request.Request(
                self.api_config["sapling"]["endpoint"],
                data=json.dumps(request_data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            )
            
            # 发送请求（使用asyncio.to_thread使其异步）
            import asyncio
            response_data = await asyncio.to_thread(self._send_request, req)
            
            if response_data.get("error"):
                return response_data
            
            log_info("AIDetector", f"Sapling API success: score={response_data.get('score', 'N/A')}")
            return response_data
                    
        except asyncio.TimeoutError:
            return {"error": "API request timeout"}
        except Exception as e:
            return {"error": str(e)}
    
    def _send_request(self, req):
        """同步发送HTTP请求（供asyncio.to_thread使用）"""
        try:
            import json
            import urllib.request
            import urllib.error
            
            with urllib.request.urlopen(req, timeout=self.api_config["sapling"]["timeout"]) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    return {"error": f"API returned status {response.status}"}
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP Error {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"error": f"URL Error: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _fallback_detection(self, text: str) -> Dict[str, Any]:
        """备用检测方案 - 优先尝试GPTZero，再降级到启发式检测"""
        # 1. 尝试GPTZero API（如果配置且可用）
        gptzero_result = await self._try_gptzero_api(text)
        if not gptzero_result.get("error"):
            return gptzero_result
        
        # 2. 降级到启发式检测
        return await self._heuristic_detection(text)
    
    async def _try_gptzero_api(self, text: str) -> Dict[str, Any]:
        """尝试调用GPTZero API"""
        # 检查是否配置了GPTZero
        gptzero_config = None
        for api in self.api_config.get("fallback_apis", []):
            if api["name"] == "gptzero" and api.get("enabled") and api.get("api_key"):
                gptzero_config = api
                break
        
        if not gptzero_config:
            return {"error": "GPTZero not configured"}
        
        try:
            import json
            import urllib.request
            import urllib.error
            import asyncio
            
            request_data = {
                "document": text,
                "version": "2024-01-09"  # GPTZero API版本
            }
            
            log_info("AIDetector", f"Trying GPTZero API fallback with {len(text)} chars")
            
            # 构建请求
            req = urllib.request.Request(
                gptzero_config["endpoint"],
                data=json.dumps(request_data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'x-api-key': gptzero_config["api_key"]  # GPTZero使用x-api-key头
                }
            )
            
            # 发送请求
            response_data = await asyncio.to_thread(self._send_gptzero_request, req)
            
            if response_data.get("error"):
                return response_data
            
            # 转换GPTZero响应格式为统一格式
            normalized_result = self._normalize_gptzero_response(response_data)
            log_info("AIDetector", f"GPTZero API fallback success: score={normalized_result.get('score', 'N/A')}")
            return normalized_result
                    
        except Exception as e:
            return {"error": f"GPTZero API failed: {str(e)}"}
    
    def _send_gptzero_request(self, req):
        """同步发送GPTZero HTTP请求"""
        try:
            import json
            import urllib.request
            import urllib.error
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    return {"error": f"GPTZero API returned status {response.status}"}
        except urllib.error.HTTPError as e:
            return {"error": f"GPTZero HTTP Error {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"error": f"GPTZero URL Error: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _normalize_gptzero_response(self, gptzero_data: Dict) -> Dict[str, Any]:
        """将GPTZero响应格式转换为统一格式"""
        try:
            # GPTZero响应包含：document_classification, class_probabilities等
            class_probs = gptzero_data.get("class_probabilities", {})
            ai_prob = class_probs.get("ai", 0.0)
            
            # 构建统一格式响应
            result = {
                "score": ai_prob,
                "source": "gptzero",
                "document_classification": gptzero_data.get("document_classification"),
                "confidence_category": gptzero_data.get("confidence_category")
            }
            
            # 如果有句子级检测，转换格式
            if "highlight_sentence_for_ai" in gptzero_data:
                highlighted = gptzero_data["highlight_sentence_for_ai"]
                if highlighted:
                    # 简化转换：将高亮句子转为句子分数格式
                    sentence_scores = []
                    for item in highlighted[:5]:  # 限制前5个
                        if isinstance(item, dict):
                            sentence_scores.append({
                                "sentence": item.get("sentence", ""),
                                "score": 0.8  # GPTZero高亮的句子给予高分
                            })
                    if sentence_scores:
                        result["sentence_scores"] = sentence_scores
            
            return result
            
        except Exception as e:
            return {"error": f"Failed to normalize GPTZero response: {str(e)}"}
    
    async def _heuristic_detection(self, text: str) -> Dict[str, Any]:
        """启发式检测作为最后备用方案"""
        patterns = {
            "ai_patterns": [
                r'\b(as an AI|I am an AI|language model|I cannot|I don\'t have access)\b',
                r'\b(However,|Furthermore,|Additionally,|In conclusion,)\b',
                r'\b(it\'s important to note|it\'s worth mentioning)\b'
            ],
            "human_patterns": [
                r'\b(I think|I feel|I believe|personally|in my opinion)\b',
                r'\b(lol|haha|wow|damn|shit)\b',
                r'[!?]{2,}',  # 多个感叹号/问号
                r'\.{3,}'     # 省略号
            ]
        }
        
        ai_score = 0
        human_score = 0
        
        for pattern in patterns["ai_patterns"]:
            ai_score += len(re.findall(pattern, text, re.IGNORECASE))
        
        for pattern in patterns["human_patterns"]:
            human_score += len(re.findall(pattern, text, re.IGNORECASE))
        
        # 简单的概率计算
        total = ai_score + human_score + 1
        ai_probability = min(0.95, ai_score / total)
        
        return {
            "score": ai_probability,
            "source": "fallback_heuristic",
            "ai_patterns_found": ai_score,
            "human_patterns_found": human_score
        }
    
    def _generate_analysis_report(self, detection_result: Dict, text: str, mode: str) -> Dict[str, Any]:
        """直接返回API数据，不做额外计算"""
        # 只保留API返回的原始数据
        report = {
            "score": detection_result.get("score", 0),
            "detection_mode": mode,
            "api_source": detection_result.get("source", "sapling"),
        }
        
        # 如果有句子分数，直接传递
        if "sentence_scores" in detection_result:
            report["sentence_scores"] = detection_result["sentence_scores"]
        
        # 如果有token信息，也传递
        if "tokens" in detection_result:
            report["tokens"] = detection_result["tokens"]
        if "token_probs" in detection_result:
            report["token_probs"] = detection_result["token_probs"]
        
        return report
    
    def _format_detection_result(self, report: Dict, text: str) -> ToolResult:
        """格式化检测结果 - 只显示原始API数据"""
        ai_score = report.get("score", 0)
        ai_percentage = round(ai_score * 100, 1)
        
        # 简化的Markdown报告 - 只显示API返回的数据
        markdown_report = f"""# AI Content Detection Report

## Detection Results
- **Score**: {ai_score:.4f} (closer to 0 = human, closer to 1 = AI)
- **AI Probability**: {ai_percentage}%
- **Mode**: {report.get('detection_mode', 'N/A')}
- **Source**: {report.get('api_source', 'sapling')}
"""
        
        # 如果有句子分数，直接显示（不排序，保持原始顺序）
        if "sentence_scores" in report and report["sentence_scores"]:
            sentences = report["sentence_scores"]
            markdown_report += f"\n## Sentence-Level Analysis\n"
            markdown_report += "*Note: Sentence scores use different detection method from overall score*\n\n"
            # 只显示前3个，保持API返回的原始顺序
            for i, sent in enumerate(sentences[:3], 1):
                score = sent.get("score", 0)
                sentence_text = sent.get("sentence", "")[:100]
                markdown_report += f"{i}. Score: {score:.4f} - {sentence_text}...\n"
        
        # 构建LLM友好的结构化数据 - 直接传递原始数据
        llm_content = {
            "score": ai_score,
            "detection_mode": report.get('detection_mode'),
            "api_source": report.get('api_source'),
            "sentence_scores": report.get('sentence_scores', []) if 'sentence_scores' in report else [],
            "interpretation_note": "Overall score and sentence scores use different methods. Low overall with high sentence scores may indicate human text with formulaic expressions."
        }
        
        # 简洁的摘要
        summary = f"AI Detection Score: {ai_score:.4f} ({ai_percentage}%)"
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display=markdown_report
        )