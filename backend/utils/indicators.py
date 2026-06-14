"""技术指标计算 — numpy统一实现，供回测引擎和信号检测器共用

包含:
  - 均线类: sma, ema
  - 动量类: rsi, macd
  - K线形态类: is_big_bullish, is_hammer, is_three_white_soldiers
  - MACD交叉检测: detect_macd_golden_cross, detect_macd_death_cross
"""
from __future__ import annotations
from typing import Optional
import numpy as np


# ═══════════════════════════════════════════════════════════════
# 均线类
# ═══════════════════════════════════════════════════════════════

def sma(arr: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均线 (Simple Moving Average)"""
    result = np.full(len(arr), np.nan)
    if len(arr) < period:
        return result
    cumsum = np.cumsum(arr)
    result[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])) / period
    return result


def ema(arr: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均线 (Exponential Moving Average)"""
    result = np.full(len(arr), np.nan)
    if len(arr) < 1:
        return result
    result[0] = arr[0]
    alpha = 2 / (period + 1)
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


# ═══════════════════════════════════════════════════════════════
# 动量类
# ═══════════════════════════════════════════════════════════════

def rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指标 (Relative Strength Index)"""
    result = np.full(len(arr), np.nan)
    if len(arr) <= period:
        return result
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(arr)):
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = round(100 - 100 / (1 + rs), 2)
        if i < len(arr) - 1:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return result


def macd(arr: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 指标 — 返回 (dif, dea, hist)"""
    ema_f = ema(arr, fast)
    ema_s = ema(arr, slow)
    dif = ema_f - ema_s
    dea = np.full(len(arr), np.nan)
    if len(arr) >= signal:
        alpha = 2 / (signal + 1)
        dea[0] = dif[0]
        for i in range(1, len(arr)):
            dea[i] = alpha * dif[i] + (1 - alpha) * dea[i - 1]
    hist = dif - dea
    return dif, dea, hist


# ═══════════════════════════════════════════════════════════════
# MACD交叉检测
# ═══════════════════════════════════════════════════════════════

def detect_macd_golden_cross(dif: np.ndarray, dea: np.ndarray, lookback: int = 3) -> set[int]:
    """检测最近 N 个 bar 内的MACD金叉 — 返回触发金叉的索引集合

    条件: dif[i-1] <= dea[i-1] 且 dif[i] > dea[i]
    """
    result: set[int] = set()
    n = len(dif)
    start = max(1, n - lookback)
    for i in range(start, n):
        if (not np.isnan(dif[i]) and not np.isnan(dif[i-1])
                and not np.isnan(dea[i]) and not np.isnan(dea[i-1])
                and dif[i-1] <= dea[i-1] and dif[i] > dea[i]):
            result.add(i)
    return result


def detect_macd_death_cross(dif: np.ndarray, dea: np.ndarray, lookback: int = 3) -> set[int]:
    """检测最近 N 个 bar 内的MACD死叉 — 返回触发死叉的索引集合

    条件: dif[i-1] >= dea[i-1] 且 dif[i] < dea[i]
    """
    result: set[int] = set()
    n = len(dif)
    start = max(1, n - lookback)
    for i in range(start, n):
        if (not np.isnan(dif[i]) and not np.isnan(dif[i-1])
                and not np.isnan(dea[i]) and not np.isnan(dea[i-1])
                and dif[i-1] >= dea[i-1] and dif[i] < dea[i]):
            result.add(i)
    return result


# ═══════════════════════════════════════════════════════════════
# K线形态检测（单根/多根）
# ═══════════════════════════════════════════════════════════════

def is_big_bullish(open_p: float, close_p: float, prev_close: float,
                   threshold_pct: float = 3.0) -> bool:
    """大阳线: 阳线实体涨幅 > threshold_pct%（以上一收盘为基准）"""
    if close_p <= open_p:
        return False
    pct = (close_p - open_p) / prev_close * 100
    return pct > threshold_pct


def is_hammer(open_p: float, close_p: float, high_p: float, low_p: float,
              min_body: float = 0.01) -> bool:
    """锤子线: 下影线 > 实体×2, 上影线 < 实体×0.3, 实体>0"""
    body = abs(close_p - open_p)
    if body < min_body:
        return False
    lower_shadow = min(open_p, close_p) - low_p
    upper_shadow = high_p - max(open_p, close_p)
    return lower_shadow > body * 2 and upper_shadow < body * 0.3


def is_three_white_soldiers(closes: list[float], opens: list[float]) -> dict | None:
    """红三兵: 连续3根阳线，涨幅递增 → 返回 {strength, desc} or None

    参数: closes/opens 各3个元素，从旧到新 [c0,c1,c2], [o0,o1,o2]
    """
    if len(closes) < 3 or len(opens) < 3:
        return None
    bears = [c <= o for c, o in zip(closes, opens)]
    if any(bears):
        return None
    gains = [closes[i] - opens[i] for i in range(3)]
    if gains[0] < gains[1] < gains[2]:
        return {'strength': 85.0, 'desc': '连续3日阳线且每日涨幅递增，多头强势上攻'}
    return {'strength': 70.0, 'desc': '连续3日阳线，多头占优'}
