#!/usr/bin/env python3
"""
小红书自动发布系统 - 主入口
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from web.app import app
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("📕 小红书自动发布系统")
    print("=" * 50)
    print("📍 访问地址：http://localhost:8080")
    print("📝 日志：查看终端输出")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080)
