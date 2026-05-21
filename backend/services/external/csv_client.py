"""A股CSV行情文件访问统一封装。
数据源：~/Jarvis/A股行情信息/沪深京A股YYYY-MM-DD.csv
编码：UTF-16，分隔符：Tab
"""
import pandas as pd
import re
from datetime import date, timedelta
from pathlib import Path
from backend.config import MARKET_DATA_DIR, POSITION_FILE


# ── 仓位文件读取（非A股价格） ─────────────────────────────

def get_price_from_position_file(code: str) -> float | None:
    """从仓位CSV读取非A股价格"""
    try:
        import csv
        with open(POSITION_FILE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("代码", "").strip() == code:
                    raw = (r.get("当前价") or "0").strip()
                    return float(raw) if raw else None
    except Exception:
        pass
    return None


def get_prices_from_position_file(codes: list[str]) -> dict[str, float]:
    """从仓位CSV批量读取非A股价格"""
    result = {}
    try:
        import csv
        with open(POSITION_FILE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rc = r.get("代码", "").strip()
                if rc in codes:
                    raw = (r.get("当前价") or "0").strip()
                    try:
                        result[rc] = float(raw) if raw else None
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass
    return result


def find_latest_csv(max_lookback: int = 30) -> str | None:
    """找最新的可用CSV（有数据行 > 0），往回搜max_lookback天"""
    today = date.today()
    for i in range(max_lookback):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            # 检查文件是否真有数据行（跳过仅有表头的空文件，如未收盘时创建的）
            try:
                df = _read_csv(str(path))
                if df is not None and len(df) > 0:
                    return str(path)
            except Exception:
                return str(path)  # 读不到就返回有内容的兜底
    return None


def _read_csv(path: str) -> pd.DataFrame:
    """读取CSV，统一处理编码和代码列清洗"""
    df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
    if "代码" in df.columns:
        df["代码"] = df["代码"].astype(str).str.strip("'\"")
    return df


def _parse_csv_date(csv_path: str) -> str:
    """从CSV文件名解析日期"""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', csv_path)
    return m.group(1) if m else str(date.today())


# ── 通用 CSV 读取 ────────────────────────────────────────

def read_market_csv(path: str) -> pd.DataFrame | None:
    """读取行情CSV，统一处理编码和代码列"""
    try:
        df = _read_csv(path) if path else None
        return df
    except Exception:
        return None


def find_latest_csv_all(prefixes: list[str] | None = None, max_lookback: int = 30) -> str | None:
    """从多个前缀中找最新的CSV"""
    if prefixes is None:
        prefixes = ["沪深京A股", "沪深重要指数"]
    today = date.today()
    for i in range(max_lookback):
        d = (today - timedelta(days=i)).isoformat()
        for prefix in prefixes:
            path = MARKET_DATA_DIR / f"{prefix}{d}.csv"
            if path.exists():
                return str(path)
    return None


# ── 价格获取（从CSV） ─────────────────────────────────────

def get_price_from_csv(code: str) -> float | None:
    """从最新行情CSV获取个股当前价"""
    csv_path = find_latest_csv(5)
    if csv_path is None:
        return None
    df = read_market_csv(csv_path)
    if df is None:
        return None
    match = df[df["代码"] == code]
    if match.empty:
        return None
    val = str(match.iloc[0].get("最新", "0"))
    val = val.replace("--", "0").strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def get_prices_from_csv(codes: list[str]) -> dict[str, float]:
    """从CSV批量获取价格"""
    result = {}
    csv_path = find_latest_csv(5)
    if csv_path is None:
        return result
    df = read_market_csv(csv_path)
    if df is None:
        return result
    for code in codes:
        match = df[df["代码"] == code]
        if not match.empty:
            val = str(match.iloc[0].get("最新", "0"))
            val = val.replace("--", "0").strip()
            try:
                result[code] = float(val)
            except (ValueError, TypeError):
                pass
    return result


# ── 市场概览（纯CSV计算） ─────────────────────────────────

def get_market_overview() -> dict:
    """从行情CSV生成全市场概览"""
    csv_path = find_latest_csv(30)
    if csv_path is None:
        return {"status": "error", "msg": "未找到行情数据"}

    csv_date = _parse_csv_date(csv_path)
    df = read_market_csv(csv_path)
    if df is None or df.empty:
        return {"status": "error", "msg": "CSV读取失败"}

    total = len(df)
    up = int((df["涨幅"] > 0).sum()) if "涨幅" in df.columns else 0
    down = int((df["涨幅"] < 0).sum()) if "涨幅" in df.columns else 0
    flat = total - up - down
    limit_up = int((df["涨幅"] >= 9.8).sum()) if "涨幅" in df.columns else 0
    limit_down = int((df["涨幅"] <= -9.8).sum()) if "涨幅" in df.columns else 0
    avg_chg = round(float(df["涨幅"].mean()), 2) if "涨幅" in df.columns else 0
    turnover = round(float(df["换手率"].mean()), 2) if "换手率" in df.columns else 0
    total_vol = round(float(df["成交额"].sum()), 2) if "成交额" in df.columns else 0
    avg_vol = round(total_vol / total, 2) if total > 0 else 0

    return {
        "date": csv_date,
        "total": total, "up": up, "down": down, "flat": flat,
        "limit_up": limit_up, "limit_down": limit_down,
        "avg_change": avg_chg, "turnover": turnover,
        "total_volume": total_vol, "avg_volume": avg_vol,
    }


# ── 行业数据 ──────────────────────────────────────────────

def get_industry_data(sector: str) -> dict | None:
    """获取行业板块数据：排名、平均涨幅、龙头股"""
    if not sector or sector == "--":
        return None

    csv_path = find_latest_csv()
    if csv_path is None:
        return None

    df = _read_csv(csv_path)
    csv_date = _parse_csv_date(csv_path)

    # 该行业全部股票
    sector_df = df[df["所属行业"] == sector].copy()
    if sector_df.empty:
        return None

    # 行业排名
    all_sectors = df.groupby("所属行业")["涨幅"].mean().sort_values(ascending=False)
    total = len(all_sectors)
    rank = all_sectors.index.get_loc(sector) + 1 if sector in all_sectors.index else None

    def _row_to_stock(r):
        return {
            "code": str(r["代码"]).strip("'\""),
            "name": r["名称"],
            "price": float(r["最新"]) if pd.notna(r["最新"]) else 0,
            "change_pct": float(r["涨幅"]) if pd.notna(r["涨幅"]) else 0,
            "market_cap": float(r["总市值"]) if pd.notna(r["总市值"]) else 0,
        }

    top_by_gain = [_row_to_stock(r) for _, r in sector_df.nlargest(5, "涨幅").iterrows()]
    top_by_mcap = [_row_to_stock(r) for _, r in sector_df.nlargest(5, "总市值").iterrows()]

    # 最差5只（退潮股）
    bottom_by_gain = [_row_to_stock(r) for _, r in sector_df.nsmallest(5, "涨幅").iterrows()]

    valid = sector_df[sector_df["涨幅"].notna()]
    avg_chg = float(valid["涨幅"].mean()) if not valid.empty else 0
    up_count = int((valid["涨幅"] > 0).sum())
    down_count = int((valid["涨幅"] < 0).sum())
    total_count = int(len(valid))

    # 分化程度：龙头均值 vs 最差均值
    top_5_avg = float(valid.nlargest(5, "涨幅")["涨幅"].mean()) if len(valid) >= 5 else avg_chg
    bottom_5_avg = float(valid.nsmallest(5, "涨幅")["涨幅"].mean()) if len(valid) >= 5 else avg_chg
    divergence = round(top_5_avg - bottom_5_avg, 2)

    return {
        "sector": sector,
        "date": csv_date,
        "rank": rank,
        "total_sectors": total,
        "avg_change": round(avg_chg, 2),
        "up_ratio": round(up_count / total_count * 100, 1) if total_count > 0 else 0,
        "down_ratio": round(down_count / total_count * 100, 1) if total_count > 0 else 0,
        "stock_count": total_count,
        "top_stocks": top_by_gain,
        "top_by_market_cap": top_by_mcap,
        "bottom_stocks": bottom_by_gain,
        "divergence": divergence,
        "top_avg_change": round(top_5_avg, 2),
        "bottom_avg_change": round(bottom_5_avg, 2),
    }


# ── 从代码查行业 ──────────────────────────────────────────

def get_industry_stocks_detail(industry: str, lookback_days: int = 10, top_n: int = 50) -> list[dict]:
    """获取行业全部股票详情（代码/名称/价格/涨幅/市值），按市值降序"""
    today = date.today()
    for i in range(lookback_days):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = _read_csv(str(path))
            match = df[df["所属行业"] == industry].copy()
            if not match.empty:
                match["总市值"] = pd.to_numeric(
                    match["总市值"].astype(str).str.replace(",", "", regex=False),
                    errors="coerce"
                )
                match["涨幅"] = pd.to_numeric(match["涨幅"], errors="coerce")
                match["最新"] = pd.to_numeric(match["最新"], errors="coerce")
                sorted_df = match.sort_values("总市值", ascending=False).head(top_n)
                stocks = []
                for _, r in sorted_df.iterrows():
                    stocks.append({
                        "code": str(r["代码"]).strip("'\""),
                        "name": r.get("名称", ""),
                        "price": round(float(r["最新"]), 2) if pd.notna(r.get("最新")) else None,
                        "change_pct": round(float(r["涨幅"]), 2) if pd.notna(r.get("涨幅")) else None,
                        "market_cap": round(float(r["总市值"]), 2) if pd.notna(r.get("总市值")) else None,
                    })
                return stocks
            break
    return []


def get_board_stocks_detail(board_name: str, lookback_days: int = 10, top_n: int = 20) -> list[dict]:
    """获取概念板块成分股详情（从akshare），含名称/价格/涨幅"""
    from backend.services.financial_service import get_concept_board_constituents
    stocks = get_concept_board_constituents(board_name)
    # get_concept_board_constituents returns top 5, but we want more
    # Try to get more from akshare directly if needed
    # The existing function returns list[dict] with code/name/price/change_pct
    return stocks[:top_n]


def get_industry_from_code(code: str, lookback_days: int = 10) -> str:
    """从最近N天的CSV中查找股票所属行业"""
    today = date.today()
    for i in range(lookback_days):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = _read_csv(str(path))
            match = df[df["代码"] == code]
            if not match.empty:
                return str(match.iloc[0].get("所属行业", ""))
            break
    return ""


# ── 同行业股票列表 ────────────────────────────────────────

def get_all_stocks_in_industry(industry: str, lookback_days: int = 10, top_n: int = 10) -> list[str]:
    """获取该行业市值最大的N只股票代码"""
    today = date.today()
    for i in range(lookback_days):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = _read_csv(str(path))
            match = df[df["所属行业"] == industry].copy()
            if not match.empty:
                match["总市值"] = pd.to_numeric(
                    match["总市值"].astype(str).str.replace(",", "", regex=False),
                    errors="coerce"
                )
                codes = match.sort_values("总市值", ascending=False)["代码"].head(top_n).tolist()
                return codes
            break
    return []


# ── 从CSV查股票详情（价格/涨幅/市值）─────────────────────

def get_stock_detail_from_csv(code: str) -> dict | None:
    """从最新CSV获取单只股票行情详情"""
    csv_path = find_latest_csv()
    if csv_path is None:
        return None
    df = _read_csv(csv_path)
    match = df[df["代码"] == code]
    if match.empty:
        return None
    r = match.iloc[0]
    return {
        "code": code,
        "name": r.get("名称", ""),
        "price": float(r["最新"]) if pd.notna(r.get("最新")) else 0,
        "change_pct": float(r["涨幅"]) if pd.notna(r.get("涨幅")) else 0,
        "market_cap": float(r["总市值"]) if pd.notna(r.get("总市值")) else 0,
        "industry": r.get("所属行业", ""),
    }
