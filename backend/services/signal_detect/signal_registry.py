"""信号注册表 — 买入/卖出/止损 三模块自由组合"""
from __future__ import annotations
from typing import Optional, Callable
import numpy as np

from backend.utils.indicators import sma


# ═══════════════════════════════════════════════
# 信号函数类型签名
# ═══════════════════════════════════════════════

# 买入信号: 返回 delayed_entry dict 或 None
EntryFunc = Callable[..., Optional[dict]]

# 卖出信号: 返回退出原因字符串或 None
ExitFunc = Callable[..., Optional[str]]


# ═══════════════════════════════════════════════
# 买入信号注册
# ═══════════════════════════════════════════════

ENTRY_SIGNALS = {}  # name -> {label, func, params_schema, patterns_needed?, cup_needed?}
EXIT_SIGNALS = {}   # name -> {label, func, params_schema}


def register_entry(name: str, label: str, params_schema: dict = None,
                   needs_patterns: bool = False, needs_cup: bool = False):
    """装饰器：注册买入信号"""
    def decorator(func):
        ENTRY_SIGNALS[name] = {
            "label": label,
            "func": func,
            "params_schema": params_schema or {},
            "needs_patterns": needs_patterns,
            "needs_cup": needs_cup,
        }
        return func
    return decorator


def register_exit(name: str, label: str, params_schema: dict = None):
    """装饰器：注册卖出信号"""
    def decorator(func):
        EXIT_SIGNALS[name] = {
            "label": label,
            "func": func,
            "params_schema": params_schema or {},
        }
        return func
    return decorator


# ═══════════════════════════════════════════════
# 预设策略名称 → (买入, 卖出, 默认止损%)
# ═══════════════════════════════════════════════

STRATEGY_PRESETS = {
    "ma_cross":           ("ma_cross",           "ma_death",         0.0),
    "rsi":                ("rsi_oversold",       "rsi_overbought",   0.0),
    "bollinger":          ("bollinger_lower",    "bollinger_mid",    0.0),
    "macd":               ("macd_golden",        "macd_death",       0.0),
    "candlestick":        ("candlestick_bullish","none",             7.0),
    "cup_handle":         ("cup_handle",         "none",             7.0),
    "kline_macd":         ("kline_macd",         "macd_death",       0.0),
    "kline_ma":           ("kline_ma",           "ma_death",         0.0),
    "kline_macd_elite":   ("kline_macd_elite",   "macd_death",       0.0),
    "bottom_reversal":    ("bottom_reversal",    "macd_death",       0.0),
    "pullback_breakout":  ("pullback_breakout",  "macd_death",       7.0),
    "bottom_reversal_weekly": ("bottom_reversal", "macd_death_daily_ma30", 0.0),
    # === RL优化底部反转（分板块）— 独立entry函数，不同默认参数 ===
    "bottom_reversal_semi":   ("bottom_reversal_semi", "macd_death", 0.0),
    "bottom_reversal_elec":   ("bottom_reversal_elec", "macd_death", 0.0),
    "bottom_reversal_comm":   ("bottom_reversal_comm", "macd_death", 0.0),
    "bottom_reversal_equip":  ("bottom_reversal_equip", "macd_death", 0.0),
    "bottom_reversal_celec":  ("bottom_reversal_celec", "macd_death", 0.0),
    "bottom_reversal_metal":  ("bottom_reversal_metal", "macd_death", 0.0),
    "bottom_reversal_coal":   ("bottom_reversal_coal", "macd_death", 0.0),
    "bottom_reversal_chem":   ("bottom_reversal_chem", "macd_death", 0.0),
    "bottom_reversal_pv":     ("bottom_reversal_pv", "macd_death", 0.0),
    "bottom_reversal_ship":   ("bottom_reversal_ship", "macd_death", 0.0),
    "bottom_reversal_auto":   ("bottom_reversal_auto", "macd_death", 0.0),
    "bottom_reversal_medi":   ("bottom_reversal_medi", "macd_death", 0.0),
    # === 新增9个板块策略（RL优化2026-06-15）===
    "bottom_reversal_aero":   ("bottom_reversal_aero", "macd_death", 0.0),
    "bottom_reversal_soft":   ("bottom_reversal_soft", "macd_death", 0.0),
    "bottom_reversal_batt":   ("bottom_reversal_batt", "macd_death", 0.0),
    "bottom_reversal_bio":    ("bottom_reversal_bio",  "macd_death", 0.0),
    "bottom_reversal_mil":    ("bottom_reversal_mil",  "macd_death", 0.0),
    "bottom_reversal_medd":   ("bottom_reversal_medd", "macd_death", 0.0),
    "bottom_reversal_grid":   ("bottom_reversal_grid", "macd_death", 0.0),
    "bottom_reversal_comp":   ("bottom_reversal_comp", "macd_death", 0.0),
    "bottom_reversal_tcm":    ("bottom_reversal_tcm",  "macd_death", 0.0),
}

# 预设描述
STRATEGY_LABELS = {
    "ma_cross":           "MA5/10 金叉做多",
    "rsi":                "RSI 超卖反弹做多",
    "bollinger":          "布林下轨反弹做多",
    "macd":               "MACD 金叉做多",
    "candlestick":        "K线看涨形态(大阳线/锤子线/看涨吞没等)",
    "cup_handle":         "🪙 杯柄形态",
    "kline_macd":         "🔥 K线看涨形态+MACD金叉+放量确认",
    "kline_ma":           "🔥 K线看涨形态+MA5/10金叉+放量确认",
    "kline_macd_elite":   "⭐ 精选系统(大阳线/红三兵/锤子线+MACD+放量)",
    "bottom_reversal":    "🧘 底部反转突破(死叉→0轴金叉→缩量筑底→放量突破)",
    "pullback_breakout":  "📈 缩量调整突破(死叉后平台+量MA5上穿量MA10+突破)",
    "bottom_reversal_weekly": "🧘 底部反转突破(周K趋势过滤·日K信号·日K<MA30退出)",
    # === RL优化底部反转（分板块） ===
    "bottom_reversal_semi":   "🔬 半导体底部反转(RL:min=25,max=35,vol=0.4,tol=0.95,dif=-5)",
    "bottom_reversal_elec":   "⚡ 电力底部反转(RL:min=30,max=35,vol=0.6,wr=60%🏅)",
    "bottom_reversal_comm":   "📡 通信设备底部反转(默认参数—RL过拟合回退)",
    "bottom_reversal_equip":  "🔧 专用设备底部反转(RL:min=5,max=90,vol=0.4,wr=54%🏅)",
    "bottom_reversal_celec":  "📱 消费电子底部反转(RL:min=25,max=45,vol=0.6,wr=100%🏅)",
    "bottom_reversal_metal":  "⛏️ 工业金属底部反转(RL:min=20,max=60,vol=0.6,wr=62%🏅)",
    "bottom_reversal_coal":   "🪨 煤炭开采底部反转(默认参数—RL过拟合回退)",
    "bottom_reversal_chem":   "🧪 化学制品底部反转(RL:min=25,max=75,vol=0.6,wr=63%🏅)",
    "bottom_reversal_pv":     "☀️ 光伏设备底部反转(RL:min=30,max=75,vol=0.4,wr=74%🏅)",
    "bottom_reversal_ship":   "🚢 航运港口底部反转(RL:min=15,max=25,vol=0.2,tol=0.98)",
    "bottom_reversal_auto":   "🚗 汽车零部件底部反转(RL:min=30,max=45,vol=0.5,wr=54%🏅)",
    "bottom_reversal_medi":   "💊 化学制药底部反转(RL:min=25,max=75,vol=0.6,wr=38%)",
    # === 新增9个板块策略（RL优化2026-06-15） ===
    "bottom_reversal_aero":   "🛩️ 航空装备Ⅱ底部反转(RL:wr=100%🏅,改进+47.0)",
    "bottom_reversal_soft":   "💻 软件开发底部反转(RL:wr=100%🏅,改进+66.9)",
    "bottom_reversal_batt":   "🔋 电池底部反转(默认参数—RL过拟合回退)",
    "bottom_reversal_bio":    "🧬 生物制品底部反转(RL:wr=58%🏅,改进+49.7)",
    "bottom_reversal_mil":    "🎖️ 军工电子Ⅱ底部反转(RL:wr=60%🏅,改进+17.5)",
    "bottom_reversal_medd":   "🏥 医疗器械底部反转(RL:wr=48%,改进+33.1)",
    "bottom_reversal_grid":   "⚡ 电网设备底部反转(默认参数—RL过拟合回退)",
    "bottom_reversal_comp":   "🔩 元件底部反转(RL:wr=75%🏅,改进+35.5)",
    "bottom_reversal_tcm":    "🌿 中药Ⅱ底部反转(RL:wr=21%)",
}


# ═══════════════════════════════════════════════
# 买入信号实现
# ═══════════════════════════════════════════════

@register_entry("ma_cross", "MA5/10金叉", params_schema={"fast": 5, "slow": 10})
def entry_ma_cross(i, fast, slow, ma_fast, ma_slow, **_):
    """MA5上穿MA10金叉 → 次日进场"""
    if i < 1 or np.isnan(ma_fast[i]) or np.isnan(ma_fast[i-1]) or np.isnan(ma_slow[i]) or np.isnan(ma_slow[i-1]):
        return None
    if ma_fast[i-1] <= ma_slow[i-1] and ma_fast[i] > ma_slow[i]:
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"MA{fast}金叉MA{slow}", "need_breakout": False}
    return None


@register_entry("rsi_oversold", "RSI超卖反弹", params_schema={"period": 14, "oversold": 30})
def entry_rsi_oversold(i, rsi_period, oversold, rsi_vals, **_):
    """RSI从超卖区反弹 → 次日进场"""
    if i < 1 or np.isnan(rsi_vals[i]) or np.isnan(rsi_vals[i-1]):
        return None
    if rsi_vals[i-1] < oversold and rsi_vals[i] >= oversold:
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"RSI({rsi_period})从超卖区反弹", "need_breakout": False}
    return None


