#!/usr/bin/env python3
"""
AICCA Web API服务器
唯一权威启动文件
"""

import os
import sys
from pathlib import Path

# 设置项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "packages" / "core" / "src"))

# 加载环境变量
env_file = project_root / ".env"
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# 导入核心app
from dbrheo.api.app import app

# 加载AICCA扩展
import packages.api.aicca_api
import packages.api.websocket_enhanced

# 主程序入口
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("AICCA - AI Content Credibility Agent")
    print("Web API Server")
    print("=" * 60)
    print(f"Project: {project_root}")
    print(f"API Key: {'✓' if os.getenv('GOOGLE_API_KEY') else '✗'}")
    print("=" * 60)
    print("Starting server on http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("API Info: http://localhost:8000/api/info")
    print("=" * 60)
    
    uvicorn.run(
        "aicca_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )