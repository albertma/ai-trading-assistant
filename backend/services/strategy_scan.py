"""
策略驱动扫描引擎 — 使用策略管理页面配置的策略逐只扫描股票

核心流程:
  For each 策略 in strategies 表:
    按 scope 解析待扫描股票列表
    For each 股票:
      获取 K 线数据 → 计算指标 → 调用 entry 信号函数
      如果触发 → 写入 strategy_signals 表

用法:
  run_strategy_scan(session="close")   # 收盘扫描
  run_strategy_scan(session="noon")    # 午盘扫描
"""
from datetime import date
from typing import Optional
import json
import sqlite3
from pathlib import Path
import uuid
import time
import numpy as np

from backend.services.signal_detect.signal_registry import ENTRY_SIGNALS
from backend.services.strategy_evol.db import DB_PATH, get_db

# ── 常量 ──
KLINE_DB = str(Path.home() / "Jarvis" / "ai_trading" / "kline_data.db")
HS300_CODES_CACHE = None
CSI500_CODES_CACHE = None
CACHE_TTL_DAYS = 90


def _get_cached_index_constituents(index_name: str) -> list[str] | None:
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT codes_json, julianday('now','localtime') - julianday(fetched_at) AS age_days"
            " FROM index_constituents_cache WHERE index_name=?",
            (index_name,),
        ).fetchone()
        conn.close()
        if not row:
            return None

        age_days = float(row["age_days"] or 9999)
        if age_days <= CACHE_TTL_DAYS:
            return json.loads(row["codes_json"])
        return None
    except Exception:
        return None