@register_entry("bollinger_lower", "布林下轨反弹", params_schema={"bb_period": 20, "bb_std": 2.0})
def entry_bollinger_lower(i, low, bb_lower, **_):
    """触布林下轨反弹 → 次日进场"""
    if np.isnan(bb_lower[i]):
        return None
    if low <= bb_lower[i]:
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"触布林下轨({bb_lower[i]:.2f})", "need_breakout": False}
    return None


@register_entry("macd_golden", "MACD金叉", params_schema={"macd_fast": 12, "macd_slow": 26, "macd_signal": 9})
def entry_macd_golden(i, macd_fast, macd_slow, macd_line, macd_signal_line, **_):
    """MACD金叉 → 次日进场"""
    if i < 1 or np.isnan(macd_line[i]) or np.isnan(macd_line[i-1]) or np.isnan(macd_signal_line[i]) or np.isnan(macd_signal_line[i-1]):
        return None
    if macd_line[i-1] <= macd_signal_line[i-1] and macd_line[i] > macd_signal_line[i]:
        return {"direction": "long", "entry_idx": i + 1,
                "signal": "MACD金叉", "need_breakout": False}
    return None


def _check_volume(i, volumes, min_ratio=1.2) -> tuple[bool, float]:
    """放量确认：当日量 > MA20量的 min_ratio 倍"""
    if i < 20:
        return False, 0.0
    vol_ma20 = sma(volumes, 20)[i]
    ratio = volumes[i] / vol_ma20
    return ratio >= min_ratio, ratio


@register_entry("candlestick_bullish", "K线看涨形态+放量确认", needs_patterns=True)
def entry_candlestick_bullish(i, all_patterns, volumes, **_):
    """任意K线看涨形态 + 放量确认 → 次日进场"""
    patterns = all_patterns[i] if i < len(all_patterns) else []
    bullish = [p for p in patterns if p["direction"] == "bullish"]
    if not bullish:
        return None
    ok, ratio = _check_volume(i, volumes)
    if not ok:
        return None
    sig = " + ".join([p["pattern"] for p in bullish[:2]])
    return {"direction": "long", "entry_idx": i + 1,
            "signal": f"看涨形态+放量{ratio:.1f}倍: {sig}", "need_breakout": False}


@register_entry("cup_handle", "杯柄形态", needs_cup=True, params_schema={"min_score": 0.35})
def entry_cup_handle(ch_signals, ch_pointer, **_):
    """杯柄形态 → 次日检查买点突破后入场"""
    # 这个特殊处理，由主循环调用
    return None  # 实际在 run_backtest 中特殊处理


@register_entry("kline_macd", "K线看涨形态+MACD金叉+放量确认", needs_patterns=True)
def entry_kline_macd(i, all_patterns, volumes, macd_line, macd_signal_line, **_):
    """K线看涨形态 + MACD金叉(3天窗口) + 放量确认"""
    patterns = all_patterns[i] if i < len(all_patterns) else []
    bullish = [p for p in patterns if p["direction"] == "bullish"]
    if not bullish:
        return None
    ok, ratio = _check_volume(i, volumes)
    if not ok:
        return None
    macd_golden = False
    for j in range(max(1, i - 2), i + 1):
        if (j >= 1 and not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] <= macd_signal_line[j-1] and macd_line[j] > macd_signal_line[j]):
            macd_golden = True
            break
    if macd_golden:
        sig = " + ".join([p["pattern"] for p in bullish[:2]])
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"K线形态+MACD金叉+放量{ratio:.1f}倍: {sig}", "need_breakout": False}
    return None


@register_entry("kline_ma", "K线看涨形态+MA5/10金叉+放量确认", needs_patterns=True)
def entry_kline_ma(i, all_patterns, volumes, fast, slow, ma_fast, ma_slow, **_):
    """K线看涨形态 + MA5/10金叉(3天窗口) + 放量确认"""
    patterns = all_patterns[i] if i < len(all_patterns) else []
    bullish = [p for p in patterns if p["direction"] == "bullish"]
    if not bullish:
        return None
    ok, ratio = _check_volume(i, volumes)
    if not ok:
        return None
    ma_golden = False
    for j in range(max(1, i - 2), i + 1):
        if (j >= 1 and not np.isnan(ma_fast[j]) and not np.isnan(ma_fast[j-1])
            and not np.isnan(ma_slow[j]) and not np.isnan(ma_slow[j-1])
            and ma_fast[j-1] <= ma_slow[j-1] and ma_fast[j] > ma_slow[j]):
            ma_golden = True
            break
    if ma_golden:
        sig = " + ".join([p["pattern"] for p in bullish[:2]])
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"K线形态+MA金叉+放量{ratio:.1f}倍: {sig}", "need_breakout": False}
    return None


