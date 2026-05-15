#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# A股行情数据拉取脚本
# ═══════════════════════════════════════════════════════════════
# 用法:
#   bash scripts/fetch_data.sh                  # 拉取今日收盘数据
#   bash scripts/fetch_data.sh --date 2026-05-15  # 指定日期
#   bash scripts/fetch_data.sh --suffix noon      # 盘中快照
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FETCH_SCRIPT="$HOME/Jarvis/fetch_a_stock_data.py"

if [ ! -f "$FETCH_SCRIPT" ]; then
    echo "❌ 未找到数据拉取脚本: $FETCH_SCRIPT"
    echo ""
    echo "请确保 ~/Jarvis/fetch_a_stock_data.py 存在，或手动放置A股CSV到:"
    echo "  ~/Jarvis/A股行情信息/"
    exit 1
fi

echo "📊 拉取A股行情数据..."
python3 "$FETCH_SCRIPT" "$@"

if [ $? -eq 0 ]; then
    echo "✅ 数据拉取完成"
    echo "   输出目录: ~/Jarvis/A股行情信息/"
else
    echo "❌ 数据拉取失败"
    exit 1
fi
