"""行情数据统一服务。
编排层：只做数据编排和网络API调用（腾讯K线、akshare新闻等），
不直接操作文件或数据库（委托给 csv_client / db_client）。
"""
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from backend.services.external.csv_client import (
    find_latest_csv,
    read_market_csv,
    get_price_from_csv,
    get_prices_from_csv,
    get_stock_detail_from_csv,
    get_industry_data,
    get_market_overview as _csv_market_overview,
)
from backend.services.db_client import get_stock_list, get_stock_name
from backend.config import POSITION_FILE


# ═══════════════════════════════════════════════════════════
# 1. 股票列表（来自db_client）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 2. 市场概况（来自csv_client）
# ═══════════════════════════════════════════════════════════

def get_market_overview() -> dict:
    """全市场概览"""
    return _csv_market_overview()


# ═══════════════════════════════════════════════════════════
# 3. 实时价格（CSV + 仓位文件兜底）
# ═══════════════════════════════════════════════════════════

def _detect_market(code: str) -> str:
    """判断股票所属市场：优先查 stock_info.market"""
    import sqlite3
    from pathlib import Path
    try:
        db = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT market FROM stock_info WHERE code = ?", (code.strip(),)).fetchone()
        conn.close()
        if row and row[0]:
            m = row[0]
            # 统一返回值：a_stock / hk_stock / us_stock / crypto / unknown
            if m in ("沪市", "科创板", "深市", "创业板", "北证"):
                return "a_stock"
            if m in ("hk_stock", "us_stock"):
                return m
    except Exception:
        pass
    code = code.strip()
    if code.endswith((".us", ".US")):
        return "us_stock"
    if code.endswith((".hk", ".HK")):
        return "hk_stock"
    if code.isdigit():
        return "a_stock"
    if code.startswith(("6", "0", "3", "2", "4", "8")):
        return "a_stock"
    if code.upper() in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA", 
                        "DOT", "DOGE", "AVAX", "HYPE"):
        return "crypto"
    return "unknown"


def _get_price_from_position_file(code: str) -> float | None:
    """从仓位CSV读取非A股价格"""
    from backend.services.external.csv_client import get_price_from_position_file
    return get_price_from_position_file(code)


def _get_prices_from_position_file(codes: list[str]) -> dict[str, float]:
    """从仓位CSV批量读取非A股价格"""
    from backend.services.external.csv_client import get_prices_from_position_file
    return get_prices_from_position_file(codes)


def get_current_price(code: str) -> float | None:
    """获取个股最新价（A股从CSV，其他从仓位文件）"""
    market = _detect_market(code)

    if market == "a_stock":
        return get_price_from_csv(code)

    # 非A股：从仓位文件读取已保存的价格
    return _get_price_from_position_file(code)


def get_prices_batch(codes: list[str]) -> dict[str, float]:
    """批量获取多个股票最新价"""
    # 先批量读CSV（A股）
    result = get_prices_from_csv(codes)
    # 非A股从仓位文件补充
    remaining = [c for c in codes if c not in result]
    if remaining:
        result.update(_get_prices_from_position_file(remaining))
    return result


# ═══════════════════════════════════════════════════════════
# 4. K线数据（腾讯API + akshare）
# ═══════════════════════════════════════════════════════════

def get_daily_history(code: str, max_days: int = 250) -> pd.DataFrame | None:
    """获取个股日线行情（统一走 ensure_kline，A股/美股同路径）"""
    from backend.services.db_client import ensure_kline

    ok, records = ensure_kline(code)
    if not ok or not records:
        return None

    # 按日期正序，取最近 max_days
    records.sort(key=lambda r: r["date"])
    records = records[-max_days:]

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df["pct_change"] = df["close"].pct_change() * 100
    # 美股 volume 是实际股数（不*100），A 股在 stock_db 入库时已统一
    df["amount"] = df["volume"] * (df["high"] + df["low"] + df["close"]) / 3
    return df


def get_ma(df: pd.DataFrame, period: int) -> float | None:
    """计算均线值"""
    if df is None or len(df) < period:
        return None
    return round(float(df["close"].tail(period).mean()), 2)


# ═══════════════════════════════════════════════════════════
# 5. 个股资料（akshare）
# ═══════════════════════════════════════════════════════════

def get_stock_info(code: str) -> dict | None:
    """从akshare获取个股详细资料"""
    from backend.services.db_client import get_stock_info as _get_info
    return _get_info(code)


# ═══════════════════════════════════════════════════════════
# 6. 新闻（akshare）
# ═══════════════════════════════════════════════════════════

def get_stock_news(code: str, limit: int = 5) -> list[dict]:
    """从akshare获取个股新闻"""
    try:
        import akshare as ak
        news = ak.stock_news_em(symbol=code)
        if news is not None and not news.empty:
            return news.head(limit).to_dict("records")
    except Exception:
        pass
    return []