@register_entry("kline_macd_elite", "精选系统(大阳线/红三兵/锤子线+MACD+放量)", needs_patterns=True)
def entry_kline_macd_elite(i, all_patterns, volumes, macd_line, macd_signal_line, **_):
    """精选系统：仅大阳线/三连阳/锤子线 + MACD金叉 + 放量确认"""
    patterns = all_patterns[i] if i < len(all_patterns) else []
    elite_set = {"大阳线", "三连阳（红三兵）", "锤子线"}
    bullish = [p for p in patterns if p["direction"] == "bullish" and p["pattern"] in elite_set]
    if not bullish:
        return None
    ok, ratio = _check_volume(i, volumes)
    if not ok:
        return None
    macd_golden = False
    for j in range(max(1, i - 2), i + 1):
        if (j >= 1 and not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] <= macd_signal_line[j-1] and macd_line[j] > macd_signal_line[j]):
            macd_golden = True
            break
    if macd_golden:
        sig = " + ".join([p["pattern"] for p in bullish[:2]])
        return {"direction": "long", "entry_idx": i + 1,
                "signal": f"精选形态+MACD金叉+放量{ratio:.1f}倍: {sig}", "need_breakout": False}
    return None


@register_entry("bottom_reversal", "底部反转突破(多头排列回踩→MA60支撑→MACD0轴附近金叉→量放)",
                 params_schema={"min_days": 10, "max_days": 45, "check_before": 10})
def entry_bottom_reversal(i, closes, highs, lows, opens, volumes, macd_line, macd_signal_line,
                           ma_fast, ma_slow, ma_20, ma_60,
                           min_days=10, max_days=45, check_before=10,
                           weekly_mode=False, ma_120=None,
                           gc_window=5, vol_ratio=0.4, ma60_tol=0.95, dif_thresh=-1.0, vol_min_idx=5, **_):
    """
    底部反转突破 v3:
    ① 回调前: MA5>MA10>MA20, 价格>MA60, MA60斜率向上
    ② 死叉: DIF>0, DEA>0, 量MA5<量MA10(置信)
    ③ 筑底: 价格在MA60附近(>=MA60*ma60_tol), 小实体K线, 量<量MA5
    ④ 突破: MACD金叉(DIF>=dif_thresh, DEA>=dif_thresh), 量>MA5或量MA5/10金叉

    weekly_mode=True 时: 增加 MA60 > MA120 趋势过滤（日K ≈ 60日 > 120日），
    信号检测仍在日K级别进行。
    """
    max_lookback = max_days + 10
    min_bars = 220  # 日K: 220个交易日 ≈ 1年
    if i < max(max_lookback, min_bars):
        return None

    window_start = max(0, i - max_lookback)

    # 周K模式：短期MA60 > 长期MA120 趋势过滤（日K ≈ 60日 > 120日）
    if weekly_mode:
        if ma_120 is None or np.isnan(ma_120[i]) or np.isnan(ma_60[i]):
            return None
        if ma_60[i] <= ma_120[i]:
            return None

    # ── 阶段④: 找MACD金叉(最后gc_window bar内) ──
    golden_cross_idx = None
    for j in range(max(window_start, i - gc_window), i + 1):
        if j < 1:
            continue
        if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] <= macd_signal_line[j-1] and macd_line[j] > macd_signal_line[j]
            and macd_line[j] >= dif_thresh and macd_signal_line[j] >= dif_thresh):
                golden_cross_idx = j
                break

    if golden_cross_idx is None:
        return None

    # ── 阶段②: 找之前的死叉(DIF>0, DEA>0) ──
    candidate_deaths = []
    for j in range(window_start, golden_cross_idx):
        if j < 1:
            continue
        if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] >= macd_signal_line[j-1] and macd_line[j] < macd_signal_line[j]
            and macd_line[j] > 0 and macd_signal_line[j] > 0):
                candidate_deaths.append(j)

    valid_deaths = [(golden_cross_idx - d, d) for d in candidate_deaths
                    if min_days <= golden_cross_idx - d <= max_days]
    if not valid_deaths:
        return None

    interval, death_cross_idx = max(valid_deaths)

    # ── 阶段①: 死叉前MA5>MA10>MA20 + 价格>MA60 + MA60斜率向上 ──
    pre_idx = death_cross_idx - check_before
    min_pre_bars = 200
    if pre_idx < min_pre_bars:
        return None
    if (np.isnan(ma_fast[pre_idx]) or np.isnan(ma_slow[pre_idx]) or np.isnan(ma_20[pre_idx])
        or np.isnan(ma_60[pre_idx])):
        return None
    if not (ma_fast[pre_idx] > ma_slow[pre_idx] > ma_20[pre_idx]):
        return None
    if closes[pre_idx] < ma_60[pre_idx]:
        return None
    ma60_lookback = 5  # 日K: 5天
    pre_ma60 = max(0, pre_idx - ma60_lookback)
    if np.isnan(ma_60[pre_idx]) or np.isnan(ma_60[pre_ma60]):
        return None
    if ma_60[pre_idx] <= ma_60[pre_ma60]:
        return None

    # ── 阶段③: 筑底期价格在MA60附近 ──
    for j in range(death_cross_idx, golden_cross_idx):
        if np.isnan(ma_60[j]) or np.isnan(closes[j]):
            continue
        if closes[j] < ma_60[j] * ma60_tol:
            return None

    # ── 阶段③: 筑底期缩量 + 小实体K线置信度 ──
    vol_ma5_win = 5   # 日K: MA5
    vol_ma10_win = 10  # 日K: MA10
    vol_sma5 = sma(volumes, vol_ma5_win)   # 预计算量MA5
    vol_sma10 = sma(volumes, vol_ma10_win)  # 预计算量MA10
    low_vol_count = 0
    total_check = 0
    small_body_count = 0
    for j in range(death_cross_idx, golden_cross_idx):
        if j < vol_ma10_win:
            continue
        vv5 = vol_sma5[j]
        vv10 = vol_sma10[j]
        total_check += 1
        if vv5 < vv10:
            low_vol_count += 1
        # 小实体K线(实体<波幅50%)
        body_ratio = abs(closes[j] - opens[j]) / max(highs[j] - lows[j], 0.01)
        if body_ratio < 0.5:
            small_body_count += 1

    min_vol_checks = 5
    if total_check < min_vol_checks or low_vol_count < total_check * vol_ratio:
        return None

    # ── 阶段④: 放量确认(量>MA5 OR 量MA5上穿量MA10) ──
    vol_ok = False
    for offset in range(gc_window):
        ii = golden_cross_idx + offset
        if ii >= len(volumes):
            break
        if ii < vol_min_idx:
            continue
        vv5 = vol_sma5[ii]
        vv10 = vol_sma10[ii] if ii >= vol_ma10_win else 0
        # 条件A: 成交量 > 量MA5
        if volumes[ii] > vv5:
            vol_ok = True
            break
        # 条件B: 量MA5上穿量MA10
        if ii >= vol_ma10_win and vv5 > vv10:
            vol_ok = True
            break

    if not vol_ok:
        return None

    label = "日"
    return {
        "direction": "long",
        "entry_idx": i + 1,
        "signal": (f"底部反转突破v3(回踩{interval}{label}+"
                   f"小实体{small_body_count}/{total_check}+"
                   f"0轴金叉DIF={macd_line[golden_cross_idx]:.1f})"),
        "need_breakout": False,
    }


