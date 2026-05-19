#!/bin/bash
# AI投研助手 - 一键初始化脚本
# 用法: bash setup/setup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== AI投研助手 初始化 ==="
echo "项目目录: $PROJECT_DIR"

# 1. 安装 Python 依赖
echo ""
echo "[1/5] 安装 Python 依赖..."
cd "$PROJECT_DIR"
pip3 install -r requirements.txt 2>/dev/null || pip3 install fastapi uvicorn akshare pandas numpy openai pyyaml

# 2. 安装前端依赖并构建
echo ""
echo "[2/5] 构建前端..."
cd "$PROJECT_DIR/frontend"
npm install 2>/dev/null
npm run build
cd "$PROJECT_DIR"

# 3. 初始化数据库
echo ""
echo "[3/5] 初始化数据库..."
DB_PATH="$HOME/Jarvis/ai_trading"
mkdir -p "$DB_PATH"
if [ -f "$DB_PATH/stock_archive.db" ]; then
    echo "数据库已存在，跳过创建"
else
    echo "创建数据库并导入种子数据..."
    sqlite3 "$DB_PATH/stock_archive.db" < "$PROJECT_DIR/setup/seed.sql"
    echo "✅ 数据库初始化完成"
fi

# 4. 创建行情数据目录
echo ""
echo "[4/5] 创建行情数据目录..."
mkdir -p "$HOME/Jarvis/A股行情信息"
mkdir -p "$HOME/Jarvis/复盘"

# 5. 启动服务
echo ""
echo "[5/5] 启动服务..."
echo "运行: python3 run.py"
echo ""
echo "================================="
echo "✅ 初始化完成！"
echo "访问: http://localhost:8080"
echo "================================="
