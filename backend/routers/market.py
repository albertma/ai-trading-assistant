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


def _find_csv(date_str: str | None = None, session: str | None = None) -> tuple[Path | None, str, str]:
    """查找指定日期或最近的行情CSV
    session: 'close' (终盘/默认) | 'noon' (午市)
    返回 (path, date_str, actual_session)
    """
    def _lookup(d_str, s):
        sfx = '_noon' if s == 'noon' else ''
        for prefix in ["沪深京A股", "沪深重要指数"]:
            path = MARKET_DATA_DIR / f"{prefix}{d_str}{sfx}.csv"
            if path.exists():
                return path
        return None

    if date_str:
        # 指定session → 精确匹配
        if session:
            path = _lookup(date_str, session)
            if path:
                return path, date_str, session
            # 指定session没找到，尝试另一个作为fallback
            fallback = 'close' if session == 'noon' else 'noon'
            path = _lookup(date_str, fallback)
            if path:
                return path, date_str, fallback
            return None, date_str, session
        # 未指定session → 优先close，其次noon
        for s in ['close', 'noon']:
            path = _lookup(date_str, s)
            if path:
                return path, date_str, s
        return None, date_str, 'close'

    # 自动找最近
    today = date.today()
    sessions_to_try = [session] if session else ['close', 'noon']
    for i in range(10):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        for s in sessions_to_try:
            path = _lookup(d_str, s)
            if path:
                return path, d_str, s
    return None, "", 'close'


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


def _load_csv(date_str: str | None = None, session: str | None = None) -> pd.DataFrame | None:
    """读取CSV (已清洗)，指定日期或取最近"""
    path, d_str, actual_session = _find_csv(date_str, session)
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
    df["_session"] = actual_session
    return df


def _list_available() -> list[dict]:
    """返回日期列表，每个日期标注有哪些session可用"""
    from collections import defaultdict
    sessions_by_date = defaultdict(list)
    for f in sorted(MARKET_DATA_DIR.glob("沪深京A股*.csv"), reverse=True):
        stem = f.stem.replace("沪深京A股", "")
        if stem.endswith("_noon"):
            d = stem.replace("_noon", "")
            sessions_by_date[d].append("noon")
        else:
            d = stem
            if "close" not in sessions_by_date[d]:
                sessions_by_date[d].insert(0, "close")

    result = []
    for d, sessions in sorted(sessions_by_date.items(), reverse=True):
        has_close = "close" in sessions
        has_noon = "noon" in sessions
        if has_close and has_noon:
            result.append({"date": d, "sessions": ["noon", "close"]})
        elif has_close:
            result.append({"date": d, "sessions": ["close"]})
        else:
            result.append({"date": d, "sessions": ["noon"]})
    return result


@router.get("/dates")
def available_dates():
    """返回有数据的日期列表"""
    dates = _list_available()
    latest = dates[0] if dates else None
    return {
        "dates": [d["date"] for d in dates],
        "sessions_by_date": {d["date"]: d["sessions"] for d in dates},
        "latest": latest["date"] if latest else None,
        "latest_sessions": latest["sessions"] if latest else [],
    }


