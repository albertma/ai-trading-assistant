"""
技术面分析服务
技术指标、均线、K线形态识别
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.patterns import detect_patterns, detect_cup_handle
from backend.services.db_client import get_db
from backend.services.market_service import get_daily_history, get_ma, get_stock_news


class TechnicalAnalyzer:
    """技术面分析 — 均线/MACD/RSI/K线形态/新闻"""

    @staticmethod
    def get_stock_list() -> dict[str, str]:
        """从SQLite stock_info表获取股票名称映射 {code: name}"""
        conn = get_db()
        rows = conn.execute("SELECT code, name FROM stock_info").fetchall()
        conn.close()
        return {r["code"]: r["name"] for r in rows}

    @staticmethod
    def calc_ma(df: pd.DataFrame, period: int) -> float | None:
        """计算均线值"""
        if df is None or df.empty or len(df) < period:
            return None
        close = df["close"].tail(period)
        return round(float(close.mean()), 2)

    @staticmethod
    def calc_macd(df: pd.DataFrame) -> dict | None:
        """计算MACD指标"""
        if df is None or df.empty or len(df) < 26:
            return None
        close = df["close"].values.astype(float)
        ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
        dif = ema12 - ema26
        dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values
        hist = 2 * (dif - dea)
        return {
            "dif": round(float(dif[-1]), 4),
            "dea": round(float(dea[-1]), 4),
            "hist": round(float(hist[-1]), 4),
        }

    @staticmethod
    def calc_rsi(df: pd.DataFrame, period: int = 14) -> float | None:
        """计算RSI指标"""
        if df is None or df.empty or len(df) <= period:
            return None
        close = df["close"].values.astype(float)
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - 100 / (1 + rs), 2)

    @staticmethod
    def calc_bollinger(df: pd.DataFrame, period: int = 20) -> dict | None:
        """计算布林带"""
        if df is None or df.empty or len(df) < period:
            return None
        close = df["close"].tail(period)
        ma = close.mean()
        std = close.std()
        return {
            "upper": round(float(ma + 2 * std), 2),
            "mid": round(float(ma), 2),
            "lower": round(float(ma - 2 * std), 2),
        }

    @classmethod
    def analyze(cls, code: str) -> dict[str, Any]:
        """全量技术分析"""
        df = get_daily_history(code)
        if df is None or df.empty:
            return {"error": "no data"}

        close_val = float(df["close"].iloc[-1]) if not df.empty else 0
        pre_close = float(df["close"].iloc[-2]) if len(df) > 1 else close_val
        change_pct = round((close_val - pre_close) / pre_close * 100, 2) if pre_close else 0

        high = float(df["high"].max())
        low = float(df["low"].min())
        volume = float(df["volume"].sum())
        amount = float((df["volume"] * df["close"]).sum()) if "volume" in df.columns else 0

        ma5 = cls.calc_ma(df, 5)
        ma10 = cls.calc_ma(df, 10)
        ma20 = cls.calc_ma(df, 20)
        ma60 = cls.calc_ma(df, 60)
        ma200 = cls.calc_ma(df, 200)

        # 均线多头排列检查
        bullish = all((
            ma5 is not None and ma10 is not None and ma20 is not None and ma60 is not None,
            ma5 > ma10 > ma20 > ma60,
        ))

        macd = cls.calc_macd(df)
        rsi14 = cls.calc_rsi(df)

        # 趋势状态
        if bullish and rsi14 and rsi14 > 60:
            trend_status = "强势上涨"
        elif ma5 and ma10 and ma5 > ma10:
            trend_status = "短期上涨"
        elif ma5 and ma10 and ma5 < ma10:
            trend_status = "短期下跌"
        else:
            trend_status = "震荡"

        # K线形态
        patterns = detect_patterns(df) or []
        cup_handle = detect_cup_handle(df) or []

        result = {
            "current_price": round(close_val, 2),
            "change_pct": change_pct,
            "high": round(high, 2),
            "low": round(low, 2),
            "volume": round(volume, 0),
            "amount": round(amount, 0),
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "ma200": ma200,
            "bullish_alignment": bullish,
            "trend_status": trend_status,
            "macd": macd,
            "rsi_14": rsi14,
            "bollinger": cls.calc_bollinger(df),
            "kline_patterns": patterns + cup_handle,
        }

        return result

    @staticmethod
    def get_news(code: str, limit: int = 10) -> list[dict]:
        """获取个股新闻"""
        news = get_stock_news(code)
        return news[:limit] if news else []

    @staticmethod
    def quick_risk_check(code: str) -> dict[str, Any]:
        """快速买入风控检查"""
        df = get_daily_history(code)
        if df is None or df.empty:
            return {"pass": False, "reason": "无行情数据"}

        close = float(df["close"].iloc[-1])
        change = (close / float(df["close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0

        ma20_val = TechnicalAnalyzer.calc_ma(df, 20)
        ma60_val = TechnicalAnalyzer.calc_ma(df, 60)

        issues = []

        # 涨幅检查
        if change > 9.5:
            issues.append({"type": "danger", "msg": f"涨幅{change:.1f}%，接近涨停，追高风险大"})
        elif change > 5:
            issues.append({"type": "warning", "msg": f"涨幅{change:.1f}%，追高需谨慎"})

        # 均线检查
        if ma20_val and close < ma20_val:
            issues.append({"type": "warning", "msg": f"收盘价{close:.2f} < MA20({ma20_val:.2f})，短期趋势偏弱"})
        if ma60_val and close < ma60_val:
            issues.append({"type": "danger", "msg": f"收盘价{close:.2f} < MA60({ma60_val:.2f})，中期趋势偏弱"})

        return {
            "pass": len([i for i in issues if i["type"] == "danger"]) == 0,
            "issues": issues,
            "total_issues": len(issues),
            "danger_count": sum(1 for i in issues if i["type"] == "danger"),
        }
