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
            df = pd.read_csv(path, encoding="utf-16", sep="\t")
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
            df = pd.read_csv(path, encoding="utf-16", sep="\t")
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
