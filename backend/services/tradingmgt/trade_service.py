"""仓位管理模块 — 交易日志（SQLite）"""

import sqlite3
from pathlib import Path

from .csv_store import read_all, write_all
from .constants import MARKET_LABELS
from .price_service import detect_market


def _get_db() -> sqlite3.Connection:
    db = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def _get_name_from_market_csv(code: str) -> str:
    """从交易日行情CSV查找股票名称"""
    from datetime import date, timedelta
    from backend.config import MARKET_DATA_DIR

    today = date.today()
    for i in range(5):
        d = today - timedelta(days=i)
        for prefix in ["沪深京A股", "沪深重要指数"]:
            path = MARKET_DATA_DIR / f"{prefix}{d.isoformat()}.csv"
            if path.exists():
                import pandas as pd
                try:
                    df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
                    df["代码"] = df["代码"].astype(str).str.strip("'\"")
                    match = df[df["代码"] == code]
                    if not match.empty:
                        return str(match.iloc[0].get("名称", ""))
                except Exception:
                    pass
    return ""


def _get_name_from_akshare(code: str) -> str:
    """通过 akshare_client 获取港股/美股名称"""
    from backend.services.external.akshare_client import get_hk_stock_name, get_us_stock_name
    from .price_service import detect_market
    market = detect_market(code)
    if market == "hk_stock":
        return get_hk_stock_name(code) or ""
    if market == "us_stock":
        return get_us_stock_name(code) or ""
    return ""


def _lookup_name(code: str) -> str:
    """综合查找股票名称：CSV → akshare → code 本身"""
    name = _get_name_from_market_csv(code)
    if name:
        return name
    name = _get_name_from_akshare(code)
    if name:
        return name
    return code


def recalc_position(code: str):
    """根据 trade_logs 重算持仓 → 更新到 CSV（含自动创建/删除）"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM trade_logs WHERE code = ? ORDER BY trade_date ASC, id ASC",
        (code,)
    ).fetchall()
    conn.close()

    buy_qty = 0.0
    buy_total = 0.0
    sell_qty = 0.0
    for r in rows:
        r = dict(r)
        if r["direction"] == "买入":
            buy_qty += r["quantity"]
            buy_total += r["total"]
        else:
            sell_qty += r["quantity"]

    remaining = round(buy_qty - sell_qty, 2)
    avg_cost = round(buy_total / buy_qty, 4) if buy_qty > 0 else 0

    csv_rows = read_all()
    found = False
    for r in csv_rows:
        if r.get("代码", "").strip() == code:
            if remaining > 0:
                cost_total = round(remaining * avg_cost, 2)
                r["数量"] = str(remaining)
                r["成本价"] = str(avg_cost)
                r["持仓成本"] = str(cost_total)
            else:
                csv_rows.remove(r)   # 全部卖完 → 删除
            found = True
            break

    if not found and remaining > 0:
        # 首次买入 → 自动创建持仓
        name = _lookup_name(code)
        if not name:
            name = code

        market = detect_market(code)
        cost_total = round(remaining * avg_cost, 2)
        csv_rows.append({
            "代码": code,
            "名称": name,
            "数量": str(remaining),
            "成本价": str(avg_cost),
            "当前价": "0",
            "持仓成本": str(cost_total),
            "当前市值": "0",
            "盈亏金额": "0",
            "盈亏比例": "0%",
            "备注": "",
            "市场": MARKET_LABELS.get(market, market),
        })

    write_all(csv_rows)


def list_trades(code: str) -> list[dict]:
    """获取某只股票的所有交易记录"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM trade_logs WHERE code = ? ORDER BY trade_date DESC, id DESC",
        (code,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_trade(code: str, direction: str, trade_date: str,
              quantity: float, price: float, note: str) -> dict:
    """新增一笔交易 → 自动更新持仓"""
    total = round(quantity * price, 2)
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO trade_logs (code, direction, trade_date, quantity, price, total, note) "
        "VALUES (?,?,?,?,?,?,?)",
        (code, direction, trade_date, quantity, price, total, note)
    )
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    recalc_position(code)
    return {"status": "ok", "id": trade_id, "message": f"{direction} {quantity}股 @ {price}"}


def update_trade(code: str, trade_id: int, direction: str, trade_date: str,
                 quantity: float, price: float, note: str):
    """修改一笔交易记录 → 自动更新持仓"""
    total = round(quantity * price, 2)
    conn = _get_db()
    cur = conn.execute(
        "UPDATE trade_logs SET direction=?, trade_date=?, quantity=?, price=?, total=?, note=? "
        "WHERE id=? AND code=?",
        (direction, trade_date, quantity, price, total, note, trade_id, code)
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if not updated:
        raise ValueError(f"交易记录 {trade_id} 不存在")
    recalc_position(code)
    return {"status": "ok"}


def delete_trade(code: str, trade_id: int):
    """删除一笔交易记录 → 自动更新持仓"""
    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM trade_logs WHERE id=? AND code=?", (trade_id, code)
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise ValueError(f"交易记录 {trade_id} 不存在")
    recalc_position(code)
    return {"status": "ok", "message": "已删除"}
