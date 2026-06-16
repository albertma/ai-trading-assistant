"""扫描池服务 — 聚合5个来源的股票列表，去重返回。

来源：
  1. 观察池  — watchlist 表
  2. 持仓池  — 仓位 CSV 文件
  3. 沪深300 — akshare 获取成分股 & 本地 kline_daily 已有数据
  4. 中证500 — akshare 获取成分股 & 本地 kline_daily 已有数据
  5. 板块指数 — stock_info 按行业分组

每个来源最多取 100 只，去重后排序返回 (code, name) 列表。
优先使用本地数据，避免频繁调用 akshare。
"""

import csv
import sqlite3
from typing import Optional
from functools import lru_cache

from backend.config import POSITION_FILE
from backend.services.strategy_evol.db import DB_PATH


# ═══════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════

def _get_db() -> sqlite3.Connection:
    """获取只读数据库连接（短连接，用完即关）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _get_name_from_stock_info(code: str) -> str:
    """从 stock_info 表查找股票名称"""
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT name FROM stock_info WHERE code = ?", (code,)
        ).fetchone()
        conn.close()
        return row["name"] if row else ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════
# 来源 1: 观察池
# ═══════════════════════════════════════════════════════════

def _get_watchlist_stocks(max_count: int = 100) -> list[tuple[str, str]]:
    """从 watchlist 表获取观察池股票"""
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT code, name FROM watchlist ORDER BY added_date DESC LIMIT ?",
            (max_count,),
        ).fetchall()
        conn.close()
        return [(r["code"], r["name"]) for r in rows]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 来源 2: 持仓池（从持仓 CSV 读取）
# ═══════════════════════════════════════════════════════════

def _get_position_stocks(max_count: int = 100) -> list[tuple[str, str]]:
    """从仓位 CSV 文件获取持仓股票"""
    try:
        with open(POSITION_FILE, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            results = []
            for row in reader:
                code = (row.get("代码") or "").strip()
                name = (row.get("名称") or "").strip()
                if code:
                    results.append((code, name))
                if len(results) >= max_count:
                    break
        return results
    except FileNotFoundError:
        # 文件不存在时静默跳过
        return []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 来源 3 & 4: 沪深300 / 中证500 — 通过 akshare 获取成分股
# 缓存到本地以避免频繁调用
# ═══════════════════════════════════════════════════════════

@lru_cache(maxsize=2)
def _fetch_index_constituents(index_name: str) -> list[str]:
    """调用 akshare 获取指数成分股代码列表。

    Args:
        index_name: "沪深300" 或 "中证500"

    Returns:
        成分股代码列表（如 ['000001', '000002', ...]）
    """
    try:
        import akshare as ak

        if index_name == "沪深300":
            df = ak.index_stock_cons_weight_csindex(symbol="000300")
        elif index_name == "中证500":
            df = ak.index_stock_cons_weight_csindex(symbol="000905")
        elif index_name == "科创50":
            df = ak.index_stock_cons_weight_csindex(symbol="000688")
        else:
            return []

        if "成分券代码" in df.columns:
            codes = df["成分券代码"].astype(str).str.strip().str.zfill(6).tolist()
        else:
            return []

        # 统一格式：去掉可能的前缀（如 'sh'/'sz'），确保6位数字
        cleaned = []
        for c in codes:
            c = c.lower().replace("sh", "").replace("sz", "").strip()
            if c.isdigit():
                cleaned.append(c)
            elif len(c) >= 6 and c[:6].isdigit():
                cleaned.append(c[:6])
        return cleaned
    except ImportError:
        print("akshelf not installed, skipping index constituents")
        return []
    except Exception as e:
        print(f"akshare error fetching {index_name}: {e}")
        return []


def _get_index_constituents_with_names(
    index_name: str, max_count: int = 100
) -> list[tuple[str, str]]:
    """获取指数成分股并限制数量，只保留本地 kline_daily 已有数据的股票"""
    codes = _fetch_index_constituents(index_name)
    if not codes:
        return []

    # 仅保留本地 kline_daily 中有数据的股票
    try:
        from backend.services.database.stock_db import get_kline_db
        conn = get_kline_db()
        placeholders = ",".join("?" for _ in codes)
        rows = conn.execute(
            f"SELECT DISTINCT code FROM kline_daily WHERE code IN ({placeholders})",
            codes,
        ).fetchall()
        conn.close()
        local_codes = {r["code"] for r in rows}
    except Exception:
        local_codes = set(codes)  # 查不到时全量保留

    results = []
    for code in codes:
        if code not in local_codes:
            continue
        name = _get_name_from_stock_info(code)
        results.append((code, name or code))
        if len(results) >= max_count:
            break

    return results


# ═══════════════════════════════════════════════════════════
# 来源 5: 板块指数（按行业分组）
# ═══════════════════════════════════════════════════════════

def _get_sector_stocks(max_count: int = 100) -> list[tuple[str, str]]:
    """从 stock_info 表按行业分组，每行业取代表性股票"""
    try:
        conn = _get_db()

        # 先尝试 sector_indices 表获取活跃板块
        sectors = conn.execute(
            "SELECT DISTINCT sector FROM sector_indices ORDER BY sector"
        ).fetchall()
        sector_names = [r["sector"] for r in sectors if r["sector"]]

        if not sector_names:
            # 兜底：从 stock_info 表取行业
            sec_rows = conn.execute(
                "SELECT DISTINCT industry FROM stock_info WHERE industry != '' ORDER BY industry"
            ).fetchall()
            sector_names = [r["industry"] for r in sec_rows]

        # 每行业取流通市值最高的股票（每个行业最多3只，总量不超过max_count）
        results: list[tuple[str, str]] = []
        per_sector = max(1, max_count // max(len(sector_names), 1))

        for sector in sector_names:
            rows = conn.execute(
                """SELECT code, name FROM stock_info
                   WHERE (industry = ? OR sector = ?)
                     AND code != ''
                   ORDER BY circulating_market_cap DESC
                   LIMIT ?""",
                (sector, sector, per_sector),
            ).fetchall()
            for r in rows:
                results.append((r["code"], r["name"]))
                if len(results) >= max_count:
                    break
            if len(results) >= max_count:
                break

        conn.close()
        return results[:max_count]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def get_scan_pool(
    max_per_source: int = 100, sort_by: str = "code"
) -> list[tuple[str, str]]:
    """聚合5个来源的股票列表，去重后返回。

    Args:
        max_per_source: 每个来源最多取的股票数
        sort_by: 排序方式 — "code"（默认，按代码排序）或 "name"（按名称排序）

    Returns:
        [(code, name), ...] 去重排序列表
    """
    seen: set[str] = set()
    pool: list[tuple[str, str]] = []

    sources = [
        ("观察池", _get_watchlist_stocks(max_per_source)),
        ("持仓池", _get_position_stocks(max_per_source)),
        ("沪深300", _get_index_constituents_with_names("沪深300", max_per_source)),
        ("中证500", _get_index_constituents_with_names("中证500", max_per_source)),
        ("板块指数", _get_sector_stocks(max_per_source)),
    ]

    for label, items in sources:
        for code, name in items:
            if code not in seen:
                seen.add(code)
                pool.append((code, name))

    # 排序
    if sort_by == "name":
        pool.sort(key=lambda x: (x[1] or x[0]))
    else:
        pool.sort(key=lambda x: x[0])

    return pool


# ═══════════════════════════════════════════════════════════
# 便捷入口：返回纯代码列表
# ═══════════════════════════════════════════════════════════

def get_scan_pool_codes(max_per_source: int = 100) -> list[str]:
    """仅返回去重后的代码列表（不含名称）"""
    return [code for code, _ in get_scan_pool(max_per_source)]
