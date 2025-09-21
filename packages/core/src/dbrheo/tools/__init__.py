"""
工具系统 - AICCA内容信任工具
遵循"工具极简，智能在Agent层"的设计原则
"""

from .base import DatabaseTool
from .registry import DatabaseToolRegistry
# from .sql_tool import SQLTool  # REMOVED: AICCA不需要
# from .schema_discovery import SchemaDiscoveryTool  # REMOVED: AICCA不需要

# 导入保留的工具
from .file_read_tool import FileReadTool
from .file_write_tool import FileWriteTool
from .web_search_tool import WebSearchTool
from .web_fetch_tool import WebFetchTool
from .directory_list_tool import DirectoryListTool
from .code_execution_tool import CodeExecutionTool
from .shell_tool import ShellTool

__all__ = [
    "DatabaseTool",
    "DatabaseToolRegistry",
    # "SQLTool",  # REMOVED
    # "SchemaDiscoveryTool",  # REMOVED
    "FileReadTool",
    "FileWriteTool",
    "WebSearchTool",
    "WebFetchTool",
    "DirectoryListTool",
    "CodeExecutionTool",
    "ShellTool"
]
