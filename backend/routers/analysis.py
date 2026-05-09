"""
个股深度分析 API
"""
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
from datetime import date, datetime
import json
import os
from pathlib import Path

from backend.config import MARKET_DATA_DIR, CACHE_DIR, CACHE_TTL_SECONDS
from backend.patterns import detect_patterns
from backend.services.db_client import get_db
from backend.services.market_service import get_daily_history, get_ma, get_stock_news
from backend.services.financial_service import get_financial_reports

router = APIRouter()


def _get_stock_list() -> dict:
    """从SQLite stock_info表获取股票名称映射 {code: name}"""
    conn = get_db()
    rows = conn.execute("SELECT code, name FROM stock_info").fetchall()
    conn.close()
    return {r["code"]: r["name"] for r in rows}


def _get_ma(df: pd.DataFrame, period: int) -> float | None:
    """计算均线值"""
    return get_ma(df, period)


def _check_trade_rules(*args, **kwargs) -> dict:
    """已废弃：由数据库风控规则替代"""
    return {"passed": True, "checks": []}


def _get_daily_history(code: str, max_days: int = 250) -> pd.DataFrame | None:
    """获取个股日线行情"""
    return get_daily_history(code, max_days)


@router.get("/{code}")
def analyze_stock(code: str):
    """个股深度分析：基本面+技术面+新闻"""
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")

    if not name:
        raise HTTPException(404, f"未找到股票代码 {code}")

    # --- 1. 技术面分析 ---
    tech_data = None
    df = _get_daily_history(code)
    if df is not None and len(df) > 20:
        close = float(df["close"].iloc[-1])
        pct = float(df["pct_change"].iloc[-1]) if "pct_change" in df.columns else 0

        ma5 = _get_ma(df, 5)
        ma10 = _get_ma(df, 10)
        ma20 = _get_ma(df, 20)
        ma30 = _get_ma(df, 30)
        ma60 = _get_ma(df, 60)
        ma200 = _get_ma(df, 200)

        # MACD
        if len(df) >= 26:
            exp12 = df["close"].ewm(span=12, adjust=False).mean()
            exp26 = df["close"].ewm(span=26, adjust=False).mean()
            macd_line = exp12 - exp26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            macd = {
                "dif": round(float(macd_line.iloc[-1]), 4),
                "dea": round(float(signal_line.iloc[-1]), 4),
                "hist": round(float(macd_hist.iloc[-1]), 4),
            }
        else:
            macd = None

        # RSI(14)
        if len(df) >= 14:
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = round(float(100 - (100 / (1 + rs.iloc[-1]))), 2) if not rs.empty and not pd.isna(rs.iloc[-1]) else None
        else:
            rsi = None

        # 成交额
        volume_amount = float(df["amount"].iloc[-1]) if "amount" in df.columns else None

        # 均线多头排列 + 趋势状态 (四级 + 震荡)
        bullish_alignment = False
        trend_status = "震荡"
        if all(v is not None for v in [ma5, ma10, ma20, ma60]):
            bullish_alignment = ma5 > ma10 > ma20 > ma60
            if bullish_alignment:
                trend_status = "多头"
            elif ma5 < ma10 < ma20 < ma60:
                trend_status = "空头"
            elif ma5 > ma20 and close > ma60:
                trend_status = "偏多"
            elif ma5 < ma20 and close < ma60:
                trend_status = "偏空"

        # K线形态识别
        kline_patterns = detect_patterns(df)

        tech_data = {
            "current_price": close,
            "change_pct": round(pct, 2),
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma30": ma30, "ma60": ma60, "ma200": ma200,
            "macd": macd,
            "rsi_14": rsi,
            "volume_amount": volume_amount,
            "bullish_alignment": bullish_alignment,
            "trend_status": trend_status,
            "kline_patterns": kline_patterns,
        }

    # --- 2. 基本面分析 ---
    fund_data = None

    # --- 3. 估值 ---
    valuation = None

    # --- 4. 交易铁律检查 ---
    risk_check = None
    if tech_data:
        # 计算近10日日均成交额（元）—— 从K线量价估算
        avg_amount_10d = None
        if df is not None and "volume" in df.columns and "close" in df.columns:
            try:
                vols = pd.to_numeric(df["volume"].tail(10), errors="coerce")
                prices = pd.to_numeric(df["close"].tail(10), errors="coerce")
                if len(vols) >= 5:
                    # 腾讯API成交量单位不确定（主板手/科创板股）
                    # 用 heuristic：若 vol*100*price > 市值上限不合理，则不乘100
                    vol = float(vols.mean())
                    price = float(prices.mean())
                    # 估算：若 vol*100*price > 300亿（A股单日成交额上限），认为已是股单位
                    if vol * 100 * price > 30_000_000_000:
                        avg_amount_10d = vol * price
                    else:
                        avg_amount_10d = vol * 100 * price
                    avg_amount_10d = round(avg_amount_10d, 2)
            except Exception:
                pass

        risk_check = _check_trade_rules(
            tech_data["current_price"],
            tech_data["ma200"],
            tech_data["change_pct"],
            tech_data.get("ma20"),
            tech_data.get("ma10"),
            tech_data.get("ma30"),
            tech_data.get("ma60"),
            avg_amount_10d,
        )

    # --- 5. 新闻 ---
    news_list = []
    try:
        news_items = get_stock_news(code, 5)
        for n in news_items:
            news_list.append({
                "title": n.get("新闻标题", n.get("标题", n.get("title", ""))),
                "time": str(n.get("发布时间", n.get("publish_time", "")))[:19],
                "source": n.get("文章来源", ""),
                "url": n.get("新闻链接", n.get("url", n.get("链接", ""))),
            })
    except:
        pass

    # --- 6. 自定义风控规则评估 ---
    custom_risk = None
    if tech_data and df is not None:
        try:
            reports = get_financial_reports(code, 1)
            fin = dict(reports[0]) if reports else None
            patterns = []
            try:
                patterns = detect_patterns(df) if df is not None else []
            except:
                pass
            from backend.services.db_client import evaluate_risk_rules
            custom_risk = evaluate_risk_rules(code, tech_data, fin, None, patterns, avg_amount_10d)
        except:
            pass

    return {
        "code": code,
        "name": name,
        "technical": tech_data,
        "fundamental": fund_data,
        "valuation": valuation,
        "risk_check": risk_check,
        "custom_risk": custom_risk,
        "news": news_list,
    }


@router.get("/{code}/risk")
def risk_check(code: str):
    """仅做买入风控检查（快速）"""
    result = analyze_stock(code)
    return {
        "code": code,
        "name": result["name"],
        "risk_check": result.get("risk_check"),
        "current_price": result.get("technical", {}).get("current_price"),
    }
