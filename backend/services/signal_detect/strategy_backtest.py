"""
策略回测引擎 — 基于技术指标/K线形态的历史回测（A股仅做多）
支持: 买入/卖出/止损三模块自由组合
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.services.signal_detect.signal_registry import (
    ENTRY_SIGNALS, EXIT_SIGNALS, STRATEGY_PRESETS,
    combo_name, combo_label,
)


# ===== DB =====

def _get_db() -> sqlite3.Connection:
    db = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy_backtest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            code TEXT NOT NULL,
            params TEXT DEFAULT '',
            direction TEXT NOT NULL,
            entry_date TEXT,
            entry_price REAL,
            exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            pnl REAL,
            return_pct REAL,
            holding_days INTEGER,
            mfe REAL,
            mae REAL,
            signal_detail TEXT DEFAULT '',
            batch_id TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sb_batch ON strategy_backtest(batch_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sb_strategy ON strategy_backtest(strategy)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sb_code ON strategy_backtest(code)")
    conn.commit()
    conn.close()


# ===== 技术指标 =====

from backend.utils.indicators import sma, ema, rsi as calc_rsi, macd as calc_macd

def _calc_sma(arr: np.ndarray, period: int) -> np.ndarray:
    return sma(arr, period)


def _calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    return ema(arr, period)


def _calc_rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    return calc_rsi(arr, period)


def _scan_cup_handle_signals(df: pd.DataFrame, min_score: float = 0.35) -> list[dict]:
    from backend.patterns import detect_cup_handle
    n = len(df)
    signals = []
    scan_step = 5
    min_window = 60
    for end in range(min_window, n, scan_step):
        sub = df.iloc[:end + 1].copy().reset_index(drop=True)
        result = detect_cup_handle(sub)
        if result and result[0].get("cup_handle_detail"):
            ch = result[0]["cup_handle_detail"]
            if ch.get("score", 0) >= min_score:
                signals.append({
                    "detection_idx": end,
                    "detection_date": str(df.iloc[end]["date"])[:10],
                    "buy_point": ch["buy_point"],
                    "handle_depth": ch["handle_depth"],
                    "cup_depth": ch["cup_depth"],
                    "score": ch["score"],
                    "confidence": result[0].get("confidence", "low"),
                })
    seen_buy_points = set()
    deduped = []
    for s in sorted(signals, key=lambda x: x["detection_idx"]):
        bp = round(s["buy_point"], 1)
        if bp not in seen_buy_points:
            seen_buy_points.add(bp)
            deduped.append(s)
    return deduped


# ===== 回测主函数 =====

def run_backtest(
    code: str,
    strategy: str = "",
    entry_signal: str = "",
    exit_signal: str = "",
    max_days: int = 500,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    params: Optional[dict] = None,
    batch_id: str = "",
    save_db: bool = True,
    weekly: bool = False,
) -> list[dict]:
    """
    对单个标的运行策略回测

    支持两种模式:
      1. 预设策略: strategy 参数指定 (如 "ma_cross", "kline_macd_elite")
      2. 自由组合: entry_signal + exit_signal + sl_pct/tp_pct

    返回: 交易记录列表
    """
    from backend.services.market_service import get_daily_history
    from backend.patterns import detect_patterns

    params = params or {}

    # 解析策略
    if strategy:
        if strategy in STRATEGY_PRESETS:
            entry_name, exit_name, preset_sl = STRATEGY_PRESETS[strategy]
            if sl_pct == 0 and preset_sl > 0:
                sl_pct = preset_sl
            # 根据预设名自动推断 weekly 模式
            if not weekly and strategy.endswith('_weekly'):
                weekly = True
        elif strategy in ENTRY_SIGNALS:
            entry_name, exit_name = strategy, "none"
        else:
            entry_name, exit_name = "ma_cross", "ma_death"
    else:
        entry_name = entry_signal or "ma_cross"
        exit_name = exit_signal or "ma_death"

    # 获取信号函数
    entry_info = ENTRY_SIGNALS.get(entry_name)
    exit_info = EXIT_SIGNALS.get(exit_name)
    if not entry_info:
        return []
    entry_fn = entry_info["func"]
    exit_fn = exit_info["func"] if exit_info else (lambda **_: None)

    # 组合策略名（用于DB存储和显示）
    combo = combo_name(entry_name, exit_name)
    display_strategy = strategy if strategy else combo

    # 取数据（周K模式需要更多原始数据计算MA120）
    daily_df = get_daily_history(code, max(max_days, 1500 if weekly else max_days))
    if daily_df is None or daily_df.empty or len(daily_df) < 30:
        return []

    df = daily_df.copy()  # 始终使用日K数据

    closes = df["close"].values.astype(float)
    highs = df["high"].values.astype(float)
    lows = df["low"].values.astype(float)
    opens = df["open"].values.astype(float)
    volumes = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(n)
    dates = df["date"].values
    n = len(closes)

    # 预计算指标
    frag = params.get("fast", 5)
    fslo = params.get("slow", 10)
    rsi_period = params.get("period", 14)
    bb_period = params.get("bb_period", 20)
    bb_std = params.get("bb_std", 2.0)
    macd_fast = params.get("macd_fast", 12)
    macd_slow = params.get("macd_slow", 26)
    macd_signal = params.get("macd_signal", 9)
    overbought = params.get("overbought", 70)
    oversold = params.get("oversold", 30)

    # MA周期
    ma_20_period = params.get("ma_20_period", 20)
    ma_60_period = params.get("ma_60_period", 60)
    # 周K模式额外 MA120（≈ 24周MA，作为中长期趋势过滤器）
    ma_120_period = 120 if weekly else 60  # 用MA120替代MA60做趋势判断

    ma_fast = _calc_sma(closes, frag)
    ma_slow = _calc_sma(closes, fslo)
    ma_20   = _calc_sma(closes, ma_20_period)
    ma_60   = _calc_sma(closes, ma_60_period)
    ma_120  = _calc_sma(closes, ma_120_period)  # 周K趋势过滤器
    ma_200  = _calc_sma(closes, 200)
    # 日K MA30（用于周K模式退出信号：日K跌破MA30）
    daily_ma30 = _calc_sma(closes, 30) if weekly else None
    rsi_vals = _calc_rsi(closes, rsi_period)

    # 布林带
    bb_mid = _calc_sma(closes, bb_period)
    bb_std_arr = np.full(n, np.nan)
    for i in range(bb_period - 1, n):
        bb_std_arr[i] = np.std(closes[i - bb_period + 1:i + 1])
    bb_upper = bb_mid + bb_std * bb_std_arr
    bb_lower = bb_mid - bb_std * bb_std_arr

    # MACD
    macd_line, macd_signal_line, macd_hist = calc_macd(closes, macd_fast, macd_slow, macd_signal)

    # K线形态预计算
    all_patterns = []
    needs_patterns = entry_info.get("needs_patterns", False)
    if needs_patterns:
        from backend.patterns import detect_patterns as _dp
        for idx in range(n):
            if idx < 4:
                all_patterns.append([])
            else:
                sub = df.iloc[idx - 4:idx + 1]
                all_patterns.append(_dp(sub))
    else:
        all_patterns = [[] for _ in range(n)]

    # 杯柄形态预扫描
    ch_signals = []
    ch_pointer = 0
    needs_cup = entry_info.get("needs_cup", False)
    if needs_cup:
        min_score = params.get("min_score", 0.35)
        ch_signals = _scan_cup_handle_signals(df, min_score)
        ch_signals.sort(key=lambda s: s["detection_idx"])

    # 共享上下文（给信号函数用的参数包）
    ctx = {
        "closes": closes, "highs": highs, "lows": lows, "opens": opens, "volumes": volumes,
        "ma_fast": ma_fast, "ma_slow": ma_slow, "ma_20": ma_20, "ma_60": ma_60, "ma_200": ma_200,
        "ma_120": ma_120,  # 周K趋势过滤
        "rsi_vals": rsi_vals,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid,
        "macd_line": macd_line, "macd_signal_line": macd_signal_line, "macd_hist": macd_hist,
        "all_patterns": all_patterns,
        "ch_signals": ch_signals,
        "n": n,
        "fast": frag, "slow": fslo,
        "rsi_period": rsi_period, "oversold": oversold, "overbought": overbought,
        "bb_period": bb_period, "bb_std": bb_std,
        "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
        **params,
    }

    # 周K模式：设置标志 + 日K MA30退出信号
    if weekly:
        ctx["weekly_mode"] = True
        ctx["daily_ma30"] = daily_ma30


    # ===== 主循环 =====
    trades = []
    in_position = False
    position = {"direction": "", "entry_price": 0, "entry_date": "", "entry_idx": 0,
                "entry_signal": "", "mfe": 0, "mae": 0}
    delayed_entry = None
    last_entry_bar = -999  # 信号冷却期跟踪

    for i in range(1, n):
        close = closes[i]
        high = highs[i]
        low = lows[i]
        date_str = str(dates[i])[:10]

        # T+1延迟入场激活
        if delayed_entry is not None and i == delayed_entry["entry_idx"]:
            de = delayed_entry
            delayed_entry = None
            if de.get("need_breakout") and not (high >= de["buy_point"]):
                pass
            else:
                entry_p = max(close, de.get("buy_point", 0)) if de.get("need_breakout") else close
                in_position = True
                position = {
                    "direction": de["direction"],
                    "entry_price": entry_p,
                    "entry_date": date_str,
                    "entry_idx": i,
                    "entry_signal": de["signal"],
                    "mfe": 0, "mae": 0,
                }
                continue

        # 持仓：检查退出
        if in_position:
            pos = position
            days_held = i - pos["entry_idx"]

            pos["mfe"] = max(pos["mfe"], high - pos["entry_price"])
            pos["mae"] = min(pos["mae"], low - pos["entry_price"])

            exit_reason = None
            exit_price = close

            # 止损
            if sl_pct > 0:
                sl_price = pos["entry_price"] * (1 - sl_pct / 100)
                if low <= sl_price:
                    exit_reason = "止损"
                    exit_price = sl_price

            # 止盈
            if tp_pct > 0 and exit_reason is None:
                tp_price = pos["entry_price"] * (1 + tp_pct / 100)
                if high >= tp_price:
                    exit_reason = "止盈"
                    exit_price = tp_price

            # 信号退出
            if exit_reason is None:
                exit_sig = exit_fn(i=i, **ctx)
                if exit_sig:
                    exit_reason = f"信号平仓({exit_sig})"
                    exit_price = close

            if exit_reason:
                pnl = exit_price - pos["entry_price"]
                return_pct = round(pnl / pos["entry_price"] * 100, 2)

                trades.append({
                    "strategy": display_strategy,
                    "code": code,
                    "params": str(params),
                    "direction": pos["direction"],
                    "entry_date": pos["entry_date"],
                    "entry_price": round(pos["entry_price"], 2),
                    "exit_date": date_str,
                    "exit_price": round(exit_price, 2),
                    "exit_reason": exit_reason,
                    "pnl": round(pnl, 2),
                    "return_pct": return_pct,
                    "holding_days": days_held,
                    "mfe": round(pos["mfe"], 2),
                    "mae": round(pos["mae"], 2),
                    "signal_detail": pos["entry_signal"],
                    "batch_id": batch_id,
                })
                in_position = False
                continue

        # 未持仓：检查入场信号
        if in_position:
            continue

        # 冷却期：同一信号不重复触发（周K模式 4周冷却）
        cooldown_bars = params.get("cooldown_bars", 4 if weekly else 0)
        if i - last_entry_bar < cooldown_bars:
            continue

        # 特殊处理：杯柄形态需要 ch_pointer
        if needs_cup:
            while ch_pointer < len(ch_signals) and ch_signals[ch_pointer]["detection_idx"] <= i:
                sig = ch_signals[ch_pointer]
                ch_pointer += 1
                last_entry_bar = i
                delayed_entry = {
                    "direction": "long", "entry_idx": i + 1,
                    "signal": (f"杯柄形态(评分{sig['score']:.2f},杯深{sig['cup_depth']*100:.1f}%,"
                              f"柄深{sig['handle_depth']*100:.1f}%,买点{sig['buy_point']:.2f})"),
                    "need_breakout": True, "buy_point": sig["buy_point"],
                }
        else:
            result = entry_fn(i=i, **ctx)
            if result:
                last_entry_bar = i
                delayed_entry = result

    # 持仓到末尾 → 强制平仓
    if in_position:
        pos = position
        last_close = closes[-1]
        last_date = str(dates[-1])[:10]
        pnl = last_close - pos["entry_price"]
        trades.append({
            "strategy": display_strategy,
            "code": code,
            "params": str(params),
            "direction": pos["direction"],
            "entry_date": pos["entry_date"],
            "entry_price": round(pos["entry_price"], 2),
            "exit_date": last_date,
            "exit_price": round(last_close, 2),
            "exit_reason": "数据结束平仓",
            "pnl": round(pnl, 2),
            "return_pct": round(pnl / pos["entry_price"] * 100, 2),
            "holding_days": n - 1 - pos["entry_idx"],
            "mfe": round(pos["mfe"], 2),
            "mae": round(pos["mae"], 2),
            "signal_detail": pos["entry_signal"],
            "batch_id": batch_id,
        })

    if save_db:
        _save_trades(trades, batch_id)
    return trades


# ===== 多标的一键跑 =====

def run_multi(code_list: list[str], strategy: str = "",
              entry_signal: str = "", exit_signal: str = "",
              sl_pct: float = 0, tp_pct: float = 0,
              params: Optional[dict] = None,
              weekly: bool = False) -> dict:
    """对多个标的批量跑回测，返回汇总统计"""
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
    all_trades = []
    for code in code_list:
        trades = run_backtest(code, strategy=strategy,
                              entry_signal=entry_signal, exit_signal=exit_signal,
                              sl_pct=sl_pct, tp_pct=tp_pct,
                              params=params, batch_id=batch_id, save_db=False,
                              weekly=weekly)
        all_trades.extend(trades)
    summary = calc_summary(all_trades)
    summary["batch_id"] = batch_id
    summary["total_trades"] = len(all_trades)
    summary["total_stocks"] = len(code_list)
    _save_trades(all_trades, batch_id)
    return summary


# ===== 汇总统计 =====

def calc_summary(trades: list[dict]) -> dict:
    if not trades:
        return {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
                "profit_factor": 0, "total_pnl": 0, "avg_return": 0,
                "avg_holding": 0, "max_drawdown_pct": 0}

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    n_wins = len(wins)
    n_losses = len(losses)
    n_total = len(trades)

    win_rate = round(n_wins / n_total * 100, 1) if n_total > 0 else 0
    total_pnl = round(sum(t["pnl"] for t in trades), 2)
    avg_return = round(sum(t["return_pct"] for t in trades) / n_total, 2) if n_total > 0 else 0

    total_win_pnl = round(sum(t["pnl"] for t in wins), 2) if wins else 0
    total_loss_pnl = round(abs(sum(t["pnl"] for t in losses)), 2) if losses else 0
    profit_factor = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl > 0 else (total_win_pnl if total_win_pnl > 0 else 0)

    avg_holding = round(sum(t["holding_days"] for t in trades) / n_total, 1) if n_total > 0 else 0

    # 最大回撤（按累计PnL计算）
    cum_pnl = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum_pnl += t["pnl"]
        if cum_pnl > peak:
            peak = cum_pnl
        dd = peak - cum_pnl
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": n_total,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "avg_return": avg_return,
        "avg_holding_days": avg_holding,
        "max_drawdown": round(max_dd, 2),
    }


# ===== CRUD =====

def _save_trades(trades: list[dict], batch_id: str):
    if not trades:
        return
    conn = _get_db()
    if batch_id:
        conn.execute("DELETE FROM strategy_backtest WHERE batch_id=?", (batch_id,))
    for t in trades:
        conn.execute(
            """INSERT INTO strategy_backtest
               (strategy, code, params, direction, entry_date, entry_price,
                exit_date, exit_price, exit_reason, pnl, return_pct,
                holding_days, mfe, mae, signal_detail, batch_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t["strategy"], t["code"], t["params"], t["direction"],
             t["entry_date"], t["entry_price"], t["exit_date"], t["exit_price"],
             t["exit_reason"], t["pnl"], t["return_pct"], t["holding_days"],
             t["mfe"], t["mae"], t["signal_detail"], batch_id)
        )
    conn.commit()
    conn.close()


