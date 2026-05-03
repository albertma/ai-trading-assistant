"""
个股基本面深度分析 API
"""
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path

from backend.config import MARKET_DATA_DIR

router = APIRouter()

# ============================================================
# 1. 财务摘要 (akshare stock_financial_abstract_ths)
# ============================================================
def _get_financial_summary(code: str) -> dict | None:
    import akshare as ak
    try:
        df = ak.stock_financial_abstract_ths(symbol=code)
        if df is None or df.empty:
            return None

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
                    # 去除单位符号（亿、万、%）
                    v = v.replace("亿", "").replace("万", "").replace("%", "").strip()
                    rec[col] = v if v not in ("--", "", "False") else None
                else:
                    rec[col] = val
            records.append(rec)

        return {"columns": list(df.columns), "records": records}
    except Exception as e:
        return None


# ============================================================
# 2. 收入构成（主营业务）
# ============================================================
def _get_revenue_breakdown(code: str) -> list | None:
    """获取主营业务构成（产品/经营范围）"""
    import akshare as ak
    try:
        df = ak.stock_zyjs_ths(symbol=code)
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


# ============================================================
# 3. 行业数据（从本地CSV获取板块表现）
# ============================================================
def _get_industry_data(sector: str | None) -> dict | None:
    """获取行业板块数据：板块排名、平均涨幅、龙头股"""
    if not sector or sector == "--":
        return None

    today = date.today()
    for i in range(5):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
            break
    else:
        return None

    # 该行业全部股票
    sector_df = df[df["所属行业"] == sector].copy()
    if sector_df.empty:
        return None

    # 行业整体排名
    all_sectors = df.groupby("所属行业")["涨幅"].mean().sort_values(ascending=False)
    total = len(all_sectors)
    rank = all_sectors.index.get_loc(sector) + 1 if sector in all_sectors.index else None

    # 头部股票
    top5 = sector_df.nlargest(5, "涨幅")[["代码", "名称", "最新", "涨幅", "总市值"]]
    top5_list = []
    for _, r in top5.iterrows():
        top5_list.append({
            "code": str(r["代码"]).strip("'\""),
            "name": r["名称"],
            "price": float(r["最新"]) if pd.notna(r["最新"]) else 0,
            "change_pct": float(r["涨幅"]) if pd.notna(r["涨幅"]) else 0,
            "market_cap": float(r["总市值"]) if pd.notna(r["总市值"]) else 0,
        })

    # 行业统计
    valid = sector_df[sector_df["涨幅"].notna()]
    avg_chg = float(valid["涨幅"].mean()) if not valid.empty else 0
    up_count = int((valid["涨幅"] > 0).sum())
    total_count = int(len(valid))

    return {
        "sector": sector,
        "date": str(today),
        "rank": rank,
        "total_sectors": total,
        "avg_change": round(avg_chg, 2),
        "up_ratio": round(up_count / total_count * 100, 1) if total_count > 0 else 0,
        "stock_count": total_count,
        "top_stocks": top5_list,
    }


# ============================================================
# API 路由
# ============================================================
# ============================================================
# 4. 杜邦分析
# ============================================================
def _parse_num(val) -> float | None:
    """把财务字段解析成数值（已去除亿/万/%等单位）"""
    if val is None or val == "" or val == "--" or val == "False":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_dupont_analysis(code: str) -> dict | None:
    """杜邦分析：拆解ROE增长来源

    ROE = 净利率 × 资产周转率 × 权益乘数

    净利率 → 盈利能力
    资产周转率 → 运营效率
    权益乘数 → 财务杠杆
    """
    fin = _get_financial_summary(code)
    if not fin or not fin.get("records"):
        return None

    records = fin["records"]
    dupont_rows = []
    for r in records:
        period = r.get("报告期", "")
        # 解析关键数据
        net_profit = _parse_num(r.get("净利润"))  # 亿
        revenue = _parse_num(r.get("营业总收入"))  # 亿
        net_margin_pct = _parse_num(r.get("销售净利率"))  # %
        roe_pct = _parse_num(r.get("净资产收益率"))  # %
        debt_ratio_pct = _parse_num(r.get("资产负债率"))  # %

        if None in (net_profit, revenue, net_margin_pct, roe_pct, debt_ratio_pct):
            # 早期数据缺失则跳过
            if net_margin_pct and debt_ratio_pct:
                # 至少可以算权益乘数和净利率
                pass
            else:
                continue

        # 计算权益乘数 = 1 / (1 - 资产负债率)
        equity_multiplier = round(1 / (1 - debt_ratio_pct / 100), 4) if debt_ratio_pct else None

        # 计算总资产 = 股东权益 / (1 - 资产负债率)
        # 股东权益 = 净利润 / ROE
        if roe_pct and roe_pct > 0:
            equity = net_profit / (roe_pct / 100)  # 亿
            total_assets = equity / (1 - debt_ratio_pct / 100) if debt_ratio_pct < 100 else None  # 亿
        else:
            equity = None
            total_assets = None

        # 资产周转率 = 营业总收入 / 总资产
        asset_turnover = round(revenue / total_assets, 4) if total_assets and total_assets > 0 else None

        # 净利率（直接用销售净利率，但也可以用净利润/营收推算验证）
        net_margin = round(net_margin_pct / 100, 4) if net_margin_pct else None

        # 计算ROE验证
        roe_calc = round(net_margin * asset_turnover * equity_multiplier, 4) if all(
            x is not None for x in [net_margin, asset_turnover, equity_multiplier]
        ) else None

        dupont_rows.append({
            "period": period,
            "roe_pct": roe_pct,  # 实际ROE(%)
            "roe_calc_pct": round(roe_calc * 100, 2) if roe_calc else None,  # 计算ROE(%)
            "net_margin_pct": net_margin_pct,  # 净利率(%)
            "asset_turnover": asset_turnover,  # 资产周转率(次)
            "equity_multiplier": equity_multiplier,  # 权益乘数
            "net_profit": round(net_profit, 2) if net_profit else None,  # 净利润(亿)
            "revenue": round(revenue, 2) if revenue else None,  # 营收(亿)
            "total_assets": round(total_assets, 2) if total_assets else None,  # 总资产(亿)
            "debt_ratio_pct": debt_ratio_pct,  # 资产负债率(%)
        })

    if not dupont_rows:
        return None

    # 计算同比变化：最近5期的逐期变化
    rows_for_changes = dupont_rows[-5:]
    changes = []
    for i in range(len(rows_for_changes) - 1, 0, -1):
        cur = rows_for_changes[i]
        prev = rows_for_changes[i - 1]
        if cur.get("roe_pct") and prev.get("roe_pct"):
            roe_chg = round(cur["roe_pct"] - prev["roe_pct"], 2)
            nm_chg = round(cur["net_margin_pct"] - prev["net_margin_pct"], 2) if cur.get("net_margin_pct") and prev.get("net_margin_pct") else None
            at_chg = round(cur["asset_turnover"] - prev["asset_turnover"], 4) if cur.get("asset_turnover") and prev.get("asset_turnover") else None
            em_chg = round(cur["equity_multiplier"] - prev["equity_multiplier"], 4) if cur.get("equity_multiplier") and prev.get("equity_multiplier") else None

            # 找出主要驱动因素
            drivers = []
            if nm_chg is not None and abs(nm_chg) >= 0.5:
                drivers.append(f"净利率{'↑' if nm_chg > 0 else '↓'}{abs(nm_chg):.1f}pp")
            if at_chg is not None and abs(at_chg) >= 0.05:
                drivers.append(f"周转率{'↑' if at_chg > 0 else '↓'}{abs(at_chg):.2f}x")
            if em_chg is not None and abs(em_chg) >= 0.1:
                drivers.append(f"杠杆{'↑' if em_chg > 0 else '↓'}{abs(em_chg):.2f}x")

            direction = "up" if roe_chg > 0 else "down" if roe_chg < 0 else "flat"
            changes.append({
                "from_period": prev["period"],
                "to_period": cur["period"],
                "roe_change": roe_chg,
                "net_margin_change": nm_chg,
                "asset_turnover_change": at_chg,
                "equity_multiplier_change": em_chg,
                "main_drivers": drivers if drivers else ["多因素综合"],
                "direction": direction,
            })

    # 只取最近5期
    dupont_rows = dupont_rows[-5:]

    return {
        "rows": dupont_rows,
        "changes": changes[:3] if changes else [],
        "latest": dupont_rows[-1] if dupont_rows else None,
    }


def _get_earnings_data(code: str) -> dict:
    """从业绩报表获取关键财务数据"""
    import akshare as ak
    try:
        result = {}
        for date_tag in ['20250331', '20250630', '20250930', '20251231', '20260331']:
            try:
                df = ak.stock_yjbb_em(date=date_tag)
                row = df[df['股票代码'] == code]
                if not row.empty:
                    r = row.to_dict('records')[0]
                    period = date_tag[:4] + '-' + date_tag[4:6] + '-31' if date_tag[4:6] in ('01','03','05','07','08','10','12') else date_tag[:4] + '-' + date_tag[4:6] + '-30'
                    if date_tag[4:6] == '09':
                        period = date_tag[:4] + '-09-30'
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


def _generate_dupont_commentary(code: str, rows: list, changes: list) -> list:
    """基于财报数据生成杜邦变化分析评论"""
    earnings = _get_earnings_data(code)
    if not earnings:
        return []

    results = []
    for chg in changes:
        cur_period = chg["to_period"]
        prev_period = chg["from_period"]
        cur_earn = earnings.get(cur_period, {})
        prev_earn = earnings.get(prev_period, {})

        parts = []

        # 净利率变化评论
        nm_chg = chg.get("net_margin_change")
        if nm_chg is not None and abs(nm_chg) >= 0.3:
            # 检查毛利率变化
            cur_gm = cur_earn.get("gross_margin")
            prev_gm = prev_earn.get("gross_margin")
            if cur_gm and prev_gm:
                gm_chg = round(cur_gm - prev_gm, 2)
                if abs(gm_chg) >= 0.5:
                    parts.append(f"毛利率{'提升' if gm_chg > 0 else '下降'}{abs(gm_chg):.1f}pp")
            # 检查营收与利润增长
            rev_yoy = cur_earn.get("revenue_yoy")
            profit_yoy = cur_earn.get("profit_yoy")
            if rev_yoy is not None and profit_yoy is not None:
                if profit_yoy > 0 and rev_yoy > 0:
                    if profit_yoy > rev_yoy + 10:
                        parts.append("利润增速显著跑赢营收，盈利能力增强")
                    elif rev_yoy > profit_yoy + 10:
                        parts.append(f"利润增速({profit_yoy:.1f}%)落后于营收({rev_yoy:.1f}%)")
                elif profit_yoy < 0 and rev_yoy > 0:
                    parts.append(f"增收不增利：营收增{rev_yoy:.1f}%但利润降{abs(profit_yoy):.1f}%")
                elif profit_yoy > 0 and rev_yoy < 0:
                    parts.append("减收增利，成本管控见效")
                if profit_yoy > 15:
                    parts.append(f"净利润同比+{profit_yoy:.1f}%，增长强劲")

        # 周转率变化评论
        at_chg = chg.get("asset_turnover_change")
        if at_chg is not None and abs(at_chg) >= 0.1:
            # 注意：累计数据导致周转率随期间累加而自然上升
            rev_yoy = cur_earn.get("revenue_yoy")
            rev_qoq = cur_earn.get("revenue_qoq")
            if chg["from_period"].endswith("03-31") or chg["to_period"].endswith("03-31"):
                parts.append("Q1为单季数据，与累计期不可直接比")
            elif rev_yoy and rev_yoy > 20:
                parts.append(f"营收同比增长{rev_yoy:.1f}%，推动周转率提升")
            elif rev_yoy and rev_yoy < -5:
                parts.append(f"营收同比下滑{abs(rev_yoy):.1f}%，拉低周转率")
            if rev_qoq and abs(rev_qoq) > 15:
                parts.append(f"营收环比{'增长' if rev_qoq > 0 else '下滑'}{abs(rev_qoq):.1f}%")

        # 杠杆变化评论
        em_chg = chg.get("equity_multiplier_change")
        if em_chg is not None and abs(em_chg) >= 0.1:
            cur_debt = next((r.get("debt_ratio_pct") for r in rows if r["period"] == cur_period), None)
            prev_debt = next((r.get("debt_ratio_pct") for r in rows if r["period"] == prev_period), None)
            if cur_debt and prev_debt:
                debt_chg = round(cur_debt - prev_debt, 1)
                if abs(debt_chg) >= 1:
                    parts.append(f"负债率{'上升' if debt_chg > 0 else '下降'}{abs(debt_chg):.1f}pp")
            if cur_debt and cur_debt > 70:
                parts.append("负债率偏高，关注偿债风险")
            elif cur_debt and cur_debt < 40:
                parts.append("负债率偏低，杠杆空间充足")

        # 整体总结
        if not parts:
            parts.append("变化幅度较小，属正常波动")

        direction_label = "利好" if chg["direction"] == "up" else "利空" if chg["direction"] == "down" else "中性"
        results.append({
            "from_period": prev_period,
            "to_period": cur_period,
            "roe_change": chg["roe_change"],
            "direction": chg["direction"],
            "direction_label": direction_label,
            "commentary": "；".join(parts),
            "details": {
                "revenue_yoy": cur_earn.get("revenue_yoy"),
                "profit_yoy": cur_earn.get("profit_yoy"),
                "gross_margin": cur_earn.get("gross_margin"),
                "eps": cur_earn.get("eps"),
            } if cur_earn else None,
        })
    return results


@router.get("/dupont/{code}")
def dupont_analysis(code: str):
    """杜邦分析API"""
    from backend.routers.analysis import _get_stock_list
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")
    result = _get_dupont_analysis(code)
    return {
        "code": code,
        "name": name,
        "dupont": result,
    }


# 缓存财报数据，避免重复拉取（内存缓存，进程内有效）
_earnings_cache: dict[str, dict] = {}
_earnings_cache_time: float = 0


@router.get("/dupont/{code}/commentary")
def dupont_commentary(code: str):
    """杜邦分析评论（异步加载版，单独接口不阻塞主数据）"""
    import time
    global _earnings_cache, _earnings_cache_time

    # 缓存5分钟
    now = time.time()
    if not _earnings_cache or (now - _earnings_cache_time) > 300:
        fresh = _get_earnings_data(code)
        if fresh:
            _earnings_cache = fresh
            _earnings_cache_time = now
    else:
        fresh = _earnings_cache

    if not fresh:
        return {"commentary": []}

    result = _get_dupont_analysis(code)
    if not result:
        return {"commentary": []}

    changes = result.get("changes", [])
    commentary = _generate_dupont_commentary(code, result.get("rows", []), changes)
    return {"commentary": commentary}


# ============================================================
# 5. 费用分析
# ============================================================
def _get_expense_data(code: str) -> dict | None:
    """共享的费用分析函数，返回 rows+summary 或 None"""
    import akshare as ak
    market = "SZ" if code.startswith(("0", "3", "2")) else "SH"
    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=f"{market}{code}")
        df = df.sort_values("REPORT_DATE", ascending=False)
    except Exception:
        return None

    rows = []
    for _, r in df.head(8).iterrows():
        revenue = r.get("TOTAL_OPERATE_INCOME")
        if not revenue or revenue <= 0:
            continue

        def as_ratio(val):
            return round(val / revenue * 100, 2) if val and val > 0 else None

        def as_yoy(val):
            return round(val, 2) if val and val not in (None, "nan", 0) else None

        item = {
            "period": str(r["REPORT_DATE"])[:10],
            "revenue": round(revenue / 1e8, 2),
            "revenue_yoy": as_yoy(r.get("TOTAL_OPERATE_INCOME_YOY")),
        }
        sale = r.get("SALE_EXPENSE")
        if sale and sale > 0:
            item["sale_expense"] = round(sale / 1e8, 4)
            item["sale_ratio"] = as_ratio(sale)
            item["sale_yoy"] = as_yoy(r.get("SALE_EXPENSE_YOY"))
        manage = r.get("MANAGE_EXPENSE")
        if manage and manage > 0:
            item["manage_expense"] = round(manage / 1e8, 4)
            item["manage_ratio"] = as_ratio(manage)
            item["manage_yoy"] = as_yoy(r.get("MANAGE_EXPENSE_YOY"))
        research = r.get("ME_RESEARCH_EXPENSE")
        if research and research > 0:
            item["research_expense"] = round(research / 1e8, 4)
            item["research_ratio"] = as_ratio(research)
            item["research_yoy"] = as_yoy(r.get("ME_RESEARCH_EXPENSE_YOY"))
        finance = r.get("FINANCE_EXPENSE")
        if finance and finance != 0:
            item["finance_expense"] = round(finance / 1e8, 4)
            item["finance_ratio"] = as_ratio(abs(finance))
            item["finance_yoy"] = as_yoy(r.get("FINANCE_EXPENSE_YOY"))
        total_cost = r.get("TOTAL_OPERATE_COST")
        if total_cost and total_cost > 0:
            item["total_cost_ratio"] = round(total_cost / revenue * 100, 2)
            item["cost_yoy"] = as_yoy(r.get("TOTAL_OPERATE_COST_YOY"))

        rows.append(item)

    rows = rows[:5]
    trend_notes = []
    if len(rows) >= 2:
        first, last = rows[-1], rows[0]
        for key, label in [("sale_ratio", "销售费用率"), ("manage_ratio", "管理费用率"),
                           ("finance_ratio", "财务费用率"), ("total_cost_ratio", "总成本率")]:
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
            if fv is not None and lv is not None:
                rev_chg_pct = (last["revenue"] / first["revenue"] - 1) * 100
                exp_chg_pct = (lv / fv - 1) * 100
                if abs(exp_chg_pct - rev_chg_pct) > 20:
                    if exp_chg_pct > rev_chg_pct + 20:
                        trend_notes.append(f"{label}增速({exp_chg_pct:+.0f}%)跑赢营收({rev_chg_pct:+.0f}%)")
                    elif rev_chg_pct > exp_chg_pct + 20:
                        trend_notes.append(f"{label}增速({exp_chg_pct:+.0f}%)跑输营收({rev_chg_pct:+.0f}%)")

    return {
        "rows": rows,
        "summary": trend_notes[:5] if trend_notes else ["近5期费用结构稳定"],
    }


