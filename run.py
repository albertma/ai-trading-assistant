"""
启动脚本 — 在项目根目录运行
用法: python3 run.py
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from backend.config import HOST, PORT, DEBUG
from backend.main import app
import uvicorn

if __name__ == "__main__":
    print(f"🚀 AI投研助手启动: http://localhost:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
