"""
市场概览 API
"""
from fastapi import APIRouter, HTTPException, Query
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path

from backend.config import MARKET_DATA_DIR

router = APIRouter()


def _find_csv(date_str: str | None = None) -> tuple[Path | None, str]:
    """查找指定日期或最近的行情CSV"""
    if date_str:
        for prefix in ["沪深京A股", "沪深重要指数"]:
            path = MARKET_DATA_DIR / f"{prefix}{date_str}.csv"
            if path.exists():
                return path, date_str
        return None, date_str

    today = date.today()
    for i in range(10):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        for prefix in ["沪深京A股", "沪深重要指数"]:
            path = MARKET_DATA_DIR / f"{prefix}{d_str}.csv"
            if path.exists():
                return path, d_str
    return None, ""


def _clean_numeric(val) -> float | None:
    if val is None or val == "--" or pd.isna(val):
        return None
    s = str(val).strip()
    for ch in ["①", "②", "③", "④", "⑤", "亏损", " "] :
        s = s.replace(ch, "")
    s = s.replace("%", "")
    for unit in ["亿元", "亿", "万元", "万手", "手", "万"]:
        s = s.replace(unit, "")
    s = s.replace(",", "")
    s = s.strip("'\"")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _load_csv(date_str: str | None = None) -> pd.DataFrame | None:
    """读取CSV (已清洗)，指定日期或取最近"""
    path, d_str = _find_csv(date_str)
    if path is None:
        return None

    df = pd.read_csv(path, encoding="utf-16", sep="\t")

    col_map = {
        "代码": "code",
        "名称": "name",
        "最新": "close",
        "涨幅": "change_pct",
        "涨跌": "change",
        "成交额": "amount",
        "所属行业": "sector",
        "总市值": "market_cap",
        "流通市值": "float_market_cap",
        "市盈率": "pe",
        "换手": "turnover",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    df["code"] = df["code"].astype(str).str.strip("'\"")
    for col in ["close", "change_pct", "change", "amount", "market_cap", "float_market_cap", "pe", "turnover"]:
        if col in df.columns:
            df[col] = df[col].apply(_clean_numeric)
    df["_date"] = d_str
    return df


@router.get("/dates")
def available_dates():
    """返回有数据的日期列表（按倒序）"""
    dates = set()
    for f in sorted(MARKET_DATA_DIR.glob("沪深京A股*.csv"), reverse=True):
        d = f.stem.replace("沪深京A股", "")
        dates.add(d)
    return {
        "dates": sorted(dates, reverse=True),
        "latest": sorted(dates, reverse=True)[0] if dates else None,
    }


@router.get("/overview")
def market_overview(date: str = Query(None, description="日期 YYYY-MM-DD，不传则取最近")):
    """市场概览：涨跌统计、热门板块、TOP榜"""
    df = _load_csv(date)
    if df is None:
        return {
            "date": date or str(date.today()),
            "status": "no_data",
            "message": f"{date or '最近'} 无行情数据",
        }

    valid = df[df["change_pct"].notna()]
    data_date = str(next(iter(df["_date"]), ""))

    up_count = int((valid["change_pct"] > 0).sum())
    down_count = int((valid["change_pct"] < 0).sum())
    flat_count = int((valid["change_pct"] == 0).sum())
    limit_up = int((valid["change_pct"] >= 9.8).sum())
    limit_down = int((valid["change_pct"] <= -9.8).sum())
    avg_change = round(float(valid["change_pct"].mean()), 2)

    # 板块热度
    hot_sectors = []
    if "sector" in df.columns:
        sector_valid = valid[valid["sector"].notna() & (valid["sector"] != "--")].copy()
        if not sector_valid.empty:
            sector_stats = (
                sector_valid.groupby("sector")
                .agg(avg_change=("change_pct", "mean"), count=("change_pct", "count"))
                .sort_values("avg_change", ascending=False)
                .head(10)
            )
            hot_sectors = [
                {"name": idx, "avg_change": round(float(r["avg_change"]), 2), "count": int(r["count"])}
                for idx, r in sector_stats.iterrows()
            ]

    # 成交额TOP10
    top_volume = []
    vol_df = valid.dropna(subset=["amount"]).sort_values("amount", ascending=False).head(10)
    for _, r in vol_df.iterrows():
        top_volume.append({
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "close": r.get("close"),
            "change_pct": r.get("change_pct"),
            "amount": r.get("amount"),
        })

    # 涨跌幅TOP5
    top_gainers = []
    top_losers = []
    sorted_up = valid.sort_values("change_pct", ascending=False).head(5)
    for _, r in sorted_up.iterrows():
        top_gainers.append({"code": r.get("code",""), "name": r.get("name",""), "change_pct": r.get("change_pct")})
    sorted_down = valid.sort_values("change_pct").head(5)
    for _, r in sorted_down.iterrows():
        top_losers.append({"code": r.get("code",""), "name": r.get("name",""), "change_pct": r.get("change_pct")})

    return {
        "date": data_date,
        "status": "ok",
        "summary": {
            "total_stocks": int(len(valid)),
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "avg_change_pct": avg_change,
        },
        "hot_sectors": hot_sectors,
        "top_volume": top_volume,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


@router.get("/sectors")
def sector_list(date: str = Query(None, description="日期 YYYY-MM-DD，不传则取最近")):
    """全部行业板块涨跌排名"""
    df = _load_csv(date)
    if df is None or "sector" not in df.columns:
        raise HTTPException(404, "行业数据不可用")

    valid = df[df["change_pct"].notna() & df["sector"].notna() & (df["sector"] != "--")]
    sectors = (
        valid.groupby("sector")
        .agg(
            avg_change=("change_pct", "mean"),
            stock_count=("change_pct", "count"),
            up_count=("change_pct", lambda x: int((x > 0).sum())),
        )
        .sort_values("avg_change", ascending=False)
    )
    return {
        "date": str(next(iter(df["_date"]), "")),
        "sectors": [
            {
                "name": idx,
                "avg_change": round(float(r["avg_change"]), 2),
                "stock_count": int(r["stock_count"]),
                "up_count": int(r["up_count"]),
            }
            for idx, r in sectors.iterrows()
        ],
    }