@router.get("/expense/{code}")
def expense_analysis(code: str):
    """费用分析：销售/管理/研发/财务费用占营收比及变化"""
    from backend.routers.analysis import _get_stock_list
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")
    data = _get_expense_data(code)
    return {"code": code, "name": name, "expenses": data}


@router.get("/{code}")
def fundamental_analysis(code: str):
    """基本面综合：财务摘要 + 收入构成 + 行业前瞻"""
    # 先从分析模块获取股票名称
    from backend.routers.analysis import _get_stock_list
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")

    # 获取财务摘要
    fin = _get_financial_summary(code)
    if fin and fin.get("records"):
        # 只保留最近5期
        fin["records"] = fin["records"][-5:]

    # 获取收入构成
    revenue = _get_revenue_breakdown(code)

    # 从CSV获取行业
    sector = None
    today = date.today()
    for i in range(5):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            match = df[df["代码"] == code]
            if not match.empty:
                sector = match.iloc[0].get("所属行业", "")
            break

    # 行业前瞻
    industry = _get_industry_data(sector)

    return {
        "code": code,
        "name": name,
        "sector": sector,
        "financial_summary": fin,
        "revenue_breakdown": revenue,
        "industry_outlook": industry,
    }


# ============================================================
# 6. 三张财务报表
# ============================================================
# 字段名→中文标签映射
_BS_LABELS = {
    "TOTAL_OPERATE_INCOME": "营业总收入", "OPERATE_COST": "营业成本",
    "SALE_EXPENSE": "销售费用", "MANAGE_EXPENSE": "管理费用",
    "ME_RESEARCH_EXPENSE": "研发费用", "FINANCE_EXPENSE": "财务费用",
    "OPERATE_PROFIT": "营业利润", "TOTAL_PROFIT": "利润总额",
    "INCOME_TAX": "所得税", "EFFECT_NETPROFIT": "净利润",
    "PARENT_NETPROFIT": "归母净利润", "MINORITY_PROFIT": "少数股东损益",
    "BASIC_EPS": "基本每股收益", "DILUTED_EPS": "稀释每股收益",
    "TOTAL_OPERATE_COST": "营业总成本",
    "ASSET_IMPAIRMENT_INCOME": "资产减值损失",
    "OTHER_INCOME": "其他收益",
    "NETCASH_OPERATE": "经营活动现金流净额",
    "NETCASH_INVEST": "投资活动现金流净额",
    "NETCASH_FINANCE": "筹资活动现金流净额",
    "CASH_EQUIVALENT_NET": "现金净增加额",
    "CASH_BALANCE": "期末现金余额",
    "TOTAL_OPERATE_INFLOW": "经营活动现金流入",
    "TOTAL_OPERATE_OUTFLOW": "经营活动现金流出",
    "TOTAL_INVEST_INFLOW": "投资活动现金流入",
    "TOTAL_INVEST_OUTFLOW": "投资活动现金流出",
    "TOTAL_FINANCE_INFLOW": "筹资活动现金流入",
    "TOTAL_FINANCE_OUTFLOW": "筹资活动现金流出",
    "TOTAL_ASSETS": "资产总计",
    "CURRENT_ASSET_BALANCE": "流动资产合计",
    "NONCURRENT_ASSET_BALANCE": "非流动资产合计",
    "MONETARYFUNDS": "货币资金",
    "ACCOUNTS_RECE": "应收账款",
    "ACCOUNTS_PAYABLE": "应付账款",
    "INVENTORY": "存货",
    "FIXED_ASSET": "固定资产",
    "INTANGIBLE_ASSET": "无形资产",
    "SHORT_LOAN": "短期借款",
    "LONG_LOAN": "长期借款",
    "LIAB_BALANCE": "负债合计",
    "CURRENT_LIAB_BALANCE": "流动负债合计",
    "NONCURRENT_LIAB_BALANCE": "非流动负债合计",
    "EQUITY_BALANCE": "股东权益合计",
    "CAPITAL_RESERVE": "资本公积",
    "SURPLUS_RESERVE": "盈余公积",
    "MINORITY_EQUITY": "少数股东权益",
    "NOTE_RECE": "应收票据",
    "NOTE_PAYABLE": "应付票据",
    "ADVANCE_RECEIVABLES": "预付款项",
    "STAFF_SALARY_PAYABLE": "应付职工薪酬",
    "TAX_PAYABLE": "应交税费",
    "BOND_PAYABLE": "应付债券",
    "LONG_PAYABLE": "长期应付款",
    "BEGIN_CASH_EQUIVALENTS": "期初现金余额",
    "END_CASH_EQUIVALENTS": "期末现金余额",
    "CASH_EQUIVALENT_NET": "现金净增加额",
}


def _fetch_statement(code: str, func_name: str) -> list[dict]:
    """获取单张报表并解析关键字段"""
    import akshare as ak
    import importlib

    market = "SZ" if code.startswith(("0", "3", "2")) else "SH"
    func = getattr(ak, func_name)
    df = func(symbol=f"{market}{code}")
    df = df.sort_values("REPORT_DATE", ascending=False)

    rows = []
    for _, r in df.head(5).iterrows():
        period = str(r["REPORT_DATE"])[:10]
        items = {}
        for col in _BS_LABELS:
            val = r.get(col)
            if val is not None and val != 0 and not (isinstance(val, float) and (val != val)):
                items[col] = round(val / 1e8, 2) if abs(val) > 1e4 else val
        rows.append({"period": period, "items": items})
    return rows


def _get_bs_items(code: str):
    return _fetch_statement(code, "stock_balance_sheet_by_report_em")


def _get_cf_items(code: str):
    return _fetch_statement(code, "stock_cash_flow_sheet_by_report_em")


def _get_ps_items(code: str):
    return _fetch_statement(code, "stock_profit_sheet_by_report_em")


