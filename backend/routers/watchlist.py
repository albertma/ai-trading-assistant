"""观察池 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.db_client import (
    get_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist
)
from backend.services.financial_service import get_financial_summary
from backend.services.market_service import get_daily_history, get_ma
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

router = APIRouter()


def _get_daily_history(code: str, max_days: int = 60) -> list | None:
    """获取个股日线行情（复用analysis的逻辑）"""
    import urllib.request, json
    try:
        market = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else "bj"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{max_days},qfq"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        raw = json.loads(resp.read().decode())
        kdata = raw["data"][f"{market}{code}"].get("qfqday") or raw["data"][f"{market}{code}"].get("day") or []

        records = []
        for k in kdata[-max_days:]:
            records.append({
                "date": k[0], "open": float(k[1]), "close": float(k[2]),
                "high": float(k[3]), "low": float(k[4]), "volume": float(k[5]),
            })
        return records
    except:
        return None


class WatchItem(BaseModel):
    code: str
    name: str
    sector: str = ""
    reason: str = ""
    priority: str = "medium"


@router.get("")
def list_watchlist():
    """获取观察池所有股票"""
    items = get_watchlist()
    return {"items": items, "count": len(items)}


@router.post("")
def add_watch(item: WatchItem):
    """添加到观察池"""
    ok = add_to_watchlist(item.code, item.name, item.sector, item.reason, item.priority)
    if not ok:
        raise HTTPException(500, "添加失败")
    return {"status": "ok", "message": f"已添加 {item.name}({item.code}) 到观察池"}


@router.delete("/{code}")
def remove_watch(code: str):
    """从观察池移除"""
    ok = remove_from_watchlist(code)
    if not ok:
        raise HTTPException(404, f"未找到 {code}")
    return {"status": "ok", "message": f"已从观察池移除 {code}"}


@router.put("/{code}")
def update_watch(code: str, priority: Optional[str] = None, reason: Optional[str] = None, notes: Optional[str] = None):
    """更新观察池信息"""
    kwargs = {}
    if priority is not None:
        kwargs["priority"] = priority
    if reason is not None:
        kwargs["reason"] = reason
    if notes is not None:
        kwargs["notes"] = notes
    ok = update_watchlist(code, **kwargs)
    if not ok:
        raise HTTPException(404, f"未找到 {code}")
    return {"status": "ok", "message": f"已更新 {code}"}


@router.get("/{code}/chart")
def watch_chart(code: str, days: int = 30):
    """获取K线走势数据"""
    records = _get_daily_history(code, max_days=days)
    if not records:
        raise HTTPException(404, f"无法获取 {code} 的K线数据")
    # 计算均线
    closes = [r["close"] for r in records]
    ma5_list = []
    ma20_list = []
    for i in range(len(closes)):
        ma5_list.append(round(np.mean(closes[max(0, i-4):i+1]), 2) if i >= 4 else None)
        ma20_list.append(round(np.mean(closes[max(0, i-19):i+1]), 2) if i >= 19 else None)

    result = []
    for i, r in enumerate(records):
        result.append({
            "date": r["date"],
            "open": r["open"],
            "close": r["close"],
            "high": r["high"],
            "low": r["low"],
            "volume": r["volume"],
            "ma5": ma5_list[i],
            "ma20": ma20_list[i],
        })
    return {"code": code, "records": result, "count": len(result)}


@router.get("/{code}/fundamental")
def watch_fundamental(code: str):
    """获取基本面变化（财务历史）"""
    try:
        fin = get_financial_summary(code)
        if fin and fin.get("records"):
            rows = []
            for r in fin["records"][:5]:
                def v(key):
                    val = r.get(key, "--")
                    return str(val) if val is not None and str(val) != "nan" else "--"
                rows.append({
                    "period": v("报告期"),
                    "revenue": v("营业总收入"),
                    "revenue_yoy": v("营业总收入同比增长"),
                    "net_profit": v("归属净利润"),
                    "net_profit_yoy": v("归属净利润同比增长"),
                    "gross_margin": v("毛利率"),
                    "net_margin": v("净利率"),
                    "eps": v("每股收益"),
                    "roe": v("净资产收益率"),
                })
            return {"code": code, "records": rows, "count": len(rows)}
        return {"code": code, "records": [], "count": 0}
    except Exception as e:
        return {"code": code, "records": [], "count": 0, "error": str(e)}


@router.post("/refresh-kline")
def refresh_all_kline():
    """为所有观察池中的股票/ETF刷新K线数据（保留400条）"""
    from backend.services.db_client import get_watchlist, fetch_and_save_kline
    items = get_watchlist()
    results = []
    for item in items:
        ok, saved = fetch_and_save_kline(item["code"])
        results.append({"code": item["code"], "name": item["name"], "ok": ok, "saved": saved})
    return {"results": results, "total": len(results), "ok_count": sum(1 for r in results if r["ok"])}


@router.post("/refresh-kline/{code}")
def refresh_one_kline(code: str):
    """为指定股票/ETF刷新K线数据（保留400条）"""
    from backend.services.db_client import fetch_and_save_kline, prune_kline
    ok, saved = fetch_and_save_kline(code)
    pruned = prune_kline(code)
    return {"code": code, "ok": ok, "saved": saved, "pruned": pruned}


@router.get("/local-kline/{code}")
def local_kline(code: str, days: int = 400):
    """从本地数据库获取K线数据，如果没有则实时抓取，并补充今日实时价格"""
    from backend.services.db_client import get_kline_records, fetch_and_save_kline
    from pathlib import Path
    from datetime import date, timedelta
    records = get_kline_records(code, limit=days)
    if len(records) < 20:
        # 数据不足，实时抓取
        fetch_and_save_kline(code)
        records = get_kline_records(code, limit=days)
    else:
        # 检查最新记录是否过旧（超过3个交易日），是则重新抓取
        latest_date = records[0].get('date', '') if records else ''
        today_str = date.today().isoformat()
        if latest_date and latest_date < (date.today() - timedelta(days=7)).isoformat():
            fetch_and_save_kline(code)
            records = get_kline_records(code, limit=days)

    # 尝试补充今日实时价格（午盘/收盘CSV）
    today_str = date.today().isoformat()
    has_today = any(r.get('date') == today_str for r in records)
    if not has_today:
        csv_dir = Path.home() / "Jarvis" / "A股行情信息"
        for suffix in [f"_noon", ""]:
            csv_path = csv_dir / f"沪深京A股{today_str}{suffix}.csv"
            if csv_path.exists():
                try:
                    import csv as csv_mod
                    with open(str(csv_path), 'r', encoding='utf-16') as f:
                        reader = csv_mod.DictReader(f, delimiter='\t')
                        target = code.strip()
                        for row in reader:
                            row_code = row.get('代码', '').strip().lstrip("'")
                            if row_code == target:
                                today_row = {
                                    'code': code,
                                    'date': today_str,
                                    'open': float(row['开盘'] or 0),
                                    'close': float(row['最新'] or 0),
                                    'high': float(row['最高'] or 0),
                                    'low': float(row['最低'] or 0),
                                    'volume': float(row.get('成交量', 0) or 0),
                                }
                                records.append(today_row)
                                break
                except Exception:
                    pass
                break

    # 按日期正序排列（前端图表需要）
    records.sort(key=lambda r: r["date"])
    return {"code": code, "records": records, "count": len(records)}
