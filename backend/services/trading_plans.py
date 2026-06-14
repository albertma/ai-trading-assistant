"""
交易计划服务 — 全生命周期管理
发现 → 研究 → 计划 → 监控信号 → 入场 → 监控出场 → 退出
"""
import sqlite3
from pathlib import Path
from datetime import date, datetime
from typing import Optional


def _get_db() -> sqlite3.Connection:
    db = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trading_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT DEFAULT '',
            direction TEXT NOT NULL DEFAULT 'long' CHECK(direction IN ('long','short')),
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','monitoring','entered','exited','cancelled')),
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            plan_quantity INTEGER DEFAULT 0,
            entry_reason TEXT DEFAULT '',
            exit_reason TEXT DEFAULT '',
            kline_notes TEXT DEFAULT '',
            signal_notes TEXT DEFAULT '',
            actual_entry_price REAL,
            actual_exit_price REAL,
            entry_date TEXT,
            exit_date TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tp_code ON trading_plans(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tp_status ON trading_plans(status)")
    conn.commit()
    conn.close()


# ===== CRUD =====

def list_plans(status: str = "", code: str = "") -> list[dict]:
    conn = _get_db()
    sql = "SELECT * FROM trading_plans"
    params = []
    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if code:
        conditions.append("code = ?")
        params.append(code)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id: int) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM trading_plans WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_plan(code: str, name: str = "", direction: str = "long",
                entry_price: float = 0, stop_loss: float = 0,
                take_profit: float = 0, plan_quantity: int = 0,
                entry_reason: str = "", kline_notes: str = "") -> int:
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO trading_plans
           (code, name, direction, status, entry_price, stop_loss, take_profit,
            plan_quantity, entry_reason, kline_notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (code, name, direction, 'draft', entry_price, stop_loss, take_profit,
         plan_quantity, entry_reason, kline_notes)
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def update_plan(plan_id: int, **kwargs) -> bool:
    allowed = {"name", "direction", "status", "entry_price", "stop_loss",
               "take_profit", "plan_quantity", "entry_reason", "exit_reason",
               "kline_notes", "signal_notes", "actual_entry_price",
               "actual_exit_price", "entry_date", "exit_date"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False
    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [plan_id]
    conn = _get_db()
    cur = conn.execute(f"UPDATE trading_plans SET {sets} WHERE id=?", vals)
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def delete_plan(plan_id: int) -> bool:
    conn = _get_db()
    cur = conn.execute("DELETE FROM trading_plans WHERE id=?", (plan_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


# ===== 支撑/阻力分析 & 盈亏比计算 =====

def analyze_support_resistance(code: str, direction: str = "long") -> dict:
    """
    基于K线数据计算支撑/阻力位，推荐入场价/止损/止盈，计算预期盈亏比。
    返回:
        current_price, support_levels[], resistance_levels[],
        suggested_entry, suggested_stop_loss, suggested_take_profit,
        risk_reward_ratio, notes
    """
    from backend.services.db_client import get_kline_records
    from backend.services.market_service import get_daily_history
    from backend.services.analyze.technical import TechnicalAnalyzer
    from backend.patterns import detect_patterns
    import numpy as np
    import pandas as pd

    df = get_daily_history(code)
    result = {
        "current_price": 0,
        "direction": direction,
        "support_levels": [],
        "resistance_levels": [],
        "suggested_entry": 0,
        "suggested_stop_loss": 0,
        "suggested_take_profit": 0,
        "risk_reward_ratio": 0,
        "notes": "",
        "ma5": None,
        "ma10": None,
        "ma20": None,
        "ma60": None,
        "bollinger": None,
        "atr": None,
        "kline_patterns": [],
        "pattern_recommended_entry": None,
        "pattern_stop_loss": None,
        "pattern_description": None,
        "kline_data": [],
    }
    if df is None or df.empty:
        result["notes"] = "暂无K线数据，无法计算支撑阻力"
        return result

    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    current_price = float(close[-1])
    result["current_price"] = round(current_price, 2)

    tech = TechnicalAnalyzer()
    ma5 = tech.calc_ma(df, 5)
    ma10 = tech.calc_ma(df, 10)
    ma20 = tech.calc_ma(df, 20)
    ma60 = tech.calc_ma(df, 60)
    result["ma5"] = ma5
    result["ma10"] = ma10
    result["ma20"] = ma20
    result["ma60"] = ma60

    boll = tech.calc_bollinger(df)
    result["bollinger"] = boll

    # ATR (14 days) — 用平均真实波幅估计波动率
    if len(close) >= 15:
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        atr = float(np.mean(tr[-14:]))
        result["atr"] = round(atr, 2)
    else:
        atr = current_price * 0.03

    # ===== K线数据（前端图表渲染用） =====
    kline_data = []
    for _, row in df.tail(120).iterrows():
        kline_data.append({
            "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
            "open": round(float(row["open"]), 2),
            "close": round(float(row["close"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
        })
    result["kline_data"] = kline_data

    # ===== K线形态检测 =====
    kline_patterns = detect_patterns(df)
    result["kline_patterns"] = kline_patterns

    # 基于K线形态推荐入场点
    bullish_patterns = [p for p in kline_patterns if p["direction"] == "bullish"]
    bearish_patterns = [p for p in kline_patterns if p["direction"] == "bearish"]

    pattern_entry = None
    pattern_sl = None
    pattern_desc = None

    if direction == "long" and bullish_patterns:
        low_recent = float(low[-5:].min())
        pattern_entry = round(max(low_recent, current_price * 0.98), 2)
        pattern_sl = round(pattern_entry - atr * 0.8, 2)
        pattern_desc = "; ".join([f"{p['pattern']}({p['description']})" for p in bullish_patterns[:2]])

    elif direction == "short" and bearish_patterns:
        high_recent = float(high[-5:].max())
        pattern_entry = round(min(high_recent, current_price * 1.02), 2)
        pattern_sl = round(pattern_entry + atr * 0.8, 2)
        pattern_desc = "; ".join([f"{p['pattern']}({p['description']})" for p in bearish_patterns[:2]])

    result["pattern_recommended_entry"] = pattern_entry
    result["pattern_stop_loss"] = pattern_sl
    result["pattern_description"] = pattern_desc

    # ===== ⭐ 精选系统检测（大阳线/三连阳/锤子线 + MACD金叉） =====
    elite_signal = None
    elite_patterns = {"大阳线", "三连阳（红三兵）", "锤子线"}
    current_bullish_patterns = [p["pattern"] for p in bullish_patterns if p["pattern"] in elite_patterns]

    # MACD金叉检测（近3天）
    macd_golden = False
    if len(df) >= 35:
        exp12 = df["close"].ewm(span=12, adjust=False).mean()
        exp26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_vals = macd_line.values
        macd_sig_vals = macd_signal.values
        for j in range(max(1, len(macd_vals) - 3), len(macd_vals)):
            if (j >= 1 and not np.isnan(macd_vals[j]) and not np.isnan(macd_vals[j-1])
                and not np.isnan(macd_sig_vals[j]) and not np.isnan(macd_sig_vals[j-1])
                and macd_vals[j-1] <= macd_sig_vals[j-1] and macd_vals[j] > macd_sig_vals[j]):
                macd_golden = True
                break

    if current_bullish_patterns and macd_golden and direction == "long":
        # 精选系统触发！覆盖推荐方案
        entry_price_elite = round(current_price, 2)  # T+1以当前价为参考开盘买入
        stop_loss_elite = round(entry_price_elite * 0.93, 2)  # 7%止损
        # 止盈：最近阻力位，最低盈亏比2:1
        risk = entry_price_elite - stop_loss_elite
        min_tp = round(entry_price_elite + risk * 2, 2)
        nearest_res = valid_resistances[0] if valid_resistances else min_tp
        tp_elite = round(max(nearest_res, min_tp), 2)

        elite_signal = {
            "triggered": True,
            "patterns": current_bullish_patterns,
            "macd_golden": True,
            "entry_price": entry_price_elite,
            "stop_loss": stop_loss_elite,
            "take_profit": tp_elite,
            "risk_reward": round((tp_elite - entry_price_elite) / max(risk, 0.01), 2),
            "notes": f"⭐ 精选系统触发！检测到{'+'.join(current_bullish_patterns)}+MACD金叉共振，"
                     f"建议次日开盘买入，7%止损，目标位¥{tp_elite:.2f}（盈亏比{round((tp_elite-entry_price_elite)/max(risk,0.01),2)}:1）。"
                     f"每笔投入¥20,000（10%仓位），¥200,000总资金最多持7笔。",
        }
        # 覆盖原推荐方案
        result["suggested_entry"] = entry_price_elite
        result["suggested_stop_loss"] = stop_loss_elite
        result["suggested_take_profit"] = tp_elite
        risk_r = (tp_elite - entry_price_elite) / max(risk, 0.01)
        result["risk_reward_ratio"] = round(risk_r, 2)
        result["notes"] = elite_signal["notes"]

    result["elite_signal"] = elite_signal

    n = len(close)

    # ===== 支撑位（过去60日 swing lows） =====
    supports = set()
    # 1. 近60日 swing lows
    lookback = min(60, n)
    for i in range(2, lookback - 1):
        idx = n - lookback + i
        if idx <= 0 or idx >= n - 1:
            continue
        if low[idx] < low[idx - 1] and low[idx] < low[idx + 1]:
            supports.add(round(float(low[idx]), 2))

    # 2. 均线支撑
    if ma60 and ma60 > 0:
        supports.add(round(ma60, 2))
    if ma20 and ma20 > 0:
        supports.add(round(ma20, 2))
    if boll and boll["lower"] > 0:
        supports.add(round(boll["lower"], 2))

    # 3. 近20日最低价
    supports.add(round(float(low[-20:].min()), 2))

    # 取介于 0.5*current_price ~ current_price 之间的有效支撑，排序
    valid_supports = sorted([s for s in supports if 0 < s <= current_price * 1.02])
    result["support_levels"] = valid_supports

    # ===== 阻力位 =====
    resistances = set()
    for i in range(2, lookback - 1):
        idx = n - lookback + i
        if idx <= 0 or idx >= n - 1:
            continue
        if high[idx] > high[idx - 1] and high[idx] > high[idx + 1]:
            resistances.add(round(float(high[idx]), 2))

    if ma20 and ma20 > current_price:
        resistances.add(round(ma20, 2))
    if ma60 and ma60 > current_price:
        resistances.add(round(ma60, 2))
    if boll and boll["upper"] > current_price:
        resistances.add(round(boll["upper"], 2))
    resistances.add(round(float(high[-20:].max()), 2))

    valid_resistances = sorted([r for r in resistances if r >= current_price * 0.98])
    result["resistance_levels"] = valid_resistances

    # ===== 推荐入场价/止损/止盈 =====
    if direction == "long":
        # 推荐入场：最近支撑位上方一点，或现价附近
        nearest_support = valid_supports[-1] if valid_supports else current_price * 0.95
        # 如果现价离最近支撑很近（<2%），直接以现价入场
        if current_price <= nearest_support * 1.02:
            suggested_entry = round(current_price, 2)
        else:
            suggested_entry = round(nearest_support * 1.01, 2)

        # 止损：最近支撑下方 1-2 倍 ATR
        stop_dist = max(atr, current_price * 0.02)
        suggested_stop_loss = round(nearest_support - stop_dist * 0.5, 2)
        # 确保至少 1.5% 止损空间
        min_stop = round(current_price * 0.975, 2)
        if suggested_stop_loss > min_stop:
            suggested_stop_loss = min_stop

        # 止盈：至少 2:1 盈亏比
        risk = current_price - suggested_stop_loss
        if risk <= 0:
            risk = current_price * 0.03
        # 目标1: R/R 2:1
        target_rr2 = round(current_price + risk * 2, 2)
        # 目标2: 最近阻力位
        target_res = valid_resistances[0] if valid_resistances else target_rr2
        # 取两者均值
        suggested_take_profit = round((target_rr2 + target_res) / 2, 2)
        # 确保止盈 > 入场
        if suggested_take_profit <= suggested_entry:
            suggested_take_profit = round(current_price + risk * 3, 2)

        actual_risk = suggested_entry - suggested_stop_loss
        actual_reward = suggested_take_profit - suggested_entry
        if actual_risk > 0:
            result["risk_reward_ratio"] = round(actual_reward / actual_risk, 2)

        result["notes"] = (
            f"基于{lookback}日K线分析。推荐在支撑位附近入场，"
            f"止损设在下方{round(stop_dist, 2)}处，止盈参考阻力位+盈亏比2:1。"
        )
    else:
        # 做空 — 逻辑对称
        nearest_resistance = valid_resistances[0] if valid_resistances else current_price * 1.05
        if current_price >= nearest_resistance * 0.98:
            suggested_entry = round(current_price, 2)
        else:
            suggested_entry = round(nearest_resistance * 0.99, 2)

        stop_dist = max(atr, current_price * 0.02)
        suggested_stop_loss = round(nearest_resistance + stop_dist * 0.5, 2)
        min_stop = round(current_price * 1.025, 2)
        if suggested_stop_loss < min_stop:
            suggested_stop_loss = min_stop

        risk = suggested_stop_loss - current_price
        if risk <= 0:
            risk = current_price * 0.03
        target_rr2 = round(current_price - risk * 2, 2)
        target_sup = valid_supports[-1] if valid_supports else target_rr2
        suggested_take_profit = round((target_rr2 + target_sup) / 2, 2)
        if suggested_take_profit >= suggested_entry:
            suggested_take_profit = round(current_price - risk * 3, 2)

        actual_risk = suggested_stop_loss - suggested_entry
        actual_reward = suggested_entry - suggested_take_profit
        if actual_risk > 0:
            result["risk_reward_ratio"] = round(actual_reward / actual_risk, 2)

        result["notes"] = (
            f"基于{lookback}日K线分析。推荐在阻力位附近入场做空，"
            f"止损设在上方{round(stop_dist, 2)}处，止盈参考支撑位+盈亏比2:1。"
        )

    result["suggested_entry"] = round(suggested_entry, 2)
    result["suggested_stop_loss"] = round(max(suggested_stop_loss, 0.01), 2)
    result["suggested_take_profit"] = round(max(suggested_take_profit, suggested_entry + 0.01), 2)

    # 防零除
    if result["risk_reward_ratio"] > 0:
        pass
    elif result["suggested_entry"] - result["suggested_stop_loss"] > 0:
        result["risk_reward_ratio"] = round(
            (result["suggested_take_profit"] - result["suggested_entry"])
            / (result["suggested_entry"] - result["suggested_stop_loss"]), 2
        )

    return result


# ===== 信号评估 =====

def evaluate_signals(plan: dict) -> dict:
    """评估交易计划的入场/出场信号，利用现有K线数据"""
    from backend.services.db_client import get_kline_records
    from backend.services.analyze.technical import TechnicalAnalyzer
    from backend.services.market_service import get_daily_history

    code = plan["code"]
    result = {
        "current_price": 0,
        "entry_signal": "wait",
        "entry_detail": "",
        "exit_signal": "wait",
        "exit_detail": "",
        "signals": [],
    }

    # 获取K线数据
    df = get_daily_history(code)
    if df is None or df.empty:
        return result

    current_price = float(df["close"].iloc[-1])
    result["current_price"] = round(current_price, 2)

    tech = TechnicalAnalyzer()
    ma5 = tech.calc_ma(df, 5)
    ma10 = tech.calc_ma(df, 10)
    ma20 = tech.calc_ma(df, 20)
    ma60 = tech.calc_ma(df, 60)

    # 均线信号
    if ma5 and ma10 and ma5 > ma10:
        result["signals"].append({"type": "bullish", "text": f"MA5({ma5}) > MA10({ma10})，短期多头", "level": "info"})
    elif ma5 and ma10 and ma5 < ma10:
        result["signals"].append({"type": "bearish", "text": f"MA5({ma5}) < MA10({ma10})，短期空头", "level": "info"})

    if ma20 and ma60 and ma20 > ma60:
        result["signals"].append({"type": "bullish", "text": f"MA20({ma20}) > MA60({ma60})，中期多头", "level": "info"})
    elif ma20 and ma60 and ma20 < ma60:
        result["signals"].append({"type": "bearish", "text": f"MA20({ma20}) < MA60({ma60})，中期空头", "level": "info"})

    # MACD信号
    macd = tech.calc_macd(df)
    if macd:
        result["signals"].append({
            "type": "bullish" if macd["hist"] > 0 else "bearish",
            "text": f"MACD柱: {macd['hist']:.4f} ({'多头' if macd['hist'] > 0 else '空头'})",
            "level": "info",
        })

    # RSI
    rsi = tech.calc_rsi(df)
    if rsi:
        if rsi > 70:
            result["signals"].append({"type": "bearish", "text": f"RSI({rsi}) > 70，超买区", "level": "warning"})
        elif rsi < 30:
            result["signals"].append({"type": "bullish", "text": f"RSI({rsi}) < 30，超卖区", "level": "warning"})

    # 入场信号（针对多单）
    entry_price = plan.get("entry_price") or 0
    stop_loss = plan.get("stop_loss") or 0
    take_profit = plan.get("take_profit") or 0

    if plan["status"] in ("draft", "monitoring"):
        if entry_price > 0 and abs(current_price - entry_price) / entry_price <= 0.03:
            result["entry_signal"] = "triggered"
            result["entry_detail"] = f"现价{current_price:.2f}已接近目标入场价{entry_price:.2f}"
        elif entry_price > 0 and current_price < entry_price * 0.95:
            result["entry_signal"] = "below"
            result["entry_detail"] = f"现价{current_price:.2f}低于入场目标{entry_price:.2f}的5%，关注企稳"
        elif entry_price > 0 and current_price > entry_price * 1.05:
            result["entry_signal"] = "above"
            result["entry_detail"] = f"现价{current_price:.2f}已超出入场目标{entry_price:.2f}的5%，等待回调"
        else:
            result["entry_signal"] = "wait"
            result["entry_detail"] = f"现价{current_price:.2f}，目标价{entry_price:.2f}，差价{((current_price-entry_price)/entry_price*100):.1f}%"

    # 出场信号（已入场）
    if plan["status"] == "entered":
        signals_list = []
        if stop_loss > 0 and current_price <= stop_loss:
            signals_list.append({"type": "danger", "text": f"⚠️ 触发止损！现价{current_price:.2f} ≤ 止损{stop_loss:.2f}", "level": "danger"})
        elif stop_loss > 0 and current_price <= stop_loss * 1.03:
            signals_list.append({"type": "warning", "text": f"⚠️ 接近止损！现价{current_price:.2f}，止损{stop_loss:.2f}", "level": "warning"})

        if take_profit > 0 and current_price >= take_profit:
            signals_list.append({"type": "success", "text": f"✅ 触发止盈！现价{current_price:.2f} ≥ 目标{take_profit:.2f}", "level": "success"})
        elif take_profit > 0 and current_price >= take_profit * 0.95:
            signals_list.append({"type": "info", "text": f"📈 接近止盈！现价{current_price:.2f}，目标{take_profit:.2f}", "level": "info"})

        if signals_list:
            result["signals"].extend(signals_list)
            exit_signals = [s for s in signals_list if s["level"] in ("danger", "success")]
            result["exit_signal"] = "triggered" if exit_signals else "watch"
            result["exit_detail"] = exit_signals[0]["text"] if exit_signals else "监控中"

    return result
