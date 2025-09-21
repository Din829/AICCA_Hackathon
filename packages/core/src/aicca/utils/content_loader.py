"""
统一的内容加载器
支持多种输入源：文件路径、URL、Base64、文件ID
最小侵入性设计，不影响现有工具逻辑
"""

import base64
import tempfile
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple
import hashlib
import mimetypes
import json


class ContentLoader:
    """
    统一的内容加载器
    智能识别和处理不同的输入源
    """
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "aicca_temp"
        self.temp_dir.mkdir(exist_ok=True)
        self._file_cache = {}
        
    async def load_content(self, content_input: str, source_hint: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        智能加载内容，返回文件路径和元信息
        
        Args:
            content_input: 输入内容（路径/URL/Base64/文件ID等）
            source_hint: 来源提示（可选）
            
        Returns:
            (file_path, metadata) - 文件路径和元数据
        """
        
        # 1. 检查是否是文件ID（Web上传） - 支持 "file:uuid" 格式
        if content_input.startswith("file:"):
            file_id = content_input[5:]  # 去掉 "file:" 前缀
            if self._is_file_id(file_id):
                return await self._load_from_file_id(file_id)
        elif self._is_file_id(content_input):
            return await self._load_from_file_id(content_input)
            
        # 2. 检查是否是Base64数据
        if self._is_base64(content_input):
            return await self._load_from_base64(content_input, source_hint)
            
        # 3. 检查是否是URL
        if self._is_url(content_input):
            return await self._load_from_url(content_input)
            
        # 4. 检查是否是本地文件路径
        if self._is_file_path(content_input):
            return await self._load_from_file(content_input)
            
        # 5. 如果都不是，作为文本内容处理
        return await self._load_as_text(content_input)
    
    def _is_file_id(self, content: str) -> bool:
        """检查是否是文件ID（UUID格式）"""
        import re
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, content.lower()))
    
    def _is_base64(self, content: str) -> bool:
        """检查是否是Base64编码"""
        # 检查是否有Base64前缀（Data URL）
        if content.startswith('data:'):
            return True
        
        # 短字符串不太可能是Base64（除非明确指定）
        if len(content) < 20:
            return False
            
        # 尝试解码检查（更智能的判断）
        try:
            # Base64字符集检查
            import re
            # Base64只包含这些字符
            if re.match(r'^[A-Za-z0-9+/]*={0,2}$', content):
                # 尝试解码验证
                base64.b64decode(content, validate=True)
                return True
        except:
            pass
        return False
    
    def _is_url(self, content: str) -> bool:
        """检查是否是URL"""
        return content.startswith(('http://', 'https://'))
    
    def _is_file_path(self, content: str) -> bool:
        """检查是否是文件路径"""
        # 排除已知的非文件路径格式
        if content.startswith(('data:', 'http://', 'https://')):
            return False
        
        try:
            path = Path(content)
            # 检查是否包含路径分隔符或文件扩展名
            return ('/' in content or '\\' in content or 
                    path.suffix != '' or path.exists())
        except:
            return False
    
    async def _load_from_file_id(self, file_id: str) -> Tuple[str, Dict[str, Any]]:
        """从文件ID加载（Web上传的文件）"""
        # 查找上传的文件
        file_storage = None
        
        # 尝试多种导入路径
        try:
            from packages.api.aicca_api import file_storage
        except ImportError:
            try:
                # 尝试相对导入
                import sys
                project_root = Path(__file__).parent.parent.parent.parent.parent
                sys.path.insert(0, str(project_root))
                from packages.api.aicca_api import file_storage
            except ImportError:
                try:
                    # 尝试直接导入（如果在同一个进程中）
                    import aicca_api
                    file_storage = aicca_api.file_storage
                except ImportError:
                    pass
        
        if file_storage is None:
            # 如果无法导入，尝试使用临时目录直接访问
            temp_path = Path(tempfile.gettempdir()) / "aicca_uploads" / file_id
            if temp_path.exists():
                return str(temp_path), {
                    'source': 'upload',
                    'file_id': file_id
                }
            raise ValueError(f"Cannot access file storage for file_id: {file_id}")
        
        file_info = file_storage.get_file_info(file_id)
        if file_info:
            return file_info['path'], {
                'source': 'upload',
                'file_id': file_id,
                'original_name': file_info.get('original_name'),
                'content_type': file_info.get('content_type'),
                'size': file_info.get('size')
            }
        
        # 如果找不到，抛出异常
        raise ValueError(f"File ID not found: {file_id}")
    
    async def _load_from_base64(self, content: str, hint: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """从Base64数据加载"""
        # 处理Data URL格式
        if content.startswith('data:'):
            header, data = content.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]
        else:
            data = content
            mime_type = 'application/octet-stream'
            
        # 解码Base64
        file_data = base64.b64decode(data)
        
        # 生成文件名
        file_hash = hashlib.md5(file_data).hexdigest()[:8]
        ext = mimetypes.guess_extension(mime_type) or '.bin'
        if hint and '.' in hint:
            ext = '.' + hint.split('.')[-1]
        
        # 保存到临时文件
        temp_path = self.temp_dir / f"base64_{file_hash}{ext}"
        temp_path.write_bytes(file_data)
        
        return str(temp_path), {
            'source': 'base64',
            'mime_type': mime_type,
            'size': len(file_data),
            'temp_file': True
        }
    
    async def _load_from_url(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """从URL下载文件"""
        # 检查缓存
        if url in self._file_cache:
            cached = self._file_cache[url]
            if Path(cached['path']).exists():
                return cached['path'], cached['metadata']
        
        # 下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # 获取文件信息
            content_type = response.headers.get('content-type', 'application/octet-stream')
            content_length = len(response.content)
            
            # 从URL提取文件名
            filename = url.split('/')[-1].split('?')[0]
            if not filename or '.' not in filename:
                ext = mimetypes.guess_extension(content_type) or '.bin'
                filename = f"download_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
            
            # 保存到临时文件
            temp_path = self.temp_dir / f"url_{filename}"
            temp_path.write_bytes(response.content)
            
            metadata = {
                'source': 'url',
                'url': url,
                'content_type': content_type,
                'size': content_length,
                'temp_file': True
            }
            
            # 缓存结果
            self._file_cache[url] = {
                'path': str(temp_path),
                'metadata': metadata
            }
            
            return str(temp_path), metadata
    
    async def _load_from_file(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """从本地文件加载"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        return str(path.absolute()), {
            'source': 'file',
            'size': path.stat().st_size,
            'mime_type': mimetypes.guess_type(str(path))[0],
            'temp_file': False
        }
    
    async def _load_as_text(self, content: str) -> Tuple[str, Dict[str, Any]]:
        """将文本内容保存为临时文件"""
        # 生成临时文本文件
        file_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        temp_path = self.temp_dir / f"text_{file_hash}.txt"
        temp_path.write_text(content, encoding='utf-8')
        
        return str(temp_path), {
            'source': 'text',
            'size': len(content),
            'mime_type': 'text/plain',
            'temp_file': True
        }
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        for file_path in self.temp_dir.glob("*"):
            try:
                file_path.unlink()
            except:
                pass


# 创建全局实例
content_loader = ContentLoader()


async def smart_load_content(content_input: str, hint: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    便捷的内容加载函数
    
    Examples:
        # 文件路径
        path, meta = await smart_load_content("/path/to/file.jpg")
        
        # URL
        path, meta = await smart_load_content("https://example.com/image.jpg")
        
        # Base64
        path, meta = await smart_load_content("data:image/jpeg;base64,/9j/4AAQ...")
        
        # 文件ID（Web上传）
        path, meta = await smart_load_content("550e8400-e29b-41d4-a716-446655440000")
        
        # 纯文本
        path, meta = await smart_load_content("这是一段文本内容")
    """
    return await content_loader.load_content(content_input, hint)