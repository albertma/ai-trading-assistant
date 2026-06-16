"""
基本面评分维度（简化版：仅用本地数据，无akshare调用）
从 kline_daily 和 stock_info 取数据评估基本面
"""
from __future__ import annotations
from typing import Any
from backend.services.database.stock_db import get_kline_db


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def score_fundamental(stock_code: str) -> dict:
    """
    基本面质量评分（0-100）— 仅用本地数据

    评分维度：
      - 是否在观察池/持仓中（15分）
      - 近期价格趋势（30分）
      - 所属板块景气度（20分）
      - 市值分档（15分）
      - 换手率/活跃度（20分）
    """
    # 只处理A股
    is_a_share = (
        stock_code.isdigit() and len(stock_code) == 6
        and stock_code[0] in ("0", "3", "6")
    )
    if not is_a_share:
        return {
            "score": 30,
            "evidence": [{"factor": "非A股", "detail": f"{stock_code} 暂不支持基本面评分", "score": 30}],
        }

    conn = get_db()
    evidence = []
    score = 0

    # ① 所属行业（从stock_info获取）
    row = conn.execute(
        "SELECT industry FROM stock_info WHERE code=?", (stock_code,)
    ).fetchone()
    industry = row["industry"] if row else ""
    conn.close()

    # ② 基础分（存在即有）
    if industry:
        score += 20
        evidence.append({"factor": "行业归属", "detail": f"所属行业: {industry}", "score": 20})
    else:
        score += 10
        evidence.append({"factor": "行业归属", "detail": "行业信息缺失", "score": 10})

    # ③ 价格趋势（从kline_daily取最近10日涨幅）
    conn2 = get_kline_db()
    rows = conn2.execute(
        """SELECT close FROM kline_daily
           WHERE code=? ORDER BY date DESC LIMIT 10""",
        (stock_code,),
    ).fetchall()
    conn2.close()

    if len(rows) >= 2:
        closes = [r["close"] for r in rows]
        change_pct = (closes[0] - closes[-1]) / closes[-1] * 100
        if change_pct > 10:
            trend_score = 30
            detail = f"近10日涨幅{change_pct:.1f}%，强势上涨"
        elif change_pct > 5:
            trend_score = 25
            detail = f"近10日涨幅{change_pct:.1f}%，稳健上涨"
        elif change_pct > 0:
            trend_score = 15
            detail = f"近10日涨幅{change_pct:.1f}%，小幅上涨"
        elif change_pct > -5:
            trend_score = 10
            detail = f"近10日涨幅{change_pct:.1f}%，小幅回调"
        else:
            trend_score = 5
            detail = f"近10日涨幅{change_pct:.1f}%，明显下跌"
        score += trend_score
        evidence.append({"factor": "价格趋势", "detail": detail, "score": trend_score})
    else:
        score += 10
        evidence.append({"factor": "价格趋势", "detail": "K线数据不足", "score": 10})

    # ④ 活跃度（最近5日均量）
    conn3 = get_kline_db()
    vol_row = conn3.execute(
        """SELECT AVG(volume) as avg_vol FROM (
            SELECT volume FROM kline_daily
            WHERE code=? ORDER BY date DESC LIMIT 5
        )""",
        (stock_code,),
    ).fetchone()
    conn3.close()

    if vol_row and vol_row["avg_vol"] and vol_row["avg_vol"] > 0:
        avg_vol = vol_row["avg_vol"]
        if avg_vol > 1_000_000:
            vol_score = 25
            detail = f"日均量{avg_vol/10000:.0f}万，非常活跃"
        elif avg_vol > 500_000:
            vol_score = 20
            detail = f"日均量{avg_vol/10000:.0f}万，较为活跃"
        elif avg_vol > 100_000:
            vol_score = 15
            detail = f"日均量{avg_vol/10000:.0f}万，正常活跃"
        else:
            vol_score = 10
            detail = f"日均量{avg_vol/10000:.0f}万，不活跃"
        score += vol_score
        evidence.append({"factor": "活跃度", "detail": detail, "score": vol_score})
    else:
        score += 10
        evidence.append({"factor": "活跃度", "detail": "数据不足", "score": 10})

    # ⑤ 市值分档（从kline_daily最后收盘价估算）
    if len(rows) >= 1:
        price = rows[0]["close"]
        if price > 100:
            price_score = 25
        elif price > 50:
            price_score = 20
        elif price > 20:
            price_score = 15
        elif price > 10:
            price_score = 10
        else:
            price_score = 5
        score += price_score
        evidence.append({"factor": "股价分档", "detail": f"当前价{price:.2f}元", "score": price_score})
    else:
        score += 10
        evidence.append({"factor": "股价分档", "detail": "数据不足", "score": 10})

    score = min(100, round(score, 1))
    return {"score": score, "evidence": evidence}
