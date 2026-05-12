"""
个股档案 API
"""
from fastapi import APIRouter, HTTPException, Query
import json
import os
from datetime import date, timedelta

from backend.config import MARKET_DATA_DIR
from backend.services.db_client import save_analysis, get_history, get_all_history, get_stock_history, add_note, get_notes, get_chat_history, get_financial_reports, save_financial_reports, save_snapshot, delete_snapshot, delete_draft, get_snapshots, save_draft_notes, get_draft_notes
from backend.routers.analysis import analyze_stock as _do_analysis
from backend.routers.fundamental import fundamental_analysis as _do_fundamental

router = APIRouter()


# ===== 固定路由（必须放在 /{code} 之前） =====

@router.get("/all-history")
def all_history_full(limit: int = Query(100, le=500)):
    """获取所有股票的全部分析历史记录（不去重）"""
    return {"total": limit, "records": get_all_history(limit)}


@router.get("")
def all_history(limit: int = Query(50, le=200)):
    return {"total": limit, "records": get_history(limit)}


# ===== 动态路由 =====

@router.get("/{code}")
def stock_profile(code: str):
    """个股档案（带20s超时保护）"""
    import pandas as pd
    import threading

    result_box = {}

    def _do_work():
        nonlocal result_box
        try:
            tech_data = _do_analysis(code)
            cached_reports = get_financial_reports(code, 20)
            if cached_reports:
                records_data = cached_reports
                fund_data = {}
            else:
                try:
                    fund_data = _do_fundamental(code)
                except Exception:
                    fund_data = {}
                fin = fund_data.get("financial_summary") or {}
                raw_records = fin.get("records") or []
                if raw_records:
                    save_financial_reports(code, raw_records)
                records_data = get_financial_reports(code, 20) or raw_records

            name = tech_data.get("name", "") or fund_data.get("name", "")
            sector = fund_data.get("sector", "")
            if not sector:
                today = date.today()
                for i in range(5):
                    d = (today - timedelta(days=i)).isoformat()
                    path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
                    if path.exists():
                        df = pd.read_csv(path, encoding="utf-16", sep="\t")
                        df["代码"] = df["代码"].astype(str).str.strip("'\"")
                        match = df[df["代码"] == code]
                        if not match.empty:
                            sector = str(match.iloc[0].get("所属行业", ""))
                            if not name:
                                name = str(match.iloc[0].get("名称", ""))
                        break

            # 行业基础数据（读CSV，快） + 景气周期分析（子线程5s超时，慢）
            if cached_reports and sector and not fund_data.get("industry_outlook"):
                try:
                    from backend.routers.fundamental import _get_industry_data, _analyze_industry_cycle
                    ind_part = _get_industry_data(sector)
                    if ind_part:
                        # _analyze_industry_cycle 可能调用akshare挂起，丢子线程+5s超时
                        cycle_box = {}
                        def _fetch_cycle():
                            try:
                                c = _analyze_industry_cycle(sector, ind_part)
                                if c:
                                    cycle_box["data"] = c
                            except Exception:
                                pass
                        ct = threading.Thread(target=_fetch_cycle, daemon=True)
                        ct.start()
                        ct.join(timeout=5)
                        if cycle_box.get("data"):
                            ind_part["cycle_analysis"] = cycle_box["data"]
                        fund_data["industry_outlook"] = ind_part
                except Exception:
                    pass

            t = tech_data.get("technical") or {}
            rc = tech_data.get("risk_check") or {}
            ind = fund_data.get("industry_outlook") or {}
            rev = fund_data.get("revenue_breakdown") or []

            profile = {
                "code": code, "name": name, "sector": sector,
                "price": t.get("current_price"), "change_pct": t.get("change_pct"),
                "ma5": t.get("ma5"), "ma10": t.get("ma10"), "ma20": t.get("ma20"),
                "ma60": t.get("ma60"), "ma200": t.get("ma200"),
                "rsi14": t.get("rsi_14"), "macd": t.get("macd"),
                "bullish_alignment": t.get("bullish_alignment"),
                "trend_status": t.get("trend_status", "空头"),
                "risk_passed": rc.get("passed"),
                "news": tech_data.get("news", []),
                "business": rev[0].get("business", "") if rev else "",
                "top_stocks": ind.get("top_stocks", []),
                "industry_rank": ind.get("rank"), "industry_total": ind.get("total_sectors"),
                "industry_avg_chg": ind.get("avg_change"),
                "latest_report": None, "revenue": None, "revenue_yoy": None,
                "net_profit": None, "net_profit_yoy": None,
                "gross_margin": None, "roe": None, "eps": None, "bps": None,
                "debt_ratio": None, "current_ratio": None,
                "financial_records": [], "notes": [], "analysis_history": [],
            }
            if records_data:
                last = records_data[0]
                profile.update({
                    "latest_report": last.get("period") or last.get("报告期", ""),
                    "revenue": last.get("revenue") or last.get("营业总收入"),
                    "revenue_yoy": last.get("revenue_yoy") or last.get("营业总收入同比增长率"),
                    "net_profit": last.get("net_profit") or last.get("净利润"),
                    "net_profit_yoy": last.get("net_profit_yoy") or last.get("净利润同比增长率"),
                    "gross_margin": last.get("gross_margin") or last.get("销售毛利率"),
                    "roe": last.get("roe") or last.get("净资产收益率"),
                    "eps": last.get("eps") or last.get("基本每股收益"),
                    "bps": last.get("bps") or last.get("每股净资产"),
                    "debt_ratio": last.get("debt_ratio") or last.get("资产负债率"),
                    "current_ratio": last.get("current_ratio") or last.get("流动比率"),
                })
                profile["financial_records"] = records_data[:20]

            profile["notes"] = get_notes(code)
            profile["analysis_history"] = get_stock_history(code)
            profile["chat_history"] = get_chat_history(code, 30)
            profile["draft_notes"] = get_draft_notes(code)

            try:
                last_rec = records_data[-1] if records_data else None
                save_analysis(code, name, sector, {
                    "technical": t,
                    "fundamental": {"revenue": last_rec.get("revenue") or last_rec.get("营业总收入") if last_rec else None,
                                   "net_profit": last_rec.get("net_profit") or last_rec.get("净利润") if last_rec else None,
                                   "gross_margin": last_rec.get("gross_margin") or last_rec.get("销售毛利率") if last_rec else None,
                                   "roe": last_rec.get("roe") or last_rec.get("净资产收益率") if last_rec else None},
                    "risk_check": rc, "industry_outlook": ind,
                    "pe": None, "pb": None, "market_cap": None,
                })
            except Exception:
                pass
            result_box["profile"] = profile
        except Exception as e:
            result_box["error"] = str(e)

    worker = threading.Thread(target=_do_work, daemon=True)
    worker.start()
    worker.join(timeout=20)

    if result_box.get("profile"):
        return result_box["profile"]

    # 超时或出错，返回最基本的信息
    return {
        "code": code,
        "name": "",
        "sector": "",
        "price": None, "change_pct": None,
        "latest_report": None, "financial_records": [],
        "_timeout": True,
    }


