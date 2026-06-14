#!/usr/bin/env python3
"""
HS300全策略回测脚本
====================
规则:
  - 信号出现后第二天开盘买入
  - 买入最高20000元，1手=100股，不够不买
  - 200MA以下的股票不买
  - 卖出和买入不能在同一天 (T+1)
  - 测试6种策略，选出盈亏比最高的组合

用法:
  python3 scripts/hs300_backtest.py
"""

import sys, os, json, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.market_service import get_daily_history
from backend.patterns import detect_patterns, detect_cup_handle

# ============================================================
# 配置
# ============================================================
MAX_AMOUNT = 20000  # 最大买入金额
SHARE_LOT = 100     # 1手股数
MAX_DAYS = 500      # 回测历史天数
MIN_TRADES = 5      # 策略最少交易次数才计入评比

HS300_CSV = Path.home() / "Jarvis" / "A股行情信息" / "HS300_2026-06-05.csv"

OUTPUT_DIR = Path.home() / "Jarvis" / "backtest_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 工具函数
# ============================================================

def load_hs300_codes() -> list[str]:
    """从CSV读取HS300成分股代码"""
    df = pd.read_csv(str(HS300_CSV), encoding="utf-16", sep="\t")
    codes = []
    for _, row in df.iterrows():
        raw = str(row["代码"]).strip().strip("'\"")
        # 跳过指数
        if raw.startswith("BK") or raw in ("HS300_",):
            continue
        # 只保留A股格式：6位数字
        if re.match(r"^\d{6}$", raw):
            codes.append(raw)
    return codes


def calc_ma(arr: np.ndarray, period: int) -> np.ndarray:
    """滚动SMA"""
    result = np.full(len(arr), np.nan)
    if len(arr) < period:
        return result
    cumsum = np.cumsum(arr)
    result[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])) / period
    return result


def calc_rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
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


def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(arr), np.nan)
    if len(arr) < 1:
        return result
    result[0] = arr[0]
    alpha = 2 / (period + 1)
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


def scan_cup_handle_signals(df: pd.DataFrame, min_score: float = 0.35) -> list[dict]:
    """扫描全历史找所有杯柄信号"""
    n = len(df)
    signals = []
    scan_step = 5
    for end in range(60, n, scan_step):
        sub = df.iloc[:end + 1].copy().reset_index(drop=True)
        result = detect_cup_handle(sub)
        if result and result[0].get("cup_handle_detail"):
            ch = result[0]["cup_handle_detail"]
            if ch.get("score", 0) >= min_score:
                signals.append({
                    "detection_idx": end,
                    "buy_point": ch["buy_point"],
                    "score": ch["score"],
                    "cup_depth": ch["cup_depth"],
                    "handle_depth": ch["handle_depth"],
                    "confidence": result[0].get("confidence", "low"),
                })
    # 去重（同买点只留第一个）
    seen = set()
    deduped = []
    for s in sorted(signals, key=lambda x: x["detection_idx"]):
        bp = round(s["buy_point"], 1)
        if bp not in seen:
            seen.add(bp)
            deduped.append(s)
    return deduped


# ============================================================
# 核心回测
# ============================================================

def run_single_backtest(
    code: str,
    strategy: str,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    params: dict = None,
) -> list[dict]:
    """
    对单只股票跑策略回测（HS300定制版）
    返回: [{
        entry_date, entry_price, entry_signal,
        exit_date, exit_price, exit_reason,
        pnl, return_pct, holding_days,
        shares, cost
    }, ...]
    """
    params = params or {}

    # 杯柄默认7%止损
    if strategy == "cup_handle" and sl_pct == 0:
        sl_pct = 7.0

    df = get_daily_history(code, MAX_DAYS)
    if df is None or df.empty or len(df) < 30:
        return []

    closes = df["close"].values.astype(float)
    opens = df["open"].values.astype(float)
    highs = df["high"].values.astype(float)
    lows = df["low"].values.astype(float)
    dates = df["date"].values
    n = len(closes)

    # 预计算指标
    fast = params.get("fast", 5)
    slow = params.get("slow", 10)
    rsi_period = params.get("period", 14)
    bb_period = params.get("bb_period", 20)
    bb_std = params.get("bb_std", 2.0)
    macd_fast = params.get("macd_fast", 12)
    macd_slow = params.get("macd_slow", 26)
    macd_signal = params.get("macd_signal", 9)
    overbought = params.get("overbought", 70)
    oversold = params.get("oversold", 30)

    ma_fast = calc_ma(closes, fast)
    ma_slow = calc_ma(closes, slow)
    rsi_vals = calc_rsi(closes, rsi_period)
    ma200 = calc_ma(closes, 200)

    # 布林带
    bb_mid = calc_ma(closes, bb_period)
    bb_std_arr = np.full(n, np.nan)
    for i in range(bb_period - 1, n):
        bb_std_arr[i] = np.std(closes[i - bb_period + 1:i + 1])
    bb_upper = bb_mid + bb_std * bb_std_arr
    bb_lower = bb_mid - bb_std * bb_std_arr

    # MACD
    ema_f = calc_ema(closes, macd_fast)
    ema_s = calc_ema(closes, macd_slow)
    macd_line = ema_f - ema_s
    macd_signal_line = np.full(n, np.nan)
    if n >= macd_signal:
        alpha = 2 / (macd_signal + 1)
        macd_signal_line[0] = macd_line[0]
        for i in range(1, n):
            macd_signal_line[i] = alpha * macd_line[i] + (1 - alpha) * macd_signal_line[i - 1]
    macd_hist = macd_line - macd_signal_line

    # K线形态预计算
    all_patterns = []
    if strategy == "candlestick":
        for idx in range(n):
            if idx < 4:
                all_patterns.append([])
            else:
                sub = df.iloc[idx - 4:idx + 1]
                all_patterns.append(detect_patterns(sub))
    else:
        all_patterns = [[] for _ in range(n)]

    # 杯柄预扫描
    ch_signals = []
    ch_pointer = 0
    if strategy == "cup_handle":
        ch_signals = scan_cup_handle_signals(df, params.get("min_score", 0.35))
        ch_signals.sort(key=lambda s: s["detection_idx"])

    trades = []
    in_position = False
    position = None
    delayed_entry = None

    # 辅助：计算可买股数
    def _calc_shares(price):
        """根据价格计算可买股数（≤20000元，100的倍数）"""
        max_shares = int(MAX_AMOUNT / price / SHARE_LOT) * SHARE_LOT
        return max_shares if max_shares >= SHARE_LOT else 0

    for i in range(1, n):
        close = closes[i]
        open_ = opens[i]
        high = highs[i]
        low = lows[i]
        date_str = str(dates[i])[:10]

        # ---- T+1延迟入场激活（次日开盘买入） ----
        if delayed_entry is not None and i == delayed_entry["entry_idx"]:
            de = delayed_entry
            delayed_entry = None

            # MA200过滤：收盘价必须 > MA200
            if np.isnan(ma200[i]) or close <= ma200[i]:
                continue  # MA200以下不买

            entry_price = open_  # 开盘买入

            # 杯柄额外检查：开盘价必须触及买点
            if de.get("need_breakout") and high < de["buy_point"]:
                continue  # 买点未突破，跳过

            if de.get("need_breakout"):
                entry_price = max(open_, de["buy_point"])

            # 仓位计算
            shares = _calc_shares(entry_price)
            if shares == 0:
                continue  # 钱不够买1手

            cost = shares * entry_price
            in_position = True
            position = {
                "direction": "long",
                "entry_price": entry_price,
                "entry_date": date_str,
                "entry_idx": i,
                "entry_signal": de["signal"],
                "shares": shares,
                "cost": cost,
                "mfe": 0.0,
                "mae": 0.0,
            }
            continue  # T+1：入场日不能卖出

        # ---- 平仓检查 ----
        if in_position and position is not None:
            pos = position
            days_held = i - pos["entry_idx"]

            # 更新浮动盈亏（按收盘价）
            unrealized = (close - pos["entry_price"]) * pos["shares"]
            unrealized_pct = (close / pos["entry_price"] - 1) * 100

            if pos["direction"] == "long":
                pos["mfe"] = max(pos["mfe"], high - pos["entry_price"])
                pos["mae"] = min(pos["mae"], low - pos["entry_price"])

            exit_reason = None
            exit_price = close

            # 止损（低点触发）
            if sl_pct > 0:
                sl_price = pos["entry_price"] * (1 - sl_pct / 100)
                if low <= sl_price:
                    exit_reason = "止损"
                    exit_price = sl_price  # 以止损价成交

            # 止盈
            if tp_pct > 0 and exit_reason is None:
                tp_price = pos["entry_price"] * (1 + tp_pct / 100)
                if high >= tp_price:
                    exit_reason = "止盈"
                    exit_price = tp_price

            # 反向信号平仓
            if exit_reason is None:
                exit_sig = None
                if strategy == "ma_cross":
                    if i >= 1 and not np.isnan(ma_fast[i]) and not np.isnan(ma_fast[i - 1]) and not np.isnan(ma_slow[i]) and not np.isnan(ma_slow[i - 1]):
                        if pos["direction"] == "long" and ma_fast[i - 1] >= ma_slow[i - 1] and ma_fast[i] < ma_slow[i]:
                            exit_sig = f"MA{fast}死叉"
                elif strategy == "rsi":
                    if i >= 1 and not np.isnan(rsi_vals[i]) and not np.isnan(rsi_vals[i - 1]):
                        if pos["direction"] == "long" and rsi_vals[i - 1] > overbought and rsi_vals[i] <= overbought:
                            exit_sig = "RSI进入超买区"
                elif strategy == "bollinger":
                    if not np.isnan(bb_mid[i]):
                        if pos["direction"] == "long" and close >= bb_mid[i]:
                            exit_sig = "价格回到布林中轨"
                elif strategy == "macd":
                    if i >= 1 and not np.isnan(macd_line[i]) and not np.isnan(macd_line[i - 1]) and not np.isnan(macd_signal_line[i]) and not np.isnan(macd_signal_line[i - 1]):
                        if pos["direction"] == "long" and macd_line[i - 1] >= macd_signal_line[i - 1] and macd_line[i] < macd_signal_line[i]:
                            exit_sig = "MACD死叉"
                # candlestick和cup_handle用止损止盈退出
                if exit_sig:
                    exit_reason = f"信号平仓({exit_sig})"

            if exit_reason:
                pnl = (exit_price - pos["entry_price"]) * pos["shares"]
                return_pct = round((exit_price / pos["entry_price"] - 1) * 100, 2)
                trades.append({
                    "code": code,
                    "strategy": strategy,
                    "direction": "long",
                    "entry_date": pos["entry_date"],
                    "entry_price": round(pos["entry_price"], 2),
                    "exit_date": date_str,
                    "exit_price": round(exit_price, 2),
                    "exit_reason": exit_reason,
                    "pnl": round(pnl, 2),
                    "return_pct": return_pct,
                    "holding_days": days_held,
                    "shares": pos["shares"],
                    "cost": round(pos["cost"], 2),
                    "signal_detail": pos["entry_signal"],
                })
                in_position = False
                position = None
                continue  # 同日不反向开仓

        # ---- 入场信号检测 ----
        if in_position:
            continue

        if strategy == "ma_cross":
            if i < 1 or np.isnan(ma_fast[i]) or np.isnan(ma_fast[i - 1]) or np.isnan(ma_slow[i]) or np.isnan(ma_slow[i - 1]):
                continue
            # 信号 → 标记次日入场
            if ma_fast[i - 1] <= ma_slow[i - 1] and ma_fast[i] > ma_slow[i]:
                delayed_entry = {"direction": "long", "entry_idx": i + 1,
                                 "signal": f"MA{fast}金叉MA{slow}", "need_breakout": False}
            elif ma_fast[i - 1] >= ma_slow[i - 1] and ma_fast[i] < ma_slow[i]:
                delayed_entry = {"direction": "short", "entry_idx": i + 1,
                                 "signal": f"MA{fast}死叉MA{slow}", "need_breakout": False}

        elif strategy == "rsi":
            if i < 1 or np.isnan(rsi_vals[i]) or np.isnan(rsi_vals[i - 1]):
                continue
            if rsi_vals[i - 1] < oversold and rsi_vals[i] >= oversold:
                delayed_entry = {"direction": "long", "entry_idx": i + 1,
                                 "signal": f"RSI({rsi_period})从超卖区反弹", "need_breakout": False}
            elif rsi_vals[i - 1] > overbought and rsi_vals[i] <= overbought:
                delayed_entry = {"direction": "short", "entry_idx": i + 1,
                                 "signal": f"RSI({rsi_period})从超买区回落", "need_breakout": False}

        elif strategy == "bollinger":
            if np.isnan(bb_upper[i]) or np.isnan(bb_lower[i]):
                continue
            if low <= bb_lower[i]:
                delayed_entry = {"direction": "long", "entry_idx": i + 1,
                                 "signal": f"触布林下轨({bb_lower[i]:.2f})", "need_breakout": False}
            elif high >= bb_upper[i]:
                delayed_entry = {"direction": "short", "entry_idx": i + 1,
                                 "signal": f"触布林上轨({bb_upper[i]:.2f})", "need_breakout": False}

        elif strategy == "macd":
            if i < 1 or np.isnan(macd_line[i]) or np.isnan(macd_line[i - 1]) or np.isnan(macd_signal_line[i]) or np.isnan(macd_signal_line[i - 1]):
                continue
            if macd_line[i - 1] <= macd_signal_line[i - 1] and macd_line[i] > macd_signal_line[i]:
                delayed_entry = {"direction": "long", "entry_idx": i + 1,
                                 "signal": "MACD金叉", "need_breakout": False}
            elif macd_line[i - 1] >= macd_signal_line[i - 1] and macd_line[i] < macd_signal_line[i]:
                delayed_entry = {"direction": "short", "entry_idx": i + 1,
                                 "signal": "MACD死叉", "need_breakout": False}

        elif strategy == "candlestick":
            patterns = all_patterns[i] if i < len(all_patterns) else []
            bullish = [p for p in patterns if p["direction"] == "bullish"]
            bearish = [p for p in patterns if p["direction"] == "bearish"]
            if bullish:
                sig = " + ".join([p["pattern"] for p in bullish[:2]])
                delayed_entry = {"direction": "long", "entry_idx": i + 1,
                                 "signal": f"看涨形态: {sig}", "need_breakout": False}
            elif bearish:
                sig = " + ".join([p["pattern"] for p in bearish[:2]])
                delayed_entry = {"direction": "short", "entry_idx": i + 1,
                                 "signal": f"看跌形态: {sig}", "need_breakout": False}

        elif strategy == "cup_handle":
            while ch_pointer < len(ch_signals) and ch_signals[ch_pointer]["detection_idx"] <= i:
                sig = ch_signals[ch_pointer]
                ch_pointer += 1
                score = sig.get("score", 0)
                delayed_entry = {
                    "direction": "long", "entry_idx": i + 1,
                    "signal": (f"杯柄形态(评分{score:.2f},杯深{sig['cup_depth']*100:.1f}%,"
                              f"柄深{sig['handle_depth']*100:.1f}%)"),
                    "need_breakout": True,
                    "buy_point": sig["buy_point"],
                }

    # 持仓到末尾 → 强制平仓
    if in_position and position is not None:
        pos = position
        last_close = closes[-1]
        last_date = str(dates[-1])[:10]
        pnl = (last_close - pos["entry_price"]) * pos["shares"]
        return_pct = round((last_close / pos["entry_price"] - 1) * 100, 2)
        trades.append({
            "code": code,
            "strategy": strategy,
            "direction": "long",
            "entry_date": pos["entry_date"],
            "entry_price": round(pos["entry_price"], 2),
            "exit_date": last_date,
            "exit_price": round(last_close, 2),
            "exit_reason": "数据结束平仓",
            "pnl": round(pnl, 2),
            "return_pct": return_pct,
            "holding_days": n - 1 - pos["entry_idx"],
            "shares": pos["shares"],
            "cost": round(pos["cost"], 2),
            "signal_detail": pos["entry_signal"],
        })

    return trades


