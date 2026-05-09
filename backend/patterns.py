"""
K线形态识别模块
"""
import pandas as pd
import numpy as np
from typing import Optional


def _candle_body(open_p, close_p):
    return abs(close_p - open_p)


def _upper_shadow(open_p, close_p, high):
    return high - max(open_p, close_p)


def _lower_shadow(open_p, close_p, low):
    return min(open_p, close_p) - low


def _total_range(high, low):
    return high - low


def _is_bullish(open_p, close_p):
    return close_p > open_p

def _is_bearish(open_p, close_p):
    return close_p < open_p


def _avg_body(df, n=14):
    """过去n根K线的平均实体长度"""
    bodies = [abs(r["close"] - r["open"]) for _, r in df.tail(n).iterrows()]
    return np.mean(bodies) if bodies else 0


def detect_patterns(df: pd.DataFrame) -> list[dict]:
    """
    识别最近5根K线的形态组合
    返回: [{pattern, direction, confidence, description}, ...]
    """
    if df is None or len(df) < 5:
        return []

    results = []
    avg_body = _avg_body(df, 14)

    # 取最近5根K线做分析
    candles = df.tail(5).reset_index(drop=True)
    c = []
    for _, r in candles.iterrows():
        o, c_, h, l = float(r["open"]), float(r["close"]), float(r["high"]), float(r["low"])
        body = _candle_body(o, c_)
        us = _upper_shadow(o, c_, h)
        ls = _lower_shadow(o, c_, l)
        tr = _total_range(h, l)
        c.append({
            "open": o, "close": c_, "high": h, "low": l,
            "body": body, "upper_shadow": us, "lower_shadow": ls,
            "total_range": tr, "bullish": _is_bullish(o, c_),
        })

    c4 = c[-1]  # 最新一根
    c3 = c[-2] if len(c) >= 2 else None
    c2 = c[-3] if len(c) >= 3 else None
    c1 = c[-4] if len(c) >= 4 else None
    c0 = c[-5] if len(c) >= 5 else None

    # --- 单K线形态 ---

    # 1. 大阳线: 实体 > 2倍平均实体，且为阳线
    if c4["bullish"] and c4["body"] > avg_body * 2:
        results.append({
            "pattern": "大阳线",
            "direction": "bullish",
            "confidence": "high",
            "description": f"阳线实体{c4['body']:.2f}（{avg_body:.2f}的{c4['body']/avg_body:.1f}倍），买盘强劲",
        })

    # 2. 大阴线: 实体 > 2倍平均实体，且为阴线
    if not c4["bullish"] and c4["body"] > avg_body * 2:
        results.append({
            "pattern": "大阴线",
            "direction": "bearish",
            "confidence": "high",
            "description": f"阴线实体{c4['body']:.2f}（{avg_body:.2f}的{c4['body']/avg_body:.1f}倍），卖盘凶猛",
        })

    # 3. 十字星: 实体极小（<10%总波幅）
    if c4["body"] < c4["total_range"] * 0.1 and c4["total_range"] > 0:
        us_ratio = c4["upper_shadow"] / c4["total_range"] if c4["total_range"] > 0 else 0
        ls_ratio = c4["lower_shadow"] / c4["total_range"] if c4["total_range"] > 0 else 0

        if abs(us_ratio - 0.5) < 0.2 and abs(ls_ratio - 0.5) < 0.2:
            results.append({
                "pattern": "十字星",
                "direction": "neutral",
                "confidence": "medium",
                "description": "开盘收盘几乎持平，多空力量均衡，变盘信号",
            })

    # 4. 锤子线: 下影线 > 2倍实体，上影线短，在下跌趋势中出现
    if c4["lower_shadow"] > c4["body"] * 2 and c4["upper_shadow"] < c4["body"] * 0.5:
        # 检查之前是否在下跌
        trend_down = False
        if c3 and not c3["bullish"]:
            trend_down = True
        if c2 and not c2["bullish"]:
            trend_down = True
        if trend_down:
            results.append({
                "pattern": "锤子线",
                "direction": "bullish",
                "confidence": "medium" if c4["bullish"] else "low",
                "description": "下影线长、实体小，下跌后出现底部反转信号",
            })

    # 5. 上吊线: 同锤子线形态，但在上涨趋势中出现（看跌）
    if c4["lower_shadow"] > c4["body"] * 2 and c4["upper_shadow"] < c4["body"] * 0.5:
        trend_up = False
        if c3 and c3["bullish"]:
            trend_up = True
        if c2 and c2["bullish"]:
            trend_up = True
        if trend_up:
            results.append({
                "pattern": "上吊线",
                "direction": "bearish",
                "confidence": "medium",
                "description": "上涨后出现长下影小实体，警惕顶部反转",
            })

    # 6. 射击之星: 上影线 > 2倍实体，下影线短，上涨趋势后
    if c4["upper_shadow"] > c4["body"] * 2 and c4["lower_shadow"] < c4["body"] * 0.3 and not c4["bullish"]:
        trend_up = False
        if c3 and c3["bullish"]:
            trend_up = True
        if c2 and c2["bullish"]:
            trend_up = True
        if trend_up:
            results.append({
                "pattern": "射击之星",
                "direction": "bearish",
                "confidence": "medium",
                "description": "长上影短实体，上涨受阻，可能见顶",
            })

    # 7. 倒锤子: 同上形态，但在下跌趋势后（看涨）
    if c4["upper_shadow"] > c4["body"] * 2 and c4["lower_shadow"] < c4["body"] * 0.3:
        trend_down = False
        if c3 and not c3["bullish"]:
            trend_down = True
        if c2 and not c2["bullish"]:
            trend_down = True
        if trend_down:
            results.append({
                "pattern": "倒锤子",
                "direction": "bullish",
                "confidence": "low",
                "description": "下跌后出现长上影，多头试探，需次日确认",
            })

    # --- 双K线形态 ---

    if c3 and c4:
        # 8. 看涨吞没: 阴线后出现阳线，阳线实体吞没阴线实体
        if not c3["bullish"] and c4["bullish"] and c4["body"] > c3["body"] * 1.2 and \
           c4["close"] > c3["open"] and c4["open"] < c3["close"]:
            results.append({
                "pattern": "看涨吞没",
                "direction": "bullish",
                "confidence": "high",
                "description": "阳线实体完全覆盖前日阴线，强烈反转信号",
            })

        # 9. 看跌吞没: 阳线后出现阴线，阴线实体吞没阳线实体
        if c3["bullish"] and not c4["bullish"] and c4["body"] > c3["body"] * 1.2 and \
           c4["open"] > c3["close"] and c4["close"] < c3["open"]:
            results.append({
                "pattern": "看跌吞没",
                "direction": "bearish",
                "confidence": "high",
                "description": "阴线实体完全覆盖前日阳线，强烈反转信号",
            })

        # 10. 看涨孕线: 大阴线后出现小阳线，完全在大阴线实体内
        if c3["body"] > avg_body * 1.2 and not c3["bullish"] and c4["body"] < c3["body"] * 0.5 and \
           c4["high"] < c3["open"] and c4["low"] > c3["close"]:
            results.append({
                "pattern": "看涨孕线",
                "direction": "bullish",
                "confidence": "medium",
                "description": "小阳线孕育在大阴线内，下跌动能减弱",
            })

        # 11. 看跌孕线: 大阳线后出现小阴线，完全在大阳线实体内
        if c3["body"] > avg_body * 1.2 and c3["bullish"] and c4["body"] < c3["body"] * 0.5 and \
           c4["high"] < c3["close"] and c4["low"] > c3["open"]:
            results.append({
                "pattern": "看跌孕线",
                "direction": "bearish",
                "confidence": "medium",
                "description": "小阴线孕育在大阳线内，上涨动能减弱",
            })

        # 12. 刺透线: 阴线后阳线收盘>阴线中点
        if not c3["bullish"] and c4["bullish"] and \
           c4["open"] < c3["close"] and c4["close"] > (c3["open"] + c3["close"]) / 2:
            results.append({
                "pattern": "刺透形态",
                "direction": "bullish",
                "confidence": "medium",
                "description": "阳线收盘刺入前阴线中点以上，底部反转",
            })

        # 13. 乌云盖顶: 阳线后阴线收盘<阳线中点
        if c3["bullish"] and not c4["bullish"] and \
           c4["open"] > c3["close"] and c4["close"] < (c3["open"] + c3["close"]) / 2:
            results.append({
                "pattern": "乌云盖顶",
                "direction": "bearish",
                "confidence": "medium",
                "description": "阴线跌破前阳线中点，顶部反转",
            })

    # --- 三K线形态 ---

    if c2 and c3 and c4:
        # 14. 晨星: 长阴 → 小实体 → 长阳
        if not c2["bullish"] and c2["body"] > avg_body * 1.2 and \
           c3["body"] < avg_body * 0.5 and \
           c4["bullish"] and c4["body"] > avg_body * 1.2 and \
           c4["close"] > (c2["open"] + c2["close"]) / 2:
            conf = "high" if not c3["bullish"] else "medium"
            results.append({
                "pattern": "晨星形态",
                "direction": "bullish",
                "confidence": conf,
                "description": "长阴→星线→长阳，经典底部反转形态",
            })

        # 15. 暮星: 长阳 → 小实体 → 长阴
        if c2["bullish"] and c2["body"] > avg_body * 1.2 and \
           c3["body"] < avg_body * 0.5 and \
           not c4["bullish"] and c4["body"] > avg_body * 1.2 and \
           c4["close"] < (c2["open"] + c2["close"]) / 2:
            conf = "high" if c3["bullish"] else "medium"
            results.append({
                "pattern": "暮星形态",
                "direction": "bearish",
                "confidence": conf,
                "description": "长阳→星线→长阴，经典顶部反转形态",
            })

        # 16. 三连阳
        if all(c["bullish"] for c in [c2, c3, c4]) and \
           all(c["body"] > avg_body * 0.7 for c in [c2, c3, c4]):
            results.append({
                "pattern": "三连阳（红三兵）",
                "direction": "bullish",
                "confidence": "medium",
                "description": "连续三根阳线稳步上涨，上升趋势强劲",
            })

        # 17. 三连阴
        if all(not c["bullish"] for c in [c2, c3, c4]) and \
           all(c["body"] > avg_body * 0.7 for c in [c2, c3, c4]):
            results.append({
                "pattern": "三连阴（黑三兵）",
                "direction": "bearish",
                "confidence": "medium",
                "description": "连续三根阴线下跌，下跌趋势强劲",
            })

    # --- 量价配合 ---
    if len(df) >= 20:
        recent5_vol = df["volume"].tail(5).mean()
        prev10_vol = df["volume"].tail(15).head(10).mean()
        last_vol = float(df["volume"].iloc[-1])
        if prev10_vol > 0 and recent5_vol > prev10_vol * 1.5:
            results.append({
                "pattern": "放量上涨" if c4["bullish"] else "放量下跌",
                "direction": "bullish" if c4["bullish"] else "bearish",
                "confidence": "medium",
                "description": f"近5日均量较前10日放大{recent5_vol/prev10_vol:.1f}倍{'，价涨量增' if c4['bullish'] else '，价跌量增'}",
            })
        elif prev10_vol > 0 and recent5_vol < prev10_vol * 0.5:
            results.append({
                "pattern": "缩量整理",
                "direction": "neutral",
                "confidence": "low",
                "description": f"近5日均量仅为前10日的{recent5_vol/prev10_vol:.0%}，市场观望",
            })

    # 去重：如果大阳线+看涨吞没同时出现，保留更重要的
    patterns_found = [r["pattern"] for r in results]
    # 如果大阳线已经出现，且吞没形态也出现了，删除普通的大阳线
    if "大阳线" in patterns_found and "看涨吞没" in patterns_found:
        results = [r for r in results if r["pattern"] != "大阳线"]
    if "大阴线" in patterns_found and "看跌吞没" in patterns_found:
        results = [r for r in results if r["pattern"] != "大阴线"]

    # 限制最多返回6个最有意义的形态
    priority = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: (priority.get(r["confidence"], 3), 0 if r["direction"] != "neutral" else 1))
    return results[:6]


