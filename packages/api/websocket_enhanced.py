"""
增强的WebSocket支持
提供实时通信、文件传输和流式分析
"""

from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState
from typing import Dict, Any, Optional, List
import json
import base64
import asyncio
from datetime import datetime
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dbrheo.api.app import app
    from dbrheo.api.dependencies import get_client, get_config
    from dbrheo.types.core_types import SimpleAbortSignal
except ImportError:
    from core.src.dbrheo.api.app import app
    from core.src.dbrheo.api.dependencies import get_client, get_config
    from core.src.dbrheo.types.core_types import SimpleAbortSignal


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_info: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """接受新的WebSocket连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_info[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "message_count": 0
        }
    
    def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_info:
            del self.connection_info[client_id]
    
    async def send_message(self, client_id: str, message: Dict[str, Any]):
        """发送消息到特定客户端"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                self.connection_info[client_id]["message_count"] += 1
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[str] = None):
        """广播消息到所有连接的客户端"""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            if client_id != exclude:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(message)
                except:
                    disconnected.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected:
            self.disconnect(client_id)


# 创建连接管理器实例
manager = ConnectionManager()

# 工具結果通過回調直接發送，不需要緩存

# 為每個 client_id 維護獨立的 DatabaseClient 實例（最小侵入性）
clients_map: Dict[str, Any] = {}  # client_id -> DatabaseClient


@app.websocket("/ws/enhanced/{client_id}")
async def websocket_enhanced(
    websocket: WebSocket,
    client_id: str,
    config = Depends(get_config)  # 获取配置而不是client
):
    """
    增强的WebSocket端点
    支持：
    - 实时聊天
    - 文件上传
    - 流式分析结果
    - 工具执行通知
    """
    await manager.connect(websocket, client_id)
    
    # 為當前連接創建獨立的 DatabaseClient 實例（最小侵入性）
    from core.src.dbrheo.core.client import DatabaseClient
    if client_id not in clients_map:
        # 創建新的客戶端實例
        client = DatabaseClient(config)
        clients_map[client_id] = client
        print(f"[SESSION] Created new DatabaseClient for {client_id}")
    else:
        # 使用現有實例（同一個client_id重連時）
        client = clients_map[client_id]
        print(f"[SESSION] Reusing existing DatabaseClient for {client_id}")
    
    # 設置工具執行回調（最小侵入性）
    async def tool_output_handler(tool_name: str, call_id: str, output: dict):
        """工具執行輸出回調 - 直接發送到前端"""
        try:
            # 發送工具結果到前端，包含原始參數
            await manager.send_message(client_id, {
                "type": "tool_result",
                "tool_name": tool_name,
                "call_id": call_id,
                "result": output.get("llm_content") if output else None,
                "display": output.get("return_display") if output else None,
                "original_args": output.get("original_args") if output else None,  # 包含文件路徑信息
                "timestamp": datetime.now().isoformat()
            })
            print(f"[CALLBACK] Sent tool result for {tool_name} via callback")
        except Exception as e:
            print(f"[CALLBACK] Error sending tool result: {e}")
    
    # 將回調設置到調度器的正確屬性（最小侵入性）
    if hasattr(client, 'tool_scheduler') and client.tool_scheduler:
        client.tool_scheduler.on_tool_result = tool_output_handler
        print(f"[CALLBACK] Tool result handler set for client {client_id}")
    
    try:
        # 发送连接成功消息
        await manager.send_message(client_id, {
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            # 接收消息
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "chat":
                # 处理聊天消息
                await handle_chat_message(client_id, data, client)
                
            elif message_type == "analyze":
                # 处理分析请求
                await handle_analysis_request(client_id, data, client)
                
            elif message_type == "file_chunk":
                # 处理文件分块上传
                await handle_file_chunk(client_id, data)
                
            elif message_type == "tool_execute":
                # 直接执行工具
                await handle_tool_execution(client_id, data, client)
                
            elif message_type == "ping":
                # 心跳响应
                await manager.send_message(client_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                
            else:
                # 未知消息类型
                await manager.send_message(client_id, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        
        # 清理客戶端實例（釋放資源，允許刷新重置）
        if client_id in clients_map:
            del clients_map[client_id]
            print(f"[SESSION] Cleaned up DatabaseClient for {client_id}")
        
        # 保留会话文件信息，允许重连后继续使用
        # 如果需要清理，可以取消下面的注释：
        # if client_id in session_files:
        #     del session_files[client_id]
        print(f"Client {client_id} disconnected, session reset")
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)
        await websocket.close()


async def handle_chat_message(client_id: str, data: Dict, client):
    """处理聊天消息"""
    try:
        message = data.get("message", "")
        session_id = data.get("session_id", f"ws_{client_id}")
        
        # 特殊命令：列出文件
        if message.strip().lower() in ["/files", "files", "list"]:
            if client_id in session_files and session_files[client_id]:
                files_list = "\n".join([
                    f"[{i+1}] {f['name']} ({f['type']}) - file:{f['file_id']}"
                    for i, f in enumerate(session_files[client_id])
                ])
                response_msg = f"Available files for analysis:\n\n{files_list}\n\nYou can request analysis by mentioning the file name or type."
            else:
                response_msg = "No files uploaded yet. Please upload files first."
            
            await manager.send_message(client_id, {
                "type": "chat_content",
                "content": response_msg,
                "session_id": session_id
            })
            await manager.send_message(client_id, {
                "type": "chat_complete",
                "session_id": session_id
            })
            return
        
        # 注入文件上下文（如果有已上传的文件）
        if client_id in session_files and session_files[client_id]:
            files_info = "\n".join([
                f"- {f['name']} (file:{f['file_id']}) - {f['type']}"
                for f in session_files[client_id]
            ])
            enhanced_message = f"""[Available Files]
{files_info}

Note: Use file:ID format to access these files when user requests analysis.

[User Message]
{message}"""
        else:
            enhanced_message = message
        
        # 创建中止信号
        signal = SimpleAbortSignal()
        
        # 发送开始处理消息
        await manager.send_message(client_id, {
            "type": "chat_start",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        # 确保消息顺序（部署环境网络延迟优化）
        # 减少延迟以改善流式体验，同时保持消息顺序
        await asyncio.sleep(0.005)  # 5ms微延迟，平衡消息顺序和流式性能

        # 获取流式响应
        response_stream = client.send_message_stream(
            request=enhanced_message,
            signal=signal,
            prompt_id=session_id,
            turns=100
        )
        
        # 流式发送响应
        last_tool_name = None  # 记录最后一个工具调用
        
        async for chunk in response_stream:
            chunk_type = chunk.get("type")
            print(f"[DEBUG] WebSocket chunk: {chunk_type} - {chunk}")
            
            if chunk_type == "Content":
                # 发送内容块
                await manager.send_message(client_id, {
                    "type": "chat_content",
                    "content": chunk.get("value", ""),
                    "session_id": session_id
                })
                
            elif chunk_type == "ToolCallRequest":
                # 工具调用通知
                tool_value = chunk.get('value')
                tool_name = _extract_tool_name(tool_value)
                last_tool_name = tool_name  # 记录工具名称
                
                # 提取call_id
                call_id = None
                if hasattr(tool_value, 'call_id'):
                    call_id = tool_value.call_id
                elif isinstance(tool_value, dict):
                    call_id = tool_value.get('call_id')
                
                await manager.send_message(client_id, {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "parameters": chunk.get("parameters", {}),
                    "session_id": session_id
                })

                # 工具結果將通過回調自動發送，無需額外處理
                
            elif chunk_type == "ToolCallResult":
                # 工具结果
                tool_name = chunk.get("tool_name") or _extract_tool_name(chunk.get('value')) or last_tool_name
                await manager.send_message(client_id, {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": chunk.get("result"),
                    "session_id": session_id
                })
                
            # 检查是否是functionResponse类型（可能表示工具完成）
            elif 'functionResponse' in str(chunk):
                print(f"[DEBUG] Found functionResponse, sending tool_result")
                if last_tool_name:
                    await manager.send_message(client_id, {
                        "type": "tool_result",
                        "tool_name": last_tool_name,
                        "result": chunk,
                        "session_id": session_id
                    })
        
        # 发送完成消息
        await manager.send_message(client_id, {
            "type": "chat_complete",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Chat processing error: {str(e)}"
        })


async def handle_analysis_request(client_id: str, data: Dict, client):
    """处理内容分析请求"""
    try:
        request_id = str(uuid.uuid4())
        
        # 发送分析开始消息
        await manager.send_message(client_id, {
            "type": "analysis_start",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # 提取分析参数
        source_type = data.get("source_type", "text")
        content = data.get("content", "")
        options = data.get("options", {})
        
        # 构建Agent请求
        agent_request = f"""分析以下内容的可信度：
源类型: {source_type}
内容: {content}
选项: {json.dumps(options, ensure_ascii=False)}"""
        
        # 调用Agent
        signal = SimpleAbortSignal()
        response_stream = client.send_message_stream(
            request=agent_request,
            signal=signal,
            prompt_id=request_id,
            turns=10
        )
        
        # 流式发送分析进度
        tool_results = {}
        async for chunk in response_stream:
            chunk_type = chunk.get("type")
            
            if chunk_type == "ToolCallRequest":
                tool_name = _extract_tool_name(chunk.get('value'))
                await manager.send_message(client_id, {
                    "type": "analysis_progress",
                    "request_id": request_id,
                    "status": f"正在执行: {tool_name}",
                    "tool_name": tool_name
                })
                
            elif chunk_type == "ToolCallResult":
                tool_name = chunk.get("tool_name", "unknown")
                result = chunk.get("result", {})
                tool_results[tool_name] = result
                
                await manager.send_message(client_id, {
                    "type": "analysis_tool_result",
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "result": result
                })
        
        # 发送最终结果
        await manager.send_message(client_id, {
            "type": "analysis_complete",
            "request_id": request_id,
            "results": tool_results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Analysis error: {str(e)}",
            "request_id": request_id
        })


# 文件分块上传缓存
file_upload_cache: Dict[str, Dict] = {}

# 会话文件映射
session_files: Dict[str, List[Dict]] = {}  # client_id -> [{"file_id": str, "name": str, "type": str}]

async def handle_file_chunk(client_id: str, data: Dict):
    """处理文件分块上传"""
    try:
        upload_id = data.get("upload_id")
        chunk_index = data.get("chunk_index")
        total_chunks = data.get("total_chunks")
        chunk_data = data.get("data")  # Base64编码的块
        file_info = data.get("file_info", {})
        
        # 初始化上传缓存 - 只在第一次创建
        if upload_id not in file_upload_cache:
            file_upload_cache[upload_id] = {
                "chunks": {},
                "total_chunks": total_chunks,
                "file_info": file_info,
                "client_id": client_id
            }
            print(f"[UPLOAD] New upload started: {upload_id}, expecting {total_chunks} chunks")
        else:
            # 验证total_chunks一致性
            if file_upload_cache[upload_id]["total_chunks"] != total_chunks:
                print(f"[UPLOAD] WARNING: total_chunks mismatch for {upload_id}: "
                      f"cached={file_upload_cache[upload_id]['total_chunks']}, received={total_chunks}")
        
        # 存储块
        file_upload_cache[upload_id]["chunks"][chunk_index] = chunk_data
        
        # 详细调试信息
        received_chunks = len(file_upload_cache[upload_id]["chunks"])
        print(f"[UPLOAD] Chunk {chunk_index}/{total_chunks-1} received for {file_info.get('name', 'unknown')}")
        print(f"[UPLOAD] Size: {len(chunk_data)} bytes, Total received: {received_chunks}/{total_chunks}")
        print(f"[UPLOAD] Cached chunks: {sorted(file_upload_cache[upload_id]['chunks'].keys())}")
        
        # 发送进度更新
        progress = (received_chunks / total_chunks) * 100
        
        await manager.send_message(client_id, {
            "type": "upload_progress",
            "upload_id": upload_id,
            "progress": progress,
            "received_chunks": received_chunks,
            "total_chunks": total_chunks
        })
        
        # 检查是否所有块都已接收 - 确保所有索引都存在
        expected_chunks = set(range(total_chunks))
        received_chunk_indices = set(file_upload_cache[upload_id]["chunks"].keys())
        
        if expected_chunks == received_chunk_indices:
            print(f"[UPLOAD] All chunks received for {file_info.get('name', 'unknown')}, merging...")
            
            # 重要：每个块都是独立的Base64编码，需要先解码再合并
            chunks = file_upload_cache[upload_id]["chunks"]
            binary_chunks = []
            
            for i in range(total_chunks):
                chunk_base64 = chunks[i]
                # 解码每个Base64块为二进制
                import base64
                try:
                    binary_chunk = base64.b64decode(chunk_base64)
                    binary_chunks.append(binary_chunk)
                    print(f"[UPLOAD] Decoded chunk {i}: {len(binary_chunk)} bytes")
                except Exception as e:
                    print(f"[UPLOAD] Failed to decode chunk {i}: {e}")
                    raise
            
            # 合并所有二进制数据
            complete_binary = b"".join(binary_chunks)
            print(f"[UPLOAD] Merged binary size: {len(complete_binary)} bytes (expected: {file_info.get('size', 0)} bytes)")
            
            # 重新编码为Base64（为了兼容现有的save_base64函数）
            complete_data = base64.b64encode(complete_binary).decode('utf-8')
            print(f"[UPLOAD] Re-encoded Base64 size: {len(complete_data)} bytes")
            
            # 保存文件
            try:
                from .aicca_api import file_storage
                file_id = await file_storage.save_base64(
                    complete_data,
                    file_info.get("name", "upload.bin")
                )
                
                # 清理缓存
                del file_upload_cache[upload_id]
                print(f"[UPLOAD] Upload completed and cleaned: {upload_id}")
            except Exception as e:
                # 清理缓存
                if upload_id in file_upload_cache:
                    del file_upload_cache[upload_id]
                
                # 发送错误消息
                await manager.send_message(client_id, {
                    "type": "error",
                    "upload_id": upload_id,
                    "message": f"Failed to save file: {str(e)}"
                })
                print(f"File upload error for {upload_id}: {e}")
                return
            
            # 将文件添加到会话文件列表
            if client_id not in session_files:
                session_files[client_id] = []
            session_files[client_id].append({
                "file_id": file_id,
                "name": file_info.get("name", "unknown"),
                "type": file_info.get("type", "unknown"),
                "size": file_info.get("size", 0)
            })
            
            # 发送完成消息
            await manager.send_message(client_id, {
                "type": "upload_complete",
                "upload_id": upload_id,
                "file_id": file_id,
                "file_info": file_info
            })
            print(f"[UPLOAD] Success: {file_info.get('name', 'unknown')} saved as {file_id}")
            
    except Exception as e:
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"File upload error: {str(e)}",
            "upload_id": data.get("upload_id")
        })


async def handle_tool_execution(client_id: str, data: Dict, client):
    """处理工具执行请求"""
    try:
        tool_name = data.get("tool_name")
        parameters = data.get("parameters", {})
        execution_id = str(uuid.uuid4())
        
        # 获取工具
        try:
            from dbrheo.tools.registry import DatabaseToolRegistry
            from dbrheo.api.dependencies import get_config
        except ImportError:
            from ..core.src.dbrheo.tools.registry import DatabaseToolRegistry
            from ..core.src.dbrheo.api.dependencies import get_config
        
        config = get_config()
        registry = DatabaseToolRegistry(config)
        tool = registry.get_tool_by_name(tool_name)
        
        if not tool:
            await manager.send_message(client_id, {
                "type": "error",
                "message": f"Tool not found: {tool_name}",
                "execution_id": execution_id
            })
            return
        
        # 发送执行开始消息
        await manager.send_message(client_id, {
            "type": "tool_execution_start",
            "execution_id": execution_id,
            "tool_name": tool_name,
            "parameters": parameters
        })
        
        # 定义输出更新回调
        async def update_output(output: str):
            await manager.send_message(client_id, {
                "type": "tool_execution_update",
                "execution_id": execution_id,
                "output": output
            })
        
        # 执行工具
        signal = SimpleAbortSignal()
        result = await tool.execute(
            params=parameters,
            signal=signal,
            update_output=update_output
        )
        
        # 发送执行结果
        await manager.send_message(client_id, {
            "type": "tool_execution_complete",
            "execution_id": execution_id,
            "tool_name": tool_name,
            "result": result.to_dict() if hasattr(result, 'to_dict') else str(result)
        })
        
    except Exception as e:
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Tool execution error: {str(e)}",
            "execution_id": data.get("execution_id")
        })


def _extract_tool_name(tool_value) -> str:
    """从工具值中提取工具名称"""
    if hasattr(tool_value, 'name'):
        return tool_value.name
    elif isinstance(tool_value, dict):
        return tool_value.get('name', 'unknown')
    else:
        return 'unknown'



@app.get("/ws/connections")
async def get_active_connections():
    """获取活跃的WebSocket连接信息"""
    return {
        "total_connections": len(manager.active_connections),
        "connections": [
            {
                "client_id": client_id,
                "info": info
            }
            for client_id, info in manager.connection_info.items()
        ]
    }


print("增强的WebSocket支持已加载")