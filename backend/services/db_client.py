"""数据库访问统一入口。
所有SQLite操作集中在此，业务层不直接操作数据库。
内部委托给 services.database.stock_db。
"""
import os as _os
from backend.services.database.stock_db import (
    # 核心
    get_db, init_db, DB_PATH,

    # 分析记录
    save_analysis, get_history, get_all_history, get_stock_history,

    # 笔记
    add_note, get_notes, delete_note,

    # 提醒
    add_reminder, get_reminders, get_all_active_reminders,
    delete_reminder, toggle_reminder, mark_reminder_triggered,

    # 矛盾分析AI缓存
    get_contradiction_ai_cache, save_contradiction_ai_cache,

    # 快照/草稿
    save_snapshot, delete_snapshot, get_snapshots,
    save_draft_notes, get_draft_notes, delete_draft,

    # 聊天
    save_chat_message, get_chat_history, save_ai_analysis, get_ai_analysis,

    # 持仓/观察池
    get_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist,

    # K线
    save_kline_records, get_kline_records, prune_kline,
    fetch_and_save_kline,

    # 财务报告
    save_financial_reports, get_financial_reports, get_latest_financial_report,
    get_financial_cache, save_financial_cache,

    # 风控规则
    get_risk_rules, add_risk_rule, update_risk_rule,
    delete_risk_rule, toggle_risk_rule, get_rule_types, seed_default_rules,
    evaluate_risk_rules,

    # 个股信息
    search_stock_info, get_stock_info, get_stock_info_count,
    refresh_stock_info_from_csv, refresh_stock_detail_from_akshare,

    # Cron历史
    add_cron_log, update_cron_log, get_cron_history,
)


# ═══════════════════════════════════════════════════════════
# 股票列表（组合查询）
# ═══════════════════════════════════════════════════════════

def get_stock_list() -> dict[str, str]:
    """获取全部股票 {code: name} 映射"""
    conn = get_db()
    rows = conn.execute("SELECT code, name FROM stock_info").fetchall()
    conn.close()
    return {r["code"]: r["name"] for r in rows}


def get_stock_name(code: str) -> str:
    """获取单只股票名称"""
    return get_stock_list().get(code, "")


# ═══════════════════════════════════════════════════════════
# 行情K线（含自动拉取）
# ═══════════════════════════════════════════════════════════

def ensure_kline(code: str) -> tuple[bool, list[dict]]:
    """确保K线数据存在，缺少时自动从akshare拉取"""
    records = get_kline_records(code)
    if not records:
        ok, count = fetch_and_save_kline(code)
        if ok:
            records = get_kline_records(code)
    return bool(records), records


# ═══════════════════════════════════════════════════════════
# 个股资料
# ═══════════════════════════════════════════════════════════

def get_stock_info_detail(code: str) -> dict | None:
    """从akshare获取个股详细资料"""
    return refresh_stock_detail_from_akshare(code)
