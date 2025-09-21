"""
API层 - FastAPI应用和路由定义
提供RESTful API和WebSocket接口
"""

from .app import create_app
from .routes import chat_router  # database_router removed for AICCA

__all__ = [
    "create_app",
    "chat_router",
    # "database_router"  # REMOVED: AICCA不需要数据库路由
]
