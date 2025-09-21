"""
图像验证工具 - 综合图像真实性验证
Image Verification Tool - 使用Google Vision、Sightengine和本地分析
"""

import asyncio
import os
import json
import tempfile
from typing import Dict, Any, Optional, Union, Callable
from pathlib import Path
import hashlib
from datetime import datetime

# 使用dbrheo接口
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
from dbrheo.tools.base import DatabaseTool, DatabaseConfirmationDetails
from dbrheo.config.base import DatabaseConfig
from dbrheo.utils.debug_logger import log_info


class ImageVerifyTool(DatabaseTool):
    """
    图像验证工具
    综合使用Google Vision API、Sightengine API和本地分析进行图像验证
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self._i18n = i18n
        super().__init__(
            name="image_verify",
            display_name=self._('image_verify_name', default="Image Verifier") if i18n else "Image Verifier",
            description="General AI-generated image detector. Detects all types of AI-created content (landscapes, objects, art, people) using Sightengine genai model. Also provides Google Vision analysis and EXIF metadata. Use this for general AI detection, use deepfake_detector specifically for face swap detection.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Image file path (local path or URL)"
                    },
                    "verification_mode": {
                        "type": "string",
                        "enum": ["quick", "standard", "comprehensive"],
                        "description": "Verification mode: quick(basic checks), standard(normal), comprehensive(all checks)",
                        "default": "standard"
                    },
                    "include_ai_detection": {
                        "type": "boolean",
                        "description": "Include AI-generated content detection (uses Sightengine API)",
                        "default": True
                    },
                    "include_vision_analysis": {
                        "type": "boolean",
                        "description": "Include Google Vision analysis (objects, text, safety)",
                        "default": True
                    },
                    "include_local_analysis": {
                        "type": "boolean",
                        "description": "Include local analysis (EXIF, hash)",
                        "default": True
                    }
                },
                "required": ["image_path"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
        
        # API配置
        self.api_config = self._initialize_api_config()
    
    def _initialize_api_config(self) -> Dict[str, Any]:
        """初始化API配置"""
        config = {}
        
        # Google Vision配置
        config["google_vision"] = {
            "enabled": self.config.get("vision_api_enabled", True),
            "credentials": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT")
        }
        
        # Sightengine配置
        # 清理环境变量中的换行符和空白字符（部署环境Secret Manager问题修复）
        api_user = os.environ.get("SIGHTENGINE_API_USER") or self.config.get("sightengine_api_user")
        api_secret = os.environ.get("SIGHTENGINE_API_SECRET") or self.config.get("sightengine_api_secret")

        config["sightengine"] = {
            "enabled": self.config.get("sightengine_enabled", True),
            "api_user": api_user.strip() if api_user else None,
            "api_secret": api_secret.strip() if api_secret else None,
            "endpoint": "https://api.sightengine.com/1.0/check.json"
        }
        
        return config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        params = self._normalize_params(params)
        
        image_path = params.get("image_path", "")
        if not image_path:
            return "Image path cannot be empty"
        
        # 如果是本地路径，检查文件是否存在
        if not image_path.startswith(('http://', 'https://')):
            path = Path(image_path)
            if not path.exists():
                return f"Image file not found: {image_path}"
            
            # 检查文件类型
            valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
            if path.suffix.lower() not in valid_extensions:
                return f"Unsupported image format: {path.suffix}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        image_path = params.get("image_path", "")
        mode = params.get("verification_mode", "standard")
        
        # 获取文件名
        if image_path.startswith('file:'):
            filename = f"uploaded_{image_path[5:][:8]}"
        elif image_path.startswith(('http://', 'https://')):
            filename = image_path.split('/')[-1][:50]
        else:
            filename = Path(image_path).name
        
        return f"Performing {mode} verification on: {filename}"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认"""
        # 图像验证不需要确认
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行图像验证"""
        params = self._normalize_params(params)
        
        image_path = params.get("image_path", "")
        mode = params.get("verification_mode", "standard")
        include_ai = params.get("include_ai_detection", True)
        include_vision = params.get("include_vision_analysis", True)
        include_local = params.get("include_local_analysis", True)
        
        try:
            # 准备图像内容
            if update_output:
                update_output("Loading image...")
            
            image_content = await self._prepare_image(image_path)
            
            results = {}
            
            # 1. 本地分析（EXIF和哈希）
            if include_local:
                if update_output:
                    update_output("Analyzing local properties...")
                local_result = await self._local_analysis(image_path)
                results["local_analysis"] = local_result
            
            # 2. Google Vision分析
            if include_vision and self.api_config["google_vision"]["enabled"]:
                if update_output:
                    update_output("Analyzing with Google Vision...")
                vision_result = await self._google_vision_analysis(image_content)
                results["vision_analysis"] = vision_result
            
            # 3. Sightengine AI检测
            if include_ai and self.api_config["sightengine"]["enabled"]:
                if update_output:
                    update_output("Checking for AI-generated content...")
                ai_result = await self._sightengine_ai_detection(image_path)
                results["ai_detection"] = ai_result
            
            # 生成报告
            report = self._generate_report(results, mode)
            
            return ToolResult(
                summary=f"Image verification completed ({mode} mode)",
                llm_content=results,
                return_display=report
            )
            
        except Exception as e:
            error_msg = f"Image verification failed: {str(e)}"
            log_info("ImageVerify", f"Error: {e}")
            return ToolResult(
                error=error_msg,
                llm_content={"error": str(e)},
                return_display=f"[ERROR] {error_msg}"
            )
    
    async def _prepare_image(self, image_path: str) -> bytes:
        """准备图像内容 - 支持多种输入格式"""
        
        # 处理file:ID格式
        if image_path.startswith('file:'):
            try:
                from aicca.utils.content_loader import ContentLoader
                loader = ContentLoader()
                actual_path, metadata = await loader.load_content(image_path)
                with open(actual_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                log_info("ImageVerify", f"ContentLoader failed: {e}, trying direct path")
                # 如果失败，尝试去掉file:前缀作为路径处理
                image_path = image_path[5:]
        
        # URL图像
        if image_path.startswith(('http://', 'https://')):
            import urllib.request
            with urllib.request.urlopen(image_path) as response:
                return response.read()
        
        # 本地文件
        # 再次检查是否还是file:格式（降级处理后可能还需要处理）
        if image_path.startswith('file:'):
            # 尝试从临时目录直接访问
            temp_path = Path(tempfile.gettempdir()) / "aicca_uploads" / image_path[5:]
            if temp_path.exists():
                with open(temp_path, 'rb') as f:
                    return f.read()
            # 如果还是找不到，抛出明确的错误
            raise FileNotFoundError(f"Cannot locate uploaded file: {image_path}")
        
        with open(image_path, 'rb') as f:
            return f.read()
    
    async def _local_analysis(self, image_path: str) -> Dict[str, Any]:
        """本地分析：EXIF和哈希"""
        result = {}
        
        try:
            # EXIF元数据提取
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            # 处理file:ID格式
            actual_path = image_path
            if image_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(image_path)
                except Exception as e:
                    log_info("ImageVerify", f"ContentLoader failed in local_analysis: {e}")
                    actual_path = image_path[5:]  # 降级处理
            
            if not actual_path.startswith(('http://', 'https://')):
                image = Image.open(actual_path)
                
                # 提取EXIF
                exifdata = image.getexif()
                if exifdata:
                    metadata = {}
                    for tag_id, value in exifdata.items():
                        tag = TAGS.get(tag_id, tag_id)
                        # 只保留关键信息
                        if tag in ['Make', 'Model', 'DateTime', 'Software', 'Orientation']:
                            metadata[tag] = str(value)
                    result["exif_metadata"] = metadata
                
                # 图像基本信息
                result["image_info"] = {
                    "format": image.format,
                    "mode": image.mode,
                    "size": image.size,
                    "width": image.width,
                    "height": image.height
                }
                
                # 计算哈希
                try:
                    import imagehash
                    result["hashes"] = {
                        "average": str(imagehash.average_hash(image)),
                        "perceptual": str(imagehash.phash(image)),
                        "difference": str(imagehash.dhash(image))
                    }
                except ImportError:
                    log_info("ImageVerify", "imagehash library not available")
        
        except Exception as e:
            result["error"] = f"Local analysis error: {str(e)}"
        
        return result
    
    async def _google_vision_analysis(self, image_content: bytes) -> Dict[str, Any]:
        """Google Vision API分析"""
        try:
            from google.cloud import vision
            
            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=image_content)
            
            result = {}
            
            # 标签检测
            response = client.label_detection(image=image)
            if response.label_annotations:
                result["labels"] = [
                    {"description": label.description, "score": label.score}
                    for label in response.label_annotations[:5]
                ]
            
            # 安全搜索检测
            response = client.safe_search_detection(image=image)
            safe = response.safe_search_annotation
            result["safe_search"] = {
                "adult": safe.adult.name,
                "violence": safe.violence.name,
                "racy": safe.racy.name
            }
            
            # 图像属性（主要颜色）
            response = client.image_properties(image=image)
            props = response.image_properties_annotation
            if props.dominant_colors:
                colors = props.dominant_colors.colors[:3]
                result["dominant_colors"] = [
                    {
                        "rgb": {"r": c.color.red, "g": c.color.green, "b": c.color.blue},
                        "score": c.score,
                        "pixel_fraction": c.pixel_fraction
                    }
                    for c in colors
                ]
            
            return result
            
        except Exception as e:
            return {"error": f"Google Vision API error: {str(e)}"}
    
    async def _sightengine_ai_detection(self, image_path: str) -> Dict[str, Any]:
        """Sightengine AI生成检测"""
        try:
            import urllib.request
            import urllib.parse

            api_user = self.api_config["sightengine"]["api_user"]
            api_secret = self.api_config["sightengine"]["api_secret"]

            # 添加详细的API调试日志
            log_info("ImageVerify", f"🔑 Sightengine API Credentials Check:")
            log_info("ImageVerify", f"  - User: {api_user[:3] if api_user else 'None'}...{api_user[-3:] if api_user and len(api_user) > 6 else ''}")
            log_info("ImageVerify", f"  - Secret: {api_secret[:3] if api_secret else 'None'}...{api_secret[-3:] if api_secret and len(api_secret) > 6 else ''}")
            log_info("ImageVerify", f"  - Endpoint: {self.api_config['sightengine']['endpoint']}")

            if not api_user or not api_secret:
                return {"error": "Sightengine API credentials not configured"}
            
            # 处理file:ID格式
            actual_path = image_path
            if image_path.startswith('file:'):
                try:
                    from aicca.utils.content_loader import ContentLoader
                    loader = ContentLoader()
                    actual_path, metadata = await loader.load_content(image_path)
                except Exception as e:
                    log_info("ImageVerify", f"ContentLoader failed in sightengine_ai: {e}")
                    actual_path = image_path[5:]  # 降级处理
            
            # 构建请求
            params = {
                'models': 'genai',
                'api_user': api_user,
                'api_secret': api_secret
            }
            
            # 根据输入类型选择参数
            if actual_path.startswith(('http://', 'https://')):
                params['url'] = actual_path
            else:
                # 本地文件需要上传
                with open(actual_path, 'rb') as f:
                    # 使用multipart上传
                    import requests
                    files = {'media': f}
                    response = requests.post(
                        self.api_config["sightengine"]["endpoint"],
                        files=files,
                        data=params
                    )
                    return response.json()
            
            # URL方式
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(
                self.api_config["sightengine"]["endpoint"],
                data=data
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                
            # 返回原始API数据
            return result
            
        except Exception as e:
            return {"error": f"Sightengine API error: {str(e)}"}
    
    def _generate_report(self, results: Dict[str, Any], mode: str) -> str:
        """生成验证报告"""
        report = "# Image Verification Report\n\n"
        report += f"**Verification Mode**: {mode}\n\n"
        
        # 本地分析结果
        if "local_analysis" in results:
            local = results["local_analysis"]
            report += "## Local Analysis\n"
            
            if "image_info" in local:
                info = local["image_info"]
                report += f"- Format: {info.get('format')}\n"
                report += f"- Dimensions: {info.get('width')}x{info.get('height')}\n"
            
            if "exif_metadata" in local:
                report += "- EXIF data found\n"
            
            if "hashes" in local:
                report += "- Perceptual hashes computed\n"
            
            report += "\n"
        
        # Google Vision结果
        if "vision_analysis" in results:
            vision = results["vision_analysis"]
            report += "## Google Vision Analysis\n"
            
            if "labels" in vision:
                report += "**Detected Objects**:\n"
                for label in vision["labels"][:3]:
                    report += f"- {label['description']} ({label['score']:.2f})\n"
            
            if "safe_search" in vision:
                safe = vision["safe_search"]
                report += f"**Content Safety**: Adult={safe['adult']}, Violence={safe['violence']}\n"
            
            report += "\n"
        
        # AI检测结果
        if "ai_detection" in results:
            ai = results["ai_detection"]
            report += "## AI Generation Detection\n"
            
            if "type" in ai and "ai_generated" in ai["type"]:
                score = ai["type"]["ai_generated"]
                report += f"**AI Generated Score**: {score:.4f}\n"
                report += f"*Score closer to 1 indicates AI-generated, closer to 0 indicates human-created*\n"
            
            report += "\n"
        
        return report