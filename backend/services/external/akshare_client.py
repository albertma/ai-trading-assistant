"""akshare 数据访问统一封装。
所有外部API调用集中在此，业务逻辑层不直接调akshare。
统一超时处理（3s）、异常兜底、Numpy类型清理。
"""
import pandas as pd
import numpy as np
import os
import json
import threading

# ── 通用akshare超时包装 ──────────────────────────────────
_AK_TIMEOUT = 8  # 所有akshare调用统一8s超时

def _ak_call(fn, *args, timeout=_AK_TIMEOUT, **kwargs):
    """在daemon线程中执行akshare函数，超时抛出TimeoutError"""
    result = []
    exc_info = []

    def worker():
        try:
            result.append(fn(*args, **kwargs))
        except Exception as e:
            exc_info.append(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"akshare {fn.__name__ if hasattr(fn, '__name__') else 'call'} timed out after {timeout}s")
    if exc_info:
        raise exc_info[0]
    return result[0]

def _to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame转为纯Python dict列表，清理numpy类型，统一单位到亿"""
    records = []
    for _, r in df.iterrows():
        rec = {}
        for col in df.columns:
            val = r[col]
            if isinstance(val, (np.integer,)):
                rec[col] = int(val)
            elif isinstance(val, (np.floating,)):
                rec[col] = round(float(val), 4) if not pd.isna(val) else None
            elif isinstance(val, str):
                v = val.strip()
                if v in ("--", "", "False"):
                    rec[col] = None
                else:
                    # 判断并处理单位
                    v_clean = v
                    if v.endswith("亿"):
                        v_clean = v[:-1].strip()
                    elif v.endswith("万"):
                        v_clean = v[:-1].strip()
                    elif v.endswith("%"):
                        v_clean = v[:-1].strip()
                    else:
                        v_clean = v

                    # 尝试转数字
                    try:
                        num = float(v_clean)
                        if v.endswith("万"):
                            num = round(num / 10000, 4)  # 万→亿
                        rec[col] = num
                    except ValueError:
                        rec[col] = v_clean if v_clean else None
            else:
                rec[col] = val
        records.append(rec)
    return records


# ── 财务摘要 ──────────────────────────────────────────────

def get_financial_summary(code: str) -> dict | None:
    """stock_financial_abstract_ths：多期财务摘要（8s超时）"""
    import akshare as ak
    try:
        df = _ak_call(ak.stock_financial_abstract_ths, symbol=code)
        if df is None or df.empty:
            return None
        return {"columns": list(df.columns), "records": _to_records(df)}
    except Exception:
        return None


# ── 主营业务构成 ─────────────────────────────────────────

def get_revenue_breakdown(code: str) -> list | None:
    """stock_zyjs_ths：主营业务构成（产品/经营范围）（8s超时）"""
    import akshare as ak
    try:
        df = _ak_call(ak.stock_zyjs_ths, symbol=code)
        if df is None or df.empty:
            return None
        result = []
        for _, r in df.iterrows():
            result.append({
                "business": r.get("主营业务", ""),
                "product_type": r.get("产品类型", ""),
                "products": r.get("产品名称", ""),
                "scope": r.get("经营范围", ""),
            })
        return result if result else None
    except Exception:
        return None


# ── 业绩报表 ──────────────────────────────────────────────

def get_earnings_data(code: str) -> dict:
    """stock_yjbb_em：多期业绩报表数据"""
    import akshare as ak
    try:
        result = {}
        for date_tag in ['20250331', '20250630', '20250930', '20251231', '20260331']:
            try:
                df = _ak_call(ak.stock_yjbb_em, date=date_tag)
                row = df[df['股票代码'] == code]
                if not row.empty:
                    r = row.to_dict('records')[0]
                    y, m = date_tag[:4], date_tag[4:6]
                    period = f"{y}-{m}-31" if m in ('01','03','05','07','08','10','12') else f"{y}-{m}-30"
                    if m == '09':
                        period = f"{y}-09-30"
                    result[period] = {
                        "revenue": r.get("营业总收入-营业总收入"),
                        "revenue_yoy": r.get("营业总收入-同比增长"),
                        "revenue_qoq": r.get("营业总收入-季度环比增长"),
                        "net_profit": r.get("净利润-净利润"),
                        "profit_yoy": r.get("净利润-同比增长"),
                        "profit_qoq": r.get("净利润-季度环比增长"),
                        "gross_margin": r.get("销售毛利率"),
                        "roe": r.get("净资产收益率"),
                        "eps": r.get("每股收益"),
                        "bps": r.get("每股净资产"),
                        "ocf_per_share": r.get("每股经营现金流量"),
                    }
            except Exception:
                pass
        return result
    except Exception:
        return {}


# ── 新浪报表前缀 ─────────────────────────────────────────

def _sina_prefix(code: str) -> str:
    """A股前缀：sh(6xx) / sz(0xx,3xx) / bj(4xx,8xx,92x)"""
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("4", "8")) or code.startswith("92"):
        return "bj"
    return "sh"


# ── 三张报表 & 费用分析（新浪源） ────────────────────────

def get_financial_report_sina(code: str, report_type: str) -> list[dict]:
    """从新浪获取财务报表（利润表/资产负债表/现金流量表）
    report_type: "资产负债表", "利润表", "现金流量表"
    返回 [{"period": "2026-03-31", "items": {"货币资金": 9.92, ...}}, ...]
    金额字段自动转为亿元单位。
    """
    import akshare as ak
    prefix = _sina_prefix(code)
    try:
        df = _ak_call(ak.stock_financial_report_sina, stock=f"{prefix}{code}", symbol=report_type)
        if df is None or df.empty:
            return []
        df = df.sort_values("报告日", ascending=False)
        rows = []
        for _, r in df.head(8).iterrows():
            period = str(r["报告日"])[:10]
            items = {}
            for col in r.index:
                if col in ("报告日", "数据源", "是否审计", "公告日期", "币种", "类型", "更新日期"):
                    continue
                val = r[col]
                if pd.notna(val):
                    if abs(val) >= 1e4:
                        items[col] = round(val / 1e8, 2)
                    elif val != 0:
                        items[col] = round(val, 2) if isinstance(val, float) else val
                    else:
                        items[col] = 0.0
            rows.append({"period": period, "items": items})
        return rows
    except Exception:
        return []


def get_balance_sheet(code: str) -> list[dict]:
    return get_financial_report_sina(code, "资产负债表")

def get_cash_flow_sheet(code: str) -> list[dict]:
    return get_financial_report_sina(code, "现金流量表")

def get_profit_sheet(code: str) -> list[dict]:
    return get_financial_report_sina(code, "利润表")


def get_expense_data(code: str) -> dict | None:
    """从新浪利润表提取费用结构分析，返回 {rows, summary} 格式"""
    rows_raw = get_financial_report_sina(code, "利润表")
    result_rows = []
    for row in rows_raw:
        items = row["items"]
        revenue = items.get("营业总收入") or items.get("营业收入")
        if not revenue or revenue <= 0:
            continue

        def _ratio(v):
            return round(v / revenue * 100, 2) if v and v > 0 else None

        entry = {
            "period": row["period"],
            "revenue": revenue,
        }
        for cn_key, en_key in [
            ("销售费用", "sale_expense"),
            ("管理费用", "manage_expense"),
            ("研发费用", "research_expense"),
            ("财务费用", "finance_expense"),
            ("营业总成本", "total_cost"),
            ("营业成本", "operating_cost"),
        ]:
            val = items.get(cn_key)
            if val is not None:
                entry[en_key] = val
                # 所有费用类型都算比率
                if cn_key in ("销售费用", "管理费用", "研发费用", "财务费用", "营业总成本", "营业成本"):
                    entry[f"{en_key}_ratio"] = _ratio(val)

        # 总费用占比 = 销售+管理+研发+财务 之和 / 营收
        total_exp = sum(filter(None, [entry.get("sale_expense"), entry.get("manage_expense"),
                                       entry.get("research_expense"), entry.get("finance_expense")]))
        if total_exp and total_exp > 0:
            entry["total_expense_ratio"] = round(total_exp / revenue * 100, 2)

        result_rows.append(entry)

    result_rows = result_rows[:5]

    # 趋势分析
    trend_notes = []
    if len(result_rows) >= 2:
        first, last = result_rows[-1], result_rows[0]
        for key, label in [("sale_expense_ratio", "销售费用率"), ("manage_expense_ratio", "管理费用率"),
                           ("finance_expense_ratio", "财务费用率"), ("total_cost_ratio", "总成本率")]:
            fv = first.get(key)
            lv = last.get(key)
            if fv is not None and lv is not None:
                chg = lv - fv
                if abs(chg) >= 0.1:
                    direction = "上升" if chg > 0 else "下降"
                    trend_notes.append(f"{label}{direction}{abs(chg):.1f}pp")
        for key, label in [("sale_expense", "销售费用"), ("manage_expense", "管理费用"),
                           ("finance_expense", "财务费用")]:
            fv = first.get(key)
            lv = last.get(key)
            if fv is not None and lv is not None and fv != 0:
                rev_chg_pct = (last["revenue"] / first["revenue"] - 1) * 100 if first.get("revenue") else 0
                exp_chg_pct = (lv / fv - 1) * 100
                if abs(exp_chg_pct - rev_chg_pct) > 20:
                    if exp_chg_pct > rev_chg_pct + 20:
                        trend_notes.append(f"{label}增速({exp_chg_pct:+.0f}%)跑赢营收({rev_chg_pct:+.0f}%)")
                    elif rev_chg_pct > exp_chg_pct + 20:
                        trend_notes.append(f"{label}增速({exp_chg_pct:+.0f}%)跑输营收({rev_chg_pct:+.0f}%)")

    return {"rows": result_rows, "summary": trend_notes[:5] if trend_notes else ["近5期费用结构稳定"]}


# ── 概念板块实时行情 ──────────────────────────────────────
_concept_board_cache: dict = {}
_concept_board_file = os.path.expanduser("~/Jarvis/ai_trading/concept_board_cache.json")
_CONCEPT_CACHE_TTL = 86400  # 24h


def _load_concept_board_cache() -> dict:
    """从磁盘加载概念板块缓存"""
    try:
        if os.path.exists(_concept_board_file):
            with open(_concept_board_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
    except Exception:
        pass
    return {}


def _save_concept_board_cache(data: dict):
    """保存概念板块缓存到磁盘"""
    try:
        os.makedirs(os.path.dirname(_concept_board_file), exist_ok=True)
        with open(_concept_board_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_concept_board_data() -> dict:
    """stock_board_concept_name_em：概念板块涨跌行情（带24h内存缓存 + 磁盘持久缓存 + 5s超时）"""
    import time
    global _concept_board_cache
    now = time.time()
    if _concept_board_cache and (now - _concept_board_cache.get("_ts", 0)) < _CONCEPT_CACHE_TTL:
        return _concept_board_cache

    # 有磁盘缓存则直接使用（akshare API常挂，不浪费时间去等）
    disk_cache = _load_concept_board_cache()
    if disk_cache:
        disk_cache["_ts"] = now
        _concept_board_cache = disk_cache
        # 后台更新：akshare有数据就刷新，不阻塞
        try:
            import threading
            def _bg_refresh():
                try:
                    import akshare as ak
                    df = _ak_call(ak.stock_board_concept_name_em)
                    if df is not None and not df.empty:
                        new_data = {}
                        for _, r in df.iterrows():
                            name = str(r.get("板块名称", ""))
                            new_data[name] = {
                                "change_pct": float(r.get("涨跌幅", 0) or 0),
                                "up_count": int(r.get("上涨家数", 0) or 0),
                                "down_count": int(r.get("下跌家数", 0) or 0),
                                "turnover": float(r.get("换手率", 0) or 0),
                                "leader": str(r.get("领涨股票", "")),
                                "leader_chg": float(r.get("领涨股票-涨跌幅", 0) or 0),
                            }
                        new_data["_ts"] = time.time()
                        _save_concept_board_cache(new_data)
                        global _concept_board_cache
                        _concept_board_cache = new_data
                except Exception:
                    pass
            t = threading.Thread(target=_bg_refresh, daemon=True)
            t.start()
        except Exception:
            pass
        return disk_cache

    # 首次无缓存时，尝试akshare（_ak_call带8s超时）
    try:
        import akshare as ak
        df = _ak_call(ak.stock_board_concept_name_em)
        if df is None or df.empty:
            return {}
        result = {}
        for _, r in df.iterrows():
            name = str(r.get("板块名称", ""))
            result[name] = {
                "change_pct": float(r.get("涨跌幅", 0) or 0),
                "up_count": int(r.get("上涨家数", 0) or 0),
                "down_count": int(r.get("下跌家数", 0) or 0),
                "turnover": float(r.get("换手率", 0) or 0),
                "leader": str(r.get("领涨股票", "")),
                "leader_chg": float(r.get("领涨股票-涨跌幅", 0) or 0),
            }
        result["_ts"] = now
        _concept_board_cache = result
        _save_concept_board_cache(result)
        return result
    except Exception:
        # akshare报错不缓存
        return {}


# ── 财务分析指标 ──────────────────────────────────────────

def get_financial_indicators(code: str, start_year: str = "2023") -> list[dict]:
    """stock_financial_analysis_indicator：杜邦/盈利能力指标时间序列"""
    import akshare as ak
    try:
        df = _ak_call(ak.stock_financial_analysis_indicator, symbol=code, start_year=start_year)
        df = df.sort_values("日期", ascending=False)
        return df.to_dict("records")
    except Exception:
        return []


# ── 管理层持股变动 ────────────────────────────────────────

def get_management_changes(code: str) -> list[dict]:
    """stock_management_change_ths：管理层持股变动记录"""
    import akshare as ak
    try:
        df = _ak_call(ak.stock_management_change_ths, symbol=code)
        df = df.sort_values("变动日期", ascending=False)
        return df.head(10).to_dict("records")
    except Exception:
        return []


# ── 主要股东 ──────────────────────────────────────────────

def get_main_shareholders(code: str) -> tuple[pd.DataFrame | None, str | None]:
    """stock_main_stock_holder：最新一期主要股东数据。
    返回 (df_sorted_by_ratio, total_holders)
    """
    import akshare as ak
    try:
        sh_df = _ak_call(ak.stock_main_stock_holder, stock=code)
        sh_df = sh_df.sort_values("截至日期", ascending=False)
        latest_date = sh_df.iloc[0].get("截至日期")
        sh_df = sh_df[sh_df["截至日期"] == latest_date].copy()
        total_holders = sh_df.iloc[0].get("股东总数") if "股东总数" in sh_df.columns else None
        if total_holders is not None and isinstance(total_holders, float) and total_holders != total_holders:
            total_holders = None
        return sh_df, total_holders
    except Exception:
        return None, None


# ── 概念板块成分股 ────────────────────────────────────────

def get_concept_board_constituents(board_name: str) -> list[dict]:
    """stock_board_concept_cons_em：获取概念板块成分股（含涨幅排序）（8s超时）"""
    import akshare as ak
    try:
        cons_df = _ak_call(ak.stock_board_concept_cons_em, symbol=board_name)
        if cons_df.empty:
            return []
        cols = ["代码", "名称", "最新价", "涨跌幅"]
        top5 = cons_df.nlargest(5, "涨跌幅")
        stocks = []
        for _, r in top5.iterrows():
            stocks.append({
                "code": str(r["代码"]).strip(),
                "name": r["名称"],
                "price": float(r["最新价"]) if pd.notna(r.get("最新价")) else 0,
                "change_pct": float(r["涨跌幅"]) if pd.notna(r.get("涨跌幅")) else 0,
            })
        return stocks
    except Exception:
        return []


# ── 港股行情 ──────────────────────────────────────────────

def get_hk_stock_daily_price(code: str) -> float | None:
    """stock_hk_daily：获取港股最近交易日收盘价（不复权），自动缓存到 kline_daily"""
    # 先查缓存
    from backend.services.database.stock_db import get_db
    conn = get_db()
    row = conn.execute(
        "SELECT close, date FROM kline_daily WHERE code=? ORDER BY date DESC LIMIT 1",
        (f"hk_{code}",)
    ).fetchone()
    if row:
        conn.close()
        return row[0]

    # 从 akshare 拉取
    import akshare as ak
    try:
        df = _ak_call(ak.stock_hk_daily, symbol=code)
        if df is not None and not df.empty:
            latest_close = float(df.iloc[-1]["close"])
            # 写入 kline_daily（全量）
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR REPLACE INTO kline_daily (code, date, open, close, high, low, volume) VALUES (?,?,?,?,?,?,?)",
                    (f"hk_{code}", str(r["date"])[:10],
                     float(r["open"]), float(r["close"]),
                     float(r["high"]), float(r["low"]),
                     float(r["volume"]))
                )
            conn.commit()
            conn.close()
            return latest_close
    except Exception:
        pass
    conn.close()
    return None


def get_hk_stock_prices_batch(codes: list[str]) -> dict[str, float]:
    """批量获取港股最近收盘价（复用单只查询，自带缓存）"""
    result = {}
    for code in codes:
        p = get_hk_stock_daily_price(code)
        if p is not None:
            result[code] = p
    return result


def get_hk_stock_name(code: str) -> str | None:
    """stock_hk_spot：获取港股中文名称（实时行情接口）"""
    import akshare as ak
    try:
        df = ak.stock_hk_spot()
        if df is None or df.empty:
            return None
        match = df[df["代码"] == code]
        if not match.empty:
            return str(match.iloc[0].get("中文名称", ""))
    except Exception:
        pass
    return None


# ── 美股行情 ──────────────────────────────────────────────

def get_us_stock_daily_price(code: str) -> float | None:
    """stock_us_daily：获取美股最近交易日收盘价（不复权），自动缓存到 kline_daily"""
    # 先查缓存
    from backend.services.database.stock_db import get_db
    conn = get_db()
    row = conn.execute(
        "SELECT close, date FROM kline_daily WHERE code=? ORDER BY date DESC LIMIT 1",
        (f"us_{code}",)
    ).fetchone()
    if row:
        conn.close()
        return row[0]

    # 从 akshare 拉取
    import akshare as ak
    try:
        df = ak.stock_us_daily(symbol=code, adjust="")
        if df is not None and not df.empty:
            latest_close = float(df.iloc[-1]["close"])
            # 写入 kline_daily（全量）
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR REPLACE INTO kline_daily (code, date, open, close, high, low, volume) VALUES (?,?,?,?,?,?,?)",
                    (f"us_{code}", str(r["date"])[:10],
                     float(r["open"]), float(r["close"]),
                     float(r["high"]), float(r["low"]),
                     float(r["volume"]))
                )
            conn.commit()
            conn.close()
            return latest_close
    except Exception:
        pass
    conn.close()
    return None


def get_us_stock_prices_batch(codes: list[str]) -> dict[str, float]:
    """批量获取美股最近收盘价（复用单只查询，自带缓存）"""
    result = {}
    for code in codes:
        p = get_us_stock_daily_price(code)
        if p is not None:
            result[code] = p
    return result


def get_us_stock_name(code: str) -> str | None:
    """stock_individual_basic_info_us_xq：获取美股中文简称"""
    import akshare as ak
    try:
        df = ak.stock_individual_basic_info_us_xq(symbol=code)
        if df is not None and not df.empty:
            d = dict(zip(df["item"], df["value"]))
            return d.get("org_short_name_cn") or d.get("org_name_cn") or code
    except Exception:
        pass
    return code