@router.get("/overview")
def market_overview(
    date: str = Query(None, description="日期 YYYY-MM-DD，不传则取最近"),
    session: str = Query(None, description="noon=午市, close=终盘, 不传自动选"),
):
    """市场概览：涨跌统计、热门板块、TOP榜"""
    df = _load_csv(date, session)
    if df is None:
        return {
            "date": date or str(date.today()),
            "session": session or "close",
            "status": "no_data",
            "message": f"{date or '最近'} 无行情数据",
        }

    valid = df[df["change_pct"].notna()]
    data_date = str(next(iter(df["_date"]), ""))
    data_session = str(next(iter(df["_session"]), "close"))

    up_count = int((valid["change_pct"] > 0).sum())
    down_count = int((valid["change_pct"] < 0).sum())
    flat_count = int((valid["change_pct"] == 0).sum())
    limit_up = int((valid["change_pct"] >= 9.8).sum())
    limit_down = int((valid["change_pct"] <= -9.8).sum())
    avg_change = round(float(valid["change_pct"].mean()), 2)

    # 板块热度（含涨跌分化指标）
    hot_sectors = []
    if "sector" in df.columns:
        sector_valid = valid[valid["sector"].notna() & (valid["sector"] != "--")].copy()
        if not sector_valid.empty:
            sector_stats = (
                sector_valid.groupby("sector")["change_pct"]
                .agg(["mean", "std", "count", lambda x: (x > 0).sum() / len(x) * 100])
                .rename(columns={"mean": "avg_change", "std": "dispersion", "count": "count", "<lambda_0>": "up_pct"})
                .reset_index()
                .sort_values("avg_change", ascending=False)
                .head(10)
            )
            # 整体市场分化
            all_dispersion = round(float(valid["change_pct"].std()), 2) if len(valid) > 1 else 0
            hot_sectors = [
                {
                    "name": str(r["sector"]),
                    "avg_change": round(float(r["avg_change"]), 2),
                    "dispersion": round(float(r["dispersion"]), 2) if pd.notna(r["dispersion"]) else 0,
                    "up_pct": round(float(r["up_pct"]), 1),
                    "count": int(r["count"]),
                }
                for _, r in sector_stats.iterrows()
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
            "amount": round(r.get("amount", 0) / 1e8, 2) if r.get("amount") else None,
            "sector": r.get("sector", ""),
        })

    # 涨跌幅TOP10
    top_gainers = []
    top_losers = []
    sorted_up = valid.sort_values("change_pct", ascending=False).head(10)
    for _, r in sorted_up.iterrows():
        top_gainers.append({"code": r.get("code",""), "name": r.get("name",""), "change_pct": r.get("change_pct"), "sector": r.get("sector", "")})
    sorted_down = valid.sort_values("change_pct").head(10)
    for _, r in sorted_down.iterrows():
        top_losers.append({"code": r.get("code",""), "name": r.get("name",""), "change_pct": r.get("change_pct"), "sector": r.get("sector", "")})

    # 当前日期的可用session
    dates_info = _list_available()
    sessions_map = {d["date"]: d["sessions"] for d in dates_info}

    # 整体市场分化值
    market_dispersion = round(float(valid["change_pct"].std()), 2) if len(valid) > 1 else 0

    # 涨跌分化最大的板块（按标准差排序）
    sector_divergence = []
    if "sector" in df.columns:
        sector_valid = valid[valid["sector"].notna() & (valid["sector"] != "--")].copy()
        if not sector_valid.empty:
            div_stats = (
                sector_valid.groupby("sector")["change_pct"]
                .agg(["mean", "std", "count"])
                .reset_index()
                .sort_values("std", ascending=False)
                .head(10)
            )
            sector_divergence = [
                {"name": str(r["sector"]), "avg_change": round(float(r["mean"]), 2),
                 "dispersion": round(float(r["std"]), 2), "count": int(r["count"])}
                for _, r in div_stats.iterrows()
            ]

    return {
        "date": data_date,
        "session": data_session,
        "sessions_available": sessions_map.get(data_date, []),
        "status": "ok",
        "summary": {
            "total_stocks": int(len(valid)),
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "avg_change_pct": avg_change,
            "market_dispersion": market_dispersion,
        },
        "hot_sectors": hot_sectors,
        "sector_divergence": sector_divergence,
        "top_volume": top_volume,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


@router.get("/sentiment-cycle")
def sentiment_cycle(
    days: int = Query(30, description="回溯天数"),
):
    """市场情绪周期分析：返回最近N个交易日的情绪指标时序"""
    dates_info = _list_available()
    # 取最近N个有close数据的交易日
    close_dates = []
    for d in dates_info:
        if "close" in d["sessions"]:
            close_dates.append(d["date"])
            if len(close_dates) >= days:
                break

    records = []
    for d in reversed(close_dates):
        df = _load_csv(d, "close")
        if df is None:
            continue
        valid = df[df["change_pct"].notna()]
        up = int((valid["change_pct"] > 0).sum())
        down = int((valid["change_pct"] < 0).sum())
        total = up + down
        ratio = round(up / total, 2) if total else 0.5
        limit_up = int((valid["change_pct"] >= 9.8).sum())
        limit_down = int((valid["change_pct"] <= -9.8).sum())
        avg_chg = round(float(valid["change_pct"].mean()), 2)
        total_stocks = int(len(valid))

        # 判断周期阶段
        stage = _classify_cycle_stage(ratio, avg_chg, limit_up, limit_down, total)

        records.append({
            "date": d,
            "up": up,
            "down": down,
            "ratio": ratio,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "avg_change_pct": avg_chg,
            "total_stocks": total_stocks,
            "stage": stage["stage"],
            "stage_label": stage["label"],
        })

    # 倒序排列（最新在前）
    records.reverse()

    # 综合当前阶段判断
    current = records[0] if records else None
    assessment = _assess_cycle(records) if records else {}

    return {
        "records": records,
        "current_stage": current["stage"] if current else None,
        "current_label": current["stage_label"] if current else None,
        "assessment": assessment,
    }


def _classify_cycle_stage(ratio: float, avg_chg: float, limit_up: int, limit_down: int, total: int) -> dict:
    """根据情绪指标判断周期阶段"""
    if ratio < 0.35 or (avg_chg < -0.8 and ratio < 0.4):
        return {"stage": "ice", "label": "冰点期 ❄️"}
    if ratio < 0.45 or (avg_chg < -0.3 and ratio < 0.48):
        return {"stage": "ice_recovery", "label": "冰点反弹 🔄"}
    if ratio > 0.7 and limit_up > 120:
        return {"stage": "climax", "label": "高潮期 🔥"}
    if ratio > 0.65 and limit_up > 100:
        return {"stage": "fermentation", "label": "发酵期 🟢"}
    if ratio > 0.55 and limit_up > 80:
        return {"stage": "launch", "label": "启动期 💡"}
    if ratio < 0.48 and avg_chg < -0.2:
        return {"stage": "recession", "label": "退潮期 🔴"}
    return {"stage": "transition", "label": "过渡期 ⚖️"}


def _assess_cycle(records: list) -> dict:
    """综合评估周期趋势（records已倒序：最新在前）"""
    if len(records) < 3:
        return {"trend": "数据不足", "outlook": "neutral"}

    recent = records[:3]
    ratios = [r["ratio"] for r in recent]
    avgs = [r["avg_change_pct"] for r in recent]
    limits = [r["limit_up"] for r in recent]

    # 趋势方向：ratios[0]最新，ratios[-1]最旧
    ratio_trend = "rising" if ratios[0] > ratios[-1] else "falling" if ratios[0] < ratios[-1] else "flat"
    avg_trend = "rising" if avgs[0] > avgs[-1] else "falling" if avgs[0] < avgs[-1] else "flat"
    limit_trend = "rising" if limits[0] > limits[-1] else "falling" if limits[0] < limits[-1] else "flat"

    # 当前阶段
    current_stage = records[0]["stage"]

    # 综合判断
    if current_stage in ("climax", "fermentation"):
        outlook = "cautious_bullish" if ratio_trend == "rising" else "watch_for_reversal"
    elif current_stage == "ice":
        outlook = "wait_for_signal" if ratio_trend == "flat" else "recovery_emerging"
    elif current_stage == "launch":
        outlook = "bullish"
    elif current_stage in ("recession", "ice_recovery"):
        outlook = "defensive"
    else:
        outlook = "neutral"

    return {
        "ratio_trend": ratio_trend,
        "avg_trend": avg_trend,
        "limit_trend": limit_trend,
        "outlook": outlook,
    }


@router.get("/sectors")
def sector_list(
    date: str = Query(None, description="日期 YYYY-MM-DD，不传则取最近"),
    session: str = Query(None, description="noon=午市, close=终盘"),
):
    """全部行业板块涨跌排名"""
    df = _load_csv(date, session)
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
        "session": str(next(iter(df["_session"]), "close")),
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


@router.get("/index-history")
def index_history(days: int = Query(60, le=730)):
    """获取沪深300和中证500的历史收盘价（用于双轴对比图）"""
    import akshare as ak

    def _fetch(symbol, name):
        try:
            df = ak.stock_zh_index_daily(symbol=f"sh{symbol}")
            df = df.rename(columns={"date": "date", "close": "close"})
            df = df.tail(days)
            return [
                {"date": str(r["date"])[:10], "close": round(float(r["close"]), 2)}
                for _, r in df.iterrows()
            ]
        except Exception as e:
            return []

    hs300 = _fetch("000300", "沪深300")
    zz500 = _fetch("000905", "中证500")

    # 对齐日期计算比值
    hs_map = {d["date"]: d["close"] for d in hs300}
    zz_map = {d["date"]: d["close"] for d in zz500}
    all_dates = sorted(set(hs_map.keys()) & set(zz_map.keys()))
    ratio = []
    for dt in all_dates:
        ratio.append({
            "date": dt,
            "ratio": round(hs_map[dt] / zz_map[dt], 4),
        })

    return {"hs300": hs300, "zz500": zz500, "ratio": ratio}


# ===== 手动刷新行情数据 =====

@router.post("/refresh")
def refresh_market_data(date_param: str = Query(None, description="日期 YYYY-MM-DD，默认今天"), suffix: str = Query("", description="文件名后缀")):
    """手动触发拉取当日行情数据"""
    import subprocess, sys
    from datetime import date
    if not date_param:
        date_param = date.today().isoformat()
    cmd = [sys.executable, str(Path.home() / "Jarvis" / "fetch_a_stock_data.py"), "--date", date_param]
    if suffix:
        cmd.extend(["--suffix", suffix])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {
            "status": "ok" if r.returncode == 0 else "error",
            "date": date_param,
            "stdout": r.stdout.strip().split("\n")[-5:],
            "stderr": r.stderr.strip().split("\n")[-5:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "date": date_param, "message": "数据拉取超时（>5分钟）"}
    except Exception as e:
        return {"status": "error", "date": date_param, "message": str(e)}
