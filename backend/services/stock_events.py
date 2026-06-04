"""限售解禁/事件提醒服务 — SQLite CRUD"""

import sqlite3
from pathlib import Path
from datetime import datetime


def _get_db() -> sqlite3.Connection:
    db = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table():
    """确保 stock_events 表存在（由 init_db 中创建，此函数为安全兜底）"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT '解禁',
            event_date TEXT NOT NULL,
            title TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_se_code ON stock_events(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_se_date ON stock_events(event_date)")
    conn.commit()
    conn.close()


def list_events(code: str = "", days: int = 90) -> list[dict]:
    """获取事件列表

    code: 筛选股票代码
    days: 未来多少天内的事件
    """
    conn = _get_db()
    from datetime import date, timedelta
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()

    if code:
        rows = conn.execute(
            "SELECT * FROM stock_events WHERE code=? AND event_date >= ? AND event_date <= ? ORDER BY event_date ASC",
            (code, today, future)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM stock_events WHERE event_date >= ? AND event_date <= ? ORDER BY event_date ASC",
            (today, future)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_past_events(code: str = "", days: int = 90) -> list[dict]:
    """获取过去的事件记录（用于展示已经发生的解禁）"""
    conn = _get_db()
    from datetime import date, timedelta
    today = date.today().isoformat()
    past = (date.today() - timedelta(days=days)).isoformat()

    if code:
        rows = conn.execute(
            "SELECT * FROM stock_events WHERE code=? AND event_date >= ? AND event_date < ? ORDER BY event_date DESC",
            (code, past, today)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM stock_events WHERE event_date >= ? AND event_date < ? ORDER BY event_date DESC",
            (past, today)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_event(code: str, event_type: str, event_date: str, title: str = "",
              detail: str = "", source: str = "") -> int:
    """新增事件"""
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO stock_events (code, event_type, event_date, title, detail, source) VALUES (?,?,?,?,?,?)",
        (code, event_type, event_date, title, detail, source)
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def update_event(event_id: int, **kwargs) -> bool:
    """更新事件"""
    allowed = {"event_type", "event_date", "title", "detail", "source"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [event_id]
    conn = _get_db()
    cur = conn.execute(f"UPDATE stock_events SET {sets} WHERE id=?", vals)
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def delete_event(event_id: int) -> bool:
    """删除事件"""
    conn = _get_db()
    cur = conn.execute("DELETE FROM stock_events WHERE id=?", (event_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok
