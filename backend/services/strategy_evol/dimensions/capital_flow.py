"""
资金流评分维度
基于 K线量价关系评估资金进出状况
不需要外部资金流 API，仅基于量价关系
"""
from __future__ import annotations

import pandas as pd

from backend.services.market_service import get_daily_history


def score_capital_flow(stock_code: str) -> dict:
    """
    资金流向评分（0-100）

    评分维度：
      - 最近5天成交量 vs 20日均量比值（量比）  40分
        量比 > 1.5（放量）→ 高分
      - 价格伴随放量上涨                         60分
        量价齐升 → 高分；放量下跌 → 低分
    """
    evidence: list[dict] = []
    total_score = 0.0

    # 获取足够多的K线数据（至少25个交易日）
    df = get_daily_history(stock_code, max_days=60)
    if df is None or df.empty or len(df) < 20:
        return {
            "score": 0,
            "evidence": [{"factor": "数据不足", "detail": "K线数据不足20个交易日", "score": 0}],
        }

    df = df.sort_values("date").reset_index(drop=True)

    # ── 1. 量比分析（40分） ──
    volumes = df["volume"].values.astype(float)
    # 最近5日均量
    vol_5 = volumes[-5:].mean() if len(volumes) >= 5 else volumes.mean()
    # 20日均量（不含最近5天，避免重叠）
    if len(volumes) >= 25:
        vol_20 = volumes[-25:-5].mean()
    elif len(volumes) >= 20:
        vol_20 = volumes[-20:].mean()
    else:
        vol_20 = volumes.mean()

    volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

    # 量比评分
    if volume_ratio > 2.5:
        vol_score = 40  # 巨量
        vol_detail = f"量比={volume_ratio:.2f}，显著放量"
    elif volume_ratio > 1.8:
        vol_score = 35
        vol_detail = f"量比={volume_ratio:.2f}，明显放量"
    elif volume_ratio > 1.5:
        vol_score = 30
        vol_detail = f"量比={volume_ratio:.2f}，放量"
    elif volume_ratio > 1.2:
        vol_score = 25
        vol_detail = f"量比={volume_ratio:.2f}，温和放量"
    elif volume_ratio > 0.8:
        vol_score = 15
        vol_detail = f"量比={volume_ratio:.2f}，量能一般"
    elif volume_ratio > 0.5:
        vol_score = 8
        vol_detail = f"量比={volume_ratio:.2f}，缩量"
    else:
        vol_score = 0
        vol_detail = f"量比={volume_ratio:.2f}，显著缩量"

    evidence.append({
        "factor": "量比分析",
        "detail": f"{vol_detail}（近5日均量={vol_5:.0f}，近20日均量={vol_20:.0f}）",
        "score": vol_score,
    })
    total_score += vol_score

    # ── 2. 量价关系分析（60分） ──
    closes = df["close"].values.astype(float)

    # 计算最近5天的收盘价变化
    if len(closes) >= 6:
        price_change_5d = (closes[-1] - closes[-6]) / closes[-6] * 100
    elif len(closes) >= 2:
        price_change_5d = (closes[-1] - closes[0]) / closes[0] * 100
    else:
        price_change_5d = 0

    # 计算最近5天每日涨跌幅
    daily_changes = []
    for i in range(max(1, len(closes) - 5), len(closes)):
        if i > 0 and closes[i - 1] > 0:
            daily_changes.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)

    # 量价配合评分
    price_vol_score = 0.0
    price_vol_detail = ""

    if volume_ratio > 1.2 and price_change_5d > 5:
        # 放量大涨 — 量价齐升，最理想
        price_vol_score = 60
        price_vol_detail = f"放量上涨（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%），量价配合良好"
    elif volume_ratio > 1.2 and price_change_5d > 2:
        price_vol_score = 50
        price_vol_detail = f"放量上涨（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    elif volume_ratio > 1.2 and price_change_5d > 0:
        price_vol_score = 35
        price_vol_detail = f"放量微涨（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    elif volume_ratio > 1.2 and price_change_5d < -3:
        # 放量下跌 — 出货信号
        price_vol_score = 10
        price_vol_detail = f"放量下跌（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%），资金流出迹象"
    elif volume_ratio > 1.2 and price_change_5d < 0:
        price_vol_score = 20
        price_vol_detail = f"放量微跌（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    elif 0.8 <= volume_ratio <= 1.2 and price_change_5d > 2:
        price_vol_score = 40
        price_vol_detail = f"价涨量平（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    elif 0.8 <= volume_ratio <= 1.2 and price_change_5d > 0:
        price_vol_score = 30
        price_vol_detail = f"价量平稳（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    elif volume_ratio < 0.8 and price_change_5d > 0:
        # 缩量上涨 — 可能缺乏后续动力
        price_vol_score = 25
        price_vol_detail = f"缩量上涨（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%），上涨动力不足"
    elif volume_ratio < 0.8 and price_change_5d < -3:
        price_vol_score = 5
        price_vol_detail = f"缩量下跌（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%），弱势"
    elif volume_ratio < 0.8:
        price_vol_score = 15
        price_vol_detail = f"缩量（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"
    else:
        price_vol_score = 20
        price_vol_detail = f"量价关系不明显（量比={volume_ratio:.2f}，5日涨幅={price_change_5d:+.1f}%）"

    evidence.append({
        "factor": "量价关系",
        "detail": price_vol_detail,
        "score": round(price_vol_score, 1),
    })
    total_score += price_vol_score

    # ── 补充：每日量价明细 ──
    recent_days = df.tail(5)
    day_details = []
    for _, row in recent_days.iterrows():
        dt = row["date"]
        if hasattr(dt, "strftime"):
            dt_str = dt.strftime("%m-%d")
        else:
            dt_str = str(dt)[5:10]
        chg = row.get("pct_change", 0)
        vol = row["volume"]
        day_details.append(f"{dt_str}({'↑' if chg > 0 else '↓'}{abs(chg):.1f}%,量{vol:.0f})")

    evidence.append({
        "factor": "近期量价明细",
        "detail": " | ".join(day_details),
        "score": 0,  # 明细项，不计分
    })

    final_score = min(round(total_score, 1), 100)

    return {
        "score": final_score,
        "evidence": evidence,
    }
