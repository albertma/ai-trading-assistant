"""
AI趋势预测 — 基于历史周期 + K线形态 + AI推理
"""
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from openai import OpenAI
import yaml
from pathlib import Path

from backend.routers.analysis import analyze_stock as _do_analysis, _get_daily_history, _get_stock_list

router = APIRouter()


def _get_deepseek_client():
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        providers = cfg.get("custom_providers", [])
        for p in providers:
            if p.get("name") == "deepseek-v4-flash":
                return OpenAI(api_key=p["api_key"], base_url=p["base_url"])
        return OpenAI(
            api_key=cfg.get("model", {}).get("api_key", ""),
            base_url=cfg.get("model", {}).get("base_url", "https://api.deepseek.com"),
        )
    except Exception:
        return OpenAI(api_key="", base_url="https://api.deepseek.com")


def _detect_cycles(df: pd.DataFrame) -> dict:
    """分析历史价格周期和浪型结构"""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    if len(close) < 30:
        return {"error": "数据不足30个交易日"}

    # 1. 支撑/阻力位 — 近60日密集区
    recent = df.tail(60)
    support_levels = []
    resistance_levels = []
    price_range = close[-1]
    # 用低点聚集找支撑
    lows = recent["low"].values
    for lv in [np.percentile(lows, p) for p in [10, 25, 50]]:
        support_levels.append(round(float(lv), 2))
    # 用高点聚集找阻力
    highs = recent["high"].values
    for hv in [np.percentile(highs, p) for p in [75, 90, 95]]:
        resistance_levels.append(round(float(hv), 2))

    # 2. 近期波动特征
    pct_changes = df["pct_change"].dropna().values[-60:] if "pct_change" in df.columns else np.diff(close[-61:]) / close[-61:-1] * 100
    volatility = round(float(np.std(pct_changes)), 2)
    avg_change = round(float(np.mean(pct_changes)), 2)
    max_up = round(float(np.max(pct_changes)), 2)
    max_down = round(float(np.min(pct_changes)), 2)

    # 3. 趋势判断（MA排列）
    ma5 = round(float(df["close"].rolling(5).mean().iloc[-1]), 2) if len(df) >= 5 else None
    ma10 = round(float(df["close"].rolling(10).mean().iloc[-1]), 2) if len(df) >= 10 else None
    ma20 = round(float(df["close"].rolling(20).mean().iloc[-1]), 2) if len(df) >= 20 else None
    ma60 = round(float(df["close"].rolling(60).mean().iloc[-1]), 2) if len(df) >= 60 else None

    # 4. 成交量分析
    vol_trend = "neutral"
    if "volume" in df.columns:
        vol_avg20 = df["volume"].rolling(20).mean().iloc[-1]
        vol_last5 = df["volume"].tail(5).mean()
        vol_ratio = round(float(vol_last5 / vol_avg20), 2) if vol_avg20 > 0 else 1
        vol_trend = "放量" if vol_ratio > 1.3 else "缩量" if vol_ratio < 0.7 else "正常"
    else:
        vol_ratio = 1

    # 5. 近20日走势形态分类
    recent_close = close[-20:] if len(close) >= 20 else close
    if len(recent_close) >= 10:
        first_half = recent_close[:len(recent_close)//2]
        second_half = recent_close[len(recent_close)//2:]
        first_avg = np.mean(first_half)
        second_avg = np.mean(second_half)
        if second_avg > first_avg * 1.03:
            shape = "震荡上行"
        elif second_avg < first_avg * 0.97:
            shape = "震荡下行"
        else:
            shape = "横盘震荡"
        # 判断是否有W底/M顶
        recent_low_min = np.min(recent_close)
        recent_low_pos = np.argmin(recent_close)
        # 简单判断：近期低点附近是否出现两次
        if len(recent_close) >= 15:
            left = recent_close[:len(recent_close)//2]
            right = recent_close[len(recent_close)//2:]
            if np.min(left) > recent_low_min * 0.98 and np.min(right) > recent_low_min * 0.98 and recent_low_min < np.mean(recent_close) * 0.95:
                shape = shape + "(疑似W底)"
            recent_high_max = np.max(recent_close)
            if np.max(left) < recent_high_max * 1.02 and np.max(right) < recent_high_max * 1.02 and recent_high_max > np.mean(recent_close) * 1.05:
                shape = shape + "(疑似M顶)"
    else:
        shape = "数据不足"

    return {
        "current_price": round(float(close[-1]), 2),
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "volatility": volatility,
        "avg_change_pct": avg_change,
        "max_up_pct": max_up,
        "max_down_pct": max_down,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "volume_trend": vol_trend,
        "volume_ratio": vol_ratio,
        "shape": shape,
    }


def _detect_patterns_recent(df: pd.DataFrame) -> list:
    """分析近期K线组合形态"""
    if len(df) < 10:
        return []
    patterns = []

    close = df["close"].values
    open_p = df["open"].values if "open" in df.columns else close
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values if "volume" in df.columns else None

    # 最近10天的K线
    for i in range(-10, 0):
        # 只保留最近5个有明显特征的
        if i < -10:
            continue
        idx = i
        c, o, h, l = close[idx], open_p[idx], high[idx], low[idx]
        body = abs(c - o)
        upper_shadow = h - max(c, o)
        lower_shadow = min(c, o) - l
        total_range = h - l
        if total_range == 0:
            continue

        # 十字星
        if body / total_range < 0.1 and total_range > close[idx] * 0.01:
            patterns.append(f"第{len(df)+i}天:十字星(方向待确认)")
        # 长上影
        elif upper_shadow > body * 2 and upper_shadow > close[idx] * 0.02:
            patterns.append(f"第{len(df)+i}天:长上影线(上方抛压)")
        # 长下影
        elif lower_shadow > body * 2 and lower_shadow > close[idx] * 0.02:
            patterns.append(f"第{len(df)+i}天:长下影线(下方承接)")
        # 大阳线
        elif body > close[idx] * 0.04 and c > o:
            patterns.append(f"第{len(df)+i}天:大阳线(强势)")
        # 大阴线
        elif body > close[idx] * 0.04 and c < o:
            patterns.append(f"第{len(df)+i}天:大阴线(弱势)")

    # 连续N天上涨/下跌
    recent_changes = np.diff(close[-11:]) / close[-11:-1] * 100 if len(close) >= 11 else []
    up_streak = 0
    down_streak = 0
    for chg in recent_changes[-5:]:
        if chg > 0:
            up_streak += 1
            down_streak = 0
        elif chg < 0:
            down_streak += 1
            up_streak = 0
    if up_streak >= 3:
        patterns.append(f"连续{up_streak}日上涨")
    if down_streak >= 3:
        patterns.append(f"连续{down_streak}日下跌")

    return patterns


PREDICT_SYSTEM_PROMPT = """你是一位顶级A股量化分析师，精通技术分析、周期理论和形态识别。
你的任务是基于历史价格走势和当前技术指标，给出未来5-10个交易日的趋势预测。

请从以下角度分析并返回 JSON 格式结果：

1. trend_direction: "看涨" | "看跌" | "震荡" — 未来5-10日方向判断
2. confidence: 0-100 的置信度数值
3. target_price: 目标价位（向上/向下空间）
4. key_levels: 关键支撑位和阻力位数组
5. reasoning: 分析推理过程（200字以内）
6. cycle_phase: 当前所处的周期阶段 — "上涨初期"|"上涨中段"|"上涨末期"|"回调"|"下跌初期"|"下跌中段"|"下跌末期"|"横盘蓄势"|"横盘分化"
7. risk_warning: 风险提示（50字以内）

只返回 JSON，不要包含其他文字。
JSON格式: {{"trend_direction":"...","confidence":N,"target_price":{{"up":N,"down":N}},"key_levels":{{"support":[N,N],"resistance":[N,N]}},"reasoning":"...","cycle_phase":"...","risk_warning":"..."}}
"""


@router.get("/{code}")
def predict_stock(code: str):
    """AI趋势预测：基于历史周期 + 形态分析"""
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")

    # 1. 获取技术分析数据
    tech_data = _do_analysis(code)
    t = tech_data.get("technical") or {}

    # 2. 获取日线数据做周期分析
    df = _get_daily_history(code)
    if df is None or len(df) < 20:
        raise HTTPException(400, f"{name}({code}) 日线数据不足，无法分析")

    # 3. 周期分析
    cycles = _detect_cycles(df)
    patterns = _detect_patterns_recent(df)

    # 4. 构建分析上下文
    ctx_lines = [f"股票: {name} ({code})"]
    ctx_lines.append(f"分析日期: {datetime.now().strftime('%Y-%m-%d')}")
    ctx_lines.append("")

    # 当前状态
    ctx_lines.append("【当前状态】")
    ctx_lines.append(f"  现价: {cycles['current_price']}")
    ctx_lines.append(f"  近60日波动率: {cycles['volatility']}%")
    ctx_lines.append(f"  近60日均涨幅: {cycles['avg_change_pct']}%")
    ctx_lines.append(f"  最大涨幅: {cycles['max_up_pct']}%")
    ctx_lines.append(f"  最大跌幅: {cycles['max_down_pct']}%")
    ctx_lines.append("")

    # 均线
    ctx_lines.append("【均线系统】")
    for ma_label in ["ma5", "ma10", "ma20", "ma60"]:
        v = cycles.get(ma_label)
        if v:
            gap = round(cycles['current_price'] - v, 2)
            gap_pct = round(gap / v * 100, 1) if v > 0 else 0
            direction = "↑在上方" if gap > 0 else "↓在下方"
            ctx_lines.append(f"  {ma_label.upper()}: {v} (现价{direction} {abs(gap_pct)}%)")
    ctx_lines.append("")

    # 支撑阻力
    ctx_lines.append("【关键位】")
    ctx_lines.append(f"  支撑: {', '.join(str(s) for s in cycles['support_levels'])}")
    ctx_lines.append(f"  阻力: {', '.join(str(r) for r in cycles['resistance_levels'])}")
    ctx_lines.append(f"  近期形态: {cycles['shape']}")
    ctx_lines.append(f"  量能趋势: {cycles['volume_trend']} (倍率: {cycles['volume_ratio']})")
    ctx_lines.append("")

    # K线组合
    if patterns:
        ctx_lines.append("【近期K线组合】")
        for p in patterns:
            ctx_lines.append(f"  • {p}")
        ctx_lines.append("")

    # 技术指标
    ctx_lines.append("【技术指标】")
    ctx_lines.append(f"  RSI(14): {t.get('rsi_14', '--')}")
    macd = t.get("macd", {})
    ctx_lines.append(f"  MACD: DIF={macd.get('dif','--')} DEA={macd.get('dea','--')} HIST={macd.get('hist','--')}")
    ctx_lines.append(f"  均线多头: {'是' if t.get('bullish_alignment') else '否'}")
    ctx_lines.append(f"  趋势状态: {t.get('trend_status', '--')}")
    ctx_lines.append("")

    # 风控
    rc = tech_data.get("risk_check") or {}
    ctx_lines.append("【风控】")
    ctx_lines.append(f"  结果: {'通过' if rc.get('passed') else '未通过'}")
    for check in rc.get("checks", []):
        ctx_lines.append(f"  - {check.get('rule','')}: {check.get('detail','')} [{check.get('status','')}]")
    ctx_lines.append("")

    context = "\n".join(ctx_lines)

    # 5. 调用 AI
    ai_client = _get_deepseek_client()
    try:
        resp = ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": PREDICT_SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下股票数据，给出未来5-10个交易日的趋势预测：\n\n{context}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        # 尝试提取 JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
    except Exception as e:
        result = {
            "trend_direction": "未知",
            "confidence": 0,
            "target_price": {"up": None, "down": None},
            "key_levels": {"support": cycles["support_levels"], "resistance": cycles["resistance_levels"]},
            "reasoning": f"AI分析失败: {str(e)}",
            "cycle_phase": "未知",
            "risk_warning": "AI调用异常，请稍后重试",
        }

    return {
        "code": code,
        "name": name,
        "current_price": cycles["current_price"],
        "support_levels": cycles["support_levels"],
        "resistance_levels": cycles["resistance_levels"],
        "shape": cycles["shape"],
        "volume_trend": cycles["volume_trend"],
        "patterns": patterns,
        "prediction": result,
    }
