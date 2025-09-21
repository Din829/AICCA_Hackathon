"""
Deepfake检测工具 - 检测面部替换、语音克隆等深度伪造内容
Deepfake Detection - 使用多种技术检测深度伪造内容
"""

import asyncio
import os
import json
from typing import Dict, Any, Optional, Union, Callable, List
from pathlib import Path
import hashlib
from datetime import datetime
import tempfile
import uuid

# 使用成熟的dbrheo接口
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
from dbrheo.tools.base import DatabaseTool, DatabaseConfirmationDetails
from dbrheo.config.base import DatabaseConfig
from dbrheo.utils.debug_logger import log_info


class DeepfakeDetector(DatabaseTool):
    """
    Deepfake检测工具
    专门检测面部替换、语音克隆、身体替换等深度伪造技术
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self._i18n = i18n
        super().__init__(
            name="deepfake_detector",
            display_name=self._('deepfake_name', default="Deepfake Detector") if i18n else "Deepfake Detector",
            description="Deepfake and face swap specialist. Focuses on detecting facial manipulation, face replacement, and voice cloning. For images: detects face swaps only. For videos: supports both facial and general AI detection. For audio: detects voice synthesis. Use image_verify for general AI image detection.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "media_path": {
                        "type": "string",
                        "description": "Path or URL to media file (image/video/audio)"
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["image", "video", "audio", "auto"],
                        "description": "Media type (auto-detect if not specified)",
                        "default": "auto"
                    },
                    "detection_focus": {
                        "type": "string",
                        "enum": ["auto", "facial", "general", "comprehensive"],
                        "description": "Detection focus: facial=face manipulation, general=AI content, comprehensive=both, auto=intelligent selection",
                        "default": "auto"
                    },
                    "analysis_depth": {
                        "type": "string",
                        "enum": ["quick", "standard", "forensic"],
                        "description": "Analysis depth: quick=fast scan, standard=balanced, forensic=detailed",
                        "default": "standard"
                    },
                    "check_metadata": {
                        "type": "boolean",
                        "description": "Check for suspicious metadata and encoder signatures",
                        "default": True
                    },
                    "biological_analysis": {
                        "type": "boolean",
                        "description": "Analyze biological features (eye blink, facial symmetry)",
                        "default": True
                    }
                },
                "required": ["media_path"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
        
        # API配置
        self.api_config = self._initialize_api_config()
        
        # 支持的媒体格式
        self.supported_formats = {
            'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
            'video': {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'},
            'audio': {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
        }
        
        # 检查ffmpeg可用性
        self.ffmpeg_available = self._check_ffmpeg_availability()
    
    def _initialize_api_config(self) -> Dict[str, Any]:
        """初始化API配置"""
        config = {}
        
        # Sightengine配置（与image_verify_tool共用凭证）
        # 清理环境变量中的换行符和空白字符（部署环境Secret Manager问题修复）
        api_user = os.environ.get("SIGHTENGINE_API_USER") or self.config.get("sightengine_api_user")
        api_secret = os.environ.get("SIGHTENGINE_API_SECRET") or self.config.get("sightengine_api_secret")

        config["sightengine"] = {
            "enabled": self.config.get("sightengine_enabled", True),  # 使用相同的配置键
            "api_user": api_user.strip() if api_user else None,
            "api_secret": api_secret.strip() if api_secret else None,
            "endpoint": "https://api.sightengine.com/1.0/check.json",  # 图像端点
            "video_sync_endpoint": "https://api.sightengine.com/1.0/video/check-sync.json",  # 同步视频端点（<=1分钟）
            "video_async_endpoint": "https://api.sightengine.com/1.0/video/check.json"  # 异步视频端点（>1分钟）
        }
        
        # Resemble AI配置（用于音频deepfake检测）
        config["resemble"] = {
            "enabled": self.config.get("deepfake_resemble_enabled", False),
            "api_key": os.environ.get("RESEMBLE_API_KEY") or self.config.get("resemble_api_key"),
            "endpoint": "https://api.resemble.ai/v1/detect"
        }
        
        # 本地分析配置（简化）
        config["local_analysis"] = {
            "enabled": True,
            "temporal_analysis": True,
            "face_landmarks": True
        }
        
        return config
    
    def _check_ffmpeg_availability(self) -> bool:
        """检查ffmpeg是否可用"""
        import subprocess
        import platform
        
        log_info("DeepfakeDetector", f"[DEBUG] Checking FFmpeg availability on {platform.system()}")
        
        # Windows特定的常见FFmpeg路径
        windows_ffmpeg_paths = [
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe"
        ]
        
        # 首先尝试直接调用ffmpeg（如果在PATH中）
        try:
            log_info("DeepfakeDetector", "[DEBUG] Trying to run 'ffmpeg -version' from PATH")
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=2
            )
            log_info("DeepfakeDetector", f"[DEBUG] ffmpeg from PATH returncode: {result.returncode}")
            if result.returncode == 0:
                log_info("DeepfakeDetector", f"[DEBUG] ffmpeg output: {result.stdout[:100]}")
                log_info("DeepfakeDetector", "✓ ffmpeg is available in PATH")
                self.ffmpeg_command = 'ffmpeg'
                return True
        except Exception as e:
            log_info("DeepfakeDetector", f"[DEBUG] Failed to run ffmpeg from PATH: {e}")
        
        # Windows系统：尝试常见路径
        if platform.system() == 'Windows':
            log_info("DeepfakeDetector", "[DEBUG] Windows detected, checking common FFmpeg paths")
            for ffmpeg_path in windows_ffmpeg_paths:
                log_info("DeepfakeDetector", f"[DEBUG] Checking: {ffmpeg_path}")
                if os.path.exists(ffmpeg_path):
                    try:
                        log_info("DeepfakeDetector", f"[DEBUG] File exists, testing: {ffmpeg_path}")
                        result = subprocess.run(
                            [ffmpeg_path, '-version'],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        log_info("DeepfakeDetector", f"[DEBUG] {ffmpeg_path} returncode: {result.returncode}")
                        if result.returncode == 0:
                            log_info("DeepfakeDetector", f"✓ ffmpeg found at: {ffmpeg_path}")
                            self.ffmpeg_command = ffmpeg_path
                            return True
                    except Exception as e:
                        log_info("DeepfakeDetector", f"[DEBUG] Failed to run {ffmpeg_path}: {e}")
                else:
                    log_info("DeepfakeDetector", f"[DEBUG] Not found: {ffmpeg_path}")
        
        log_info("DeepfakeDetector", "✗ ffmpeg not found - video analysis will be limited")
        self.ffmpeg_command = 'ffmpeg'  # 默认值
        return False
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        params = self._normalize_params(params)
        
        media_path = params.get("media_path", "")
        if not media_path:
            return "Media path cannot be empty"
        
        # 检查文件是否存在（本地文件）
        if not media_path.startswith(('http://', 'https://')):
            path = Path(media_path)
            if not path.exists():
                return f"File not found: {media_path}"
            
            # 检查文件类型
            valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov', '.mp3', '.wav', '.m4a'}
            if path.suffix.lower() not in valid_extensions:
                return f"Unsupported media format: {path.suffix}. Supported: {', '.join(valid_extensions)}"
        
        return None
    
    def _determine_video_model(self, detection_focus: str, video_path: str) -> str:
        """智能决定使用哪个模型进行视频分析"""
        # 完全由Agent通过detection_focus参数控制，无任何关键词匹配
        # Agent会根据用户需求智能选择合适的模型
        
        if detection_focus == "facial":
            # Agent明确选择了面部检测（用户明确提到人脸相关）
            return "deepfake"
        elif detection_focus == "general":
            # Agent选择了通用AI检测（默认选择）
            return "genai"
        elif detection_focus == "comprehensive":
            # Agent选择了全面检测（需要两种检测）
            return "comprehensive"
        elif detection_focus == "auto":
            # auto模式：默认使用genai（通用AI检测）
            # 因为genai可以检测所有类型的AI生成内容
            # 只有用户明确提到人脸时Agent才会选择facial
            return "genai"  # 默认genai，检测所有AI生成内容
        else:
            return "genai"  # 未知情况也默认genai
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        media_path = params.get("media_path", "")
        media_type = params.get("media_type", "auto")
        analysis_depth = params.get("analysis_depth", "standard")
        
        # 获取文件名，限制长度
        if media_path.startswith('file:'):
            filename = f"uploaded_{media_path[5:][:8]}"
        elif media_path.startswith(('http://', 'https://')):
            filename = media_path.split('/')[-1].split('?')[0][:50]
        else:
            filename = Path(media_path).name
        
        return f"Performing {analysis_depth} deepfake detection: {filename}"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认"""
        # Deepfake检测通常不需要确认
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行Deepfake检测"""
        params = self._normalize_params(params)
        
        media_path = params.get("media_path", "")
        media_type = params.get("media_type", "auto")
        analysis_depth = params.get("analysis_depth", "standard")
        
        try:
            # 准备媒体文件
            if update_output:
                update_output("Loading media file...")
            
            # 确定媒体类型
            if media_type == "auto":
                media_type = self._detect_media_type(media_path)
            
            if update_output:
                update_output(f"Analyzing {media_type} for deepfakes (depth: {analysis_depth})...")
            
            results = {}
            
            # 根据媒体类型选择检测策略
            if media_type == "image":
                # 图像deepfake检测
                results = await self._detect_image_deepfake(
                    media_path, analysis_depth, 
                    params.get("check_metadata", True),
                    params.get("biological_analysis", True),
                    update_output
                )
            
            elif media_type == "video":
                # 视频deepfake检测
                results = await self._detect_video_deepfake(
                    media_path, analysis_depth,
                    params.get("detection_focus", "auto"),
                    params.get("check_metadata", True),
                    update_output
                )
            
            elif media_type == "audio":
                # 音频deepfake检测
                results = await self._detect_audio_deepfake(
                    media_path, analysis_depth,
                    update_output
                )
            
            else:
                return ToolResult(
                    error="Unsupported media type",
                    llm_content={"error": f"Unsupported media type: {media_type}"},
                    return_display=f"Unsupported media type: {media_type}"
                )
            
            # 生成分析报告
            report = self._generate_report(results, media_type, analysis_depth)
            
            # 生成摘要
            summary = self._generate_summary(results, media_type)
            
            return ToolResult(
                summary=summary,
                llm_content=results,
                return_display=report
            )
            
        except Exception as e:
            error_msg = f"Deepfake detection failed: {str(e)}"
            log_info("DeepfakeDetector", f"Error: {e}")
            return ToolResult(
                error=error_msg,
                llm_content={"error": str(e)},
                return_display=f"[ERROR] {error_msg}"
            )
    
    def _detect_media_type(self, media_path: str) -> str:
        """自动检测媒体类型"""
        if media_path.startswith(('http://', 'https://')):
            # URL - 从扩展名推断
            ext = '.' + media_path.split('.')[-1].lower().split('?')[0]
        elif media_path.startswith('file:'):
            # 对于file:ID格式，尝试从file_storage获取原始文件名
            try:
                # 尝试多种方式导入file_storage
                try:
                    from packages.api.aicca_api import file_storage
                except ImportError:
                    try:
                        from api.aicca_api import file_storage
                    except ImportError:
                        import sys
                        import os
                        # 添加项目根目录到路径
                        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                        sys.path.insert(0, os.path.join(root_dir, 'api'))
                        from aicca_api import file_storage
                file_id = media_path[5:]  # 去掉'file:'前缀
                file_info = file_storage.get_file_info(file_id)
                if file_info and file_info.get('original_name'):
                    # 从原始文件名获取扩展名
                    ext = Path(file_info['original_name']).suffix.lower()
                    log_info("DeepfakeDetector", f"Detected extension from original_name: {ext}")
                else:
                    # 如果没有原始文件名，尝试从content_type推断
                    if file_info and file_info.get('content_type'):
                        content_type = file_info['content_type']
                        if 'video' in content_type:
                            ext = '.mp4'
                        elif 'image' in content_type:
                            ext = '.jpg'
                        elif 'audio' in content_type:
                            ext = '.mp3'
                        else:
                            ext = '.jpg'  # 默认
                    else:
                        ext = '.jpg'  # 默认
            except Exception as e:
                log_info("DeepfakeDetector", f"Failed to get file info for media type detection: {e}")
                ext = '.jpg'  # 出错时默认为图像
        else:
            ext = Path(media_path).suffix.lower()
        
        for media_type, extensions in self.supported_formats.items():
            if ext in extensions:
                return media_type
        
        return "image"  # 默认
    
    async def _detect_image_deepfake(
        self, 
        image_path: str, 
        analysis_depth: str,
        check_metadata: bool,
        biological_analysis: bool,
        update_output: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """检测图像deepfake"""
        results = {"media_type": "image"}
        
        # 1. Sightengine API检测
        if self.api_config["sightengine"]["enabled"]:
            if update_output:
                update_output("Analyzing with Sightengine deepfake detector...")
            
            sightengine_result = await self._call_sightengine_image_api(image_path)
            results["sightengine_analysis"] = sightengine_result
        
        # 2. 本地分析（如果启用）
        if self.api_config["local_analysis"]["enabled"] and analysis_depth != "quick":
            if update_output:
                update_output("Performing local forensic analysis...")
            
            local_result = await self._local_image_analysis(image_path, check_metadata)
            results["local_analysis"] = local_result
        
        # 3. 生物特征分析（如果启用且是深度分析）
        if biological_analysis and analysis_depth == "forensic":
            if update_output:
                update_output("Analyzing biological features...")
            
            bio_result = await self._biological_feature_analysis(image_path)
            results["biological_analysis"] = bio_result
        
        return results
    
    async def _detect_video_deepfake(
        self,
        video_path: str,
        analysis_depth: str,
        detection_focus: str,
        check_metadata: bool,
        update_output: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """检测视频deepfake - 支持facial和general两种模式"""
        results = {"media_type": "video"}
        
        # 1. Sightengine视频检测
        if self.api_config["sightengine"]["enabled"]:
            if update_output:
                ffmpeg_status = "available" if self.ffmpeg_available else "not available"
                update_output(f"Analyzing video (ffmpeg: {ffmpeg_status})...")
            
            # 决定使用哪个模型
            use_model = self._determine_video_model(detection_focus, video_path)
            log_info("DeepfakeDetector", f"Using model: {use_model} for video analysis")
            
            # 根据模型选择不同的处理策略
            if use_model == "deepfake":
                # 使用deepfake模型（面部检测）- 支持同步API
                video_duration = await self._get_video_duration(video_path)
                
                if video_duration and video_duration <= 60:
                    # 短视频：使用同步API (check-sync.json)
                    if update_output:
                        update_output(f"Using sync API for {video_duration}s video (facial detection)...")
                    video_result = await self._call_video_sync_api(video_path, model="deepfake")
                else:
                    # 长视频：检查是否有callback_url
                    callback_url = self.config.get("sightengine_callback_url")
                    if callback_url:
                        # 有callback：使用异步API
                        if update_output:
                            update_output("Using async API with callback (facial detection)...")
                        video_result = await self._call_video_async_api(video_path, callback_url, model="deepfake")
                    else:
                        # 无callback：降级到关键帧分析
                        if update_output:
                            update_output("No callback URL, using keyframe analysis (facial detection)...")
                        video_result = await self._analyze_video_keyframes_with_model(video_path, model="deepfake")
            
            elif use_model == "genai":
                # 使用genai模型（通用AI检测）- 只能通过关键帧分析
                if update_output:
                    update_output("Using frame extraction for general AI detection...")
                video_result = await self._analyze_video_keyframes_with_model(video_path, model="genai")
            
            elif use_model == "comprehensive":
                # 综合检测：同时使用两个模型
                if update_output:
                    update_output("Performing comprehensive analysis (facial + general AI)...")
                
                # 先做deepfake检测
                deepfake_result = await self._analyze_video_keyframes_with_model(video_path, model="deepfake")
                # 再做genai检测
                genai_result = await self._analyze_video_keyframes_with_model(video_path, model="genai")
                
                video_result = {
                    "comprehensive_mode": True,
                    "facial_analysis": deepfake_result,
                    "general_ai_analysis": genai_result,
                    "combined_assessment": self._combine_assessments(deepfake_result, genai_result)
                }
            else:
                video_result = {"error": f"Unknown model: {use_model}"}
            
            results["video_analysis"] = video_result
            results["model_used"] = use_model
        
        # 2. 时序一致性分析
        if self.api_config["local_analysis"]["temporal_analysis"] and analysis_depth != "quick":
            if update_output:
                update_output("Analyzing temporal consistency...")
            
            temporal_result = await self._temporal_consistency_analysis(video_path)
            results["temporal_analysis"] = temporal_result
        
        # 3. 元数据检查
        if check_metadata:
            log_info("DeepfakeDetector", f"[DEBUG] Metadata check enabled: {check_metadata}")
            if update_output:
                update_output("Checking video metadata...")
            
            metadata_result = await self._check_video_metadata(video_path)
            log_info("DeepfakeDetector", f"[DEBUG] Metadata result status: {metadata_result.get('status', 'unknown')}")
            results["metadata_analysis"] = metadata_result
        else:
            log_info("DeepfakeDetector", f"[DEBUG] Metadata check disabled: check_metadata={check_metadata}")
        
        return results
    
    async def _detect_audio_deepfake(
        self,
        audio_path: str,
        analysis_depth: str,
        update_output: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """检测音频deepfake"""
        results = {
            "media_type": "audio",
            "note": "Audio deepfake detection is limited. Consider using specialized audio analysis tools.",
            "alternatives": ["Resemble AI", "Pindrop", "Deepware Scanner"]
        }
        
        # Resemble AI检测（如果配置）
        if self.api_config["resemble"]["enabled"] and self.api_config["resemble"]["api_key"]:
            if update_output:
                update_output("Analyzing with Resemble AI...")
            
            resemble_result = await self._call_resemble_api(audio_path)
            results["resemble_analysis"] = resemble_result
        else:
            # 基础分析
            if update_output:
                update_output("Performing basic audio analysis...")
            
            basic_result = await self._basic_audio_analysis(audio_path)
            results["basic_analysis"] = basic_result
        
        return results
    
    async def _call_sightengine_image_api(self, image_path: str) -> Dict[str, Any]:
        """调用Sightengine图像deepfake检测API"""
        try:
            import urllib.request
            import urllib.parse
            import urllib.error

            api_user = self.api_config["sightengine"]["api_user"]
            api_secret = self.api_config["sightengine"]["api_secret"]

            # 添加详细的API调试日志
            log_info("DeepfakeDetector", f"🔑 API Credentials Check:")
            log_info("DeepfakeDetector", f"  - User: {api_user[:3] if api_user else 'None'}...{api_user[-3:] if api_user and len(api_user) > 6 else ''}")
            log_info("DeepfakeDetector", f"  - Secret: {api_secret[:3] if api_secret else 'None'}...{api_secret[-3:] if api_secret and len(api_secret) > 6 else ''}")
            log_info("DeepfakeDetector", f"  - Endpoint: {self.api_config['sightengine']['endpoint']}")

            if not api_user or not api_secret:
                log_info("DeepfakeDetector", "Sightengine API credentials not configured")
                return {
                    "error": "Sightengine API credentials not configured",
                    "help": "Set SIGHTENGINE_API_USER and SIGHTENGINE_API_SECRET environment variables"
                }
            
            # 处理file:ID格式
            actual_path = image_path
            if image_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(image_path)
                    log_info("DeepfakeDetector", f"Resolved file:ID to {actual_path}")
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed: {e}, using fallback")
                    actual_path = image_path[5:]  # 降级处理
            
            # 构建请求参数
            params = {
                'models': 'deepfake',  # 使用deepfake模型而不是genai
                'api_user': api_user,
                'api_secret': api_secret
            }
            
            # 根据输入类型选择参数
            if actual_path.startswith(('http://', 'https://')):
                params['url'] = actual_path

                # 添加请求调试日志
                log_info("DeepfakeDetector", f"📤 Sending URL request to Sightengine:")
                log_info("DeepfakeDetector", f"  - URL: {actual_path}")
                log_info("DeepfakeDetector", f"  - Params: {params}")

                # URL方式
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(
                    self.api_config["sightengine"]["endpoint"],
                    data=data
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode())
                    log_info("DeepfakeDetector", f"📥 Received response: {result}")
            else:
                # 本地文件需要上传
                log_info("DeepfakeDetector", f"📤 Sending file upload request to Sightengine:")
                log_info("DeepfakeDetector", f"  - File: {actual_path}")
                log_info("DeepfakeDetector", f"  - Params: {params}")

                import requests
                with open(actual_path, 'rb') as f:
                    files = {'media': f}
                    response = requests.post(
                        self.api_config["sightengine"]["endpoint"],
                        files=files,
                        data=params,
                        timeout=self.api_config["sightengine"].get("timeout", 30)
                    )
                    result = response.json()
                    log_info("DeepfakeDetector", f"📥 Received response: {result}")
            
            # 提取deepfake分数
            if "type" in result and "deepfake" in result["type"]:
                log_info("DeepfakeDetector", f"Sightengine deepfake score: {result['type']['deepfake']}")
                return {
                    "deepfake_score": result["type"]["deepfake"],
                    "status": result.get("status", "unknown"),
                    "operations": result.get("request", {}).get("operations", 1)
                }
            elif "error" in result:
                log_info("DeepfakeDetector", f"Sightengine API error: {result.get('error', {}).get('message', 'Unknown')}")
                return {
                    "error": result.get("error", {}).get("message", "API error"),
                    "code": result.get("error", {}).get("code")
                }
            else:
                return result  # 返回原始结果
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            log_info("DeepfakeDetector", f"HTTP Error {e.code}: {error_body}")
            
            # 解析错误响应
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get("error", {}).get("message", f"HTTP {e.code}")
            except:
                error_msg = f"HTTP Error {e.code}: {e.reason}"
            
            return {
                "error": error_msg,
                "http_code": e.code,
                "url": image_path if image_path.startswith(('http://', 'https://')) else "local_file"
            }
        except Exception as e:
            log_info("DeepfakeDetector", f"Sightengine API exception: {e}")
            return {
                "error": f"Sightengine API error: {str(e)}",
                "exception_type": type(e).__name__
            }
    
    async def _get_video_duration(self, video_path: str) -> Optional[float]:
        """获取视频时长（秒）- 使用ffmpeg/ffprobe"""
        try:
            import subprocess
            import json as json_module
            
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in get_video_duration: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            # 对于URL，使用ffprobe获取时长
            if actual_path.startswith(('http://', 'https://')):
                # ffprobe可以直接分析URL
                ffprobe_cmd = getattr(self, 'ffmpeg_command', 'ffmpeg').replace('ffmpeg', 'ffprobe')
                cmd = [
                    ffprobe_cmd,
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    video_path
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10  # URL可能需要更长时间
                    )
                    
                    if result.returncode == 0:
                        data = json_module.loads(result.stdout)
                        # 从format中获取时长
                        if 'format' in data and 'duration' in data['format']:
                            duration = float(data['format']['duration'])
                            log_info("DeepfakeDetector", f"Video duration (URL): {duration:.2f}s")
                            return duration
                    else:
                        log_info("DeepfakeDetector", f"ffprobe failed for URL: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    log_info("DeepfakeDetector", "ffprobe timeout for URL")
                except FileNotFoundError:
                    log_info("DeepfakeDetector", "ffprobe not found, please install ffmpeg")
                except Exception as e:
                    log_info("DeepfakeDetector", f"ffprobe error for URL: {e}")
            
            # 对于本地文件，优先使用ffprobe
            else:
                # 方法1: 使用ffprobe（最准确）
                ffprobe_cmd = getattr(self, 'ffmpeg_command', 'ffmpeg').replace('ffmpeg', 'ffprobe')
                cmd = [
                    ffprobe_cmd,
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    video_path
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        data = json_module.loads(result.stdout)
                        if 'format' in data and 'duration' in data['format']:
                            duration = float(data['format']['duration'])
                            log_info("DeepfakeDetector", f"Video duration (local): {duration:.2f}s")
                            return duration
                            
                except FileNotFoundError:
                    # ffprobe不存在，尝试ffmpeg
                    log_info("DeepfakeDetector", "ffprobe not found, trying ffmpeg")
                    
                    # 方法2: 使用ffmpeg -i
                    ffmpeg_cmd = getattr(self, 'ffmpeg_command', 'ffmpeg')
                    cmd = [ffmpeg_cmd, '-i', actual_path, '-f', 'null', '-']
                    
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        # 从stderr中解析Duration
                        import re
                        duration_match = re.search(
                            r'Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)',
                            result.stderr
                        )
                        
                        if duration_match:
                            hours = int(duration_match.group(1))
                            minutes = int(duration_match.group(2))
                            seconds = float(duration_match.group(3))
                            duration = hours * 3600 + minutes * 60 + seconds
                            log_info("DeepfakeDetector", f"Video duration via ffmpeg: {duration:.2f}s")
                            return duration
                            
                    except FileNotFoundError:
                        log_info("DeepfakeDetector", "Neither ffprobe nor ffmpeg found")
                        
                        # 方法3: 最后尝试OpenCV（如果安装了）
                        try:
                            import cv2
                            cap = cv2.VideoCapture(actual_path)
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                            cap.release()
                            if fps > 0 and frame_count > 0:
                                duration = frame_count / fps
                                log_info("DeepfakeDetector", f"Video duration via OpenCV: {duration:.2f}s")
                                return duration
                        except ImportError:
                            log_info("DeepfakeDetector", "OpenCV not installed")
                
                except Exception as e:
                    log_info("DeepfakeDetector", f"Error in duration detection: {e}")
            
            # 无法确定时长
            log_info("DeepfakeDetector", "Could not determine video duration")
            return None
            
        except Exception as e:
            log_info("DeepfakeDetector", f"Error getting video duration: {e}")
            return None
    
    async def _analyze_video_keyframes_with_model(self, video_path: str, model: str = "deepfake") -> Dict[str, Any]:
        """分析视频关键帧 - 支持不同模型"""
        try:
            import subprocess
            import tempfile
            from pathlib import Path as PathLib
            
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in keyframes: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            # 创建临时目录存储提取的帧
            with tempfile.TemporaryDirectory() as temp_dir:
                # 获取视频时长
                duration = await self._get_video_duration(video_path)  # 这个方法内部已处理file:ID
                
                # 对于genai检测，减少帧数以节省API调用
                if model == "genai":
                    max_frames = 5  # genai检测最多5帧
                    interval = max(3, int(duration / 5)) if duration else 5
                else:
                    max_frames = 10  # deepfake检测最多10帧
                    interval = max(1, int(duration / 10)) if duration else 3
                
                log_info("DeepfakeDetector", f"Extracting max {max_frames} frames for {model} analysis")
                
                # 使用ffmpeg提取关键帧
                output_pattern = str(PathLib(temp_dir) / "frame_%03d.jpg")
                
                cmd = [
                    'ffmpeg',
                    '-i', actual_path,
                    '-vf', f'fps=1/{interval}',
                    '-frames:v', str(max_frames),
                    '-q:v', '2',
                    output_pattern,
                    '-y'
                ]
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode != 0:
                        # 尝试简单提取
                        cmd_simple = [
                            ffmpeg_cmd,
                            '-i', actual_path,
                            '-frames:v', '3',  # 至少提取3帧
                            str(PathLib(temp_dir) / "frame_%03d.jpg"),
                            '-y'
                        ]
                        result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=10)
                        
                        if result.returncode != 0:
                            return {"error": "Failed to extract frames"}
                
                except subprocess.TimeoutExpired:
                    return {"error": "Frame extraction timeout"}
                except FileNotFoundError:
                    return {"error": "ffmpeg not found"}
                
                # 分析提取的帧
                frame_files = sorted(PathLib(temp_dir).glob("frame_*.jpg"))
                
                if not frame_files:
                    return {"error": "No frames extracted"}
                
                log_info("DeepfakeDetector", f"Analyzing {len(frame_files)} frames with {model} model")
                
                # 分析每帧
                frame_results = []
                api_user = self.api_config["sightengine"]["api_user"]
                api_secret = self.api_config["sightengine"]["api_secret"]
                
                if not api_user or not api_secret:
                    return {"error": "API credentials not configured"}
                
                for i, frame_file in enumerate(frame_files[:max_frames]):
                    # 调用对应模型的API
                    if model == "genai":
                        result = await self._call_sightengine_genai_api(str(frame_file))
                    else:
                        result = await self._call_sightengine_image_api(str(frame_file))
                    
                    if model == "genai" and "ai_generated_score" in result:
                        frame_results.append({
                            "frame": i + 1,
                            "timestamp": i * interval,
                            "ai_generated_score": result["ai_generated_score"]
                        })
                    elif model == "deepfake" and "deepfake_score" in result:
                        frame_results.append({
                            "frame": i + 1,
                            "timestamp": i * interval,
                            "deepfake_score": result["deepfake_score"]
                        })
                
                # 计算统计
                if frame_results:
                    if model == "genai":
                        scores = [f["ai_generated_score"] for f in frame_results]
                        return {
                            "method": "keyframe_extraction",
                            "model": "genai",
                            "frames_analyzed": len(frame_results),
                            "average_ai_score": sum(scores) / len(scores),
                            "max_ai_score": max(scores),
                            "min_ai_score": min(scores),
                            "frame_details": frame_results,
                            "note": "Analyzed for general AI-generated content"
                        }
                    else:
                        scores = [f["deepfake_score"] for f in frame_results]
                        return {
                            "method": "keyframe_extraction",
                            "model": "deepfake",
                            "frames_analyzed": len(frame_results),
                            "average_deepfake_score": sum(scores) / len(scores),
                            "max_deepfake_score": max(scores),
                            "min_deepfake_score": min(scores),
                            "frame_details": frame_results,
                            "note": "Analyzed for facial manipulation"
                        }
                else:
                    return {"error": "No valid results from frame analysis"}
            
        except Exception as e:
            return {"error": f"Frame analysis error: {str(e)}"}
    
    async def _call_sightengine_genai_api(self, image_path: str) -> Dict[str, Any]:
        """调用Sightengine的genai模型检测AI生成内容"""
        try:
            import urllib.request
            import urllib.parse
            import urllib.error
            
            api_user = self.api_config["sightengine"]["api_user"]
            api_secret = self.api_config["sightengine"]["api_secret"]
            
            if not api_user or not api_secret:
                return {"error": "API credentials not configured"}
            
            # 处理file:ID格式
            actual_path = image_path
            if image_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(image_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in genai_api: {e}")
                    actual_path = image_path[5:]  # 降级处理
            
            # 使用genai模型而不是deepfake
            params = {
                'models': 'genai',  # AI生成内容检测
                'api_user': api_user,
                'api_secret': api_secret
            }
            
            if actual_path.startswith(('http://', 'https://')):
                params['url'] = actual_path
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(
                    self.api_config["sightengine"]["endpoint"],
                    data=data
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode())
            else:
                # 本地文件
                import requests
                with open(actual_path, 'rb') as f:
                    files = {'media': f}
                    response = requests.post(
                        self.api_config["sightengine"]["endpoint"],
                        files=files,
                        data=params,
                        timeout=30
                    )
                    result = response.json()
            
            # 提取AI生成分数
            if "type" in result and "ai_generated" in result["type"]:
                return {
                    "ai_generated_score": result["type"]["ai_generated"],
                    "status": result.get("status", "unknown")
                }
            else:
                return result
                
        except Exception as e:
            return {"error": f"GenAI API error: {str(e)}"}
    
    def _combine_assessments(self, deepfake_result: Dict, genai_result: Dict) -> Dict[str, Any]:
        """组合两个模型的评估结果"""
        combined = {
            "facial_manipulation": False,
            "ai_generated": False,
            "overall_risk": "low"
        }
        
        # 检查deepfake结果
        if deepfake_result and "average_deepfake_score" in deepfake_result:
            if deepfake_result["average_deepfake_score"] > 0.5:
                combined["facial_manipulation"] = True
        
        # 检查genai结果
        if genai_result and "average_ai_score" in genai_result:
            if genai_result["average_ai_score"] > 0.5:
                combined["ai_generated"] = True
        
        # 计算整体风险
        if combined["facial_manipulation"] and combined["ai_generated"]:
            combined["overall_risk"] = "high"
        elif combined["facial_manipulation"] or combined["ai_generated"]:
            combined["overall_risk"] = "medium"
        else:
            combined["overall_risk"] = "low"
        
        return combined
    
    async def _call_video_sync_api(self, video_path: str, model: str = "deepfake") -> Dict[str, Any]:
        """调用Sightengine同步视频API（1分钟内视频）"""
        try:
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in call_video_sync_api: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            api_user = self.api_config["sightengine"]["api_user"]
            api_secret = self.api_config["sightengine"]["api_secret"]
            
            if not api_user or not api_secret:
                return {
                    "error": "Sightengine API credentials not configured",
                    "note": "Set SIGHTENGINE_API_USER and SIGHTENGINE_API_SECRET"
                }
            
            # 同步API端点（根据官方文档）
            sync_endpoint = "https://api.sightengine.com/1.0/video/check-sync.json"
            
            if video_path.startswith(('http://', 'https://')):
                # URL方式
                import urllib.request
                import urllib.parse
                import urllib.error
                
                params = {
                    'stream_url': video_path,  # 视频URL
                    'models': model,            # 使用指定的模型
                    'api_user': api_user,
                    'api_secret': api_secret
                }
                
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(sync_endpoint, data=data)
                
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        result = json.loads(response.read().decode())
                    
                    # 可选：记录原始响应以便调试
                    # log_info("DeepfakeDetector", f"Sync API raw response: {json.dumps(result)[:500]}")
                    
                    # 解析结果
                    return self._parse_video_sync_result(result)
                    
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode() if e.fp else ""
                    return {
                        "error": f"HTTP {e.code}: {e.reason}",
                        "details": error_body[:200]
                    }
            else:
                # 本地文件上传
                import requests
                
                with open(actual_path, 'rb') as f:
                    files = {'media': f}
                    data = {
                        'models': 'deepfake',
                        'api_user': api_user,
                        'api_secret': api_secret
                    }
                    
                    response = requests.post(
                        sync_endpoint,
                        files=files,
                        data=data,
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # log_info("DeepfakeDetector", f"Local file sync API response: {json.dumps(result)[:500]}")
                        return self._parse_video_sync_result(result)
                    else:
                        return {
                            "error": f"HTTP {response.status_code}",
                            "details": response.text[:200]
                        }
                        
        except Exception as e:
            log_info("DeepfakeDetector", f"Video sync API error: {e}")
            return {
                "error": f"Video sync API error: {str(e)}",
                "fallback": "Consider using keyframe analysis"
            }
    
    async def _call_video_async_api(self, video_path: str, callback_url: str) -> Dict[str, Any]:
        """调用Sightengine异步视频API（超过1分钟视频）"""
        try:
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in call_video_async_api: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            api_user = self.api_config["sightengine"]["api_user"]
            api_secret = self.api_config["sightengine"]["api_secret"]
            
            if not api_user or not api_secret:
                return {
                    "error": "API credentials not configured"
                }
            
            # 异步API端点
            async_endpoint = "https://api.sightengine.com/1.0/video/check.json"
            
            params = {
                'models': 'deepfake',
                'callback_url': callback_url,
                'api_user': api_user,
                'api_secret': api_secret
            }
            
            if actual_path.startswith(('http://', 'https://')):
                params['stream_url'] = actual_path
            else:
                # 需要上传文件
                return {
                    "note": "Async file upload requires implementation",
                    "media_id": "pending",
                    "callback_url": callback_url,
                    "status": "File upload for async processing not yet implemented"
                }
            
            import urllib.request
            import urllib.parse
            
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(async_endpoint, data=data)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            # 异步API返回media_id，结果会发送到callback
            return {
                "media_id": result.get("media", {}).get("id"),
                "status": "processing",
                "callback_url": callback_url,
                "note": "Results will be sent to callback URL when ready"
            }
            
        except Exception as e:
            log_info("DeepfakeDetector", f"Video async API error: {e}")
            return {
                "error": f"Async API error: {str(e)}"
            }
    
    def _parse_video_sync_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解析同步视频API结果 - 基于实际API响应结构"""
        try:
            # 实际API响应结构（根据curl测试）:
            # {
            #   "status": "success",
            #   "request": {...},
            #   "media": {...},
            #   "data": {
            #     "frames": [
            #       {
            #         "info": {"id": "...", "position": 0},
            #         "type": {"deepfake": 0.001}
            #       }
            #     ]
            #   }
            # }
            
            # 检查响应状态
            if result.get("status") != "success":
                return {
                    "status": result.get("status", "error"),
                    "error": result.get("error", {}).get("message", "Unknown error"),
                    "raw_result": result
                }
            
            # 获取frames数据 - 在data.frames中
            frames_data = []
            if "data" in result and "frames" in result["data"]:
                frames_data = result["data"]["frames"]
                log_info("DeepfakeDetector", f"Found {len(frames_data)} frames")
            
            # 解析每帧的deepfake分数
            deepfake_scores = []
            for i, frame in enumerate(frames_data):
                # 分数在 frame.type.deepfake
                if isinstance(frame, dict) and "type" in frame and "deepfake" in frame["type"]:
                    score = frame["type"]["deepfake"]
                    deepfake_scores.append(float(score))
                    
                    # 可选：记录详细信息
                    # position = frame.get("info", {}).get("position", i)
                    # log_info("DeepfakeDetector", f"Frame at {position}ms: deepfake score = {score}")
            
            # 计算统计数据
            if deepfake_scores:
                avg_score = sum(deepfake_scores) / len(deepfake_scores)
                max_score = max(deepfake_scores)
                min_score = min(deepfake_scores)
            else:
                avg_score = max_score = min_score = 0
                log_info("DeepfakeDetector", "No deepfake scores found in response")
            
            # 获取请求信息
            request_info = result.get("request", {})
            operations_used = request_info.get("operations", 0)
            
            return {
                "status": "success",
                "frames_analyzed": len(frames_data),
                "average_deepfake_score": avg_score,
                "max_deepfake_score": max_score,
                "min_deepfake_score": min_score,
                "frame_scores": deepfake_scores,
                "operations_used": operations_used,
                "media_id": result.get("media", {}).get("id"),
                "request_id": request_info.get("id")
            }
                
        except Exception as e:
            return {
                "error": f"Failed to parse result: {str(e)}",
                "raw_result": result
            }
    
    async def _analyze_video_keyframes(self, video_path: str) -> Dict[str, Any]:
        """分析视频关键帧进行deepfake检测（降级方案）- 使用ffmpeg提取关键帧"""
        try:
            import subprocess
            import tempfile
            from pathlib import Path as PathLib
            
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                    log_info("DeepfakeDetector", f"Resolved file:ID to {actual_path}")
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in analyze_keyframes: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            # 创建临时目录存储提取的帧
            with tempfile.TemporaryDirectory() as temp_dir:
                # 提取关键帧的策略：
                # 1. 提取I帧（关键帧）
                # 2. 每隔N秒提取一帧
                # 3. 限制最多分析10帧（API配额考虑）
                
                # 获取视频时长以计算采样间隔
                duration = await self._get_video_duration(video_path)
                
                if duration:
                    # 计算采样间隔（最多10帧）
                    interval = max(1, int(duration / 10))
                    log_info("DeepfakeDetector", f"Extracting frames every {interval}s from {duration:.2f}s video")
                else:
                    # 默认每5秒一帧
                    interval = 5
                    log_info("DeepfakeDetector", "Using default 5s interval for frame extraction")
                
                # 使用ffmpeg提取关键帧
                output_pattern = str(PathLib(temp_dir) / "frame_%03d.jpg")
                
                # ffmpeg命令：提取关键帧
                ffmpeg_cmd = getattr(self, 'ffmpeg_command', 'ffmpeg')
                cmd = [
                    ffmpeg_cmd,
                    '-i', actual_path,              # 输入文件
                    '-vf', f'fps=1/{interval}',    # 每N秒一帧
                    '-frames:v', '10',              # 最多10帧
                    '-q:v', '2',                    # 高质量JPEG
                    output_pattern,                 # 输出模式
                    '-y'                            # 覆盖文件
                ]
                
                # 如果是URL，ffmpeg可以直接处理
                log_info("DeepfakeDetector", f"Extracting keyframes from {'URL' if actual_path.startswith('http') else 'file'}")
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30  # 30秒超时
                    )
                    
                    if result.returncode != 0:
                        log_info("DeepfakeDetector", f"ffmpeg extraction failed: {result.stderr[:200]}")
                        
                        # 尝试备用方法：只提取第一帧
                        cmd_simple = [
                            ffmpeg_cmd,
                            '-i', actual_path,
                            '-frames:v', '1',
                            str(PathLib(temp_dir) / "frame_001.jpg"),
                            '-y'
                        ]
                        
                        result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=10)
                        
                        if result.returncode != 0:
                            return {
                                "error": "Failed to extract frames",
                                "details": result.stderr[:200],
                                "recommendation": "Check video format or URL accessibility"
                            }
                    
                except subprocess.TimeoutExpired:
                    return {
                        "error": "Frame extraction timeout",
                        "note": "Video might be too large or network too slow"
                    }
                except FileNotFoundError:
                    return {
                        "error": "ffmpeg not found",
                        "note": "Please install ffmpeg for video frame extraction",
                        "recommendation": "apt-get install ffmpeg or download from ffmpeg.org"
                    }
                
                # 分析提取的帧
                frame_files = sorted(PathLib(temp_dir).glob("frame_*.jpg"))
                
                if not frame_files:
                    return {
                        "error": "No frames extracted",
                        "note": "Video might be corrupted or empty"
                    }
                
                log_info("DeepfakeDetector", f"Extracted {len(frame_files)} frames for analysis")
                
                # 对每个帧进行deepfake检测
                frame_results = []
                api_user = self.api_config["sightengine"]["api_user"]
                api_secret = self.api_config["sightengine"]["api_secret"]
                
                if not api_user or not api_secret:
                    return {
                        "frames_extracted": len(frame_files),
                        "error": "API credentials not configured for frame analysis"
                    }
                
                for i, frame_file in enumerate(frame_files[:5]):  # 最多分析5帧以节省API调用
                    log_info("DeepfakeDetector", f"Analyzing frame {i+1}/{len(frame_files[:5])}")
                    
                    # 调用图像deepfake API
                    result = await self._call_sightengine_image_api(str(frame_file))
                    
                    if "deepfake_score" in result:
                        frame_results.append({
                            "frame": i + 1,
                            "timestamp": i * interval,
                            "deepfake_score": result["deepfake_score"]
                        })
                    else:
                        log_info("DeepfakeDetector", f"Frame {i+1} analysis failed: {result.get('error', 'Unknown')}")
                
                # 计算统计信息
                if frame_results:
                    scores = [f["deepfake_score"] for f in frame_results]
                    avg_score = sum(scores) / len(scores)
                    
                    return {
                        "method": "keyframe_extraction",
                        "frames_analyzed": len(frame_results),
                        "frames_extracted": len(frame_files),
                        "average_deepfake_score": avg_score,
                        "max_deepfake_score": max(scores),
                        "min_deepfake_score": min(scores),
                        "frame_details": frame_results,
                        "note": "Analyzed video keyframes instead of full video"
                    }
                else:
                    return {
                        "frames_extracted": len(frame_files),
                        "frames_analyzed": 0,
                        "error": "Failed to analyze extracted frames",
                        "note": "Frames were extracted but API analysis failed"
                    }
            
        except Exception as e:
            log_info("DeepfakeDetector", f"Keyframe analysis error: {e}")
            return {
                "error": f"Keyframe analysis error: {str(e)}",
                "fallback": "Unable to perform keyframe analysis"
            }
    
    async def _local_image_analysis(self, image_path: str, check_metadata: bool) -> Dict[str, Any]:
        """本地图像分析"""
        result = {}
        
        try:
            # 处理file:ID格式
            actual_path = image_path
            if image_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(image_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in local_analysis: {e}")
                    actual_path = image_path[5:]  # 降级处理
            
            # EXIF元数据检查
            if check_metadata and not actual_path.startswith(('http://', 'https://')):
                from PIL import Image
                from PIL.ExifTags import TAGS
                
                image = Image.open(actual_path)
                exifdata = image.getexif()
                
                if exifdata:
                    suspicious_indicators = []
                    
                    # 检查可疑的编辑软件
                    for tag_id, value in exifdata.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "Software":
                            value_str = str(value).lower()
                            if any(tool in value_str for tool in ['faceswap', 'deepface', 'gan', 'ai']):
                                suspicious_indicators.append(f"Suspicious software: {value}")
                    
                    result["metadata_check"] = {
                        "has_exif": True,
                        "suspicious_indicators": suspicious_indicators
                    }
                else:
                    result["metadata_check"] = {
                        "has_exif": False,
                        "note": "No EXIF data (could be stripped)"
                    }
            
            # 图像统计分析
            result["statistical_analysis"] = {
                "note": "Advanced forensic analysis requires specialized libraries"
            }
            
        except Exception as e:
            result["error"] = f"Local analysis error: {str(e)}"
        
        return result
    
    async def _biological_feature_analysis(self, image_path: str) -> Dict[str, Any]:
        """生物特征分析（眨眼、瞳孔反射等）"""
        # 处理file:ID格式
        actual_path = image_path
        if image_path.startswith('file:'):
            try:
                from aicca.utils.content_loader import ContentLoader
                loader = ContentLoader()
                actual_path, metadata = await loader.load_content(image_path)
            except Exception as e:
                log_info("DeepfakeDetector", f"ContentLoader failed in biological_analysis: {e}")
                actual_path = image_path[5:]  # 降级处理
        
        return {
            "note": "Biological feature analysis requires face_recognition and dlib libraries",
            "features_checked": ["eye_blinking", "pupil_reflection", "facial_symmetry"],
            "status": "not_implemented"
        }
    
    async def _temporal_consistency_analysis(self, video_path: str) -> Dict[str, Any]:
        """时序一致性分析"""
        try:
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in temporal: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            # 尝试使用OpenCV进行真实分析
            import cv2
            import numpy as np
            
            cap = cv2.VideoCapture(actual_path)
            if not cap.isOpened():
                raise Exception("Cannot open video")
            
            # 提取帧进行分析
            frames = []
            frame_count = 0
            max_frames = 10  # 限制分析帧数
            
            while len(frames) < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % 30 == 0:  # 每30帧采样一次
                    frames.append(frame)
                frame_count += 1
            
            cap.release()
            
            if len(frames) < 2:
                return {
                    "status": "insufficient_frames",
                    "frames_analyzed": len(frames)
                }
            
            # 计算帧间差异
            consistency_scores = []
            for i in range(1, len(frames)):
                diff = cv2.absdiff(frames[i], frames[i-1])
                score = np.mean(diff)
                consistency_scores.append(float(score))
            
            avg_consistency = np.mean(consistency_scores)
            
            return {
                "frames_analyzed": len(frames),
                "consistency_score": float(100 - min(avg_consistency, 100)),  # 转换为0-100分数
                "frame_differences": consistency_scores[:5],  # 返回前5个差异值
                "status": "analyzed"
            }
            
        except ImportError:
            # OpenCV未安装，返回简化版本
            return {
                "note": "Install opencv-python for advanced temporal analysis",
                "status": "opencv_not_available"
            }
        except Exception as e:
            # 其他错误，返回原始占位信息
            return {
                "note": "Temporal consistency analysis detects frame-to-frame inconsistencies",
                "metrics": ["facial_feature_drift", "lighting_consistency", "background_stability"],
                "status": "simplified_version",
                "error": str(e)
            }
    
    async def _check_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """检查视频元数据"""
        log_info("DeepfakeDetector", f"[DEBUG] Starting metadata check for: {video_path}")
        try:
            # 处理file:ID格式
            actual_path = video_path
            if video_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(video_path)
                    log_info("DeepfakeDetector", f"[DEBUG] Loaded file path: {actual_path}")
                except Exception as e:
                    log_info("DeepfakeDetector", f"[DEBUG] ContentLoader failed: {e}")
                    actual_path = video_path[5:]  # 降级处理
            
            # 尝试使用ffmpeg-python进行真实元数据分析
            log_info("DeepfakeDetector", "[DEBUG] Trying to import ffmpeg-python")
            import ffmpeg
            import json
            log_info("DeepfakeDetector", "[DEBUG] ffmpeg-python imported successfully")
            
            probe = ffmpeg.probe(actual_path)
            log_info("DeepfakeDetector", "[DEBUG] ffmpeg.probe() executed successfully")
            
            suspicious_indicators = []
            metadata_info = {}
            
            # 提取基本信息
            if 'format' in probe:
                format_info = probe['format']
                metadata_info['format'] = format_info.get('format_name', 'unknown')
                metadata_info['duration'] = float(format_info.get('duration', 0))
                metadata_info['bit_rate'] = format_info.get('bit_rate', 'unknown')
                
                # 检查编码器
                if 'tags' in format_info:
                    encoder = format_info['tags'].get('encoder', '')
                    metadata_info['encoder'] = encoder
                    
                    # 检查可疑编码器
                    suspicious_encoders = ['fakeapp', 'deepfacelab', 'faceswap', 'wombo', 'reface']
                    for sus in suspicious_encoders:
                        if sus in encoder.lower():
                            suspicious_indicators.append(f"Suspicious encoder: {encoder}")
                            break
                    
                    # 检查时间戳
                    creation_time = format_info['tags'].get('creation_time', '')
                    if creation_time:
                        metadata_info['creation_time'] = creation_time
            
            # 检查视频流
            if 'streams' in probe:
                for stream in probe['streams']:
                    if stream.get('codec_type') == 'video':
                        metadata_info['codec'] = stream.get('codec_name', 'unknown')
                        metadata_info['width'] = stream.get('width', 0)
                        metadata_info['height'] = stream.get('height', 0)
                        metadata_info['frame_rate'] = stream.get('r_frame_rate', 'unknown')
                        break
            
            return {
                "metadata": metadata_info,
                "suspicious_indicators": suspicious_indicators,
                "suspicious_count": len(suspicious_indicators),
                "status": "analyzed"
            }
            
        except ImportError as e:
            log_info("DeepfakeDetector", f"[DEBUG] ffmpeg-python import failed: {e}")
            # ffmpeg-python未安装，尝试基础方法
            try:
                import subprocess
                import json
                
                # 使用命令行ffprobe
                ffprobe_cmd = getattr(self, 'ffmpeg_command', 'ffmpeg').replace('ffmpeg', 'ffprobe')
                log_info("DeepfakeDetector", f"[DEBUG] Using command-line ffprobe: {ffprobe_cmd}")
                
                # 处理actual_path（可能需要从上面的try块获取）
                if 'actual_path' not in locals():
                    actual_path = video_path
                    if video_path.startswith('file:'):
                        actual_path = video_path[5:]
                
                cmd = [
                    ffprobe_cmd, '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', actual_path
                ]
                log_info("DeepfakeDetector", f"[DEBUG] Running ffprobe command: {' '.join(cmd[:3])}...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                log_info("DeepfakeDetector", f"[DEBUG] ffprobe returncode: {result.returncode}")
                
                if result.returncode == 0:
                    probe = json.loads(result.stdout)
                    log_info("DeepfakeDetector", "[DEBUG] ffprobe output parsed successfully")
                    # 简化的元数据提取
                    metadata = {
                        "format": probe.get('format', {}).get('format_name', 'unknown'),
                        "duration": probe.get('format', {}).get('duration', 'unknown'),
                        "bit_rate": probe.get('format', {}).get('bit_rate', 'unknown'),
                        "size": probe.get('format', {}).get('size', 'unknown')
                    }
                    
                    # 提取视频流信息
                    for stream in probe.get('streams', []):
                        if stream.get('codec_type') == 'video':
                            metadata['codec'] = stream.get('codec_name', 'unknown')
                            metadata['width'] = stream.get('width', 0)
                            metadata['height'] = stream.get('height', 0)
                            metadata['frame_rate'] = stream.get('r_frame_rate', 'unknown')
                            break
                    
                    log_info("DeepfakeDetector", f"[DEBUG] Basic metadata extracted: {metadata}")
                    return {
                        "metadata": metadata,
                        "status": "basic_analysis",
                        "note": "Using command-line ffprobe (install ffmpeg-python for advanced analysis)"
                    }
                else:
                    log_info("DeepfakeDetector", f"[DEBUG] ffprobe failed with stderr: {result.stderr[:200]}")
                
            except Exception as e2:
                log_info("DeepfakeDetector", f"[DEBUG] Command-line ffprobe failed: {e2}")
            
            # 返回原始占位信息
            log_info("DeepfakeDetector", "[DEBUG] Falling back to placeholder metadata")
            return {
                "note": "Install ffmpeg-python for advanced metadata analysis",
                "checks": ["creation_time", "encoder", "frame_rate", "compression_artifacts"],
                "status": "ffmpeg_not_available"
            }
            
        except Exception as e:
            # 其他错误，返回基础信息
            return {
                "note": "Video metadata analysis requires ffmpeg-python",
                "status": "analysis_failed",
                "error": str(e)
            }
    
    async def _call_resemble_api(self, audio_path: str) -> Dict[str, Any]:
        """调用Resemble AI音频deepfake检测"""
        # 处理file:ID格式
        actual_path = audio_path
        if audio_path.startswith('file:'):
            try:
                from aicca.utils.content_loader import ContentLoader
                loader = ContentLoader()
                actual_path, metadata = await loader.load_content(audio_path)
            except Exception as e:
                log_info("DeepfakeDetector", f"ContentLoader failed in call_resemble_api: {e}")
                actual_path = audio_path[5:]  # 降级处理
        
        return {
            "note": "Resemble AI integration requires API key",
            "free_tier": "2 free submissions available",
            "status": "not_configured",
            "audio_path": actual_path  # 返回解析后的路径用于后续实现
        }
    
    async def _basic_audio_analysis(self, audio_path: str) -> Dict[str, Any]:
        """基础音频分析"""
        try:
            # 处理file:ID格式
            actual_path = audio_path
            if audio_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(audio_path)
                except Exception as e:
                    log_info("DeepfakeDetector", f"ContentLoader failed in basic_audio_analysis: {e}")
                    actual_path = audio_path[5:]  # 降级处理
            
            # 尝试使用librosa进行真实音频分析
            import librosa
            import numpy as np
            
            # 加载音频
            y, sr = librosa.load(actual_path, sr=None)
            
            # 计算基础特征
            analysis_result = {}
            
            # 1. 音频长度
            duration = len(y) / sr
            analysis_result['duration'] = float(duration)
            
            # 2. 静音比例
            rms = librosa.feature.rms(y=y)[0]
            silence_threshold = np.percentile(rms, 10)
            silence_ratio = np.sum(rms < silence_threshold) / len(rms)
            analysis_result['silence_ratio'] = float(silence_ratio)
            
            # 3. 频谱质心（音色特征）
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            analysis_result['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
            analysis_result['spectral_centroid_std'] = float(np.std(spectral_centroids))
            
            # 4. 零交叉率（语音/非语音检测）
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            analysis_result['zero_crossing_rate'] = float(np.mean(zcr))
            
            # 简单的异常检测
            suspicious_indicators = []
            
            # 过于稳定的频谱质心可能表示合成音频
            if analysis_result['spectral_centroid_std'] < 100:
                suspicious_indicators.append("Unusually stable spectral centroid")
            
            # 过多静音可能表示拼接
            if silence_ratio > 0.5:
                suspicious_indicators.append("Excessive silence detected")
            
            # 异常的零交叉率
            if analysis_result['zero_crossing_rate'] < 0.01 or analysis_result['zero_crossing_rate'] > 0.5:
                suspicious_indicators.append("Abnormal zero crossing rate")
            
            return {
                "audio_features": analysis_result,
                "suspicious_indicators": suspicious_indicators,
                "deepfake_risk": len(suspicious_indicators) / 3.0,  # 简单风险评分
                "status": "analyzed"
            }
            
        except ImportError:
            # librosa未安装，返回简化版本
            try:
                # 尝试使用wave库获取基础信息
                import wave
                
                # 处理file:ID格式
                actual_path = audio_path
                if audio_path.startswith('file:'):
                    try:
                        from aicca.utils.content_loader import ContentLoader
                        loader = ContentLoader()
                        actual_path, metadata = await loader.load_content(audio_path)
                    except Exception as e:
                        log_info("DeepfakeDetector", f"ContentLoader failed in audio analysis: {e}")
                        actual_path = audio_path[5:]  # 降级处理
                
                with wave.open(actual_path, 'rb') as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / float(rate)
                    
                    return {
                        "audio_features": {
                            "duration": duration,
                            "sample_rate": rate,
                            "channels": wav.getnchannels()
                        },
                        "note": "Install librosa for advanced audio analysis",
                        "status": "basic_info"
                    }
            except Exception:
                pass
            
            # 返回原始占位信息
            return {
                "note": "Install librosa for audio deepfake detection",
                "metrics": ["pitch_consistency", "formant_analysis", "silence_patterns"],
                "status": "librosa_not_available"
            }
            
        except Exception as e:
            # 其他错误，返回基础信息
            return {
                "note": "Audio analysis failed",
                "status": "analysis_failed",
                "error": str(e)
            }
    
    def _generate_report(self, results: Dict[str, Any], media_type: str, analysis_depth: str) -> str:
        """生成检测报告"""
        report = "# Deepfake Detection Report\n\n"
        report += f"**Media Type**: {media_type}\n"
        report += f"**Analysis Depth**: {analysis_depth}\n\n"
        
        if media_type == "image":
            # Sightengine结果
            if "sightengine_analysis" in results:
                se = results["sightengine_analysis"]
                if "deepfake_score" in se:
                    score = se["deepfake_score"]
                    report += "## Deepfake Detection\n"
                    report += f"**Deepfake Score**: {score:.4f}\n"
                    report += f"*Score closer to 1 indicates higher probability of deepfake*\n\n"
                    
                    # 解释分数
                    if score < 0.3:
                        report += "**Assessment**: Low probability of deepfake\n"
                    elif score < 0.7:
                        report += "**Assessment**: Moderate probability of deepfake\n"
                    else:
                        report += "**Assessment**: High probability of deepfake\n"
                elif "error" in se:
                    report += f"**API Error**: {se['error']}\n"
                report += "\n"
            
            # 本地分析结果
            if "local_analysis" in results:
                local = results["local_analysis"]
                if "metadata_check" in local:
                    meta = local["metadata_check"]
                    report += "## Metadata Analysis\n"
                    if meta.get("suspicious_indicators"):
                        report += "**Suspicious Indicators Found**:\n"
                        for indicator in meta["suspicious_indicators"]:
                            report += f"- {indicator}\n"
                    else:
                        report += "No suspicious metadata found\n"
                    report += "\n"
        
        elif media_type == "video":
            report += "## Video Analysis Report\n\n"
            
            # 添加使用的模型信息
            if "model_used" in results:
                model = results["model_used"]
                if model == "genai":
                    report += "**Detection Type**: AI-Generated Content Detection\n"
                    report += "*Analyzing for all types of AI-generated content (synthetic scenes, objects, animations)*\n\n"
                elif model == "deepfake":
                    report += "**Detection Type**: Facial Deepfake Detection\n"
                    report += "*Analyzing specifically for face swaps and facial manipulations*\n\n"
                elif model == "comprehensive":
                    report += "**Detection Type**: Comprehensive Analysis\n"
                    report += "*Analyzing both facial deepfakes and general AI-generated content*\n\n"
            
            if "video_analysis" in results:
                va = results["video_analysis"]
                
                # GenAI模型结果
                if "average_ai_score" in va:
                    report += "### AI Content Detection Results\n"
                    report += f"**Frames Analyzed**: {va.get('frames_analyzed', 0)}\n"
                    report += f"**Average AI Score**: {va.get('average_ai_score', 0):.4f}\n"
                    report += f"**Highest AI Score**: {va.get('max_ai_score', 0):.4f}\n"
                    report += f"**Lowest AI Score**: {va.get('min_ai_score', 0):.4f}\n\n"
                    
                    # 帧级别详细信息
                    if "frame_details" in va and va["frame_details"]:
                        report += "**Frame-by-Frame Analysis**:\n"
                        for frame in va["frame_details"]:
                            score = frame.get('ai_generated_score', 0)
                            timestamp = frame.get('timestamp', 0)
                            frame_num = frame.get('frame', 0)
                            
                            # 评估等级
                            if score < 0.3:
                                assessment = "likely human-created"
                            elif score < 0.7:
                                assessment = "possibly AI-generated"
                            else:
                                assessment = "likely AI-generated"
                            
                            report += f"- Frame {frame_num} (@{timestamp}s): {score:.3f} *{assessment}*\n"
                    
                    # 整体评估
                    report += "\n**Overall Assessment**: "
                    avg = va.get('average_ai_score', 0)
                    if avg < 0.3:
                        report += "Low probability of AI-generated content (appears authentic)\n"
                    elif avg < 0.5:
                        report += "Mixed signals - some frames may contain AI elements\n"
                    elif avg < 0.7:
                        report += "Moderate probability of AI-generated content\n"
                    else:
                        report += "High probability of AI-generated content detected\n"
                
                # Deepfake模型结果
                elif "average_deepfake_score" in va:
                    report += "### Facial Deepfake Detection Results\n"
                    report += f"**Frames Analyzed**: {va.get('frames_analyzed', 0)}\n"
                    report += f"**Average Deepfake Score**: {va.get('average_deepfake_score', 0):.4f}\n"
                    report += f"**Highest Score**: {va.get('max_deepfake_score', 0):.4f}\n"
                    report += f"**Lowest Score**: {va.get('min_deepfake_score', 0):.4f}\n\n"
                    
                    # 帧级别详细信息
                    if "frame_details" in va and va["frame_details"]:
                        report += "**Frame-by-Frame Analysis**:\n"
                        for frame in va["frame_details"]:
                            score = frame.get('deepfake_score', 0)
                            timestamp = frame.get('timestamp', 0)
                            frame_num = frame.get('frame', 0)
                            
                            if score < 0.3:
                                assessment = "no facial manipulation"
                            elif score < 0.7:
                                assessment = "possible manipulation"
                            else:
                                assessment = "likely face swap/deepfake"
                            
                            report += f"- Frame {frame_num} (@{timestamp}s): {score:.3f} *{assessment}*\n"
                    
                    # 评估
                    report += "\n**Overall Assessment**: "
                    avg = va.get('average_deepfake_score', 0)
                    if avg < 0.3:
                        report += "Low probability of facial deepfake\n"
                    elif avg < 0.7:
                        report += "Moderate probability of facial manipulation\n"
                    else:
                        report += "High probability of facial deepfake detected\n"
                
                # Comprehensive模式结果
                elif "comprehensive_mode" in va:
                    report += "### Comprehensive Analysis Results\n\n"
                    
                    # 面部分析
                    if "facial_analysis" in va:
                        fa = va["facial_analysis"]
                        report += "**Facial Deepfake Detection**:\n"
                        report += f"- Average Score: {fa.get('average_deepfake_score', 0):.4f}\n"
                        report += f"- Frames Analyzed: {fa.get('frames_analyzed', 0)}\n\n"
                    
                    # AI内容分析
                    if "general_ai_analysis" in va:
                        ga = va["general_ai_analysis"]
                        report += "**AI Content Detection**:\n"
                        report += f"- Average Score: {ga.get('average_ai_score', 0):.4f}\n"
                        report += f"- Frames Analyzed: {ga.get('frames_analyzed', 0)}\n\n"
                    
                    # 综合评估
                    if "combined_assessment" in va:
                        ca = va["combined_assessment"]
                        report += "**Combined Assessment**:\n"
                        if ca.get("facial_manipulation"):
                            report += "- Facial manipulation detected\n"
                        else:
                            report += "- No facial manipulation detected\n"
                        
                        if ca.get("ai_generated"):
                            report += "- AI-generated content detected\n"
                        else:
                            report += "- No AI-generated content detected\n"
                        
                        report += f"- Overall Risk Level: **{ca.get('overall_risk', 'unknown').upper()}**\n"
                
                # 异步API结果
                elif "media_id" in va:
                    report += f"**Status**: {va.get('status', 'processing')}\n"
                    report += f"**Media ID**: {va.get('media_id')}\n"
                    report += f"**Callback URL**: {va.get('callback_url', 'N/A')}\n"
                    report += f"*{va.get('note', 'Processing in progress')}*\n"
                
                # 添加技术细节
                if "method" in va:
                    report += f"\n**Technical Details**:\n"
                    report += f"- Method: {va['method']}\n"
                    if "note" in va:
                        report += f"- Note: {va['note']}\n"
            
            # 时序一致性分析
            if "temporal_analysis" in results:
                ta = results["temporal_analysis"]
                report += "\n## Temporal Consistency Analysis\n"
                if ta.get("status") == "analyzed":
                    report += f"**Frames Analyzed**: {ta.get('frames_analyzed', 0)}\n"
                    report += f"**Consistency Score**: {ta.get('consistency_score', 0):.2f}/100\n"
                    if "frame_differences" in ta:
                        report += f"**Frame Differences**: {', '.join([f'{d:.2f}' for d in ta['frame_differences'][:3]])}\n"
                elif ta.get("status") == "opencv_not_available":
                    report += f"Note: {ta.get('note', 'OpenCV not installed')}\n"
                else:
                    report += f"Status: {ta.get('status', 'not analyzed')}\n"
                report += "\n"
            
            # 元数据分析
            if "metadata_analysis" in results:
                ma = results["metadata_analysis"]
                report += "## Video Metadata Analysis\n"
                if ma.get("status") == "analyzed":
                    metadata = ma.get("metadata", {})
                    report += f"**Format**: {metadata.get('format', 'unknown')}\n"
                    report += f"**Duration**: {metadata.get('duration', 'unknown')} seconds\n"
                    report += f"**Resolution**: {metadata.get('width', 'unknown')}x{metadata.get('height', 'unknown')}\n"
                    report += f"**Codec**: {metadata.get('codec', 'unknown')}\n"
                    report += f"**Frame Rate**: {metadata.get('frame_rate', 'unknown')}\n"
                    report += f"**Encoder**: {metadata.get('encoder', 'unknown')}\n"
                    
                    if ma.get("suspicious_indicators"):
                        report += "\n**Suspicious Indicators**:\n"
                        for indicator in ma["suspicious_indicators"]:
                            report += f"- {indicator}\n"
                elif ma.get("status") == "basic_analysis":
                    metadata = ma.get("metadata", {})
                    report += f"**Format**: {metadata.get('format', 'unknown')}\n"
                    report += f"**Duration**: {metadata.get('duration', 'unknown')}\n"
                else:
                    report += f"Status: {ma.get('status', 'not analyzed')}\n"
                report += "\n"
        
        elif media_type == "audio":
            report += "## Audio Deepfake Analysis\n"
            report += f"*{results.get('note', '')}*\n"
            
            if "basic_analysis" in results:
                ba = results["basic_analysis"]
                report += "\n**Metrics Checked**:\n"
                for metric in ba.get("metrics", []):
                    report += f"- {metric}\n"
        
        return report
    
    def _generate_summary(self, results: Dict[str, Any], media_type: str) -> str:
        """生成简洁摘要"""
        if media_type == "image":
            if "sightengine_analysis" in results:
                se = results["sightengine_analysis"]
                if "deepfake_score" in se:
                    score = se["deepfake_score"]
                    percentage = round(score * 100, 1)
                    return f"Deepfake detection: {score:.4f} ({percentage}% probability)"
                elif "ai_generated_score" in se:
                    score = se["ai_generated_score"]
                    percentage = round(score * 100, 1)
                    return f"AI content detection: {score:.4f} ({percentage}% probability)"
        
        elif media_type == "video":
            if "video_analysis" in results:
                va = results["video_analysis"]
                
                # GenAI检测结果
                if "average_ai_score" in va:
                    score = va["average_ai_score"]
                    percentage = round(score * 100, 1)
                    frames = va.get("frames_analyzed", 0)
                    if score > 0.7:
                        return f"High AI content probability: {percentage}% (analyzed {frames} frames)"
                    elif score > 0.5:
                        return f"Moderate AI content detected: {percentage}% (analyzed {frames} frames)"
                    else:
                        return f"Low AI content probability: {percentage}% (analyzed {frames} frames)"
                
                # Deepfake检测结果
                elif "average_deepfake_score" in va:
                    score = va["average_deepfake_score"]
                    percentage = round(score * 100, 1)
                    frames = va.get("frames_analyzed", 0)
                    if score > 0.7:
                        return f"High deepfake probability: {percentage}% (analyzed {frames} frames)"
                    elif score > 0.3:
                        return f"Moderate deepfake risk: {percentage}% (analyzed {frames} frames)"
                    else:
                        return f"Low deepfake probability: {percentage}% (analyzed {frames} frames)"
                
                # Comprehensive检测结果
                elif "comprehensive_mode" in va:
                    ca = va.get("combined_assessment", {})
                    risk = ca.get("overall_risk", "unknown")
                    has_facial = ca.get("facial_manipulation", False)
                    has_ai = ca.get("ai_generated", False)
                    
                    if has_facial and has_ai:
                        return f"Both facial manipulation and AI content detected - {risk.upper()} risk"
                    elif has_facial:
                        return f"Facial manipulation detected - {risk.upper()} risk"
                    elif has_ai:
                        return f"AI-generated content detected - {risk.upper()} risk"
                    else:
                        return f"No significant manipulation detected - {risk.upper()} risk"
        
        return f"Analysis completed for {media_type}"