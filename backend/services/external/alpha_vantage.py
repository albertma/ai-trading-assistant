"""
美股数据 — Alpha Vantage API
=============================
获取美股实时价格、资产负债表、利润表、现金流量表。
缓存策略：价格4小时，财报30天，通过 SQLite financial_cache 持久化。
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from backend.services.db_client import get_financial_cache, save_financial_cache

log = logging.getLogger(__name__)

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

# 兜底：从 .zshrc 加载（terminal 子进程可能不继承 env）
if not ALPHA_VANTAGE_API_KEY:
    try:
        zshrc = Path.home() / ".zshrc"
        if zshrc.exists():
            for line in zshrc.read_text(encoding="utf-8").splitlines():
                if "ALPHA_VANTAGE_API_KEY" in line and "=" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1].strip().strip("'\"")
                        if val and not val.startswith("$"):
                            ALPHA_VANTAGE_API_KEY = val
                            os.environ["ALPHA_VANTAGE_API_KEY"] = val
                            break
    except Exception:
        pass

_BASE = "https://www.alphavantage.co/query"

# 缓存键前缀
_CACHE_KEY_PRICE = "AV_PRICE_{}"
_CACHE_KEY_FIN = "AV_FIN_{}"

# 缓存过期时间
_PRICE_TTL = 60 * 60 * 4      # 4 小时
_FIN_TTL = 60 * 60 * 24 * 30  # 30 天


# ── 内部工具 ───────────────────────────────────────────────


def _validate_key():
    if not ALPHA_VANTAGE_API_KEY:
        raise ValueError(
            "ALPHA_VANTAGE_API_KEY 环境变量未设置，"
            "请先 export 或添加到 backend/config.py"
        )


def _cache_get(key: str, ttl: int) -> dict | None:
    """从 SQLite 读取缓存，过期返回 None"""
    data = get_financial_cache(key)
    if not data:
        return None
    elapsed = time.time() - data.get("_ts", 0)
    if elapsed > ttl:
        return None
    return data.get("_payload")


def _cache_set(key: str, payload: dict):
    """写入 SQLite 缓存"""
    save_financial_cache(key, {"_ts": time.time(), "_payload": payload})


# ── API 调用 ───────────────────────────────────────────────


def _get_fin_report(symbol: str, report_type: str = "BALANCE_SHEET") -> dict:
    """获取单张财报，遇限流自动重试1次"""
    _validate_key()
    url = (
        f"{_BASE}?function={report_type}&symbol={symbol}"
        f"&apikey={ALPHA_VANTAGE_API_KEY}"
    )
    r = requests.get(url, timeout=30)
    data = r.json()
    # 限流重试（"Information" key 表示被限流了）
    if isinstance(data, dict) and "Information" in data:
        log.warning("Alpha Vantage 限流，等待2s重试 %s %s", symbol, report_type)
        time.sleep(2)
        r = requests.get(url, timeout=30)
        data = r.json()
    return data


def get_us_stock_price(symbol: str) -> dict:
    """获取美股当前价格（SQLite 缓存4小时）"""
    cache_key = _CACHE_KEY_PRICE.format(symbol.upper())
    cached = _cache_get(cache_key, _PRICE_TTL)
    if cached:
        return cached

    _validate_key()
    url = (
        f"{_BASE}?function=GLOBAL_QUOTE&symbol={symbol}"
        f"&apikey={ALPHA_VANTAGE_API_KEY}"
    )
    r = requests.get(url, timeout=30)
    data = r.json()
    log.debug("Alpha Vantage GLOBAL_QUOTE response: %s", data)

    try:
        result = {
            "symbol": symbol,
            "price": float(data["Global Quote"]["05. price"]),
            "market": "us",
        }
        _cache_set(cache_key, result)
        return result
    except (KeyError, TypeError, ValueError) as e:
        log.error("获取 %s 股价失败: %s", symbol, e)
        raise Exception(
            f"请求失败：请检查API密钥或股票代码 {symbol}"
        ) from e


def get_us_stock_financial_report(symbol: str) -> dict:
    """获取美股三张财务报表（并行请求，SQLite 永久缓存 + 每30天后台刷新）

    策略：
    - 缓存永久有效，始终优先返回
    - 如果缓存超过30天，后台悄悄刷新，不阻塞调用方
    - 首次获取时同步请求

    Returns:
        dict: {"balance_sheet": ..., "income_statement": ..., "cashflow": ...}
    """
    cache_key = _CACHE_KEY_FIN.format(symbol.upper())
    cached = get_financial_cache(cache_key)

    if cached:
        # 检查是否需要后台刷新
        elapsed = time.time() - cached.get("_ts", 0)
        payload = cached.get("_payload")
        if payload and elapsed > _FIN_TTL:
            _refresh_fin_report_in_bg(symbol, cache_key)
        if payload:
            return payload

    # 无缓存或缓存损坏 → 同步请求
    return _fetch_and_cache_fin_report(symbol, cache_key)


def _fetch_and_cache_fin_report(symbol: str, cache_key: str) -> dict:
    """同步请求三张财报并写入SQLite缓存"""
    _validate_key()
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            balance_fut = executor.submit(
                _get_fin_report, symbol, "BALANCE_SHEET"
            )
            time.sleep(1)
            income_fut = executor.submit(
                _get_fin_report, symbol, "INCOME_STATEMENT"
            )
            time.sleep(1)
            cash_fut = executor.submit(
                _get_fin_report, symbol, "CASH_FLOW"
            )

            balance_sheet = balance_fut.result()
            income_statement = income_fut.result()
            cash_flow = cash_fut.result()

        bs_reports = (balance_sheet or {}).get("annualReports") or []
        inc_reports = (income_statement or {}).get("annualReports") or []
        cf_reports = (cash_flow or {}).get("annualReports") or []

        if not bs_reports:
            raise Exception(f"获取 {symbol} 资产负债表失败")
        if not inc_reports:
            raise Exception(f"获取 {symbol} 利润表失败")
        if not cf_reports:
            raise Exception(f"获取 {symbol} 现金流量表失败")

    except Exception as e:
        log.error("获取 %s 财务报表失败: %s", symbol, e)
        raise

    result = {
        "balance_sheet": balance_sheet,
        "income_statement": income_statement,
        "cashflow": cash_flow,
    }
    _cache_set(cache_key, result)
    return result


def _refresh_fin_report_in_bg(symbol: str, cache_key: str):
    """后台刷新财报，失败静默"""
    import threading

    def _bg():
        try:
            log.info("后台刷新 %s 财报...", symbol)
            _fetch_and_cache_fin_report(symbol, cache_key)
            log.info("后台刷新 %s 财报完成", symbol)
        except Exception as e:
            log.warning("后台刷新 %s 财报失败（保留旧缓存）: %s", symbol, e)

    t = threading.Thread(target=_bg, daemon=True)
    t.start()


# ── 独立测试 ───────────────────────────────────────────────

if __name__ == "__main__":
    data = get_us_stock_price("AAPL")
    print(data)