@router.post("/{code}/save-full-analysis")
def save_full_analysis(code: str, data: dict):
    """从分析页面保存全量分析数据到SQLite"""
    from backend.services.db_client import save_analysis
    try:
        name = (data or {}).get("name", "")
        sector = (data or {}).get("sector", "")
        analysis_data = (data or {}).get("analysis_data", {})
        ok = save_analysis(code, name, sector, analysis_data)
        return {"status": "ok" if ok else "failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/{code}/note")
def add_stock_note(code: str, data: dict):
    note = (data or {}).get("note", "").strip()
    if not note:
        raise HTTPException(400, "备注不能为空")
    nid = add_note(code, note)
    return {"status": "ok", "note_id": nid}


@router.get("/{code}/history")
def stock_analysis_history(code: str):
    return {"code": code, "records": get_stock_history(code)}


@router.get("/{code}/refresh-finance")
def refresh_finance(code: str):
    """刷新并缓存财报数据（全部历史）"""
    from backend.routers.fundamental import _get_financial_summary
    try:
        fin = _get_financial_summary(code)
        raw_records = (fin or {}).get("records") or []
        if raw_records:
            saved = save_financial_reports(code, raw_records)
            return {"code": code, "saved": saved, "total": len(raw_records)}
        return {"code": code, "saved": 0, "total": 0, "message": "未获取到财报数据"}
    except Exception as e:
        return {"code": code, "error": str(e)}


@router.post("/{code}/save-snapshot")
def save_analysis_snapshot(code: str, data: dict):
    """保存当前分析结果为快照"""
    snapshot_id = save_snapshot(
        code,
        (data or {}).get("name", ""),
        (data or {}).get("sector", ""),
        (data or {}).get("analysis_data", {}),
        (data or {}).get("notes", ""),
    )
    if snapshot_id is None:
        raise HTTPException(500, "保存快照失败")
    return {"status": "ok", "snapshot_id": snapshot_id}


@router.put("/{code}/draft-notes")
def update_draft_notes(code: str, data: dict):
    """保存草稿笔记"""
    notes = (data or {}).get("notes", "").strip()
    ok = save_draft_notes(code, notes)
    if not ok:
        raise HTTPException(404, "该股票暂无分析记录，请先打开档案")
    return {"status": "ok"}


@router.get("/{code}/snapshots")
def list_snapshots(code: str):
    """获取所有快照（不含草稿）"""
    records = get_snapshots(code)
    return {"code": code, "records": records}


@router.delete("/{code}/snapshot/{snapshot_id}")
def delete_analysis_snapshot(code: str, snapshot_id: int):
    """删除分析快照"""
    ok = delete_snapshot(snapshot_id)
    if not ok:
        raise HTTPException(404, "快照不存在或已删除")
    return {"status": "ok"}


@router.delete("/{code}/draft/{analysis_date}")
def delete_analysis_draft(code: str, analysis_date: str):
    """删除分析草稿"""
    ok = delete_draft(code, analysis_date)
    if not ok:
        raise HTTPException(404, "草稿不存在或已删除")
    return {"status": "ok"}


TAGS_PATH = os.path.expanduser("~/Jarvis/stock_tags.json")

def _load_tags() -> dict:
    if os.path.exists(TAGS_PATH):
        try:
            with open(TAGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_tags(tags: dict):
    os.makedirs(os.path.dirname(TAGS_PATH), exist_ok=True)
    with open(TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


@router.get("/{code}/tags")
def get_stock_tags(code: str):
    """获取股票tag列表"""
    tags = _load_tags()
    return {"code": code, "tags": tags.get(code, [])}


@router.post("/{code}/tags")
def set_stock_tags(code: str, data: dict):
    """设置股票tag列表，tags应为字符串数组"""
    new_tags = (data or {}).get("tags", [])
    if not isinstance(new_tags, list):
        raise HTTPException(400, "tags must be a list of strings")
    tags = _load_tags()
    tags[code] = [str(t).strip() for t in new_tags if str(t).strip()]
    _save_tags(tags)
    return {"code": code, "tags": tags[code]}
