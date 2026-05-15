#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# AI 投研助手 — 完整环境搭建脚本
# ═══════════════════════════════════════════════════════════════
# 用法: bash scripts/setup.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "════════════════════════════════════════════════"
echo "  AI 投研助手 — 环境搭建"
echo "════════════════════════════════════════════════"

# ── 1. Python 依赖 ──
echo ""
echo "📦 [1/4] 安装 Python 依赖..."
python3 -m pip install --upgrade pip -q
pip install -r scripts/requirements.txt -q
echo "  ✅ Python 依赖安装完成"

# ── 2. 前端 ──
echo ""
echo "📦 [2/4] 安装前端依赖并构建..."
if [ ! -d "frontend/node_modules" ]; then
    cd frontend
    npm install --silent
    cd "$ROOT_DIR"
    echo "  ✅ 前端依赖安装完成"
else
    echo "  ⏩ node_modules 已存在，跳过安装"
fi

# 构建前端
cd frontend
npm run build --silent
cd "$ROOT_DIR"
echo "  ✅ 前端构建完成"

# ── 3. 数据目录 ──
echo ""
echo "📁 [3/4] 创建数据目录结构..."
mkdir -p ~/Jarvis/{A股行情信息,复盘,个股分析,reports,ai_trading}
echo "  ✅ 数据目录结构就绪"
echo "     ~/Jarvis/A股行情信息/   (A股日线CSV)"
echo "     ~/Jarvis/复盘/          (复盘报告)"
echo "     ~/Jarvis/个股分析/       (个股分析)"
echo "     ~/Jarvis/reports/       (新闻/早报)"
echo "     ~/Jarvis/ai_trading/    (SQLite数据库)"

# ── 4. 验证 ──
echo ""
echo "🔍 [4/4] 环境验证..."
PY_OK=true
python3 -c "import fastapi; print(f'  ✅ fastapi {fastapi.__version__}')" 2>/dev/null || { echo "  ❌ fastapi 未安装"; PY_OK=false; }
python3 -c "import pandas; print(f'  ✅ pandas {pandas.__version__}')" 2>/dev/null || { echo "  ❌ pandas 未安装"; PY_OK=false; }
python3 -c "import akshare; print(f'  ✅ akshare {akshare.__version__}')" 2>/dev/null || { echo "  ⚠️ akshare 未安装（部分功能不可用）"; }
python3 -c "import openai; print(f'  ✅ openai {openai.__version__}')" 2>/dev/null || { echo "  ⚠️ openai 未安装（AI功能不可用）"; }

# 前端
if [ -d "frontend/node_modules" ]; then
    echo "  ✅ node_modules 就绪"
fi
if [ -f "frontend/dist/index.html" ]; then
    echo "  ✅ 前端构建产物就绪"
fi

echo ""
if [ "$PY_OK" = true ]; then
    echo "════════════════════════════════════════════════"
    echo "  ✅ 环境搭建完成！"
    echo ""
    echo "  启动: python3 run.py"
    echo "  访问: http://localhost:8080"
    echo "════════════════════════════════════════════════"
else
    echo "  ⚠️ 部分依赖安装失败，请检查上面日志"
    exit 1
fi
