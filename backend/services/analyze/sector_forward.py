"""板块前瞻分析 — 技术面指标 + AI综合研判

基于 sector_indices 表（板块指数历史），计算：
  1. 均线趋势 (MA5/10/20/60)
  2. MACD金叉/死叉
  3. RSI
  4. 相对强度排名 (RPS 5/10日)
  5. AI综合研判（看多/观望/看空）
"""
import json
import numpy as np
from datetime import datetime, date
from typing import Any

from backend.services.database.stock_db import get_db
from backend.services.tradingmgt.sector_index_service import (
    get_sector_indices, get_latest_sector_indices
)


def _sma(values: list[float], n: int) -> list[float]:
    """简单移动平均"""
    if not values or len(values) < n:
        return []
    out = []
    for i in range(len(values)):
        if i < n - 1:
            out.append(0.0)
        else:
            out.append(round(sum(values[i - n + 1:i + 1]) / n, 2))
    return out


def _ema(values: list[float], n: int) -> list[float]:
    """指数移动平均"""
    if not values or len(values) == 0:
        return []
    k = 2 / (n + 1)
    out = [values[0]]
    for i in range(1, len(values)):
        out.append(round(values[i] * k + out[-1] * (1 - k), 2))
    return out


def _macd(values: list[float], fast=12, slow=26, signal=9) -> dict:
    """计算MACD线、信号线、柱状图"""
    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)
    if not ema_fast or not ema_slow:
        return {"dif": [], "dea": [], "macd": []}
    dif = [round(ema_fast[i] - ema_slow[i], 2) if i < len(ema_slow) else 0
           for i in range(len(ema_fast))]
    dea = _ema([d for d in dif if d != 0] if any(d != 0 for d in dif) else dif, signal)
    # align lengths
    while len(dea) < len(dif):
        dea.insert(0, 0.0)
    macd_bar = [round((dif[i] - dea[i]) * 2, 2) if i < len(dea) else 0 for i in range(len(dif))]
    return {"dif": dif, "dea": dea, "macd": macd_bar}


def _last_n(arr: list, n: int = 1) -> float:
    """取最后n个元素中的最后一个有效值"""
    vals = [v for v in arr if v != 0 and v is not None]
    return vals[-n] if len(vals) >= n else 0.0


def compute_tech_signals(sector_history: list[dict]) -> dict:
    """计算单个板块的技术面信号"""
    closes = [r["index_value"] for r in sector_history]
    daily_rets = [r["daily_return"] for r in sector_history]
    if len(closes) < 5:
        return {"error": "数据不足（<5日）"}

    # 均线
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)

    last = closes[-1]
    ma5_now = _last_n(ma5)
    ma10_now = _last_n(ma10)
    ma20_now = _last_n(ma20)
    ma60_now = _last_n(ma60)

    # 均线排列状态
    if ma5_now > ma10_now > ma20_now >= ma60_now and ma60_now > 0:
        ma_trend = "多头排列"
        ma_score = 3
    elif ma5_now > ma10_now > ma20_now:
        ma_trend = "短多"
        ma_score = 2
    elif ma5_now < ma10_now < ma20_now:
        ma_trend = "空头排列"
        ma_score = -2
    elif ma5_now < ma10_now:
        ma_trend = "短空"
        ma_score = -1
    else:
        ma_trend = "缠绕"
        ma_score = 0

    # 价格与均线关系
    if ma20_now > 0:
        price_vs_ma20 = round((last - ma20_now) / ma20_now * 100, 1)
    else:
        price_vs_ma20 = 0

    # MACD
    macd_data = _macd(closes)
    dif = macd_data["dif"]
    dea = macd_data["dea"]
    dif_now = _last_n(dif, 1)
    dea_now = _last_n(dea, 1)
    dif_prev = _last_n(dif, 2)
    dea_prev = _last_n(dea, 2)

    macd_status = "无信号"
    macd_score = 0
    if dif_now > 0 and dea_now > 0:
        macd_status = "多头区域"
        macd_score = 1
    elif dif_now < 0 and dea_now < 0:
        macd_status = "空头区域"
        macd_score = -1
    if dif_prev < dea_prev and dif_now >= dea_now:
        macd_status = "金叉🔥"
        macd_score = 3
    elif dif_prev > dea_prev and dif_now <= dea_now:
        macd_status = "死叉❌"
        macd_score = -3

    # RSI14
    rsi_score = 0
    rsi_status = "中性"
    if len(closes) >= 15:
        gains, losses = 0, 0
        for i in range(-14, 0):
            diff = closes[i] - closes[i - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        avg_gain = gains / 14
        avg_loss = losses / 14
        rsi_val = round(50 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss), 1) if avg_loss > 0 else 100
        if rsi_val > 70:
            rsi_status = "超买⚠️"
            rsi_score = -1
        elif rsi_val < 30:
            rsi_status = "超卖💡"
            rsi_score = 2
        else:
            rsi_status = f"{rsi_val:.0f}"
            rsi_score = 0
    else:
        rsi_val = 50

    # 成交量趋势（用每日return的波动率proxy代替成交量）
    vol_trend = "—"
    if len(daily_rets) >= 10:
        recent_vol = np.std(daily_rets[-5:])
        prev_vol = np.std(daily_rets[-10:-5])
        if recent_vol > prev_vol * 1.3:
            vol_trend = "放量"
        elif recent_vol < prev_vol * 0.7:
            vol_trend = "缩量"

    # 综合技术面分数
    tech_score = ma_score + macd_score + rsi_score

    return {
        "price": round(last, 2),
        "ma5": ma5_now, "ma10": ma10_now, "ma20": ma20_now,
        "ma_trend": ma_trend,
        "price_vs_ma20": price_vs_ma20,
        "macd_status": macd_status,
        "rsi": rsi_val,
        "rsi_status": rsi_status,
        "vol_trend": vol_trend,
        "tech_score": tech_score,
    }


def compute_rps(all_sectors: dict[str, list[dict]], latest_date: str) -> dict[str, dict]:
    """计算所有板块的相对强度排名"""
    rps_5d = {}
    rps_10d = {}

    for sector, hist in all_sectors.items():
        rets = [r["daily_return"] for r in hist if r["date"] <= latest_date]
        if len(rets) >= 5:
            rps_5d[sector] = round(sum(rets[-5:]), 2)
        if len(rets) >= 10:
            rps_10d[sector] = round(sum(rets[-10:]), 2)

    def _rank(d: dict) -> dict[str, int]:
        sorted_items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        return {k: i + 1 for i, (k, _) in enumerate(sorted_items)}

    return {
        "rps_5d": rps_5d,
        "rps_10d": rps_10d,
        "rank_5d": _rank(rps_5d),
        "rank_10d": _rank(rps_10d),
    }


def get_deepseek_client():
    """复用现有DeepSeek API客户端配置"""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    import yaml
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
    except Exception:
        cfg = {}
    # 从custom_providers查找deepseek-v4-flash
    providers = cfg.get("custom_providers", [])
    for p in providers:
        if p.get("name") == "deepseek-v4-flash":
            return OpenAI(api_key=p["api_key"], base_url=p["base_url"])
    # fallback到顶层model配置
    try:
        return OpenAI(
            api_key=cfg.get("model", {}).get("api_key", ""),
            base_url=cfg.get("model", {}).get("base_url", "https://api.deepseek.com"),
        )
    except Exception:
        return None


import os


def _ai_forward(sectors_signal: list[dict]) -> str:
    """调用DeepSeek做板块前瞻判断"""
    client = get_deepseek_client()
    if not client:
        return json.dumps({"error": "未配置AI API密钥"}, ensure_ascii=False)

    # 构建信号数据摘要（按tech_score排序，取前30个板块）
    sorted_signals = sorted(
        [s for s in sectors_signal if "tech_score" in s],
        key=lambda x: x["tech_score"], reverse=True
    )
    top_bull = [s for s in sorted_signals if s.get("tech_score", 0) >= 3][:10]
    top_bear = [s for s in sorted_signals if s.get("tech_score", 0) <= -3][:10]
    others = [s for s in sorted_signals if -3 < s.get("tech_score", 0) < 3][:10]

    prompt_parts = ["你是一位A股板块轮动分析师。请根据以下板块技术面数据，判断每个板块的短期走势。",
                    "",
                    "评分标准：",
                    "  tech_score ≥ 3: 技术面偏多（🟢看多）",
                    "  tech_score ≤ -3: 技术面偏空（🔴看空）",
                    "  其他: 方向不明（🟡观望）",
                    "",
                    "返回严格JSON格式：",
                    '{  "analysis_date": "2026-06-13",',
                    '   "summary": "一句话总体判断",',
                    '   "sectors": [',
                    '     {"name": "板块名", "signal": "bullish/bearish/neutral",',
                    '      "reason": "判断理由", "key_level": "关键价位或信号"}',
                    "   ]",
                    "}",
                    "",
                    "--- 🟢 偏多板块 ---"]
    for s in top_bull:
        prompt_parts.append(
            f"{s['name']}: MA={s.get('ma_trend')}, MACD={s.get('macd_status')}, "
            f"RSI={s.get('rsi')}, RPS5排名={s.get('rps_rank_5d')}, "
            f"得分={s.get('tech_score')}"
        )
    prompt_parts.append("")
    prompt_parts.append("--- 🟡 中性板块 ---")
    for s in others:
        prompt_parts.append(
            f"{s['name']}: MA={s.get('ma_trend')}, MACD={s.get('macd_status')}, "
            f"RSI={s.get('rsi')}, RPS5排名={s.get('rps_rank_5d')}, "
            f"得分={s.get('tech_score')}"
        )
    prompt_parts.append("")
    prompt_parts.append("--- 🔴 偏空板块 ---")
    for s in top_bear:
        prompt_parts.append(
            f"{s['name']}: MA={s.get('ma_trend')}, MACD={s.get('macd_status')}, "
            f"RSI={s.get('rsi')}, RPS5排名={s.get('rps_rank_5d')}, "
            f"得分={s.get('tech_score')}"
        )

    prompt = "\n".join(prompt_parts)

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位A股板块轮动分析师。返回严格JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        content = resp.choices[0].message.content or ""
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return content
    except Exception as e:
        return json.dumps({"error": f"AI调用失败: {str(e)[:80]}"}, ensure_ascii=False)


def run(target_date: str | None = None) -> dict:
    """入口：计算板块前瞻"""
    if not target_date:
        target_date = date.today().isoformat()

    # 1. 获取所有板块的完整指数历史
    all_rows = get_sector_indices(limit_dates=5000)

    # 按板块分组
    sector_histories: dict[str, list[dict]] = {}
    for row in all_rows:
        s = row["sector"]
        if s not in sector_histories:
            sector_histories[s] = []
        sector_histories[s].append(row)

    today = target_date

    # 2. 计算每个板块的技术面信号
    signals = []
    for sector, hist in sector_histories.items():
        sig = compute_tech_signals(hist)
        if "error" in sig:
            continue
        sig["name"] = sector
        sig["date"] = today
        signals.append(sig)

    # 3. 计算RPS排名
    rps_data = compute_rps(sector_histories, today)
    for sig in signals:
        sig["rps_5d"] = rps_data["rps_5d"].get(sig["name"], 0)
        sig["rps_10d"] = rps_data["rps_10d"].get(sig["name"], 0)
        sig["rps_rank_5d"] = rps_data["rank_5d"].get(sig["name"], 999)
        sig["rps_rank_10d"] = rps_data["rank_10d"].get(sig["name"], 999)

    # 4. AI前瞻
    ai_result_raw = _ai_forward(signals)
    ai_result = {}
    try:
        ai_result = json.loads(ai_result_raw)
    except Exception:
        ai_result = {"error": "AI返回格式异常", "raw": ai_result_raw[:200]}

    # 5. 聚合结果
    total = len(signals)
    bull_count = sum(1 for s in signals if s.get("tech_score", 0) >= 3)
    bear_count = sum(1 for s in signals if s.get("tech_score", 0) <= -3)
    neutral_count = total - bull_count - bear_count

    # 6. RL强化学习预测（加载已训练的模型）
    rl_predictions = None
    ai_rl = None
    try:
        from backend.services.analyze.sector_rl import load_model, predict_sectors
        policy_net, rl_meta = load_model()
        if policy_net is not None:
            from backend.services.analyze.sector_rl import load_all_sector_data as _load_rl_data
            rl_features = _load_rl_data()
            if rl_features:
                # 使用RL数据中最近的可预测日期
                all_rl_dates = sorted(set(f["date"] for feats in rl_features.values() for f in feats))
                rl_target = all_rl_dates[-1] if all_rl_dates else today
                rl_preds = predict_sectors(policy_net, rl_features, rl_target)
                if rl_preds:
                    rl_predictions = rl_preds[:30]
                    # 构建信号到每个板块
                    rl_map = {p["sector"]: p for p in rl_preds}
                    for sig in signals:
                        rp = rl_map.get(sig["name"])
                        if rp:
                            sig["rl_prob"] = rp["prob_up"]
                            sig["rl_pred"] = rp["prediction"]
                    # AI解读RL结果
                    up_count = sum(1 for p in rl_preds[:15] if p["prediction"] == "up")
                    top3_sectors = [p["sector"] for p in rl_preds[:3]]
                    ai_rl = {
                        "verdict": "偏多" if up_count >= 10 else ("偏空" if up_count <= 5 else "震荡"),
                        "confidence": round(abs(up_count - 7.5) / 7.5, 2),
                        "top3": top3_sectors,
                        "up_ratio": round(up_count / 15, 2),
                    }
    except Exception as e:
        ai_rl = {"error": str(e)[:60]}

    return {
        "date": today,
        "total_sectors": total,
        "summary": {
            "bullish": bull_count,
            "bearish": bear_count,
            "neutral": neutral_count,
        },
        "ai_analysis": ai_result,
        "rl_analysis": ai_rl,
        "rl_top_picks": rl_predictions[:10] if rl_predictions else None,
        "signals": signals,
        "rps_top5": sorted(
            [s for s in signals if s.get("rps_rank_5d", 999) <= 5],
            key=lambda x: x["rps_rank_5d"]
        )[:5],
    }
