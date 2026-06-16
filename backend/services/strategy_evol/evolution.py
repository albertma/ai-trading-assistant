"""进化引擎 — 每月统计各维度准确率，贝叶斯更新权重"""

from datetime import date, timedelta
from backend.services.strategy_evol.db import get_db, ensure_tables
import json


def run_evolution(cycle_date: str = "") -> dict:
    """月度进化：对比上月评分与股票实际走势，更新权重

    1. 查上月 stock_scores 记录
    2. 取每只记分后30天的股价变化
    3. 对比decision与实际走势判断预测是否准确
    4. 统计每个维度的准确率
    5. 贝叶斯更新权重
    6. 入库 evolution_log
    """
    ensure_tables()
    from backend.services.market_service import get_daily_history

    today = date.today()
    cycle_date = cycle_date or today.strftime("%Y-%m")

    # 上月的日期范围
    if today.month == 1:
        prev_month = today.replace(year=today.year - 1, month=12)
    else:
        prev_month = today.replace(month=today.month - 1)
    month_start = prev_month.replace(day=1).isoformat()
    month_end = today.isoformat()

    conn = get_db()

    # 取上月所有评分记录
    rows = conn.execute(
        """SELECT * FROM stock_scores
           WHERE date >= ? AND date < ?
           ORDER BY id""",
        (month_start, month_end),
    ).fetchall()

    if not rows:
        conn.close()
        return {"cycle_date": cycle_date, "message": "上月无评分记录", "dimensions": []}

    # 按 dimension 统计
    dim_stats = {}
    for dim in ("technical", "fundamental", "narrative", "capital_flow", "sentiment"):
        dim_stats[dim] = {"correct": 0, "total": 0}

    for row in rows:
        r = dict(row)
        decision = r.get("decision", "HOLD")
        code = r.get("stock_code", "")
        score_date = r.get("date", "")

        if not code or not score_date:
            continue

        # 取评分日之后30天的K线，看涨跌
        df = get_daily_history(code, 60)
        if df is None or df.empty:
            continue

        dates_list = df["date"].values
        closes = df["close"].values.astype(float)

        # 找评分日在K线中的位置
        entry_idx = None
        for i, d in enumerate(dates_list):
            if str(d)[:10] >= score_date:
                entry_idx = i
                break

        if entry_idx is None or entry_idx >= len(closes) - 5:
            continue

        entry_price = closes[entry_idx]
        # 看30天后（或最后一根K线）的价格
        exit_idx = min(entry_idx + 30, len(closes) - 1)
        exit_price = closes[exit_idx]
        change_pct = (exit_price - entry_price) / entry_price * 100

        # 判断预测是否准确
        bought = decision in ("BUY", "STRONG_BUY")
        correct = (bought and change_pct > 2) or (not bought and change_pct <= 2)

        # 每个维度都计入（因为decision是综合的，所有维度共享同一个胜负判定）
        for dim in dim_stats:
            dim_stats[dim]["total"] += 1
            if correct:
                dim_stats[dim]["correct"] += 1

    # 获取当前权重
    weights_before = {}
    dim_rows = conn.execute("SELECT dimension, weight FROM dimension_weights").fetchall()
    for dr in dim_rows:
        weights_before[dr["dimension"]] = dr["weight"]

    # 贝叶斯更新权重
    results = []
    for dim, stats in dim_stats.items():
        total = stats["total"]
        correct = stats["correct"]
        accuracy = round(correct / total * 100, 1) if total > 0 else 0

        w_before = weights_before.get(dim, 1.0)

        # 简单贝叶斯：准确率偏离50%越多，调整幅度越大
        # 新权重 = 旧权重 * (1 + (准确率 - 50) / 100)
        adjustment = (accuracy - 50) / 100 * 0.5  # 最大调整 ±25%
        w_after = round(w_before * (1 + adjustment), 2)
        w_after = max(0.1, min(3.0, w_after))  # 限制 0.1 ~ 3.0

        # 入库
        conn.execute(
            """INSERT INTO evolution_log
               (cycle_date, dimension, weight_before, weight_after,
                accuracy, total_predictions, correct_predictions, notes)
               VALUES (?,?,?,?, ?,?,?,?)""",
            (
                cycle_date, dim, w_before, w_after,
                accuracy, total, correct,
                f"准确率{accuracy}%，{'权重上调' if w_after > w_before else '权重下调'}"
                if total > 0 else "无数据",
            ),
        )

        # 更新权重表
        conn.execute(
            "UPDATE dimension_weights SET weight=?, last_updated=datetime('now','localtime') WHERE dimension=?",
            (w_after, dim),
        )

        results.append({
            "dimension": dim,
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "weight_before": w_before,
            "weight_after": w_after,
        })

    conn.commit()
    conn.close()

    results.sort(key=lambda r: -r["accuracy"])
    return {
        "cycle_date": cycle_date,
        "total_records": len(rows),
        "dimensions": results,
    }


def get_evolution_history(limit: int = 12) -> list:
    """获取进化历史"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM evolution_log ORDER BY id DESC LIMIT ?", (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
