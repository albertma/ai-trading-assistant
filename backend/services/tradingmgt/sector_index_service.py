"""
板块指数计算服务 — 从每日CSV行情计算市值加权板块指数
逻辑：
  1. 按行业分组，计算每只股票的市值加权涨幅
  2. 从最早有数据的日期开始，以 1000 为基准逐日链式累加
  3. 结果持久化到 sector_indices 表
"""

import os
import glob
import pandas as pd
import numpy as np
from datetime import date, datetime
from backend.services.database.stock_db import get_db


def _get_csv_date_from_filename(fname: str) -> str | None:
    """从CSV文件名提取日期 (YYYY-MM-DD)，排除 noon"""
    base = os.path.basename(fname)
    if "noon" in base:
        return None
    # 沪深京A股2026-05-11.csv
    parts = base.replace("沪深京A股", "").replace(".csv", "").split("_")
    if parts and len(parts[0]) == 10:
        return parts[0]
    return None


def _load_csv_by_date(target_date: str) -> pd.DataFrame | None:
    """读取指定日期的收盘CSV"""
    csv_dir = os.path.expanduser("~/Jarvis/A股行情信息")
    fname = f"沪深京A股{target_date}.csv"
    fpath = os.path.join(csv_dir, fname)
    if not os.path.exists(fpath):
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-16", sep="\t")
        df.columns = [c.strip() for c in df.columns]
        # 统一数值清洗：总市值等列可能有脚注符号或 '--'
        for col in ["总市值", "涨幅", "最新"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', regex=True)
                df[col] = df[col].str.replace('--', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # 代码列清洗
        if "代码" in df.columns:
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
        return df
    except Exception as e:
        print(f"CSV load error: {e}")
        return None


def _compute_weighted_daily_return(df: pd.DataFrame) -> list[dict]:
    """
    从当日行情DataFrame计算各板块的市值加权涨跌幅
    
    Args:
        df: 列含 '所属行业', '涨幅', '总市值'
    
    Returns:
        [{"sector": str, "daily_return": float, "total_mv": float, "stock_count": int}, ...]
    """
    valid = df[
        df["所属行业"].notna()
        & (df["所属行业"] != "--")
        & df["涨幅"].notna()
        & df["总市值"].notna()
        & (df["总市值"] > 0)
    ].copy()

    if valid.empty:
        return []

    results = []
    for sector_name, group in valid.groupby("所属行业"):
        changes = group["涨幅"].values
        mvs = group["总市值"].values

        # 市值加权平均涨幅
        total_mv = float(mvs.sum())
        if total_mv <= 0:
            continue
        weighted_return = float(np.average(changes, weights=mvs))
        stock_count = len(changes)

        results.append({
            "sector": sector_name,
            "daily_return": round(weighted_return, 2),
            "total_mv": round(total_mv, 2),
            "stock_count": stock_count,
        })

    return results


def _get_all_csv_dates() -> list[str]:
    """获取所有收盘CSV的日期列表，升序"""
    csv_dir = os.path.expanduser("~/Jarvis/A股行情信息")
    pattern = os.path.join(csv_dir, "沪深京A股*.csv")
    dates = []
    for fpath in sorted(glob.glob(pattern)):
        d = _get_csv_date_from_filename(fpath)
        if d:
            dates.append(d)
    return sorted(set(dates))


def refresh_sector_indices(target_date: str | None = None) -> dict:
    """
    刷新板块指数：
    - 如果指定 target_date，只计算该日的日收益率并更新
    - 如果 target_date 为 None，重建所有日期的完整指数链

    首次运行会从最早有数据的日期开始，逐日回填 index_value。
    """
    db = get_db()

    if target_date:
        # 仅计算单日 -> 追加到已有链上
        df = _load_csv_by_date(target_date)
        if df is None:
            db.close()
            return {"date": target_date, "sectors": 0, "error": "无行情数据"}

        daily_data = _compute_weighted_daily_return(df)
        if not daily_data:
            db.close()
            return {"date": target_date, "sectors": 0, "error": "无有效板块数据"}

        # 获取前一日的指数值做链式累加
        prev_rows = db.execute(
            "SELECT sector, index_value FROM sector_indices WHERE date < ? "
            "ORDER BY date DESC LIMIT 200",
            (target_date,)
        ).fetchall()
        prev_index_map = {}
        for r in prev_rows:
            if r["sector"] not in prev_index_map:
                prev_index_map[r["sector"]] = r["index_value"]

        inserted = 0
        for item in daily_data:
            sector = item["sector"]
            daily_ret = item["daily_return"]
            prev_val = prev_index_map.get(sector, 1000.0)
            new_index = round(prev_val * (1 + daily_ret / 100), 2)

            db.execute(
                """INSERT OR REPLACE INTO sector_indices
                   (date, sector, index_value, daily_return, total_mv, stock_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (target_date, sector, new_index, daily_ret,
                 item["total_mv"], item["stock_count"])
            )
            inserted += 1

        db.commit()
        db.close()
        return {"date": target_date, "sectors": inserted, "status": "ok"}
    else:
        # 全量重建
        db.execute("DELETE FROM sector_indices")
        all_dates = _get_all_csv_dates()
        if not all_dates:
            db.close()
            return {"dates": 0, "error": "无CSV数据"}

        # sector -> latest_index 追踪
        latest_index: dict[str, float] = {}
        total_dates = len(all_dates)
        total_inserted = 0

        for csv_date in all_dates:
            df = _load_csv_by_date(csv_date)
            if df is None:
                continue
            daily_data = _compute_weighted_daily_return(df)
            if not daily_data:
                continue

            for item in daily_data:
                sector = item["sector"]
                daily_ret = item["daily_return"]
                prev_val = latest_index.get(sector, 1000.0)
                new_index = round(prev_val * (1 + daily_ret / 100), 2)
                latest_index[sector] = new_index

                db.execute(
                    """INSERT OR REPLACE INTO sector_indices
                       (date, sector, index_value, daily_return, total_mv, stock_count)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (csv_date, sector, new_index, daily_ret,
                     item["total_mv"], item["stock_count"])
                )
                total_inserted += 1

        db.commit()
        db.close()
        return {
            "dates": total_dates,
            "date_range": f"{all_dates[0]} ~ {all_dates[-1]}",
            "sectors": total_inserted,
            "status": "ok",
        }


def get_sector_indices(
    sector: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit_dates: int = 5000,
) -> list[dict]:
    """
    查询板块指数历史
    
    Args:
        sector: 板块名称，None=返回所有板块
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 截止日期 (YYYY-MM-DD)
        limit_dates: 最多返回的交易日数
    
    Returns:
        [{date, sector, index_value, daily_return, total_mv, stock_count}, ...]
    """
    db = get_db()
    conditions = []
    params = []

    if sector:
        conditions.append("sector = ?")
        params.append(sector)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = db.execute(
        f"SELECT date, sector, index_value, daily_return, total_mv, stock_count "
        f"FROM sector_indices WHERE {where} "
        f"ORDER BY date DESC LIMIT ?",
        (*params, limit_dates)
    ).fetchall()
    db.close()

    # 按日期升序返回
    result = [dict(r) for r in rows]
    result.sort(key=lambda x: x["date"])
    return result


def get_latest_sector_indices(target_date: str | None = None) -> list[dict]:
    """获取指定日期（或最新日期）所有板块的指数值"""
    db = get_db()
    if target_date:
        rows = db.execute(
            "SELECT * FROM sector_indices WHERE date = ? ORDER BY sector",
            (target_date,)
        ).fetchall()
    else:
        latest = db.execute(
            "SELECT date FROM sector_indices ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if not latest:
            db.close()
            return []
        rows = db.execute(
            "SELECT * FROM sector_indices WHERE date = ? ORDER BY sector",
            (latest["date"],)
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_base_date() -> str | None:
    """获取指数链的起始日期"""
    db = get_db()
    row = db.execute(
        "SELECT date FROM sector_indices ORDER BY date ASC LIMIT 1"
    ).fetchone()
    db.close()
    return row["date"] if row else None