# ============================================================
# 7. 财报健康评分
# ============================================================
def _compute_health_score(code: str) -> dict | None:
    """基于三张报表 + 财务摘要 计算综合健康评分，返回详细评分过程"""
    try:
        bs = _get_bs_items(code)
        cf = _get_cf_items(code)
        ps = _get_ps_items(code)
    except Exception:
        return None

    fin = _get_financial_summary(code)

    if not bs and not ps:
        return None

    latest_bs = bs[0]["items"] if bs else {}
    latest_cf = cf[0]["items"] if cf else {}
    latest_ps = ps[0]["items"] if ps else {}

    def val(d, key):
        return d.get(key) or d.get(_BS_LABELS.get(key, key))

    def get_fin(key):
        """从财务摘要取最新值"""
        if not fin or not fin.get("records"):
            return None
        last = fin["records"][-1]
        v = last.get(key)
        if v is None or v == "--" or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    dimensions = []
    total_score = 0
    total_weight = 0

    # ---- 1. 偿债能力 (Solvency) - 权重20 ----
    solvency_score = 0
    solvency_max = 20
    solvency_details = []

    # 1a. 现金短债比
    cash = val(latest_bs, "MONETARYFUNDS")  # 亿
    short_loan = val(latest_bs, "SHORT_LOAN")  # 亿
    if cash is not None and short_loan and short_loan > 0:
        ratio = cash / short_loan
        pts = min(7, ratio / 2 * 7)
        sub = min(7, round(pts, 1))
        solvency_score += sub
        solvency_details.append({
            "item": "现金短债比",
            "value": f"{ratio:.2f}",
            "desc": f"货币资金{cash:.1f}亿 ÷ 短期借款{short_loan:.1f}亿 = {ratio:.2f}",
            "score": sub, "max": 7, "verdict": "✅ 充足" if ratio > 1.5 else ("⚠️ 一般" if ratio > 0.8 else "❌ 不足"),
        })
    elif cash is not None and (short_loan is None or short_loan == 0):
        solvency_score += 7
        solvency_details.append({
            "item": "现金短债比", "value": "无短债", "desc": "无短期借款，偿债风险低",
            "score": 7, "max": 7, "verdict": "✅ 安全",
        })

    # 1b. 资产负债率
    total_liab = val(latest_bs, "LIAB_BALANCE") or val(latest_bs, "CURRENT_LIAB_BALANCE")
    total_assets = val(latest_bs, "TOTAL_ASSETS")
    if total_liab is not None and total_assets and total_assets > 0:
        debt_ratio = total_liab / total_assets * 100
        if debt_ratio < 40:
            pts = 7
        elif debt_ratio < 60:
            pts = 5
        elif debt_ratio < 70:
            pts = 3
        elif debt_ratio < 85:
            pts = 1
        else:
            pts = 0
        solvency_score += pts
        solvency_details.append({
            "item": "资产负债率",
            "value": f"{debt_ratio:.1f}%",
            "desc": f"负债合计{total_liab:.1f}亿 ÷ 资产总计{total_assets:.1f}亿",
            "score": pts, "max": 7,
            "verdict": "✅ 低杠杆" if debt_ratio < 40 else ("✅ 合理" if debt_ratio < 60 else ("⚠️ 偏高" if debt_ratio < 70 else "❌ 过高")),
        })

    # 1c. 流动资产/流动负债（粗略流动比率）
    ca = val(latest_bs, "CURRENT_ASSET_BALANCE")
    cl = val(latest_bs, "CURRENT_LIAB_BALANCE")
    if ca is not None and ca > 0 and cl is not None and cl > 0:
        cr = ca / cl
        pts = min(6, cr * 2.5)
        sub = min(6, round(pts, 1))
        solvency_score += sub
        solvency_details.append({
            "item": "流动比率",
            "value": f"{cr:.2f}",
            "desc": f"流动资产{ca:.1f}亿 ÷ 流动负债{cl:.1f}亿 = {cr:.2f}",
            "score": sub, "max": 6,
            "verdict": "✅ 健康" if cr > 1.5 else ("⚠️ 偏低" if cr > 1.0 else "❌ 风险"),
        })

    dimensions.append({
        "name": "偿债能力",
        "icon": "🏛️",
        "score": round(solvency_score, 1), "max": solvency_max,
        "details": solvency_details,
        "summary": f"得分 {round(solvency_score, 1)}/{solvency_max}",
    })
    total_score += solvency_score
    total_weight += solvency_max

    # ---- 2. 盈利能力 (Profitability) - 权重25 ----
    profit_score = 0
    profit_max = 25
    profit_details = []

    # 2a. 毛利率趋势（最近2期利润表）
    if ps and len(ps) >= 2:
        rev_cur = val(ps[0]["items"], "TOTAL_OPERATE_INCOME")
        cost_cur = val(ps[0]["items"], "OPERATE_COST")
        rev_prev = val(ps[1]["items"], "TOTAL_OPERATE_INCOME")
        cost_prev = val(ps[1]["items"], "OPERATE_COST")
        if all(x is not None and x > 0 for x in [rev_cur, cost_cur, rev_prev, cost_prev]):
            gm_cur = (rev_cur - cost_cur) / rev_cur * 100
            gm_prev = (rev_prev - cost_prev) / rev_prev * 100
            gm_trend = gm_cur - gm_prev
            if gm_trend > 2:
                pts = 8
                trend_label = "显著提升"
            elif gm_trend > 0:
                pts = 6
                trend_label = "微幅提升"
            elif gm_trend > -2:
                pts = 4
                trend_label = "基本稳定"
            else:
                pts = 1
                trend_label = "明显下滑"
            profit_score += pts
            profit_details.append({
                "item": "毛利率趋势",
                "value": f"{gm_cur:.1f}%",
                "desc": f"最新毛利率{gm_cur:.1f}%（上期{gm_prev:.1f}%），变化{gm_trend:+.1f}pp",
                "score": pts, "max": 8, "verdict": f"{'✅' if pts > 4 else '⚠️'} {trend_label}",
            })

    # 2b. 净利率
    net_profit = val(latest_ps, "EFFECT_NETPROFIT") or val(latest_ps, "PARENT_NETPROFIT")
    revenue = val(latest_ps, "TOTAL_OPERATE_INCOME")
    if net_profit is not None and revenue and revenue > 0:
        npm = net_profit / revenue * 100
        if npm > 20:
            pts = 9
            label = "极高"
        elif npm > 10:
            pts = 7
            label = "优秀"
        elif npm > 5:
            pts = 5
            label = "良好"
        elif npm > 0:
            pts = 3
            label = "偏低"
        else:
            pts = 0
            label = "亏损"
        profit_score += pts
        profit_details.append({
            "item": "净利率",
            "value": f"{npm:.2f}%",
            "desc": f"净利润{net_profit:.2f}亿 ÷ 营收{revenue:.2f}亿 = {npm:.2f}%",
            "score": pts, "max": 9, "verdict": f"{'✅' if pts > 4 else ('⚠️' if pts > 1 else '❌')} {label}",
        })

    # 2c. ROE（从财务摘要取）
    roe_val = get_fin("净资产收益率")
    if roe_val is not None:
        if roe_val > 20:
            pts = 8
            label = "极强"
        elif roe_val > 15:
            pts = 7
            label = "优秀"
        elif roe_val > 10:
            pts = 5
            label = "良好"
        elif roe_val > 5:
            pts = 3
            label = "一般"
        elif roe_val > 0:
            pts = 1
            label = "偏低"
        else:
            pts = 0
            label = "负值"
        profit_score += pts
        profit_details.append({
            "item": "净资产收益率(ROE)",
            "value": f"{roe_val:.2f}%",
            "desc": f"财务摘要最新ROE = {roe_val:.2f}%",
            "score": pts, "max": 8, "verdict": f"{'✅' if pts > 4 else ('⚠️' if pts > 0 else '❌')} {label}",
        })

    dimensions.append({
        "name": "盈利能力",
        "icon": "📊",
        "score": round(profit_score, 1), "max": profit_max,
        "details": profit_details,
        "summary": f"得分 {round(profit_score, 1)}/{profit_max}",
    })
    total_score += profit_score
    total_weight += profit_max

    # ---- 3. 现金质量 (Cash Quality) - 权重20 ----
    cash_score = 0
    cash_max = 20
    cash_details = []

    # 3a. 经营现金流正负
    ocf = val(latest_cf, "NETCASH_OPERATE")
    if ocf is not None:
        if ocf > 0:
            pts = 8
            label = "正面"
        else:
            pts = 0
            label = "负值"
        cash_score += pts
        cash_details.append({
            "item": "经营现金流",
            "value": f"{ocf:.2f}亿",
            "desc": f"经营活动现金流净额 = {ocf:.2f}亿",
            "score": pts, "max": 8, "verdict": f"{'✅ 正面造血' if pts > 0 else '❌ 净流出'}",
        })

    # 3b. 经营现金流/净利润比
    net_profit_val = val(latest_ps, "EFFECT_NETPROFIT") or val(latest_ps, "PARENT_NETPROFIT")
    if ocf is not None and net_profit_val is not None and net_profit_val > 0:
        ratio = ocf / net_profit_val
        if ratio > 1.0:
            pts = 8
            label = "利润质量高"
        elif ratio > 0.5:
            pts = 5
            label = "利润质量一般"
        elif ratio > 0:
            pts = 3
            label = "利润质量低"
        else:
            pts = 0
            label = "利润为纸面利润"
        cash_score += pts
        cash_details.append({
            "item": "经营现金流/净利润",
            "value": f"{ratio:.2f}",
            "desc": f"经营现金流{ocf:.2f}亿 ÷ 净利润{net_profit_val:.2f}亿 = {ratio:.2f}",
            "score": pts, "max": 8, "verdict": f"{'✅' if pts > 5 else ('⚠️' if pts > 2 else '❌')} {label}",
        })

    # 3c. 现金余额
    cash_bal = val(latest_cf, "CASH_BALANCE") or val(latest_bs, "MONETARYFUNDS")
    if cash_bal is not None and cash_bal > 0:
        # 与营收比较
        if revenue and revenue > 0:
            cash_ratio = cash_bal / revenue * 100
            if cash_ratio > 30:
                pts = 4
                label = "现金充裕"
            elif cash_ratio > 10:
                pts = 3
                label = "合理"
            else:
                pts = 1
                label = "偏紧"
            cash_score += pts
            cash_details.append({
                "item": "现金/营收比",
                "value": f"{cash_ratio:.1f}%",
                "desc": f"现金余额{cash_bal:.1f}亿 ÷ 营收{revenue:.1f}亿 = {cash_ratio:.1f}%",
                "score": pts, "max": 4, "verdict": f"{'✅' if pts > 2 else '⚠️'} {label}",
            })

    dimensions.append({
        "name": "现金质量",
        "icon": "💵",
        "score": round(cash_score, 1), "max": cash_max,
        "details": cash_details,
        "summary": f"得分 {round(cash_score, 1)}/{cash_max}",
    })
    total_score += cash_score
    total_weight += cash_max

    # ---- 4. 成长性 (Growth) - 权重20 ----
    growth_score = 0
    growth_max = 20
    growth_details = []

    # 4a. 营收增速（最新2期利润表比较）
    if ps and len(ps) >= 2:
        rev_cur = val(ps[0]["items"], "TOTAL_OPERATE_INCOME")
        rev_prev = val(ps[1]["items"], "TOTAL_OPERATE_INCOME")
        if rev_cur is not None and rev_prev is not None and rev_prev > 0:
            rev_growth = (rev_cur - rev_prev) / rev_prev * 100
            if rev_growth > 30:
                pts = 7
            elif rev_growth > 15:
                pts = 6
            elif rev_growth > 0:
                pts = 4
            elif rev_growth > -10:
                pts = 2
            else:
                pts = 0
            growth_score += pts
            growth_details.append({
                "item": "营收增速(末2期)",
                "value": f"{rev_growth:+.2f}%",
                "desc": f"最新{ps[0]['period']}营收{rev_cur:.2f}亿 vs 上期{rev_prev:.2f}亿",
                "score": pts, "max": 7,
                "verdict": f"{'✅ 高增长' if rev_growth > 15 else ('✅ 正增长' if rev_growth > 0 else '⚠️ 下滑')}",
            })

    # 4b. 利润增速
    if ps and len(ps) >= 2:
        np_cur = val(ps[0]["items"], "EFFECT_NETPROFIT") or val(ps[0]["items"], "PARENT_NETPROFIT")
        np_prev = val(ps[1]["items"], "EFFECT_NETPROFIT") or val(ps[1]["items"], "PARENT_NETPROFIT")
        if np_cur is not None and np_prev is not None and np_prev != 0:
            np_growth = (np_cur - np_prev) / abs(np_prev) * 100
            # 检查是增收不增利
            rev_growth_for_check = None
            rev_cur = val(ps[0]["items"], "TOTAL_OPERATE_INCOME")
            rev_prev = val(ps[1]["items"], "TOTAL_OPERATE_INCOME")
            if rev_cur and rev_prev and rev_prev > 0:
                rev_growth_for_check = (rev_cur - rev_prev) / rev_prev * 100

            if np_growth > 30:
                pts = 7
                label = "爆发增长"
            elif np_growth > 15:
                pts = 6
                label = "高增长"
            elif np_growth > 0:
                pts = 4
                label = "正增长"
            elif np_growth > -15:
                pts = 2
                label = "小幅下滑"
            else:
                pts = 0
                label = "大幅下滑"

            # 增收不增利检测
            extra = ""
            if rev_growth_for_check and rev_growth_for_check > 5 and np_growth < -5:
                extra = "（增收不增利 ⚠️）"
            elif rev_growth_for_check and rev_growth_for_check < -5 and np_growth > 5:
                extra = "（减收增利，或有一次性收益）"

            growth_score += pts
            growth_details.append({
                "item": "利润增速(末2期)",
                "value": f"{np_growth:+.2f}%",
                "desc": f"净利润{np_cur:.2f}亿 vs 上期{np_prev:.2f}亿 {extra}",
                "score": pts, "max": 7,
                "verdict": f"{'✅' if pts > 3 else '⚠️'} {label}{extra}",
            })

    # 4c. 三期的营收趋势
    if ps and len(ps) >= 3:
        revs = []
        for i in range(min(3, len(ps))):
            r = val(ps[i]["items"], "TOTAL_OPERATE_INCOME")
            if r is not None:
                revs.append(r)
        if len(revs) == 3:
            if revs[0] > revs[1] > revs[2]:
                pts = 6
                label = "持续增长"
            elif revs[0] > revs[2]:
                pts = 4
                label = "波动向上"
            elif revs[0] < revs[2]:
                pts = 1
                label = "持续下滑"
            else:
                pts = 3
                label = "波动"
            growth_score += pts
            growth_details.append({
                "item": "近3期营收趋势",
                "value": f"{revs[0]:.1f}→{revs[1]:.1f}→{revs[2]:.1f}亿",
                "desc": f"{ps[0]['period']}:{revs[0]:.1f}亿 → {ps[1]['period']}:{revs[1]:.1f}亿 → {ps[2]['period']}:{revs[2]:.1f}亿",
                "score": pts, "max": 6,
                "verdict": f"{'✅ 持续增长' if pts == 6 else ('✅ 波动向上' if pts == 4 else '⚠️ 趋势弱')}",
            })

    dimensions.append({
        "name": "成长性",
        "icon": "📈",
        "score": round(growth_score, 1), "max": growth_max,
        "details": growth_details,
        "summary": f"得分 {round(growth_score, 1)}/{growth_max}",
    })
    total_score += growth_score
    total_weight += growth_max

    # ---- 5. 运营效率 (Operating Efficiency) - 权重15 ----
    ops_score = 0
    ops_max = 15
    ops_details = []

    # 5a. 总费用率（从利润表计算：销售+管理+财务费用率）
    sale_exp = val(latest_ps, "SALE_EXPENSE")
    mgmt_exp = val(latest_ps, "MANAGE_EXPENSE")
    fin_exp = val(latest_ps, "FINANCE_EXPENSE")
    if revenue and revenue > 0:
        total_expense_ratio = 0
        count = 0
        if sale_exp is not None:
            total_expense_ratio += sale_exp / revenue * 100
            count += 1
        if mgmt_exp is not None:
            total_expense_ratio += mgmt_exp / revenue * 100
            count += 1
        if fin_exp is not None:
            total_expense_ratio += abs(fin_exp) / revenue * 100
            count += 1

        if count > 0:
            if total_expense_ratio < 5:
                pts = 6
                label = "费用控制优秀"
            elif total_expense_ratio < 10:
                pts = 5
                label = "费用控制良好"
            elif total_expense_ratio < 20:
                pts = 3
                label = "费用偏高"
            else:
                pts = 1
                label = "费用过高"
            ops_score += pts
            ops_details.append({
                "item": "总费用率",
                "value": f"{total_expense_ratio:.2f}%",
                "desc": f"销售{abs(sale_exp or 0):.2f}+管理{abs(mgmt_exp or 0):.2f}+财务{abs(fin_exp or 0):.2f}亿 ÷ 营收{revenue:.2f}亿",
                "score": pts, "max": 6, "verdict": f"{'✅' if pts > 4 else '⚠️'} {label}",
            })

    # 5b. 应收账款占营收比
    ar = val(latest_bs, "ACCOUNTS_RECE")
    note_rece = val(latest_bs, "NOTE_RECE")
    total_ar = (ar or 0) + (note_rece or 0)
    if revenue and revenue > 0 and total_ar > 0:
        ar_ratio = total_ar / revenue * 100
        if ar_ratio < 5:
            pts = 5
            label = "回款极佳"
        elif ar_ratio < 15:
            pts = 4
            label = "回款良好"
        elif ar_ratio < 30:
            pts = 2
            label = "回款一般"
        else:
            pts = 0
            label = "回款风险"
        ops_score += pts
        ops_details.append({
            "item": "应收/营收比",
            "value": f"{ar_ratio:.1f}%",
            "desc": f"应收账款{total_ar:.2f}亿 ÷ 营收{revenue:.2f}亿 = {ar_ratio:.1f}%",
            "score": pts, "max": 5, "verdict": f"{'✅' if pts > 3 else '⚠️'} {label}",
        })

    # 5c. 存货占比（存货/营收）
    inv = val(latest_bs, "INVENTORY")
    if inv is not None and revenue and revenue > 0:
        inv_ratio = inv / revenue * 100
        if inv_ratio < 10:
            pts = 4
            label = "存货低"
        elif inv_ratio < 30:
            pts = 3
            label = "存货合理"
        elif inv_ratio < 50:
            pts = 1
            label = "存货偏高"
        else:
            pts = 0
            label = "存货过高"
        ops_score += pts
        ops_details.append({
            "item": "存货/营收比",
            "value": f"{inv_ratio:.1f}%",
            "desc": f"存货{inv:.2f}亿 ÷ 营收{revenue:.2f}亿 = {inv_ratio:.1f}%",
            "score": pts, "max": 4, "verdict": f"{'✅' if pts > 2 else '⚠️'} {label}",
        })

    dimensions.append({
        "name": "运营效率",
        "icon": "⚙️",
        "score": round(ops_score, 1), "max": ops_max,
        "details": ops_details,
        "summary": f"得分 {round(ops_score, 1)}/{ops_max}",
    })
    total_score += ops_score
    total_weight += ops_max

    # ---- 最终综合 ----
    pct = total_score / total_weight * 100 if total_weight > 0 else 0
    if pct >= 85:
        overall = "优秀"
        emoji = "🟢"
    elif pct >= 65:
        overall = "良好"
        emoji = "🟡"
    elif pct >= 45:
        overall = "一般"
        emoji = "🟠"
    else:
        overall = "较差"
        emoji = "🔴"

    return {
        "total_score": round(total_score, 1),
        "total_max": total_weight,
        "total_pct": round(pct, 1),
        "overall": overall,
        "emoji": emoji,
        "dimensions": dimensions,
    }


