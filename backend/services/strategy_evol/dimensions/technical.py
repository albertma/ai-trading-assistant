"""技术面维度评分器

对个股进行技术面评分，综合MACD、均线排列、量价关系等指标，
返回 0-100 分与精选 evidence。
"""

from __future__ import annotations

import numpy as np

from backend.services.signal_detect.signal_registry import ENTRY_SIGNALS
from backend.services.signal_detect.strategy_backtest import check_current_signal
from backend.services.market_service import get_daily_history
from backend.utils.indicators import sma, macd


def score_technical(stock_code: str) -> dict:
    """技术面综合评分

    评分逻辑：
      1. 遍历所有底部反转相关的 entry 信号，调用 check_current_signal
         - 任一触发 → base=60 + confidence调整(0-40)，最高100
      2. 均未触发 → 评估趋势健康度（0-40 分）
         - MA5>MA10>MA20 多头排列   20分
         - MACD DIF>0              10分
         - 收盘价在MA60之上         10分
      3. evidence：最多3条，精炼

    Args:
        stock_code: 股票代码（如 "000001" 或 "AAPL"）

    Returns:
        {
            "score": 0-100,
            "evidence": [
                {"strategy": "...", "detail": "...", "confidence": 55},
            ]
        }
    """
    # ── 候选底部反转信号（包括板块优化版本） ──
    reversal_signals = [
        name for name in ENTRY_SIGNALS
        if "bottom_reversal" in name
    ]

    best_signal: dict | None = None          # check_current_signal 返回的完整结果
    best_entry_name: str | None = None

    for name in reversal_signals:
        try:
            result = check_current_signal(
                code=stock_code,
                entry_signal=name,
                max_days=500,
            )
        except Exception:
            continue

        if result and result.get("triggered"):
            # 胆大的截断判断：仅用 confidence 排序
            if (best_signal is None
                    or result["confidence"] > best_signal["confidence"]):
                best_signal = result
                best_entry_name = name

    # ── 加载日线数据（趋势健康度 & evidence 共用） ──
    daily_df = get_daily_history(stock_code, 250)
    closes = daily_df["close"].values.astype(float) if daily_df is not None and not daily_df.empty else None

    # ── 有信号触发 → 评分 60-100 ──
    if best_signal is not None:
        conf = best_signal["confidence"]  # 0-100
        score = min(100, 60 + int(conf * 0.4))  # confidence 0→60, 100→100

        evidence = _build_triggered_evidence(best_signal, best_entry_name, daily_df, closes)

        return {"score": score, "evidence": evidence}

    # ── 无信号触发 → 趋势健康度评分 0-40 ──
    if closes is None or len(closes) < 60:
        return {"score": 0, "evidence": [{"strategy": "底部反转", "detail": "数据不足（<60日）", "confidence": 0}]}

    score = 0
    evidence: list[dict] = []
    i = len(closes) - 1  # 最后一根K线

    # 计算均线和MACD
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    dif, dea, hist = macd(closes)

    # ① MA5>MA10>MA20 多头排列（20分）
    if not (np.isnan(ma5[i]) or np.isnan(ma10[i]) or np.isnan(ma20[i])):
        if ma5[i] > ma10[i] > ma20[i]:
            score += 20
            evidence.append({
                "strategy": "MA趋势",
                "detail": f"MA5({ma5[i]:.2f})>MA10({ma10[i]:.2f})>MA20({ma20[i]:.2f})多头排列",
                "confidence": 80,
            })
        elif ma5[i] > ma10[i]:
            score += 10
            evidence.append({
                "strategy": "MA趋势",
                "detail": f"MA5({ma5[i]:.2f})>MA10({ma10[i]:.2f})短多，但未突破MA20({ma20[i]:.2f})",
                "confidence": 45,
            })
        else:
            evidence.append({
                "strategy": "MA趋势",
                "detail": f"均线空头/交织 MA5({ma5[i]:.2f}) MA10({ma10[i]:.2f}) MA20({ma20[i]:.2f})",
                "confidence": 20,
            })
    else:
        evidence.append({
            "strategy": "MA趋势",
            "detail": "均线数据不足",
            "confidence": 0,
        })

    # ② MACD DIF>0（10分）
    if not np.isnan(dif[i]):
        if dif[i] > 0:
            score += 10
            evidence.append({
                "strategy": "MACD动量",
                "detail": f"DIF({dif[i]:.2f})>0，MACD处于多头区域",
                "confidence": 70,
            })
        else:
            evidence.append({
                "strategy": "MACD动量",
                "detail": f"DIF({dif[i]:.2f})<0，MACD空头区域",
                "confidence": 30,
            })
    else:
        evidence.append({
            "strategy": "MACD动量",
            "detail": "MACD数据不足",
            "confidence": 0,
        })

    # ③ 价格在MA60之上（10分）
    if not (np.isnan(closes[i]) or np.isnan(ma60[i])):
        if closes[i] > ma60[i]:
            score += 10
            evidence.append({
                "strategy": "MA60支撑",
                "detail": f"收盘价({closes[i]:.2f})>MA60({ma60[i]:.2f})，中期趋势偏多",
                "confidence": 65,
            })
        else:
            evidence.append({
                "strategy": "MA60支撑",
                "detail": f"收盘价({closes[i]:.2f})<MA60({ma60[i]:.2f})，中期趋势偏弱",
                "confidence": 35,
            })
    else:
        evidence.append({
            "strategy": "MA60支撑",
            "detail": "MA60数据不足",
            "confidence": 0,
        })

    # 精炼：最多保留3条evidence
    evidence = evidence[:3]

    return {"score": score, "evidence": evidence}


def _build_triggered_evidence(
    signal: dict,
    entry_name: str | None,
    daily_df,
    closes: np.ndarray | None,
) -> list[dict]:
    """当有信号触发时，构造 evidence 列表（最多3条）"""
    evidence: list[dict] = []
    label = ENTRY_SIGNALS.get(entry_name, {}).get("label", entry_name or "底部反转")

    conf = signal.get("confidence", 50)

    # 第一条：信号触发详情
    detail_parts = [signal.get("signal_detail", label)]
    if signal.get("entry_price"):
        detail_parts.append(f"入场参考价={signal['entry_price']}")
    if signal.get("stop_loss_price"):
        detail_parts.append(f"止损={signal['stop_loss_price']}")
    if signal.get("target_price"):
        detail_parts.append(f"目标={signal['target_price']}")

    evidence.append({
        "strategy": "底部反转",
        "detail": " | ".join(detail_parts),
        "confidence": conf,
    })

    # 第二条：MA趋势（如有可能）
    if closes is not None and len(closes) >= 20:
        i = len(closes) - 1
        ma5_arr = sma(closes, 5)
        ma10_arr = sma(closes, 10)
        ma20_arr = sma(closes, 20)
        if not (np.isnan(ma5_arr[i]) or np.isnan(ma10_arr[i]) or np.isnan(ma20_arr[i])):
            if ma5_arr[i] > ma10_arr[i] > ma20_arr[i]:
                evidence.append({
                    "strategy": "MA趋势",
                    "detail": f"MA5({ma5_arr[i]:.2f})>MA10({ma10_arr[i]:.2f})>MA20({ma20_arr[i]:.2f})多头排列",
                    "confidence": 80,
                })

    # 第三条：盈亏比
    rr = signal.get("risk_reward_ratio", 0)
    if rr:
        evidence.append({
            "strategy": "盈亏比",
            "detail": f"风险回报比 1:{rr}",
            "confidence": min(100, int(rr * 20)),
        })

    return evidence[:3]