# ═══════════════════════════════════════════════
# RL优化底部反转（分板块 wrapper）
# ═══════════════════════════════════════════════
_RL_PARAMS = {
    # ── 以下16个板块通过150天样本外验证 ✅ ──
    # 半导体：旧检查点无数据，保留原参数
    "bottom_reversal_semi":  {"min_days": 25, "max_days": 35, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -5, "gc_window": 10},
    # 电力: ✅ WR 33.6%→60.0%, PnL 4.0→15.8
    "bottom_reversal_elec":  {"min_days": 30, "max_days": 35, "vol_ratio": 0.6,  "ma60_tol": 0.90, "dif_thresh": -3, "gc_window": 5},
    # 通信设备: ❌ 过拟合 → 回退默认参数
    "bottom_reversal_comm":  {"min_days": 10, "max_days": 45, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -1, "gc_window": 5},
    # 专用设备: ✅ WR 39.8%→54.4%, PnL 0.5→647.7
    "bottom_reversal_equip": {"min_days":  5, "max_days": 90, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -3, "gc_window": 7},
    # 消费电子: ✅ WR 37.1%→100.0%, PnL -3.0→63.6
    "bottom_reversal_celec": {"min_days": 25, "max_days": 45, "vol_ratio": 0.6,  "ma60_tol": 0.97, "dif_thresh": -5, "gc_window": 10},
    # 工业金属: ✅ WR 36.8%→62.5%, PnL 27.0→110.0
    "bottom_reversal_metal": {"min_days": 20, "max_days": 60, "vol_ratio": 0.6,  "ma60_tol": 0.97, "dif_thresh": -5, "gc_window": 7},
    # 煤炭开采: ❌ 过拟合 → 回退默认参数
    "bottom_reversal_coal":  {"min_days": 10, "max_days": 45, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -1, "gc_window": 5},
    # 化学制品: ✅ WR 40.3%→63.1%, PnL 6.9→200.3
    "bottom_reversal_chem":  {"min_days": 25, "max_days": 75, "vol_ratio": 0.6,  "ma60_tol": 0.90, "dif_thresh": -3, "gc_window": 10},
    # 光伏设备: ✅⭐ WR 30.8%→73.9%, PnL 426.4→1785.6（效果最显著）
    "bottom_reversal_pv":    {"min_days": 30, "max_days": 75, "vol_ratio": 0.4,  "ma60_tol": 0.93, "dif_thresh": -3, "gc_window": 10},
    # 航运港口：不在RL优化板块中（CSI500中<8只），保留原参数
    "bottom_reversal_ship":  {"min_days": 15, "max_days": 25, "vol_ratio": 0.2,  "ma60_tol": 0.98, "dif_thresh": -5, "gc_window": 10},
    # 汽车零部件: ✅ WR 32.8%→53.5%, PnL 43.0→64.9
    "bottom_reversal_auto":  {"min_days": 30, "max_days": 45, "vol_ratio": 0.5,  "ma60_tol": 0.95, "dif_thresh": -3, "gc_window": 10},
    # 化学制药: ✅ WR 16.7%→37.5%, PnL -64.5→33.1
    "bottom_reversal_medi":  {"min_days": 25, "max_days": 75, "vol_ratio": 0.6,  "ma60_tol": 0.90, "dif_thresh": -1, "gc_window": 7},

    # ── 新增9个板块策略（以下通过验证的已确认） ──
    # 航空装备Ⅱ: ✅ WR 20.8%→100.0%, PnL -189.3→103.9
    "bottom_reversal_aero":  {"min_days": 30, "max_days": 60, "vol_ratio": 0.4,  "ma60_tol": 0.93, "dif_thresh": -5, "gc_window": 5},
    # 软件开发: ✅ WR 25.0%→100.0%, PnL 66.0→138.9
    "bottom_reversal_soft":  {"min_days": 20, "max_days": 60, "vol_ratio": 0.5,  "ma60_tol": 0.93, "dif_thresh":  0, "gc_window": 3},
    # 电池: ❌ 过拟合 → 回退默认参数
    "bottom_reversal_batt":  {"min_days": 10, "max_days": 45, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -1, "gc_window": 5},
    # 生物制品: ✅ WR 0.0%→58.3%, PnL -1.1→178.7
    "bottom_reversal_bio":   {"min_days":  5, "max_days": 75, "vol_ratio": 0.3,  "ma60_tol": 0.90, "dif_thresh": -5, "gc_window": 7},
    # 军工电子Ⅱ: ✅ WR 58.9%→67.1%, PnL 391.1→723.7
    "bottom_reversal_mil":   {"min_days": 20, "max_days": 45, "vol_ratio": 0.3,  "ma60_tol": 0.90, "dif_thresh": -5, "gc_window": 5},
    # 医疗器械: ✅ WR 15.8%→48.5%, PnL -47.1→187.7
    "bottom_reversal_medd":  {"min_days": 30, "max_days": 60, "vol_ratio": 0.5,  "ma60_tol": 0.97, "dif_thresh": -1, "gc_window": 10},
    # 电网设备: ❌ 过拟合 → 回退默认参数
    "bottom_reversal_grid":  {"min_days": 10, "max_days": 45, "vol_ratio": 0.4,  "ma60_tol": 0.95, "dif_thresh": -1, "gc_window": 5},
    # 元件: ⚠️ 勉强可用（75.0%但仅8笔, PnL 569.8→309.7下降）
    "bottom_reversal_comp":  {"min_days": 30, "max_days": 35, "vol_ratio": 0.4,  "ma60_tol": 0.93, "dif_thresh":  2, "gc_window": 7},
    # 中药Ⅱ: ✅ WR 18.2%→23.8%, PnL -20.8→13.5
    "bottom_reversal_tcm":   {"min_days": 30, "max_days": 35, "vol_ratio": 0.3,  "ma60_tol": 0.95, "dif_thresh": -3, "gc_window": 7},
}

