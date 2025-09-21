"""
API路由模块 - 组织不同功能的路由
"""

from .chat import chat_router
# from .database import database_router  # REMOVED: AICCA不需要数据库功能
from .websocket import websocket_router

__all__ = [
    "chat_router",
    # "database_router",  # REMOVED: AICCA不需要
    "websocket_router"
]