# ============================================================
# 汇总统计
# ============================================================

def calc_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
                "profit_factor": 0, "total_pnl": 0, "avg_return": 0,
                "avg_win_return": 0, "avg_loss_return": 0, "max_drawdown": 0}

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    n_total = len(trades)

    win_rate = len(wins) / n_total * 100 if n_total > 0 else 0
    total_pnl = sum(t["pnl"] for t in trades)
    avg_return = sum(t["return_pct"] for t in trades) / n_total if n_total > 0 else 0
    avg_win = sum(t["return_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t["return_pct"] for t in losses) / len(losses)) if losses else 0

    total_win_pnl = sum(t["pnl"] for t in wins) if wins else 0
    total_loss_pnl = abs(sum(t["pnl"] for t in losses)) if losses else 0
    profit_factor = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl > 0 else (total_win_pnl if total_win_pnl > 0 else 0)

    avg_holding = sum(t["holding_days"] for t in trades) / n_total if n_total > 0 else 0

    # 最大回撤（按累计PnL）
    cum = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum += t["pnl"]
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    return {
        "trades": n_total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "profit_factor": profit_factor,
        "total_pnl": round(total_pnl, 2),
        "avg_return": round(avg_return, 2),
        "avg_win_return": round(avg_win, 2),
        "avg_loss_return": round(avg_loss, 2),
        "avg_holding_days": round(avg_holding, 1),
        "max_drawdown": round(max_dd, 2),
    }


# ============================================================
# 主流程
# ============================================================

STRATEGIES = {
    "ma_cross":    {"name": "MA5/10金叉死叉", "params": {"fast": 5, "slow": 10}},
    "rsi":         {"name": "RSI超买超卖", "params": {"period": 14, "overbought": 70, "oversold": 30}},
    "bollinger":   {"name": "布林带突破", "params": {"bb_period": 20, "bb_std": 2.0}},
    "macd":        {"name": "MACD金叉死叉", "params": {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9}},
    "candlestick": {"name": "K线形态", "params": {}},
    "cup_handle":  {"name": "杯柄形态", "params": {"min_score": 0.35}},
    "kline_macd":  {"name": "🔥K线+MACD共振", "params": {}},
    "kline_ma":    {"name": "🔥K线+MA金叉共振", "params": {}},
    "kline_macd_elite": {"name": "⭐精选系统(大阳线/红三兵+MACD)", "params": {}},
}


def main():
    print("=" * 70)
    print("  HS300全策略回测")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. 加载HS300成分股
    print("\n📥 加载HS300成分股...")
    codes = load_hs300_codes()
    print(f"   有效A股代码: {len(codes)}只")
    print(f"   样例: {codes[:3]} ... {codes[-3:]}")

    # 2. 逐策略回测
    all_results = {}
    all_trades = {}

    for sk, sv in STRATEGIES.items():
        print(f"\n{'=' * 50}")
        print(f"  📊 策略: {sv['name']} ({sk})")
        print(f"{'=' * 50}")

        total_trades = []
        count = 0
        for code in codes:
            trades = run_single_backtest(code, sk, sl_pct=0, params=sv["params"])
            total_trades.extend(trades)
            count += 1
            if count % 50 == 0:
                print(f"   进度: {count}/{len(codes)} 只股票...")

        stats = calc_stats(total_trades)
        all_results[sk] = stats
        all_trades[sk] = total_trades

        print(f"   交易次数: {stats['trades']}")
        print(f"   胜率:     {stats['win_rate']}%")
        print(f"   盈亏比:   {stats['profit_factor']}")
        print(f"   总盈亏:   {stats['total_pnl']:+.2f}")
        print(f"   平均收益: {stats['avg_return']:+.2f}%")
        print(f"   最大回撤: {stats['max_drawdown']:.2f}")

    # 3. 输出对比表
    print("\n\n" + "=" * 80)
    print("  📋 策略对比总表 (按盈利能力排序)")
    print("=" * 80)
    print(f"{'策略':<14} {'交易':<6} {'胜率':<7} {'盈亏比':<8} {'总盈亏':<12} {'均收益':<8} {'盈利均':<8} {'亏损均':<8} {'持仓':<6} {'回撤':<8}")
    print("-" * 80)

    ranked = sorted(all_results.items(), key=lambda x: x[1]["profit_factor"], reverse=True)
    rank = 0
    for sk, stats in ranked:
        if stats["trades"] < MIN_TRADES:
            continue
        rank += 1
        print(f"{STRATEGIES[sk]['name']:<14} {stats['trades']:<6} {stats['win_rate']:<6.1f}% "
              f"{stats['profit_factor']:<8.2f} {stats['total_pnl']:<+11.2f} {stats['avg_return']:<+7.2f}% "
              f"{stats['avg_win_return']:<+7.2f}% {stats['avg_loss_return']:<7.2f}% "
              f"{stats['avg_holding_days']:<6.1f} {stats['max_drawdown']:<8.2f}")

    # 4. 最佳策略的详细交易分析
    if ranked:
        best_sk = ranked[0][0]
        best_name = STRATEGIES[best_sk]["name"]
        print(f"\n\n{'=' * 80}")
        print(f"  🏆 最佳策略: {best_name} (盈亏比: {all_results[best_sk]['profit_factor']})")
        print(f"{'=' * 80}")

        # 按股票分析
        stock_pnl = defaultdict(float)
        stock_trades = defaultdict(int)
        for t in all_trades[best_sk]:
            stock_pnl[t["code"]] += t["pnl"]
            stock_trades[t["code"]] += 1

        print(f"\n  收益贡献TOP10:")
        for code, pnl in sorted(stock_pnl.items(), key=lambda x: -x[1])[:10]:
            print(f"    {code}  {stock_trades[code]:3d}笔  PnL: {pnl:+9.2f}")

        print(f"\n  亏损TOP10:")
        for code, pnl in sorted(stock_pnl.items(), key=lambda x: x[1])[:10]:
            print(f"    {code}  {stock_trades[code]:3d}笔  PnL: {pnl:+9.2f}")

    # 5. 保存结果
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_stocks": len(codes),
        "strategies": {},
    }
    for sk in STRATEGIES:
        output["strategies"][sk] = {
            "name": STRATEGIES[sk]["name"],
            "stats": all_results.get(sk, {}),
        }

    out_path = OUTPUT_DIR / f"hs300_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 结果已保存: {out_path}")

    # 也保存CSV明细
    for sk in ["macd", "ma_cross", "rsi", "bollinger", "candlestick", "cup_handle"]:
        if all_trades.get(sk):
            df_trades = pd.DataFrame(all_trades[sk])
            csv_path = OUTPUT_DIR / f"hs300_{sk}_trades.csv"
            df_trades.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"  明细: {csv_path}")

    print("\n✅ 完成!")


if __name__ == "__main__":
    main()