for _rl_name, _rl_p in _RL_PARAMS.items():
    # 动态注册：每个板块一个独立entry函数
    # 注意：必须从**kw中移除冲突key，避免"multiple values"错误
    _rl_keys_str = repr(list(_rl_p.keys()))
    _rl_params_str = ','.join(f'{k}={v}' for k, v in _rl_p.items())
    _fn = eval(f"lambda i, **kw: entry_bottom_reversal(i, **{{k:v for k,v in kw.items() if k not in {_rl_keys_str}}}, {_rl_params_str})")
    _fn.__name__ = f"entry_{_rl_name}"
    _fn.__qualname__ = _fn.__name__
    register_entry(_rl_name,
                   f"RL底部反转({_rl_name.split('_')[-1]}板块)",
                   params_schema=_rl_p)(_fn)


@register_entry("pullback_breakout", "缩量调整放量突破(死叉后小幅回踩+MACD金叉+量MA5上穿量MA10+突破)",
                 params_schema={"max_lookback": 10, "min_days_since_death": 3})
def entry_pullback_breakout(i, closes, highs, lows, volumes, macd_line, macd_signal_line,
                             max_lookback=10, min_days_since_death=3, **_):
    """缩量调整放量突破：MACD死叉后短期回踩横盘→MACD金叉→量MA5上穿量MA10→突破
       上涨趋势中的回调（死叉时DIF>0），周期3-10天"""
    if i < max_lookback + 5:
        return None

    window_start = max(0, i - max_lookback)

    # ── 1. 找窗口内的MACD死叉（DIF>0，上涨回调性质） ──
    death_cross_idx = None
    for j in range(window_start, i):
        if j < 1:
            continue
        if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] >= macd_signal_line[j-1] and macd_line[j] < macd_signal_line[j]
            and macd_line[j] > 0):  # 死叉时DIF>0（上涨回调）
            death_cross_idx = j
            break

    if death_cross_idx is None:
        return None

    # ── 2. 找MACD金叉（突破日前后2天内） ──
    golden_cross_idx = None
    for j in range(max(window_start, i - 2), min(i + 3, len(macd_line))):
        if j < 1 or j >= len(macd_line):
            continue
        if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
            and not np.isnan(macd_signal_line[j]) and not np.isnan(macd_signal_line[j-1])
            and macd_line[j-1] <= macd_signal_line[j-1] and macd_line[j] > macd_signal_line[j]):
            golden_cross_idx = j
            break

    if golden_cross_idx is None:
        return None

    # ── 3. 检查时间跨度 ──
    days_since_death = i - death_cross_idx
    if days_since_death < min_days_since_death or days_since_death > max_lookback:
        return None

    # ── 4. 横盘区间检查 ──
    consol_start = death_cross_idx
    consol_end = i - 1
    if consol_end - consol_start < 2:
        return None

    consol_highs = highs[consol_start:consol_end + 1]
    consol_lows = lows[consol_start:consol_end + 1]
    plat_high = float(np.max(consol_highs))
    plat_low = float(np.min(consol_lows))
    plat_mid = (plat_high + plat_low) / 2
    plat_range = (plat_high - plat_low) / plat_mid

    if plat_range > 0.15:
        return None

    # ── 5. 缩量：横盘期量MA5 < 量MA10 ──
    low_vol_count = 0
    total_check = 0
    pb_vol_sma5 = sma(volumes, 5)
    pb_vol_sma10 = sma(volumes, 10)
    for j in range(consol_start, consol_end + 1):
        if j < 9:
            continue
        vol_ma5 = pb_vol_sma5[j]
        vol_ma10 = pb_vol_sma10[j]
        total_check += 1
        if vol_ma5 < vol_ma10:
            low_vol_count += 1

    if total_check < 2 or low_vol_count < total_check * 0.5:
        return None

    # ── 6. 突破+放量确认 ──
    if i < 9:
        return None
    vol_ma5_today = pb_vol_sma5[i]
    vol_ma10_today = pb_vol_sma10[i]

    # 价格突破 或 量MA5上穿量MA10
    if closes[i] <= plat_high and vol_ma5_today <= vol_ma10_today:
        # 收盘价和量MA5都没突破
        if not (highs[i] > plat_high and vol_ma5_today > vol_ma10_today):
            # 除非日内突破+量确认
            return None

    return {
        "direction": "long",
        "entry_idx": i + 1,
        "signal": (f"缩量调整放量突破(死叉后{days_since_death}天+"
                   f"横盘{plat_range*100:.1f}%+量MA5上穿量MA10)"),
        "need_breakout": False,
    }


