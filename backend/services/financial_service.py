"""财务数据统一服务。
所有财务报表/指标/管理层/股东数据获取集中在此，
统一超时、SQLite缓存策略、异常处理。
"""
import time
import sqlite3
import os
from datetime import date, datetime, timedelta

from backend.services.external.akshare_client import (
    get_financial_summary as _ak_get_financial_summary,
    get_revenue_breakdown as _ak_get_revenue_breakdown,
    get_earnings_data as _ak_get_earnings_data,
    get_expense_data as _ak_get_expense_data,
    get_financial_indicators as _ak_get_financial_indicators,
    get_management_changes as _ak_get_management_changes,
    get_main_shareholders as _ak_get_main_shareholders,
    get_balance_sheet as _ak_get_balance_sheet,
    get_cash_flow_sheet as _ak_get_cash_flow_sheet,
    get_profit_sheet as _ak_get_profit_sheet,
    get_concept_board_data as _ak_get_concept_board_data,
    get_concept_board_constituents as _ak_get_concept_board_constituents,
)

DB_PATH = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")

# ═══════════════════════════════════════════════════════════
# SQLite缓存操作
# ═══════════════════════════════════════════════════════════

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_financial_table():
    """确保financial_data表存在"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            code TEXT,
            report_period TEXT,
            report_type TEXT,
            data_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (code, report_period, report_type)
        )
    """)
    conn.commit()
    conn.close()


def get_financial_reports(code: str, limit: int = 20) -> list[dict]:
    """从SQLite获取财务报告缓存"""
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT * FROM financial_reports WHERE code=? ORDER BY report_date DESC LIMIT ?",
            (code, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def save_financial_reports(code: str, data: dict):
    """保存财务报告到SQLite"""
    try:
        conn = _get_db()
        for report in data.get("records", []):
            period = report.get("报告期", "")
            if period:
                conn.execute("""
                    INSERT OR REPLACE INTO financial_reports
                    (code, report_date, data_json) VALUES (?, ?, ?)
                """, (code, period, str(report)))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_db_financial(code: str, report_type: str = "summary") -> dict | None:
    """从SQLite获取缓存的财务数据（检查是否超过50天）"""
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT * FROM financial_data WHERE code=? AND report_type=? ORDER BY report_period DESC LIMIT 1",
            (code, report_type)
        ).fetchone()
        if row:
            import json
            created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
            days_old = (datetime.now() - created).days
            conn.close()
            if days_old <= 50:
                return json.loads(row["data_json"])
            return None  # 过期
        conn.close()
    except Exception:
        pass
    return None


def _save_db_financial(code: str, report_type: str, data: dict, period: str = ""):
    """保存财务数据到SQLite"""
    try:
        import json
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO financial_data (code, report_period, report_type, data_json) VALUES (?, ?, ?, ?)",
            (code, period or str(date.today()), report_type, json.dumps(data, ensure_ascii=False))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# 财务摘要（带缓存）
# ═══════════════════════════════════════════════════════════

def get_financial_summary(code: str) -> dict | None:
    """财务摘要（SQLite缓存→akshare）"""
    cached = _get_db_financial(code, "summary")
    if cached:
        return cached
    data = _ak_get_financial_summary(code)
    if data:
        _save_db_financial(code, "summary", data)
    return data


# ═══════════════════════════════════════════════════════════
# 主营业务构成（带缓存）
# ═══════════════════════════════════════════════════════════

def get_revenue_breakdown(code: str) -> list | None:
    """主营业务构成（SQLite缓存→akshare）"""
    cached = _get_db_financial(code, "revenue")
    if cached:
        return cached.get("data")
    data = _ak_get_revenue_breakdown(code)
    if data:
        _save_db_financial(code, "revenue", {"data": data})
    return data


def get_earnings_data(code: str) -> dict:
    """业绩报表数据"""
    return _ak_get_earnings_data(code)


def get_expense_data(code: str) -> dict | None:
    """费用分析（带SQLite缓存）"""
    cached = _get_db_financial(code, "expense")
    if cached:
        return cached
    data = _ak_get_expense_data(code)
    if data:
        _save_db_financial(code, "expense", data)
    return data


def _get_db_indicators(code: str) -> list[dict] | None:
    """从SQLite读取全部已缓存的财务指标（按报告期）"""
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT report_period, data_json FROM financial_data "
            "WHERE code=? AND report_type='indicator' "
            "ORDER BY report_period DESC",
            (code,)
        ).fetchall()
        conn.close()
        if rows:
            import json
            return [json.loads(r["data_json"]) for r in rows]
        return None
    except Exception:
        return None


def _save_db_indicators(code: str, data: list[dict]):
    """逐条保存财务指标到SQLite（按报告期）"""
    import json
    try:
        conn = _get_db()
        for record in data:
            # 日期可能是 datetime.date 对象，转字符串
            period_raw = record.get("日期", "")
            if not period_raw:
                continue
            period = str(period_raw)  # date → "2026-03-31"
            # 深拷贝并确保所有值可 JSON 序列化
            safe = {}
            for k, v in record.items():
                if isinstance(v, (int, float, str, bool)):
                    safe[k] = v
                elif v is None:
                    safe[k] = None
                elif hasattr(v, 'isoformat'):  # date/datetime
                    safe[k] = v.isoformat()
                else:
                    safe[k] = str(v)
            conn.execute(
                "INSERT OR REPLACE INTO financial_data (code, report_period, report_type, data_json) "
                "VALUES (?, ?, 'indicator', ?)",
                (code, period, json.dumps(safe, ensure_ascii=False))
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_financial_indicators(code: str, start_year: str = "2023") -> list[dict]:
    """财务分析指标时间序列（持久化SQLite缓存，按报告期保存）"""
    cached = _get_db_indicators(code)
    if cached:
        return cached
    data = _ak_get_financial_indicators(code, start_year)
    if data:
        _save_db_indicators(code, data)
    return data if data else []


def get_management_changes(code: str) -> list[dict]:
    """管理层持股变动"""
    return _ak_get_management_changes(code)


def get_main_shareholders(code: str) -> tuple:
    """主要股东数据"""
    return _ak_get_main_shareholders(code)


def _cached_sheet(code: str, report_type: str, fetch_fn) -> list[dict]:
    """通用缓存逻辑：先查SQLite → 未命中或过期则实时拉取并保存"""
    cached = _get_db_financial(code, report_type)
    if cached:
        return cached.get("data", [])
    data = fetch_fn(code)
    if data:
        _save_db_financial(code, report_type, {"data": data})
    return data if data else []


def get_balance_sheet(code: str) -> list[dict]:
    return _cached_sheet(code, "balance_sheet", _ak_get_balance_sheet)


def get_cash_flow_sheet(code: str) -> list[dict]:
    return _cached_sheet(code, "cash_flow", _ak_get_cash_flow_sheet)


def get_profit_sheet(code: str) -> list[dict]:
    return _cached_sheet(code, "profit_sheet", _ak_get_profit_sheet)


# ═══════════════════════════════════════════════════════════
# 概念板块（从akshare）
# ═══════════════════════════════════════════════════════════

def get_concept_board_data() -> dict:
    """概念板块实时行情（24h缓存）"""
    return _ak_get_concept_board_data()


def get_concept_board_constituents(board_name: str) -> list[dict]:
    """概念板块成分股"""
    return _ak_get_concept_board_constituents(board_name)


# ═══════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════

_init_financial_table()
