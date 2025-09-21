"""
AICCA Web API扩展层
基于最小侵入原则，不修改原有的dbrheo API
提供内容信任相关的Web接口
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import base64
import hashlib
import tempfile
import shutil
import asyncio
import json
from datetime import datetime
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原有的app和依赖
try:
    # 尝试绝对导入
    from dbrheo.api.app import app as base_app
    from dbrheo.api.dependencies import get_client, get_config
except ImportError:
    # 如果失败，使用绝对路径导入
    from core.src.dbrheo.api.app import app as base_app
    from core.src.dbrheo.api.dependencies import get_client, get_config


# ============= 数据模型定义 =============

class ContentAnalysisRequest(BaseModel):
    """内容分析请求模型"""
    source_type: str = Field(description="输入源类型: upload/url/text")
    content: Optional[str] = Field(None, description="文本内容或URL")
    file_data: Optional[str] = Field(None, description="Base64编码的文件数据")
    file_name: Optional[str] = Field(None, description="文件名")
    file_type: Optional[str] = Field(None, description="文件MIME类型")
    analysis_options: Dict[str, Any] = Field(default_factory=dict, description="分析选项")


class BatchAnalysisRequest(BaseModel):
    """批量分析请求模型"""
    items: List[ContentAnalysisRequest]
    parallel: bool = Field(True, description="是否并行处理")
    
    
class AnalysisResult(BaseModel):
    """分析结果模型"""
    request_id: str
    timestamp: str
    source_type: str
    results: Dict[str, Any]
    confidence_scores: Dict[str, float]
    recommendations: List[str]
    visualizations: Optional[Dict[str, Any]] = None


class ToolExecutionRequest(BaseModel):
    """工具执行请求模型"""
    tool_name: str
    parameters: Dict[str, Any]
    async_execution: bool = False
    webhook_url: Optional[str] = None


# ============= 文件处理服务 =============

class FileStorageService:
    """临时文件存储服务"""
    
    def __init__(self):
        self.storage_path = Path(tempfile.gettempdir()) / "aicca_uploads"
        self.storage_path.mkdir(exist_ok=True)
        self.file_cache: Dict[str, Dict] = {}
    
    async def save_upload(self, file: UploadFile) -> str:
        """保存上传的文件，返回文件ID"""
        file_id = str(uuid.uuid4())
        file_path = self.storage_path / file_id
        
        # 保存文件
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 缓存文件信息
        self.file_cache[file_id] = {
            "original_name": file.filename,
            "content_type": file.content_type,
            "size": file_path.stat().st_size,
            "path": str(file_path),
            "timestamp": datetime.now().isoformat()
        }
        
        return file_id
    
    async def save_base64(self, data: str, filename: str = None) -> str:
        """保存Base64编码的数据"""
        file_id = str(uuid.uuid4())
        file_path = self.storage_path / file_id
        
        try:
            # 调试：输入数据大小
            print(f"[SAVE_BASE64] Input data length: {len(data)} bytes")
            
            # 清理Base64数据（移除空格、换行等）
            clean_data = data.strip()
            print(f"[SAVE_BASE64] After strip: {len(clean_data)} bytes")
            
            # 如果数据包含data URL前缀，移除它
            if clean_data.startswith('data:'):
                clean_data = clean_data.split(',')[1] if ',' in clean_data else clean_data
                print(f"[SAVE_BASE64] After removing data URL: {len(clean_data)} bytes")
            
            # 移除可能的换行符、空格和其他非Base64字符
            import re
            # 只保留Base64字符（字母、数字、+、/、=）
            clean_data = re.sub(r'[^A-Za-z0-9+/=]', '', clean_data)
            print(f"[SAVE_BASE64] After regex clean: {len(clean_data)} bytes")
            
            # 解码并保存（让Python自动处理填充）
            try:
                file_data = base64.b64decode(clean_data)
                print(f"[SAVE_BASE64] Decoded size: {len(file_data)} bytes")
            except Exception as decode_error:
                # 如果失败，尝试标准的URL安全Base64解码
                try:
                    file_data = base64.urlsafe_b64decode(clean_data)
                    print(f"[SAVE_BASE64] URL-safe decoded size: {len(file_data)} bytes")
                except:
                    # 如果还是失败，抛出原始错误
                    raise decode_error
            
            # 验证文件不为空
            if len(file_data) == 0:
                raise ValueError("Decoded file is empty")
            
            file_path.write_bytes(file_data)
            
            # 对于图像文件，验证其有效性
            content_type = self._guess_content_type(filename) if filename else "application/octet-stream"
            if content_type.startswith("image/"):
                try:
                    from PIL import Image
                    # 尝试打开图像以验证其有效性
                    with Image.open(file_path) as img:
                        img.verify()
                    print(f"Image file verified: {filename}, format: {img.format if 'img' in locals() else 'unknown'}")
                except Exception as img_error:
                    print(f"Warning: Image verification failed for {filename}: {img_error}")
                    # 不阻止保存，只是警告
            
            # 缓存文件信息
            self.file_cache[file_id] = {
                "original_name": filename or f"upload_{file_id}",
                "size": len(file_data),
                "path": str(file_path),
                "timestamp": datetime.now().isoformat(),
                "content_type": content_type
            }
            
            print(f"File saved successfully: {file_id}, name: {filename}, size: {len(file_data)} bytes, type: {content_type}")
            return file_id
            
        except Exception as e:
            # 清理失败的文件
            if file_path.exists():
                file_path.unlink()
            print(f"Failed to save Base64 file: {e}")
            raise ValueError(f"Failed to save file: {str(e)}")
    
    def _guess_content_type(self, filename: str) -> str:
        """根据文件名猜测内容类型"""
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """获取文件信息"""
        return self.file_cache.get(file_id)
    
    def get_file_path(self, file_id: str) -> Optional[Path]:
        """获取文件路径"""
        info = self.file_cache.get(file_id)
        return Path(info["path"]) if info else None
    
    async def cleanup_old_files(self, max_age_hours: int = 24):
        """清理旧文件"""
        # TODO: 实现基于时间的文件清理
        pass


# 创建文件存储服务实例
file_storage = FileStorageService()


# ============= 内容分析路由 =============

@base_app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_content(
    request: ContentAnalysisRequest,
    background_tasks: BackgroundTasks,
    client = Depends(get_client)
):
    """
    统一的内容分析接口
    支持多种输入源：上传文件、URL、直接文本
    """
    try:
        request_id = str(uuid.uuid4())
        
        # 根据源类型准备内容
        content_to_analyze = None
        file_id = None
        
        if request.source_type == "upload" and request.file_data:
            # 处理Base64上传
            file_id = await file_storage.save_base64(
                request.file_data, 
                request.file_name
            )
            content_to_analyze = f"file:{file_id}"
            
        elif request.source_type == "url" and request.content:
            # URL直接传递
            content_to_analyze = request.content
            
        elif request.source_type == "text" and request.content:
            # 文本直接传递
            content_to_analyze = request.content
        else:
            raise HTTPException(400, "Invalid source type or missing content")
        
        # 构建Agent请求
        agent_request = f"""请分析以下内容的可信度和真实性：
        