# ═══════════════════════════════════════════════
# 卖出信号实现
# ═══════════════════════════════════════════════

@register_exit("none", "无(仅止损退出)")
def exit_none(**_) -> Optional[str]:
    return None


@register_exit("ma20_or_macd_death", "价格跌破MA20或MACD死叉")
def exit_ma20_or_macd_death(i, closes, ma_20, macd_line, macd_signal_line, **_):
    """组合退出：价格跌破MA20 或者 MACD在0轴上方死叉"""
    # MA20跌破
    if i >= 20 and not np.isnan(ma_20[i]):
        if closes[i] < ma_20[i]:
            return "价格跌破MA20"
    # MACD在0轴上方死叉
    if i >= 1 and (not np.isnan(macd_line[i]) and not np.isnan(macd_line[i-1])
                   and not np.isnan(macd_signal_line[i]) and not np.isnan(macd_signal_line[i-1])):
        if (macd_line[i] > 0 and macd_signal_line[i] > 0  # 0轴上方
            and macd_line[i-1] >= macd_signal_line[i-1] and macd_line[i] < macd_signal_line[i]):
            return "MACD死叉"
    return None


@register_exit("ma_death", "MA5/10死叉", params_schema={"fast": 5, "slow": 10})
def exit_ma_death(i, fast, slow, ma_fast, ma_slow, **_):
    """做多单MA5下穿MA10死叉退出"""
    if i < 1 or np.isnan(ma_fast[i]) or np.isnan(ma_fast[i-1]) or np.isnan(ma_slow[i]) or np.isnan(ma_slow[i-1]):
        return None
    if ma_fast[i-1] >= ma_slow[i-1] and ma_fast[i] < ma_slow[i]:
        return f"MA{fast}死叉"
    return None


@register_exit("rsi_overbought", "RSI进入超买区", params_schema={"overbought": 70})
def exit_rsi_overbought(i, rsi_vals, overbought, **_):
    """RSI进入超买区，上升动能减弱"""
    if i < 1 or np.isnan(rsi_vals[i]) or np.isnan(rsi_vals[i-1]):
        return None
    if rsi_vals[i-1] > overbought and rsi_vals[i] <= overbought:
        return "RSI进入超买区"
    return None


@register_exit("bollinger_mid", "价格回到布林中轨")
def exit_bollinger_mid(i, closes, bb_mid, **_):
    """做多单价格跌破布林中轨退出"""
    if np.isnan(bb_mid[i]):
        return None
    if closes[i] <= bb_mid[i]:
        return "价格回到布林中轨"
    return None


