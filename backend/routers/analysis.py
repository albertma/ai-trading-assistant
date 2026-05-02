"""
个股深度分析 API
"""
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
import akshare as ak
from datetime import date, datetime
import json
import os
from pathlib import Path

from backend.config import MARKET_DATA_DIR, CACHE_DIR, CACHE_TTL_SECONDS
from backend.patterns import detect_patterns

router = APIRouter()


def _get_stock_list() -> dict:
    """从本地CSV获取股票名称映射 {code: name}"""
    today = date.today()
    for i in range(4):
        d = today.isoformat() if i == 0 else pd.Timestamp(today - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            return dict(zip(df["代码"], df["名称"]))
    return {}


def _get_ma(df: pd.DataFrame, period: int) -> float | None:
    """计算均线值"""
    if df is None or len(df) < period:
        return None
    return round(float(df["close"].tail(period).mean()), 2)


def _check_trade_rules(*args, **kwargs) -> dict:
    """已废弃：由数据库风控规则替代"""
    return {"passed": True, "checks": []}


def _get_daily_history(code: str, max_days: int = 250) -> pd.DataFrame | None:
    """获取个股日线行情（腾讯API优先，akshare兜底）"""
    import urllib.request, json

    # 方法1: 腾讯K线API（快、稳）
    try:
        market = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else "bj"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{min(max_days, 800)},qfq"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        raw = json.loads(resp.read().decode())
        kdata = raw["data"][f"{market}{code}"].get("qfqday") or raw["data"][f"{market}{code}"].get("day") or []

        records = []
        for k in kdata:
            records.append({
                "date": k[0], "open": float(k[1]), "close": float(k[2]),
                "high": float(k[3]), "low": float(k[4]), "volume": float(k[5]),
            })
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["pct_change"] = df["close"].pct_change() * 100
        # 腾讯API成交量单位为"手"（1手=100股），换算成元
        df["amount"] = df["volume"] * 100 * (df["high"] + df["low"] + df["close"]) / 3
        return df
    except Exception:
        pass

    # 方法2: akshare（兜底）
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            df.columns = [c.strip() for c in df.columns]
            df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
                "成交额": "amount", "振幅": "amplitude",
                "涨跌幅": "pct_change", "涨跌额": "change",
                "换手率": "turnover",
            }, inplace=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            for col in ["open", "close", "high", "low", "volume", "amount", "amplitude", "pct_change", "turnover"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
    except Exception:
        return None


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

        # 均线多头排列
        bullish_alignment = False
        if all(v is not None for v in [ma5, ma10, ma20, ma60]):
            bullish_alignment = ma5 > ma10 > ma20 > ma60

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
        news = ak.stock_news_em(symbol=code)
        if news is not None and not news.empty:
            for _, n in news.head(5).iterrows():
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
            from backend.stock_db import get_financial_reports
            reports = get_financial_reports(code, 1)
            fin = dict(reports[0]) if reports else None
            patterns = []
            try:
                patterns = detect_patterns(df) if df is not None else []
            except:
                pass
            from backend.stock_db import evaluate_risk_rules
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
