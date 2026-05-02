"""
AI投研助手 - 配置文件
"""
import os
from pathlib import Path

# ========== 基础路径 ==========
HOME = Path.home()
PROJECT_ROOT = Path(__file__).parent.parent

# Jarvis数据目录（软链/硬编码）
JARVIS_DIR = HOME / "Jarvis"

# ========== 数据路径 ==========
MARKET_DATA_DIR = JARVIS_DIR / "A股行情信息"        # 沪深京A股CSV
POSITION_FILE = JARVIS_DIR / "仓位管理.csv"          # 持仓CSV
REPORT_DIR = JARVIS_DIR / "复盘"                     # 复盘报告
ANALYSIS_DIR = JARVIS_DIR / "个股分析"               # 个股分析
NEWS_DIR = JARVIS_DIR / "reports"                    # 新闻/早报

# ========== 缓存 ==========
CACHE_DIR = PROJECT_ROOT / "backend" / "data"
CACHE_TTL_SECONDS = 30 * 60  # 个股分析缓存30分钟

# ========== 服务配置 ==========
HOST = "0.0.0.0"
PORT = 8080
DEBUG = True

# ========== akshare配置 ==========
AKSHARE_TIMEOUT = 30  # 秒