@router.get("/statements/{code}")
def financial_statements(code: str):
    """三张财务报表（资产负债表、现金流量表、利润表）+ 健康评分"""
    from backend.routers.analysis import _get_stock_list
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")

    try:
        balance_sheet = _get_bs_items(code)
    except Exception:
        balance_sheet = None
    try:
        cash_flow = _get_cf_items(code)
    except Exception:
        cash_flow = None
    try:
        profit_sheet = _get_ps_items(code)
    except Exception:
        profit_sheet = None

    # 计算健康评分
    health = _compute_health_score(code)

    # 将字段名转为中文标签
    def labelize(rows):
        if not rows:
            return rows
        for row in rows:
            row["items"] = {_BS_LABELS.get(k, k): v for k, v in row["items"].items()}
        return rows

    return {
        "code": code,
        "name": name,
        "balance_sheet": labelize(balance_sheet),
        "cash_flow": labelize(cash_flow),
        "profit_sheet": labelize(profit_sheet),
        "health_score": health,
    }


# ============================================================
# 8. 综合基本面分析（6大维度 + 同行对比 + 管理层）
# ============================================================
# 能力维度的中文映射
_DIM_LABELS = {
    "growth": {"name": "成长能力", "icon": "📈", "weight": 20},
    "profitability": {"name": "盈利能力", "icon": "💰", "weight": 25},
    "cashflow": {"name": "现金流能力", "icon": "💵", "weight": 20},
    "operations": {"name": "运营能力", "icon": "⚙️", "weight": 15},
    "solvency": {"name": "偿债能力", "icon": "🏛️", "weight": 20},
}