def _get_cached_index_constituents_raw(index_name: str) -> list[str] | None:
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT codes_json FROM index_constituents_cache WHERE index_name=?",
            (index_name,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(row["codes_json"])
    except Exception:
        return None


def _save_index_constituents_cache(index_name: str, codes: list[str]) -> None:
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO index_constituents_cache(index_name, codes_json, fetched_at)"
            " VALUES (?, ?, datetime('now','localtime'))",
            (index_name, json.dumps(codes, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def _get_kline_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(KLINE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _get_name_from_stock_info(code: str) -> str:
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT name FROM stock_info WHERE code = ?", (code,)
        ).fetchone()
        conn.close()
        return row["name"] if row else code
    except Exception:
        return code


def _get_sector_stocks(sector_name: str, conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """获取某个板块对应的股票列表（stock_info 表中 industry 字段为准）"""
    rows = conn.execute(
        "SELECT code, name FROM stock_info WHERE industry = ? ORDER BY circulating_market_cap DESC",
        (sector_name,),
    ).fetchall()
    return [(r["code"], r["name"]) for r in rows]


def _get_index_constituents(index_name: str) -> list[str]:
    """获取指数成分股，优先从SQLite缓存读取，过期或不存在时再从akshare获取。"""
    INDEX_CODE_MAP = {
        "沪深300": "000300",
        "中证500": "000905",
        "科创50": "000688",
    }
    code = INDEX_CODE_MAP.get(index_name)
    if not code:
        return []

    cached = _get_cached_index_constituents(index_name)
    if cached is not None:
        return cached

    try:
        import akshare as ak
        df = ak.index_stock_cons_weight_csindex(symbol=code)
        if "成分券代码" in df.columns:
            codes = df["成分券代码"].astype(str).str.strip().str.zfill(6).tolist()
            if codes:
                _save_index_constituents_cache(index_name, codes)
            return codes
        return []
    except Exception as e:
        print(f"akshare error fetching {index_name}: {e}")
        stale = _get_cached_index_constituents_raw(index_name)
        return stale if stale is not None else []


# ═══════════════════════════════════════════════════════════
# 指标计算（精简版，复用 backtest 的方法）
# ═══════════════════════════════════════════════════════════

def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(arr), np.nan)
    for i in range(period - 1, len(arr)):
        result[i] = np.mean(arr[i - period + 1 : i + 1])
    return result


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(arr), np.nan)
    if len(arr) < 1:
        return result
    result[0] = arr[0]
    alpha = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


def _macd(arr: np.ndarray, fast=12, slow=26, signal=9):
    ema_fast = _ema(arr, fast)
    ema_slow = _ema(arr, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    bar = 2 * (dif - dea)
    return dif, dea, bar


def _rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    result = np.full(len(arr), np.nan)
    if len(arr) < period + 1:
        return result
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - 100 / (1 + rs)
    for i in range(period + 1, len(arr)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - 100 / (1 + rs)
    return result


# ═══════════════════════════════════════════════════════════
# 核心：检查单只股票是否触发某个策略的信号
# ═══════════════════════════════════════════════════════════

def check_strategy_signal(
    stock_code: str,
    stock_name: str,
    entry_name: str,
    entry_params: Optional[dict] = None,
    stop_loss: float = 5.0,
) -> Optional[dict]:
    """
    检查一只股票是否触发了某个策略的买入信号。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        entry_name: 策略使用的买入信号名（如 'bottom_reversal_elec'）
        entry_params: 可选的参数覆盖
        stop_loss: 默认止损百分比

    Returns:
        { "confidence": 分, "entry_price": 参考价, "signal_detail": 描述 }
        或 None（未触发）
    """
    entry_info = ENTRY_SIGNALS.get(entry_name)
    if not entry_info:
        return None

    entry_fn = entry_info["func"]
    needs_patterns = entry_info.get("needs_patterns", False)
    params = entry_params or {}

    # 获取K线数据
    try:
        conn = _get_kline_conn()
        rows = conn.execute(
            "SELECT date, open, close, high, low, volume FROM kline_daily WHERE code=? ORDER BY date ASC",
            (stock_code,),
        ).fetchall()
        conn.close()
    except Exception:
        return None

    if not rows or len(rows) < 60:
        return None

    n = len(rows)
    dates = [str(r["date"])[:10] for r in rows]
    closes = np.array([float(r["close"]) for r in rows], dtype=float)
    highs = np.array([float(r["high"]) for r in rows], dtype=float)
    lows = np.array([float(r["low"]) for r in rows], dtype=float)
    opens = np.array([float(r["open"]) for r in rows], dtype=float)
    volumes = np.array([float(r["volume"] or 0) for r in rows], dtype=float)

    # 预计算指标
    ma_fast = _sma(closes, params.get("fast", 5))
    ma_slow = _sma(closes, params.get("slow", 10))
    ma_20 = _sma(closes, 20)
    ma_60 = _sma(closes, 60)
    ma_200 = _sma(closes, 200)
    rsi_vals = _rsi(closes, params.get("period", 14))

    # MACD
    macd_fast = params.get("macd_fast", 12)
    macd_slow = params.get("macd_slow", 26)
    macd_signal = params.get("macd_signal", 9)
    macd_line, macd_signal_line, macd_hist = _macd(closes, macd_fast, macd_slow, macd_signal)

    # K线形态（只在 needs_patterns=True 时计算）
    all_patterns = []
    if needs_patterns:
        from backend.patterns import detect_patterns as _dp
        for idx in range(n):
            if idx < 4:
                all_patterns.append([])
            else:
                # 构造一个小的 DataFrame 给 detect_patterns
                import pandas as _pd
                sub = _pd.DataFrame({
                    "close": closes[idx - 4 : idx + 1],
                    "open": opens[idx - 4 : idx + 1],
                    "high": highs[idx - 4 : idx + 1],
                    "low": lows[idx - 4 : idx + 1],
                    "volume": volumes[idx - 4 : idx + 1],
                })
                all_patterns.append(_dp(sub))
    else:
        all_patterns = [[] for _ in range(n)]

    # 构造 ctx（和 backtest 一致）
    ctx = {
        "closes": closes, "highs": highs, "lows": lows, "opens": opens, "volumes": volumes,
        "ma_fast": ma_fast, "ma_slow": ma_slow, "ma_20": ma_20, "ma_60": ma_60, "ma_200": ma_200,
        "ma_120": _sma(closes, 120),
        "rsi_vals": rsi_vals,
        "macd_line": macd_line, "macd_signal_line": macd_signal_line, "macd_hist": macd_hist,
        "all_patterns": all_patterns,
        "n": n,
        "fast": params.get("fast", 5), "slow": params.get("slow", 10),
        "rsi_period": params.get("period", 14),
        "oversold": params.get("oversold", 30),
        "overbought": params.get("overbought", 70),
        "bb_period": params.get("bb_period", 20),
        "bb_std": params.get("bb_std", 2.0),
        "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
        **params,
    }

    # 检查末尾几天（当前信号就在最近几天）
    check_window = params.get("check_window", 3)  # 默认看最近3天
    i = n - 1  # 从最新 bar 开始往前查
    try:
        result = entry_fn(i, **ctx)
        if result and isinstance(result, dict):
            sig_detail = result.get("signal", f"策略{entry_name}")
            entry_idx = result.get("entry_idx", i + 1)

            # 估算置信度：从 entry_fn 返回里提取，或用固定值
            confidence = params.get("_confidence", 65)
            if "confidence" in result:
                confidence = result["confidence"]

            # 最新收盘价作为参考入场价
            latest_close = round(float(closes[-1]), 2)

            # 止损价 = 入场价 * (1 - 止损%)
            sl_pct = stop_loss / 100.0
            stop_loss_price = round(latest_close * (1 - sl_pct), 2)

            # 目标价（简单用 2:1 盈亏比）
            risk = latest_close - stop_loss_price if latest_close > stop_loss_price else latest_close * 0.05
            target_price = round(latest_close + risk * 2, 2)

            return {
                "confidence": confidence,
                "entry_price": latest_close,
                "stop_loss": stop_loss_price,
                "target_price": target_price,
                "signal_detail": sig_detail,
            }
    except Exception as e:
        pass

    return None


# ═══════════════════════════════════════════════════════════
# 批量扫描：遍历所有策略 × 所有适用股票
# ═══════════════════════════════════════════════════════════

def run_strategy_scan(
    session: str = "close",
    batch_id: str = "",
    max_stocks_per_strategy: int = 200,
) -> dict:
    """
    执行全量策略驱动扫描。

    流程：
      1. 从 strategies 表加载所有策略
      2. 构建扫描池（沪深300 + 中证500 + 科创50+ 观察池）
      3. 对每个策略，匹配其 scope 到扫描池中的股票
      4. 对每只(策略, 股票)组合调用 check_strategy_signal
      5. 结果写入 strategy_signals 表

    Returns:
        {
            "batch_id": "...",
            "total_strategies": 17,
            "total_stocks_scanned": 800,
            "total_signals": 5,
            "signals_by_strategy": {...}
        }
    """
    score_date = str(date.today())
    batch_id = batch_id or uuid.uuid4().hex[:12]
    t0 = time.time()

    conn = get_db()

    # 1. 加载所有策略
    strategies = conn.execute(
        "SELECT id, name, buy_signal, sell_signal, stop_loss, scope_type, scope_value, config_json FROM strategies ORDER BY id"
    ).fetchall()
    strategies = [dict(r) for r in strategies]
    conn.close()

    if not strategies:
        return {
            "batch_id": batch_id,
            "total_strategies": 0,
            "total_stocks_scanned": 0,
            "total_signals": 0,
            "signals_by_strategy": {},
            "duration": 0,
        }

    # 2. 构建全量扫描池
    pool = _build_scan_pool(session)

    total_stocks_scanned = 0
    total_signals = 0
    signals_by_strategy = {}

    for s in strategies:
        strat_id = s["id"]
        strat_name = s["name"]
        buy_signal = s.get("buy_signal", "")
        stop_loss = s.get("stop_loss", 5.0)
        scope_type = s.get("scope_type", "all")
        scope_value = s.get("scope_value", "")
        config_json_raw = s.get("config_json", "{}")

        # 解析 entry 参数（如果有）
        entry_params = {}
        if config_json_raw:
            try:
                import json
                cfg = json.loads(config_json_raw) if isinstance(config_json_raw, str) else config_json_raw
                if isinstance(cfg, dict):
                    entry_params = cfg
            except Exception:
                pass

        # 如果 buy_signal 不在 ENTRY_SIGNALS 中，跳过
        if buy_signal not in ENTRY_SIGNALS:
            continue

        # 根据 scope 确定该策略需要检查哪些股票
        scope_stocks = _resolve_scope(scope_type, scope_value, pool)
        if not scope_stocks:
            continue

        # 限制每策略扫描数量
        scope_stocks = scope_stocks[:max_stocks_per_strategy]

        strat_signals = []
        for code, name in scope_stocks:
            result = check_strategy_signal(
                stock_code=code,
                stock_name=name,
                entry_name=buy_signal,
                entry_params=entry_params,
                stop_loss=stop_loss,
            )
            if result:
                strat_signals.append({
                    "stock_code": code,
                    "stock_name": name,
                    **result,
                })
                total_signals += 1
            total_stocks_scanned += 1

        # 将信号写入数据库
        _save_signals(
            conn=get_db(),
            strategy_id=strat_id,
            strategy_name=strat_name,
            signals=strat_signals,
            session=session,
            batch_id=batch_id,
        )

        signals_by_strategy[strat_name] = {
            "scanned": len(scope_stocks),
            "triggered": len(strat_signals),
            "signals": strat_signals[:10],  # 返回前10个
        }

    duration = round(time.time() - t0, 2)
    return {
        "batch_id": batch_id,
        "date": score_date,
        "session": session,
        "total_strategies": len(strategies),
        "total_stocks_scanned": total_stocks_scanned,
        "total_signals": total_signals,
        "signals_by_strategy": signals_by_strategy,
        "duration": duration,
    }


# ═══════════════════════════════════════════════════════════
# 内部：构建扫描池 + 解析 scope
# ═══════════════════════════════════════════════════════════

def _build_scan_pool(session: str = "close") -> set[tuple[str, str]]:
    """
    构建全量扫描池：沪深300(300只) + 中证500(500只) + 科创50(50只) + 观察池。
    通过 akshare index_stock_cons_weight_csindex 获取最新成分股。
    """
    from backend.services.strategy_evol.scan_pool import get_scan_pool as _old_pool

    pool = set()
    seen_codes = set()

    def _add(code, name):
        if code not in seen_codes:
            seen_codes.add(code)
            pool.add((code, name or code))

    # 1. 用新方法获取沪深300 + 中证500 + 科创50 成分股
    for idx_name in ("沪深300", "中证500", "科创50"):
        codes = _get_index_constituents(idx_name)
        for code in codes:
            name = _get_name_from_stock_info(code)
            _add(code, name)

    # 2. 补充观察池和持仓池（旧方法）
    old_stocks = _old_pool(max_per_source=100, sort_by="code")
    for code, name in old_stocks:
        _add(code, name)

    return pool


def _has_kline_data(code: str, min_bars: int = 60) -> bool:
    """检查某只股票是否有足够的K线数据"""
    try:
        conn = sqlite3.connect(KLINE_DB)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM kline_daily WHERE code=?", (code,)
        ).fetchone()[0]
        conn.close()
        return cnt >= min_bars
    except Exception:
        return False


def _resolve_scope(
    scope_type: str,
    scope_value: str,
    pool: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    根据 scope 筛选出适用的股票。

    规则：
      - all:    从扫描池中取（仅限指数成分股）
      - sector: 从 stock_info 取全部该板块股票，要求有K线数据（不限于池）
      - stock:  单只个股，要求有K线数据（不限于池）
      - group:  群组内个股，要求有K线数据（不限于池）
    """
    if scope_type == "all":
        return sorted(pool, key=lambda x: x[0])

    if scope_type == "sector" and scope_value:
        try:
            conn = get_db()
            sector_stocks = _get_sector_stocks(scope_value, conn)
            conn.close()
        except Exception:
            return []
        # 不限于池，只要有K线数据即可
        result = []
        for code, name in sector_stocks:
            if _has_kline_data(code):
                result.append((code, name or code))
        return result

    if scope_type == "stock" and scope_value:
        name = _get_name_from_stock_info(scope_value)
        if _has_kline_data(scope_value):
            return [(scope_value, name or scope_value)]
        # 没有K线数据也返回，让 check_strategy_signal 自己决定
        return [(scope_value, name or scope_value)]

    if scope_type == "group" and scope_value:
        try:
            conn = get_db()
            rows = conn.execute(
                "SELECT code, name FROM watchlist WHERE group_name=? OR code IN (SELECT unnest(code_list) FROM strategy_groups WHERE name=?)",
                (scope_value, scope_value),
            ).fetchall()
            conn.close()
        except Exception:
            return []
        # 不限于池，只要有K线数据即可
        result = []
        for r in rows:
            code, name = r["code"], r.get("name", "") or r["code"]
            if _has_kline_data(code):
                result.append((code, name))
        return result

    return []


# ═══════════════════════════════════════════════════════════
# 内部：批量写入策略信号
# ═══════════════════════════════════════════════════════════

def _save_signals(
    conn: sqlite3.Connection,
    strategy_id: int,
    strategy_name: str,
    signals: list[dict],
    session: str,
    batch_id: str,
):
    """批量写入 strategy_signals 表"""
    if not signals:
        conn.close()
        return
    for sig in signals:
        try:
            conn.execute(
                """INSERT INTO strategy_signals
                   (strategy_id, strategy_name, stock_code, stock_name,
                    session, signal_type, confidence, entry_price,
                    stop_loss, target_price, signal_detail, batch_id)
                   VALUES (?,?,?,?, ?,?,?,?, ?,?,?,?)""",
                (
                    strategy_id,
                    strategy_name,
                    sig["stock_code"],
                    sig.get("stock_name", ""),
                    session,
                    "entry",
                    sig.get("confidence", 0),
                    sig.get("entry_price", 0),
                    sig.get("stop_loss", 0),
                    sig.get("target_price", 0),
                    sig.get("signal_detail", ""),
                    batch_id,
                ),
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