@register_exit("macd_death", "MACD死叉")
def exit_macd_death(i, macd_line, macd_signal_line, **_):
    """MACD死叉退出"""
    if i < 1 or np.isnan(macd_line[i]) or np.isnan(macd_line[i-1]) or np.isnan(macd_signal_line[i]) or np.isnan(macd_signal_line[i-1]):
        return None
    if macd_line[i-1] >= macd_signal_line[i-1] and macd_line[i] < macd_signal_line[i]:
        return "MACD死叉"
    return None


@register_exit("macd_death_pred", "MACD死叉(提前1-2日预测)")
def exit_macd_death_pred(i, macd_line, macd_signal_line,
                          weekly_mode=False,
                          death_cross_flags=None,
                          death_cross_pred_flags=None,
                          **_):
    """
    MACD死叉退出（含提前1-2日预测）：
    日K模式：标准MACD死叉
    周K模式：使用日K聚合标志，要求预测标志在前1-2根bar有效
    """
    if not weekly_mode:
        # 日K模式：标准MACD死叉
        if i < 1 or np.isnan(macd_line[i]) or np.isnan(macd_line[i-1]) or np.isnan(macd_signal_line[i]) or np.isnan(macd_signal_line[i-1]):
            return None
        if macd_line[i-1] >= macd_signal_line[i-1] and macd_line[i] < macd_signal_line[i]:
            return "MACD死叉"
        return None

    # 周K模式：使用日K聚合标志+预测标志
    if death_cross_flags is None or i >= len(death_cross_flags) or not bool(death_cross_flags[i]):
        return None
    if np.isnan(macd_line[i]) or np.isnan(macd_signal_line[i]):
        return None
    if not (macd_line[i] > 0 and macd_signal_line[i] > 0):
        return None

    # 预测检查：当天或前1天必须有逼近死叉标志
    has_pred = (death_cross_pred_flags is not None and
                len(death_cross_pred_flags) > i and
                bool(death_cross_pred_flags[i]))
    has_pred_prev = (i >= 1 and death_cross_pred_flags is not None and
                     len(death_cross_pred_flags) > i - 1 and
                     bool(death_cross_pred_flags[i - 1]))
    if has_pred or has_pred_prev:
        return f"MACD死叉(已预测)"
    return None


@register_exit("macd_death_daily_ma30", "日K跌破MA30或MACD死叉")
def exit_macd_death_daily_ma30(i, closes, macd_line, macd_signal_line,
                                weekly_mode=False, daily_ma30=None,
                                **_):
    """退出：日K跌破MA30 或 MACD死叉

    周K模式：使用日K MA30跌破作为退出信号
    日K模式：标准MACD死叉
    """
    if weekly_mode:
        # 周K模式：日K跌破MA30 或 MACD死叉
        if daily_ma30 is not None and i < len(daily_ma30) and not np.isnan(daily_ma30[i]):
            if closes[i] < daily_ma30[i]:
                return "日K跌破MA30"
        if i >= 1 and (not np.isnan(macd_line[i]) and not np.isnan(macd_line[i - 1])
                       and not np.isnan(macd_signal_line[i]) and not np.isnan(macd_signal_line[i - 1])):
            if macd_line[i - 1] >= macd_signal_line[i - 1] and macd_line[i] < macd_signal_line[i]:
                return "MACD死叉"
        return None

    # 日K模式：标准MACD死叉
    if i >= 1 and (not np.isnan(macd_line[i]) and not np.isnan(macd_line[i - 1])
                   and not np.isnan(macd_signal_line[i]) and not np.isnan(macd_signal_line[i - 1])):
        if macd_line[i - 1] >= macd_signal_line[i - 1] and macd_line[i] < macd_signal_line[i]:
            return "MACD死叉"
    return None


@register_exit("price_below_ma20", "价格跌破MA20")
def exit_price_below_ma20(i, closes, **_):
    """做多单价格跌破MA20退出"""
    if i < 20:
        return None
    ma20 = sma(closes, 20)[i]
    if closes[i] < ma20:
        return "价格跌破MA20"
    return None


# ═══════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════

def resolve_strategy(strategy: str) -> tuple[str, str, float]:
    """将策略名称解析为(买入信号, 卖出信号, 默认止损%)"""
    if strategy in STRATEGY_PRESETS:
        return STRATEGY_PRESETS[strategy]
    # 如果策略名本身已经是 entry+exit 格式
    parts = strategy.split("+")
    if len(parts) == 2:
        entry, exit = parts
        if entry in ENTRY_SIGNALS and exit in EXIT_SIGNALS:
            return entry, exit, 0.0
    # 如果策略名直接是买入信号名，卖出用none
    if strategy in ENTRY_SIGNALS:
        return strategy, "none", 0.0
    # 默认
    return "ma_cross", "ma_death", 0.0


def combo_name(entry_signal: str, exit_signal: str) -> str:
    """返回组合策略名，如 ma_cross+macd_death"""
    return f"{entry_signal}+{exit_signal}"


def combo_label(entry_signal: str, exit_signal: str) -> str:
    """返回组合的中文描述"""
    e_label = ENTRY_SIGNALS.get(entry_signal, {}).get("label", entry_signal)
    x_label = EXIT_SIGNALS.get(exit_signal, {}).get("label", exit_signal)
    return f"{e_label} → {x_label}"