def _get_industry_from_code(code: str) -> str:
    """从CSV获取股票所属行业"""
    from datetime import date, timedelta
    today = date.today()
    for i in range(10):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            match = df[df["代码"] == code]
            if not match.empty:
                return str(match.iloc[0].get("所属行业", ""))
            break
    return ""


def _get_all_stocks_in_industry(industry: str) -> list[str]:
    """获取该行业所有股票代码"""
    from datetime import date, timedelta
    today = date.today()
    for i in range(10):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            match = df[df["所属行业"] == industry].copy()
            if not match.empty:
                match["总市值"] = match["总市值"].astype(str).str.replace(",", "", regex=False)
                match["总市值"] = pd.to_numeric(match["总市值"], errors="coerce")
                codes = match.sort_values("总市值", ascending=False)["代码"].head(10).tolist()
                return codes
            break
    return []


@router.get("/comprehensive/{code}")
def comprehensive_analysis(code: str):
    """综合基本面分析：6大维度 + 同行对比 + 管理层分析"""
    import akshare as ak
    from backend.routers.analysis import _get_stock_list

    stock_map = _get_stock_list()
    name = stock_map.get(code, "")
    market = "SZ" if code.startswith(("0", "3", "2")) else "SH"
    result = {"code": code, "name": name}

    # ---- 1. 财务分析指标（核心数据源） ----
    indicators = {}
    try:
        df_ind = ak.stock_financial_analysis_indicator(symbol=code, start_year="2023")
        df_ind = df_ind.sort_values("日期", ascending=False)
        records = df_ind.to_dict("records")
        indicators = {"raw": records, "latest": records[0] if records else {}}
    except Exception as e:
        indicators = {"raw": [], "latest": {}, "error": str(e)}

    result["indicators"] = indicators
    lat = indicators.get("latest", {})

    def flt(v):
        if v is None or v == "" or v != v:
            return None
        try:
            return round(float(v), 2)
        except (ValueError, TypeError):
            return None

    def fmt(v, suffix=""):
        vv = flt(v)
        if vv is None:
            return None
        return vv

    # ---- 2. 六大维度评分 ----
    dimensions = []

    # 2a. 成长能力
    growth_items = []
    rev_growth = fmt(lat.get("主营业务收入增长率(%)"))
    profit_growth = fmt(lat.get("净利润增长率(%)"))
    asset_growth = fmt(lat.get("总资产增长率(%)"))
    net_asset_growth = fmt(lat.get("净资产增长率(%)"))

    g_score = 0
    if rev_growth is not None:
        g_pts = min(7, max(0, (rev_growth + 10) / 30 * 7)) if rev_growth > -10 else 0
        g_score += g_pts
        growth_items.append({"label": "营收增长率", "value": f"{rev_growth:+.2f}%", "score": round(g_pts, 1), "max": 7,
                             "verdict": "高增长" if rev_growth > 20 else ("正增长" if rev_growth > 0 else "下滑")})
    if profit_growth is not None:
        p_pts = min(7, max(0, (profit_growth + 15) / 35 * 7)) if profit_growth > -15 else 0
        g_score += p_pts
        growth_items.append({"label": "净利润增长率", "value": f"{profit_growth:+.2f}%", "score": round(p_pts, 1), "max": 7,
                             "verdict": "爆发" if profit_growth > 30 else ("增长" if profit_growth > 0 else "下滑")})
    if asset_growth is not None:
        a_pts = min(6, max(0, asset_growth / 15 * 6))
        g_score += a_pts
        growth_items.append({"label": "总资产增长率", "value": f"{asset_growth:+.2f}%", "score": round(a_pts, 1), "max": 6,
                             "verdict": "扩张中" if asset_growth > 10 else ("稳定" if asset_growth > 0 else "收缩")})

    dimensions.append({
        "key": "growth", "name": "成长能力", "icon": "📈",
        "score": round(g_score, 1), "max": 20,
        "items": growth_items,
    })

    # 2b. 盈利能力
    profit_items = []
    gross_margin = fmt(lat.get("销售毛利率(%)"))
    net_margin = fmt(lat.get("销售净利率(%)"))
    roe = fmt(lat.get("净资产收益率(%)"))
    roa = fmt(lat.get("总资产利润率(%)"))

    p_score = 0
    if gross_margin is not None:
        gm_pts = min(8, gross_margin / 50 * 8)
        p_score += gm_pts
        profit_items.append({"label": "毛利率", "value": f"{gross_margin:.2f}%", "score": round(gm_pts, 1), "max": 8,
                             "verdict": "极高" if gross_margin > 50 else ("高" if gross_margin > 25 else ("中" if gross_margin > 10 else "低"))})
    if net_margin is not None:
        nm_pts = min(9, max(0, net_margin / 15 * 9))
        p_score += nm_pts
        profit_items.append({"label": "净利率", "value": f"{net_margin:.2f}%", "score": round(nm_pts, 1), "max": 9,
                             "verdict": "极高" if net_margin > 20 else ("优秀" if net_margin > 10 else ("良好" if net_margin > 5 else "偏低"))})
    if roe is not None:
        roe_pts = min(8, max(0, roe / 20 * 8))
        p_score += roe_pts
        profit_items.append({"label": "ROE", "value": f"{roe:.2f}%", "score": round(roe_pts, 1), "max": 8,
                             "verdict": "极强" if roe > 20 else ("优秀" if roe > 15 else ("良好" if roe > 10 else "一般"))})

    dimensions.append({
        "key": "profitability", "name": "盈利能力", "icon": "💰",
        "score": round(p_score, 1), "max": 25,
        "items": profit_items,
    })

    # 2c. 现金流能力
    cf_items = []
    ocf_ps = fmt(lat.get("每股经营性现金流(元)"))
    ocf_sales_ratio = fmt(lat.get("经营现金净流量对销售收入比率(%)"))
    ocf_profit_ratio = fmt(lat.get("经营现金净流量与净利润的比率(%)"))
    ocf_debt_ratio = fmt(lat.get("经营现金净流量对负债比率(%)"))

    cf_score = 0
    if ocf_ps is not None:
        cf_pts = min(6, max(0, (ocf_ps + 1) / 3 * 6))
        cf_score += cf_pts
        cf_items.append({"label": "每股经营现金流", "value": f"{ocf_ps:.2f}元", "score": round(cf_pts, 1), "max": 6,
                         "verdict": "充足" if ocf_ps > 1 else ("一般" if ocf_ps > 0 else "为负")})
    if ocf_profit_ratio is not None:
        ratio = fmt(ocf_profit_ratio)
        if ratio and ratio > 0:
            cf_pts = min(8, ratio / 150 * 8)
            cf_score += cf_pts
            label = "利润质量高" if ratio > 100 else ("利润质量中" if ratio > 50 else "利润质量低")
        else:
            cf_pts = 0
            label = "净利润无现金支撑"
        cf_items.append({"label": "OCF/净利润", "value": f"{ocf_profit_ratio:.2f}%" if ocf_profit_ratio else "N/A", "score": round(cf_pts, 1), "max": 8,
                         "verdict": label})
    if ocf_sales_ratio is not None:
        cf_pts = min(6, max(0, ocf_sales_ratio / 15 * 6))
        cf_score += cf_pts
        cf_items.append({"label": "OCF/营收", "value": f"{ocf_sales_ratio:.2f}%", "score": round(cf_pts, 1), "max": 6,
                         "verdict": "造血强" if ocf_sales_ratio > 15 else ("正常" if ocf_sales_ratio > 5 else "偏低")})

    dimensions.append({
        "key": "cashflow", "name": "现金流能力", "icon": "💵",
        "score": round(cf_score, 1), "max": 20,
        "items": cf_items,
    })

    # 2d. 运营能力
    op_items = []
    inv_turnover = fmt(lat.get("存货周转率(次)"))
    ar_turnover = fmt(lat.get("应收账款周转率(次)"))
    asset_turnover = fmt(lat.get("总资产周转率(次)"))
    three_cost_ratio = fmt(lat.get("三项费用比重"))

    op_score = 0
    if inv_turnover is not None:
        inv_pts = min(4, inv_turnover / 10 * 4)
        op_score += inv_pts
        op_items.append({"label": "存货周转率", "value": f"{inv_turnover:.2f}次", "score": round(inv_pts, 1), "max": 4,
                         "verdict": "快" if inv_turnover > 5 else ("中" if inv_turnover > 2 else "慢")})
    if ar_turnover is not None:
        ar_pts = min(4, ar_turnover / 20 * 4)
        op_score += ar_pts
        op_items.append({"label": "应收周转率", "value": f"{ar_turnover:.2f}次", "score": round(ar_pts, 1), "max": 4,
                         "verdict": "回款快" if ar_turnover > 10 else ("正常" if ar_turnover > 5 else "回款慢")})
    if asset_turnover is not None:
        at_pts = min(4, asset_turnover / 1.5 * 4)
        op_score += at_pts
        op_items.append({"label": "总资产周转率", "value": f"{asset_turnover:.2f}次", "score": round(at_pts, 1), "max": 4,
                         "verdict": "高" if asset_turnover > 1 else ("中" if asset_turnover > 0.5 else "低")})
    if three_cost_ratio is not None:
        tc_pts = min(3, max(0, (50 - three_cost_ratio) / 50 * 3))
        op_score += tc_pts
        op_items.append({"label": "三项费用比重", "value": f"{three_cost_ratio:.2f}%", "score": round(tc_pts, 1), "max": 3,
                         "verdict": "费用控制好" if three_cost_ratio < 10 else ("合理" if three_cost_ratio < 25 else "费用偏高")})

    dimensions.append({
        "key": "operations", "name": "运营能力", "icon": "⚙️",
        "score": round(op_score, 1), "max": 15,
        "items": op_items,
    })

    # 2e. 偿债能力
    sol_items = []
    current_ratio = fmt(lat.get("流动比率"))
    quick_ratio = fmt(lat.get("速动比率"))
    cash_ratio = fmt(lat.get("现金比率(%)"))
    debt_ratio_pct = fmt(lat.get("资产负债率(%)"))

    s_score = 0
    if current_ratio is not None:
        cr_pts = min(6, current_ratio / 2 * 6)
        s_score += cr_pts
        sol_items.append({"label": "流动比率", "value": f"{current_ratio:.2f}", "score": round(cr_pts, 1), "max": 6,
                          "verdict": "健康" if current_ratio > 1.5 else ("偏低" if current_ratio > 1 else "风险")})
    if quick_ratio is not None:
        qr_pts = min(5, quick_ratio / 1.5 * 5)
        s_score += qr_pts
        sol_items.append({"label": "速动比率", "value": f"{quick_ratio:.2f}", "score": round(qr_pts, 1), "max": 5,
                          "verdict": "健康" if quick_ratio > 1 else ("偏低" if quick_ratio > 0.5 else "风险")})
    if debt_ratio_pct is not None:
        dr_pts = min(6, max(0, (85 - debt_ratio_pct) / 85 * 6))
        s_score += dr_pts
        sol_items.append({"label": "资产负债率", "value": f"{debt_ratio_pct:.2f}%", "score": round(dr_pts, 1), "max": 6,
                          "verdict": "低杠杆" if debt_ratio_pct < 40 else ("合理" if debt_ratio_pct < 60 else ("偏高" if debt_ratio_pct < 75 else "过高"))})
    if cash_ratio is not None:
        ca_pts = min(3, cash_ratio / 50 * 3)
        s_score += ca_pts
        sol_items.append({"label": "现金比率", "value": f"{cash_ratio:.2f}%", "score": round(ca_pts, 1), "max": 3,
                          "verdict": "充裕" if cash_ratio > 50 else ("一般" if cash_ratio > 20 else "偏紧")})

    dimensions.append({
        "key": "solvency", "name": "偿债能力", "icon": "🏛️",
        "score": round(s_score, 1), "max": 20,
        "items": sol_items,
    })

    result["dimensions"] = dimensions

    # 总分
    total_s = sum(d["score"] for d in dimensions)
    total_m = sum(d["max"] for d in dimensions)
    result["total_score"] = round(total_s, 1)
    result["total_max"] = total_m
    result["total_pct"] = round(total_s / total_m * 100, 1) if total_m > 0 else 0

    # ---- 3. 管理层分析 ----
    management = {}
    # 3a. 管理层持股变动（近2年）
    try:
        mgmt_df = ak.stock_management_change_ths(symbol=code)
        mgmt_df = mgmt_df.sort_values("变动日期", ascending=False)
        recent = mgmt_df.head(10)
        mgmt_changes = []
        insider_buy = 0
        insider_sell = 0
        for _, r in recent.iterrows():
            chg = str(r.get("变动数量", "")).strip()
            qty = None
            if "增持" in chg:
                try:
                    qty = float(chg.replace("增持", "").replace("万", "").strip())
                    insider_buy += qty
                except:
                    pass
            elif "减持" in chg:
                try:
                    qty = float(chg.replace("减持", "").replace("万", "").strip())
                    insider_sell += qty
                except:
                    pass
            mgmt_changes.append({
                "date": str(r.get("变动日期", "")),
                "person": str(r.get("变动人", "")),
                "action": chg[:4],
                "price": str(r.get("交易均价", "N/A")),
                "remaining": str(r.get("剩余股数", "N/A")),
            })
        management["changes"] = mgmt_changes[:8]
        management["buy_total"] = round(insider_buy, 2)
        management["sell_total"] = round(insider_sell, 2)
        management["net_action"] = "净增持" if insider_buy > insider_sell else "净减持"
    except Exception:
        management["changes"] = []
        management["error"] = "暂无管理层持股变动数据"

    # 3b. 主要股东
    try:
        sh_df = ak.stock_main_stock_holder(stock=code)
        # 取最新报告期
        sh_df = sh_df.sort_values("截至日期", ascending=False)
        latest_date = sh_df.iloc[0].get("截至日期")
        sh_df = sh_df[sh_df["截至日期"] == latest_date].copy()
        # 获取股东总数（从第一行）
        total_holders = sh_df.iloc[0].get("股东总数") if "股东总数" in sh_df.columns else None
        if total_holders is not None and isinstance(total_holders, float) and total_holders != total_holders:
            total_holders = None
        management["total_holders"] = flt(total_holders) if total_holders else None
        # 按持股比例排序，去重（同一股东多类别合并）
        sh_df = sh_df.dropna(subset=["持股比例"])
        sh_df["持股比例"] = pd.to_numeric(sh_df["持股比例"], errors="coerce")
        sh_df = sh_df.sort_values("持股比例", ascending=False)
        # 合并同名股东的不同股本性质
        sh_df = sh_df.groupby("股东名称", as_index=False).agg({
            "持股比例": "sum",
            "股本性质": lambda x: ",".join(x.unique()),
            "截至日期": "first",
        })
        sh_df = sh_df.sort_values("持股比例", ascending=False)
        top_holders = []
        for _, r in sh_df.head(10).iterrows():
            top_holders.append({
                "name": str(r.get("股东名称", "")),
                "ratio": round(float(r.get("持股比例", 0)), 2),
                "nature": str(r.get("股本性质", "")),
                "date": str(r.get("截至日期", "")),
            })
        management["top_holders"] = top_holders
    except Exception:
        management["top_holders"] = []

    result["management"] = management

    # ---- 4. 同行对比 ----
    industry = _get_industry_from_code(code)
    result["industry"] = industry
    peer_comparison = {}

    # ---- 4a. 获取本股原始报表数据（用于验证比率计算） ----
    raw_bs = None
    raw_ps = None
    raw_cf = None
    raw_fin = None
    try:
        raw_bs = _get_bs_items(code)
    except Exception:
        pass
    try:
        raw_ps = _get_ps_items(code)
    except Exception:
        pass
    try:
        raw_cf = _get_cf_items(code)
    except Exception:
        pass
    try:
        raw_fin = _get_financial_summary(code)
    except Exception:
        pass

    def _raw_val(rows, key):
        """从最近一期报表提取原始值（亿）"""
        if not rows:
            return None
        items = rows[0].get("items", {})
        v = items.get(key)
        if v is not None and isinstance(v, (int, float)) and v == v:
            return round(v, 2)
        return None

    def _raw_fin_val(key):
        """从财务摘要提取原始值"""
        if not raw_fin or not raw_fin.get("records"):
            return None
        last = raw_fin["records"][-1]
        v = last.get(key)
        if v is None or v == "--" or v == "":
            return None
        try:
            return round(float(v), 2)
        except:
            return None

    # 整理原始数据
    raw_report = {}
    raw_report["报告期"] = raw_ps[0]["period"] if raw_ps else "N/A"

    # 利润表原始值
    raw_report["营业总收入"] = _raw_val(raw_ps, "TOTAL_OPERATE_INCOME")
    raw_report["营业成本"] = _raw_val(raw_ps, "OPERATE_COST")
    raw_report["净利润"] = _raw_val(raw_ps, "EFFECT_NETPROFIT") or _raw_val(raw_ps, "PARENT_NETPROFIT")
    raw_report["归母净利润"] = _raw_val(raw_ps, "PARENT_NETPROFIT")
    raw_report["销售费用"] = _raw_val(raw_ps, "SALE_EXPENSE")
    raw_report["管理费用"] = _raw_val(raw_ps, "MANAGE_EXPENSE")
    raw_report["研发费用"] = _raw_val(raw_ps, "ME_RESEARCH_EXPENSE")
    raw_report["财务费用"] = _raw_val(raw_ps, "FINANCE_EXPENSE")

    # 上期营收/利润（用于计算增长率验证）
    raw_report["上期营收"] = _raw_val(raw_ps[1:], "TOTAL_OPERATE_INCOME") if raw_ps and len(raw_ps) > 1 else None
    raw_report["上期净利润"] = _raw_val(raw_ps[1:], "EFFECT_NETPROFIT") or _raw_val(raw_ps[1:], "PARENT_NETPROFIT") if raw_ps and len(raw_ps) > 1 else None

    # 资产负债表原始值（尝试多种可能的列名）
    raw_report["资产总计"] = _raw_val(raw_bs, "TOTAL_ASSETS")
    raw_report["负债合计"] = _raw_val(raw_bs, "LIAB_BALANCE") or _raw_val(raw_bs, "CURRENT_LIAB_BALANCE") or _raw_val(raw_bs, "TOTAL_LIABILITIES")
    raw_report["流动资产"] = _raw_val(raw_bs, "CURRENT_ASSET_BALANCE") or _raw_val(raw_bs, "CURRENT_ASSETS")
    raw_report["流动负债"] = _raw_val(raw_bs, "CURRENT_LIAB_BALANCE") or _raw_val(raw_bs, "CURRENT_LIABILITIES")
    raw_report["货币资金"] = _raw_val(raw_bs, "MONETARYFUNDS")
    raw_report["应收账款"] = _raw_val(raw_bs, "ACCOUNTS_RECE")
    raw_report["存货"] = _raw_val(raw_bs, "INVENTORY")
    raw_report["固定资产"] = _raw_val(raw_bs, "FIXED_ASSET")
    raw_report["短期借款"] = _raw_val(raw_bs, "SHORT_LOAN")
    raw_report["长期借款"] = _raw_val(raw_bs, "LONG_LOAN")
    raw_report["股东权益"] = _raw_val(raw_bs, "EQUITY_BALANCE") or _raw_val(raw_bs, "TOTAL_EQUITY") or _raw_val(raw_bs, "OWNERS_EQUITY")

    # 现金流量表原始值
    raw_report["经营现金流"] = _raw_val(raw_cf, "NETCASH_OPERATE")
    raw_report["投资现金流"] = _raw_val(raw_cf, "NETCASH_INVEST")
    raw_report["筹资现金流"] = _raw_val(raw_cf, "NETCASH_FINANCE")

    # 财务摘要原始值
    raw_report["净资产收益率_ROE"] = _raw_fin_val("净资产收益率")
    raw_report["销售毛利率"] = _raw_fin_val("销售毛利率")
    raw_report["销售净利率"] = _raw_fin_val("销售净利率")
    raw_report["资产负债率"] = _raw_fin_val("资产负债率")
    raw_report["基本每股收益"] = _raw_fin_val("基本每股收益")
    raw_report["每股净资产"] = _raw_fin_val("每股净资产")
    raw_report["每股经营现金流"] = _raw_fin_val("每股经营现金流")
    raw_report["流动比率_fin"] = _raw_fin_val("流动比率")
    raw_report["速动比率_fin"] = _raw_fin_val("速动比率")

    # 补填缺失的负债和权益（用资产负债率反推）
    total_assets = raw_report.get("资产总计")
    debt_ratio = raw_report.get("资产负债率")
    if total_assets and debt_ratio and raw_report.get("负债合计") is None:
        raw_report["负债合计"] = round(total_assets * debt_ratio / 100, 2)
    if total_assets and raw_report.get("股东权益") is None:
        raw_report["股东权益"] = round(total_assets - (raw_report.get("负债合计") or 0), 2)

    peer_comparison["raw_report"] = raw_report

    # ---- 4b. 费用率分析 ----
    expense_data = _get_expense_data(code)
    if expense_data:
        result["expense_analysis"] = expense_data

    if industry:
        peer_codes = _get_all_stocks_in_industry(industry)
        # 取前5大同行（不包括自己）
        peer_codes = [c for c in peer_codes if c != code][:5]

        # 获取同行的关键指标
        peer_metrics = {k: [] for k in [
            "主营业务收入增长率(%)", "净利润增长率(%)",
            "销售毛利率(%)", "销售净利率(%)", "净资产收益率(%)",
            "每股经营性现金流(元)", "经营现金净流量与净利润的比率(%)",
            "存货周转率(次)", "应收账款周转率(次)", "总资产周转率(次)", "三项费用比重",
            "流动比率", "速动比率", "资产负债率(%)",
        ]}

        for pc in peer_codes:
            try:
                pdf = ak.stock_financial_analysis_indicator(symbol=pc, start_year="2024")
                if not pdf.empty:
                    plat = pdf.sort_values("日期", ascending=False).iloc[0]
                    for k in peer_metrics:
                        v = plat.get(k)
                        if v is not None and v != "" and v == v:
                            try:
                                peer_metrics[k].append(float(v))
                            except:
                                pass
            except Exception:
                continue

        # 计算同行均值，与本股对比
        company_ind = indicators.get("raw", [])
        company_latest = company_ind[0] if company_ind else {}

        comparisons = []
        key_labels = {
            "主营业务收入增长率(%)": ("营收增长率", "%", "growth"),
            "净利润增长率(%)": ("净利润增长率", "%", "growth"),
            "销售毛利率(%)": ("毛利率", "%", "profitability"),
            "销售净利率(%)": ("净利率", "%", "profitability"),
            "净资产收益率(%)": ("ROE", "%", "profitability"),
            "每股经营性现金流(元)": ("每股经营现金流", "元", "cashflow"),
            "经营现金净流量与净利润的比率(%)": ("OCF/净利润", "%", "cashflow"),
            "存货周转率(次)": ("存货周转率", "次", "operations"),
            "应收账款周转率(次)": ("应收周转率", "次", "operations"),
            "总资产周转率(次)": ("总资产周转率", "次", "operations"),
            "三项费用比重": ("三项费用比重", "%", "operations"),
            "流动比率": ("流动比率", "", "solvency"),
            "速动比率": ("速动比率", "", "solvency"),
            "资产负债率(%)": ("资产负债率", "%", "solvency"),
        }

        def _build_raw_calc(key, raw_report):
            """给出每个比率的计算公式和原始数值"""
            r = raw_report
            formulas = {
                "主营业务收入增长率(%)": f"营收增长率 = 本期营收({r.get('营业总收入','?')}亿 - 上期营收({r.get('上期营收','?')}亿) / 上期营收 × 100%",
                "净利润增长率(%)": f"净利润增长率 = 本期净利润({r.get('净利润','?')}亿 - 上期净利润({r.get('上期净利润','?')}亿) / 上期净利润 × 100%",
                "销售毛利率(%)": f"毛利率 = (营收({r.get('营业总收入','?')}亿 - 成本({r.get('营业成本','?')}亿) / 营收 × 100%",
                "销售净利率(%)": f"净利率 = 净利润({r.get('净利润','?')}亿 / 营收({r.get('营业总收入','?')}亿 × 100%",
                "净资产收益率(%)": f"ROE = 净利润({r.get('净利润','?')}亿 / 股东权益({r.get('股东权益','?')}亿 × 100%",
                "每股经营性现金流(元)": f"每股经营现金流 = 经营现金流 / 总股本",
                "经营现金净流量与净利润的比率(%)": f"OCF/净利润 = 经营现金流({r.get('经营现金流','?')}亿 / 净利润({r.get('净利润','?')}亿 × 100%",
                "存货周转率(次)": f"存货周转率 = 营业成本({r.get('营业成本','?')}亿 / 存货({r.get('存货','?')}亿",
                "应收账款周转率(次)": f"应收周转率 = 营收({r.get('营业总收入','?')}亿 / 应收账款({r.get('应收账款','?')}亿",
                "总资产周转率(次)": f"总资产周转率 = 营收({r.get('营业总收入','?')}亿 / 资产总计({r.get('资产总计','?')}亿",
                "三项费用比重": f"三项费用比重 = (销售+管理+财务费用) / 营收 × 100%",
                "流动比率": f"流动比率 = 流动资产({r.get('流动资产','?')}亿 / 流动负债({r.get('流动负债','?')}亿",
                "速动比率": f"速动比率 = (流动资产-存货) / 流动负债",
                "资产负债率(%)": f"资产负债率 = 负债合计({r.get('负债合计','?')}亿 / 资产总计({r.get('资产总计','?')}亿 × 100%",
            }
            return formulas.get(key, "")

        for k, (label, unit, cat) in key_labels.items():
            cv = company_latest.get(k)
            peers = peer_metrics.get(k, [])
            if cv is not None and peers:
                try:
                    cv_f = float(cv)
                    avg = sum(peers) / len(peers)
                    diff = cv_f - avg
                    # 判断优劣：毛利率等正向指标越高越好，费用率/负债率越低越好
                    inverse = k in ("三项费用比重", "资产负债率(%)")
                    better = (diff > 0 and not inverse) or (diff < 0 and inverse)
                    # 计算公式说明
                    raw_calc = _build_raw_calc(k, raw_report)
                    comparisons.append({
                        "label": label,
                        "unit": unit,
                        "category": cat,
                        "company": round(cv_f, 2),
                        "peer_avg": round(avg, 2),
                        "diff": round(diff, 2),
                        "better": better,
                        "verdict": ("优于" if better else "落后于") + "行业",
                        "raw_calc": raw_calc,
                    })
                except:
                    pass

        peer_comparison["peers"] = peer_codes[:5]
        peer_comparison["comparisons"] = comparisons
        result["peer_comparison"] = peer_comparison

    # 清理NaN/Inf，确保JSON可序列化
    def _clean(obj):
        import math
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    return _clean(result)