# ═══════════════════════════════════════════════════════════════
# 杯柄形态（中长期价格结构）
# ═══════════════════════════════════════════════════════════════

def detect_cup_handle(df: pd.DataFrame) -> list[dict]:
    """
    检测杯柄形态（Cup & Handle）。
    扫描最近250根K线，找最优的杯+柄价格结构。
    返回格式与 detect_patterns 一致。
    """
    if df is None or len(df) < 60:
        return []

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values if "volume" in df.columns else None
    n = len(df)

    best_score = 0.0
    best_result = None

    min_len, max_len = 50, min(250, n)

    for total_len in range(min_len, max_len, 10):
        for start in range(0, max(1, n - total_len), 5):
            end = start + total_len
            if end > n:
                continue

            seg_h = high[start:end]
            seg_l = low[start:end]

            # 杯左沿（前半段最高）
            left_rel = np.argmax(seg_h[:max(len(seg_h) // 2, 10)])
            left_idx = start + left_rel
            left_price = high[left_idx]

            # 杯底（左沿之后最低）
            after_left = low[left_idx:end]
            if len(after_left) < 15:
                continue
            bottom_rel = np.argmin(after_left)
            bottom_idx = left_idx + bottom_rel
            bottom_price = low[bottom_idx]

            cup_depth = (left_price - bottom_price) / left_price
            if cup_depth < 0.08 or cup_depth > 0.70:
                continue

            # 杯右沿（杯底之后最高）
            after_bottom = high[bottom_idx + 1 : end]
            if len(after_bottom) < 8:
                continue
            right_rel = np.argmax(after_bottom)
            right_idx = bottom_idx + 1 + right_rel
            right_price = high[right_idx]
            if right_price < left_price * 0.75:
                continue

            # U型对称度
            if bottom_rel > 10 and (len(after_bottom) - right_rel) > 10:
                left_slope = (left_price - bottom_price) / max(1, bottom_rel)
                right_slope = (right_price - bottom_price) / max(1, right_idx - bottom_idx)
                symmetry = 1 - min(
                    abs(left_slope - right_slope) / max(left_slope, right_slope, 0.01), 1
                )
            else:
                symmetry = 0.3

            # 柄（右沿之后的小回调）
            after_right = close[right_idx + 1 :]
            if len(after_right) < 3:
                continue
            handle_min_rel = np.argmin(after_right)
            handle_min_idx = right_idx + 1 + handle_min_rel
            handle_min_price = min(close[right_idx : handle_min_idx + 1])
            handle_depth = (right_price - handle_min_price) / right_price
            if handle_depth > 0.25 or handle_depth < 0.002:
                continue

            # 打分
            depth_score = 1 - abs(cup_depth - 0.35) / 0.35
            handle_score = 1 - handle_depth / 0.12
            score = depth_score * 0.4 + symmetry * 0.35 + handle_score * 0.25

            if score > best_score:
                best_score = score
                best_result = {
                    "score": score,
                    "left_idx": left_idx,
                    "left_price": left_price,
                    "bottom_idx": bottom_idx,
                    "bottom_price": bottom_price,
                    "cup_depth": cup_depth,
                    "right_idx": right_idx,
                    "right_price": right_price,
                    "handle_idx": handle_min_idx,
                    "handle_price": handle_min_price,
                    "handle_depth": handle_depth,
                }

    if best_result and best_score > 0.25:
        cd = best_result
        depth_pct = round(cd["cup_depth"] * 100, 1)
        handle_pct = round(cd["handle_depth"] * 100, 1)
        close_current = close[-1]
        pct_from_buy = round((close_current / cd["right_price"] - 1) * 100, 1)
        buy_date = str(df["date"].iloc[cd["right_idx"]])[:10] if "date" in df.columns else "—"
        bottom_date = str(df["date"].iloc[cd["bottom_idx"]])[:10] if "date" in df.columns else "—"

        return [
            {
                "pattern": "杯柄形态（Cup & Handle）",
                "direction": "bullish",
                "confidence": "high" if best_score > 0.65 else "medium",
                "description": (
                    f"理想买点{buy_date} ¥{cd['right_price']:.2f}（突破柄部高点），"
                    f"当前价{close_current:.2f}（距买点{pct_from_buy:+.1f}%），"
                    f"杯深{depth_pct}%（{bottom_date}见底），柄深{handle_pct}%，"
                    f"匹配度{round(best_score*100):.0f}%"
                ),
                "cup_handle_detail": {
                    "score": round(best_score, 2),
                    "buy_date": buy_date,
                    "buy_point": cd["right_price"],
                    "bottom_date": bottom_date,
                    "bottom_price": cd["bottom_price"],
                    "current_price": close_current,
                    "pct_from_buy": pct_from_buy,
                    "cup_depth": cd["cup_depth"],
                    "handle_depth": cd["handle_depth"],
                },
            }
        ]

    return []