内容源: {request.source_type}
内容: {content_to_analyze}
分析选项: {json.dumps(request.analysis_options, ensure_ascii=False)}

请使用所有相关工具进行全面分析。"""
        
        # 调用Agent（使用现有的客户端）
        signal = None  # TODO: 实现信号控制
        response_stream = client.send_message_stream(
            request=agent_request,
            signal=signal,
            prompt_id=request_id,
            turns=10
        )
        
        # 收集响应
        analysis_results = {}
        confidence_scores = {}
        recommendations = []
        
        async for chunk in response_stream:
            if chunk.get("type") == "ToolCallResult":
                # 处理工具结果
                tool_name = chunk.get("tool_name", "unknown")
                tool_result = chunk.get("result", {})
                analysis_results[tool_name] = tool_result
                
                # 提取置信度分数
                if "confidence" in tool_result:
                    confidence_scores[tool_name] = tool_result["confidence"]
                    
        # 后台清理临时文件
        if file_id:
            background_tasks.add_task(
                cleanup_temp_file, 
                file_id, 
                delay_seconds=3600
            )
        
        return AnalysisResult(
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            source_type=request.source_type,
            results=analysis_results,
            confidence_scores=confidence_scores,
            recommendations=recommendations,
            visualizations=None  # TODO: 生成可视化数据
        )
        
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@base_app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = Form("analysis")
):
    """
    文件上传接口
    返回文件ID供后续使用
    """
    try:
        # 文件大小限制（100MB）
        max_size = 100 * 1024 * 1024
        
        # 检查文件大小
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > max_size:
            raise HTTPException(413, f"File too large. Max size: {max_size} bytes")
        
        # 保存文件
        file_id = await file_storage.save_upload(file)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "purpose": purpose,
            "status": "uploaded"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")


@base_app.post("/api/batch/analyze")
async def batch_analyze(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    client = Depends(get_client)
):
    """
    批量内容分析接口
    支持并行或串行处理多个内容
    """
    try:
        batch_id = str(uuid.uuid4())
        results = []
        
        if request.parallel:
            # 并行处理
            tasks = []
            for item in request.items:
                task = analyze_content(item, background_tasks, client)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "index": i,
                        "status": "failed",
                        "error": str(result)
                    })
                else:
                    processed_results.append({
                        "index": i,
                        "status": "success",
                        "result": result.dict()
                    })
            results = processed_results
        else:
            # 串行处理
            for i, item in enumerate(request.items):
                try:
                    result = await analyze_content(item, background_tasks, client)
                    results.append({
                        "index": i,
                        "status": "success",
                        "result": result.dict()
                    })
                except Exception as e:
                    results.append({
                        "index": i,
                        "status": "failed",
                        "error": str(e)
                    })
        
        return {
            "batch_id": batch_id,
            "total_items": len(request.items),
            "parallel_processing": request.parallel,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(500, f"Batch analysis failed: {str(e)}")


@base_app.post("/api/tools/execute")
async def execute_tool(
    request: ToolExecutionRequest,
    client = Depends(get_client)
):
    """
    直接执行特定工具
    绕过Agent推理，直接调用工具
    """
    try:
        execution_id = str(uuid.uuid4())
        
        # 获取工具注册表
        try:
            from dbrheo.tools.registry import DatabaseToolRegistry
        except ImportError:
            from ..core.src.dbrheo.tools.registry import DatabaseToolRegistry
        config = get_config()
        registry = DatabaseToolRegistry(config)
        
        # 查找工具
        tool = registry.get_tool_by_name(request.tool_name)
        if not tool:
            raise HTTPException(404, f"Tool not found: {request.tool_name}")
        
        # 执行工具
        signal = None  # TODO: 实现信号控制
        
        if request.async_execution:
            # 异步执行，立即返回
            asyncio.create_task(
                _execute_tool_async(
                    tool, 
                    request.parameters, 
                    signal, 
                    execution_id,
                    request.webhook_url
                )
            )
            
            return {
                "execution_id": execution_id,
                "status": "started",
                "tool_name": request.tool_name,
                "async": True
            }
        else:
            # 同步执行
            result = await tool.execute(
                params=request.parameters,
                signal=signal,
                update_output=None
            )
            
            return {
                "execution_id": execution_id,
                "status": "completed",
                "tool_name": request.tool_name,
                "result": result.to_dict() if hasattr(result, 'to_dict') else str(result)
            }
            
    except Exception as e:
        raise HTTPException(500, f"Tool execution failed: {str(e)}")


# ============= 辅助函数 =============

async def cleanup_temp_file(file_id: str, delay_seconds: int = 3600):
    """延迟清理临时文件"""
    await asyncio.sleep(delay_seconds)
    file_path = file_storage.get_file_path(file_id)
    if file_path and file_path.exists():
        file_path.unlink()
    if file_id in file_storage.file_cache:
        del file_storage.file_cache[file_id]


async def _execute_tool_async(tool, parameters, signal, execution_id, webhook_url):
    """异步执行工具并可选发送webhook通知"""
    try:
        result = await tool.execute(
            params=parameters,
            signal=signal,
            update_output=None
        )
        
        if webhook_url:
            # TODO: 发送webhook通知
            pass
            
    except Exception as e:
        # TODO: 错误处理和通知
        pass


# ============= 健康检查和元数据 =============

@base_app.get("/api/info")
async def get_api_info():
    """获取API信息和能力"""
    return {
        "service": "AICCA - AI Content Credibility Agent",
        "version": "1.0.0",
        "capabilities": [
            "ai_content_detection",
            "deepfake_detection", 
            "c2pa_credential_management",
            "image_verification",
            "compliance_reporting"
        ],
        "supported_formats": [
            "text", "image/jpeg", "image/png", 
            "image/webp", "audio/mp3", "audio/wav",
            "video/mp4", "application/pdf"
        ],
        "api_endpoints": {
            "analyze": "/api/analyze",
            "upload": "/api/upload",
            "batch": "/api/batch/analyze",
            "tools": "/api/tools/execute",
            "chat": "/api/chat/send",
            "websocket": "/ws/chat"
        }
    }


@base_app.get("/api/tools")
async def list_available_tools():
    """列出所有可用的工具"""
    try:
        from dbrheo.tools.registry import DatabaseToolRegistry
    except ImportError:
        from ..core.src.dbrheo.tools.registry import DatabaseToolRegistry
    config = get_config()
    registry = DatabaseToolRegistry(config)
    
    tools = []
    for name, tool_info in registry.tools.items():
        tools.append({
            "name": name,
            "display_name": tool_info.tool.display_name,
            "description": tool_info.tool.description,
            "capabilities": [cap.value for cap in tool_info.capabilities],
            "priority": tool_info.priority
        })
    
    return {
        "total": len(tools),
        "tools": tools
    }


# ============= 更新CORS配置 =============

# 更新CORS中间件配置以支持更多源
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js开发服务器
        "http://localhost:3001",  # 备用端口
        "https://aicca.app",      # 生产域名（预留）
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


print("AICCA Web API层已加载")