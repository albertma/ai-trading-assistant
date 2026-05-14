"""仓位管理模块 — 行情价格获取（委托 akshare_client）"""

from datetime import date, timedelta

import sqlite3
from pathlib import Path

from backend.config import MARKET_DATA_DIR
from backend.services.external.akshare_client import (
    get_hk_stock_daily_price,
    get_hk_stock_prices_batch,
    get_us_stock_daily_price,
    get_us_stock_prices_batch,
)
from .constants import CRYPTO_SYMBOLS

_STOCK_DB = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"


def _get_market_from_db(code: str) -> str | None:
    """优先从 stock_info.market 查询市场"""
    try:
        conn = sqlite3.connect(str(_STOCK_DB))
        row = conn.execute(
            "SELECT market FROM stock_info WHERE code = ?", (code.strip(),)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return None


def detect_market(code: str) -> str:
    """判断股票所属市场：优先查 stock_info.market，代码格式兜底"""
    c = code.strip().upper()

    # ① 优先从 SQLite stock_info 表查
    db_market = _get_market_from_db(code)
    if db_market:
        return db_market

    # ② 已知名单
    if c in CRYPTO_SYMBOLS:
        return "crypto"

    # ③ 代码格式推断
    if c.isdigit():
        if len(c) == 6:
            return "a_stock"
        if len(c) == 5:
            return "hk_stock"
        return "other"
    return "us_stock"


def get_current_price(code: str) -> float | None:
    """从本地行情CSV或实时API获取最新价"""
    market = detect_market(code)

    # A股：从本地CSV读取
    if market == "a_stock":
        today = date.today()
        for i in range(5):
            d = today - timedelta(days=i)
            for prefix in ["沪深京A股", "沪深重要指数"]:
                path = MARKET_DATA_DIR / f"{prefix}{d.isoformat()}.csv"
                if path.exists():
                    import pandas as pd
                    try:
                        df = pd.read_csv(path, encoding="utf-16", sep="\t")
                        df["代码"] = df["代码"].astype(str).str.strip("'\"")
                        match = df[df["代码"] == code]
                        if not match.empty:
                            val = str(match.iloc[0].get("最新", "0"))
                            val = val.replace("--", "0").strip()
                            return float(val) if val else None
                    except Exception:
                        pass
        return None

    # 港股：委托 akshare_client
    if market == "hk_stock":
        return get_hk_stock_daily_price(code)

    # 美股：委托 akshare_client
    if market == "us_stock":
        return get_us_stock_daily_price(code)

    return None


def get_us_prices_batch(codes: list[str]) -> dict[str, float]:
    """美股价格：委托 akshare_client 批量获取"""
    return get_us_stock_prices_batch(codes)


def get_hk_prices_batch(codes: list[str]) -> dict[str, float]:
    """港股价格：委托 akshare_client 批量获取"""
    return get_hk_stock_prices_batch(codes)