def list_results(strategy: str = "", code: str = "", batch_id: str = "", limit: int = 500) -> list[dict]:
    conn = _get_db()
    sql = "SELECT * FROM strategy_backtest WHERE 1=1"
    params = []
    if strategy:
        sql += " AND strategy=?"
        params.append(strategy)
    if code:
        sql += " AND code=?"
        params.append(code)
    if batch_id:
        sql += " AND batch_id=?"
        params.append(batch_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_batches() -> list[dict]:
    conn = _get_db()
    rows = conn.execute("""
        SELECT batch_id, strategy, COUNT(*) as trade_count,
               ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
               ROUND(COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                     NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0), 0), 2) as profit_factor,
               ROUND(SUM(pnl), 2) as total_pnl,
               ROUND(AVG(return_pct), 2) as avg_return,
               ROUND(AVG(holding_days), 1) as avg_holding_days,
               created_at
        FROM strategy_backtest
        WHERE batch_id != ''
        GROUP BY batch_id
        ORDER BY created_at DESC
        LIMIT 50
    """).fetchall()
    batches = [dict(r) for r in rows]
    for b in batches:
        trade_rows = conn.execute(
            "SELECT pnl FROM strategy_backtest WHERE batch_id=? ORDER BY id ASC",
            (b["batch_id"],)
        ).fetchall()
        cum_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        for tr in trade_rows:
            cum_pnl += tr[0]
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl
            if dd > max_dd:
                max_dd = dd
        b["max_drawdown"] = round(max_dd, 2)
    conn.close()
    return batches


def delete_batch(batch_id: str) -> bool:
    conn = _get_db()
    cur = conn.execute("DELETE FROM strategy_backtest WHERE batch_id=?", (batch_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok
