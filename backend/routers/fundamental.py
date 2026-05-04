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

    def _row_to_stock(r):
        return {
            "code": str(r["代码"]).strip("'\""),
            "name": r["名称"],
            "price": float(r["最新"]) if pd.notna(r["最新"]) else 0,
            "change_pct": float(r["涨幅"]) if pd.notna(r["涨幅"]) else 0,
            "market_cap": float(r["总市值"]) if pd.notna(r["总市值"]) else 0,
        }

    # 头部股票（按涨幅）
    top_by_gain = []
    for _, r in sector_df.nlargest(5, "涨幅").iterrows():
        top_by_gain.append(_row_to_stock(r))

    # 龙头股（按总市值）
    top_by_mcap = []
    for _, r in sector_df.nlargest(5, "总市值").iterrows():
        top_by_mcap.append(_row_to_stock(r))

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
        "top_stocks": top_by_gain,
        "top_by_market_cap": top_by_mcap,
    }


# ============================================================
# 4. 供应链上下游（概念板块）
# ============================================================
_chain_cache = {}
_CHAIN_CACHE_TTL = 3600  # 1小时缓存

# 常见行业的供应链概念板块映射
_INDUSTRY_CHAIN_MAP = {
    "电池": {
        "上游-资源": ["锂矿概念"],
        "中游-材料": ["锂电池概念"],
        "下游-应用": ["新能源车", "储能概念", "充电桩"],
        "相关": ["固态电池", "动力电池回收"],
    },
    "半导体": {
        "上游-设备材料": ["半导体概念", "光刻机(胶)"],
        "中游-设计制造": ["国产芯片", "第三代半导体"],
        "下游-封测应用": ["先进封装", "汽车芯片", "AI芯片"],
        "相关": ["存储芯片", "第四代半导体"],
    },
    "汽车零部件": {
        "上游-原材料": ["汽车热管理", "汽车轻量化"],
        "中游-零部件": ["汽车零部件", "一体化压铸"],
        "下游-整车": ["汽车整车", "新能源汽车"],
        "相关": ["汽车电子", "无人驾驶"],
    },
    "光伏设备": {
        "上游-原材料": ["硅能源", "有机硅"],
        "中游-电池组件": ["光伏概念", "HJT电池", "TOPCon电池"],
        "下游-运营": ["绿色电力"],
        "相关": ["储能概念", "碳中和"],
    },
    "白酒": {
        "上游-粮食": ["农业种植"],
        "中游-生产": ["白酒概念"],
        "下游-渠道": ["新零售", "电子商务"],
        "相关": ["食品饮料", "大消费"],
    },
    "证券": {
        "相关-同行": ["证券概念"],
        "相关-市场": ["参股券商", "互联网金融"],
    },
    "医疗器械": {
        "上游-材料": ["医疗耗材", "生物材料"],
        "中游-设备": ["医疗器械概念", "体外诊断"],
        "下游-服务": ["医疗服务", "互联网医疗"],
        "相关": ["医药电商"],
    },
    "软件开发": {
        "上游-基础设施": ["国产软件", "信创", "操作系统"],
        "相关-应用": ["人工智能", "数字经济", "云计算", "大数据"],
        "下游-行业": ["金融科技", "智慧政务"],
    },
    "航空装备Ⅱ": {
        "上游-材料": ["军工材料"],
        "中游-制造": ["航空发动机", "大飞机", "军工"],
        "相关": ["无人机", "商业航天"],
    },
    "军工电子Ⅱ": {
        "上游-元器件": ["军工电子", "军工信息化"],
        "中游-系统": ["军工", "卫星导航"],
        "相关": ["商业航天", "军民融合"],
    },
    "自动化设备": {
        "上游-核心部件": ["机器人概念", "机器视觉"],
        "中游-整机": ["工业母机", "工业自动化"],
        "下游-应用": ["智能物流"],
        "相关": ["人形机器人"],
    },
    "化学制品": {
        "上游-原料": ["氟化工", "磷化工", "煤化工"],
        "中游-生产": ["化工", "化工合成材料"],
        "下游-应用": ["可降解塑料", "电子化学品"],
        "相关": ["锂电池概念", "新材料"],
    },
    "化学原料": {
        "上游": ["氟化工", "磷化工", "煤化工"],
        "中游": ["化工", "化工合成材料"],
        "下游": ["锂电池概念", "可降解塑料"],
        "相关": ["新材料"],
    },
    "通信设备": {
        "上游-芯片": ["5G概念", "通信模组"],
        "中游-设备": ["通信设备", "光通信"],
        "下游-运营": ["电信运营", "数据中心"],
        "相关": ["物联网", "6G概念"],
    },
    "计算机设备": {
        "上游-零部件": ["存储芯片", "AI芯片"],
        "中游-整机": ["服务器", "计算机设备"],
        "下游-应用": ["云计算", "数据中心"],
        "相关": ["信创", "国产软件"],
    },
    "电力": {
        "上游-发电": ["绿色电力", "风电", "光伏概念"],
        "中游-传输": ["智能电网", "特高压"],
        "下游-服务": ["储能概念", "电力物联网"],
        "相关": ["碳中和", "充电桩"],
    },
    "电子化学品Ⅱ": {
        "上游-原料": ["氟化工", "磷化工"],
        "中游-材料": ["光刻胶", "半导体材料"],
        "下游-应用": ["半导体", "显示面板"],
        "相关": ["PCB概念"],
    },
}


def _get_supply_chain(sector: str | None) -> list | None:
    """获取行业供应链上下游的概念板块及代表股"""
    if not sector or sector == "--":
        return None

    import akshare as ak
    import time

    cache_key = f"chain_{sector}"
    now = time.time()
    cached = _chain_cache.get(cache_key)
    if cached and (now - cached["ts"]) < _CHAIN_CACHE_TTL:
        return cached["data"]

    chain_def = _INDUSTRY_CHAIN_MAP.get(sector)
    if not chain_def:
        return None

    try:
        boards_df = ak.stock_board_concept_name_em()
        board_map = {}
        for _, r in boards_df.iterrows():
            board_map[r["板块名称"]] = r["板块代码"]
    except Exception:
        return None

    result = []
    for role, board_names in chain_def.items():
        role_data = {"role": role, "boards": []}
        for bname in board_names:
            board_code = board_map.get(bname)
            if not board_code:
                continue
            try:
                cons_df = ak.stock_board_concept_cons_em(symbol=bname)
                top5 = cons_df.nlargest(5, "涨跌幅")[["代码", "名称", "最新价", "涨跌幅"]]
                stocks = []
                for _, r in top5.iterrows():
                    stocks.append({
                        "code": str(r["代码"]).strip(),
                        "name": r["名称"],
                        "price": float(r["最新价"]) if pd.notna(r["最新价"]) else 0,
                        "change_pct": float(r["涨跌幅"]) if pd.notna(r["涨跌幅"]) else 0,
                    })
                role_data["boards"].append({
                    "board_name": bname,
                    "board_code": board_code,
                    "stock_count": len(cons_df),
                    "top_stocks": stocks,
                })
            except Exception:
                continue
        if role_data["boards"]:
            result.append(role_data)

    _chain_cache[cache_key] = {"ts": now, "data": result}
    return result


# ============================================================
# 5. API 路由
# ============================================================
# ============================================================
# 6. 杜邦分析
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


_concept_board_cache = {}
_CONCEPT_CACHE_TTL = 300  # 5分钟

def _get_concept_board_data() -> dict:
    """获取概念板块实时行情并缓存"""
    global _concept_board_cache
    import time
    now = time.time()
    if _concept_board_cache and (now - _concept_board_cache.get("_ts", 0)) < _CONCEPT_CACHE_TTL:
        return _concept_board_cache
    
    try:
        import akshare as ak
        df = ak.stock_board_concept_name_em()
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
        return result
    except Exception:
        return _concept_board_cache or {}


def _lookup_board(board_name: str, board_data: dict) -> dict | None:
    """智能模糊匹配概念板块名称"""
    if not board_name or not board_data:
        return None
    # 1. 精确匹配
    if board_name in board_data:
        return board_data[board_name]
    
    # 2. 构建关键词（去除通用词后取2字以上的词）
    key_words = []
    for kw in [board_name, board_name[:2], board_name[:3]]:
        if len(kw) >= 2:
            key_words.append(kw)
    
    # 3. 对每个真实板块名打分
    best_match = None
    best_score = 0
    for real_name, info in board_data.items():
        if real_name.startswith("_"):
            continue
        score = 0
        # 子串包含
        if board_name in real_name:
            score += 10
        if real_name in board_name:
            score += 8
        # 关键词匹配
        for kw in key_words:
            if kw in real_name:
                score += 5
        if score > best_score:
            best_score = score
            best_match = info
    
    # 4. 阈值：至少5分才认为匹配
    if best_score >= 5:
        return best_match
    return None


def _analyze_industry_cycle(sector: str, industry_data: dict | None) -> dict | None:
    """行业景气周期 + 供需矛盾分析 + 量化预测"""
    if not industry_data:
        return None
    
    avg_chg = industry_data.get("avg_change", 0) or 0
    up_ratio = industry_data.get("up_ratio", 0) or 0
    rank = industry_data.get("rank")
    total = industry_data.get("total_sectors", 100) or 100
    stock_count = industry_data.get("stock_count", 0) or 0
    
    # ---- 1. 行业景气周期判定 ----
    rank_pct = round(rank / total * 100, 1) if rank else 50  # rank百分比(越小越好)
    
    if avg_chg > 3 and up_ratio > 70 and rank_pct < 20:
        cycle_stage = "过热期 🔥"
        cycle_score = 90
        cycle_desc = "板块涨幅大、上涨占比高、排名靠前，市场情绪亢奋，需警惕过热后回调风险"
        cycle_risk = "追高风险大，不建议新建仓位"
    elif avg_chg > 1 and up_ratio > 60 and rank_pct < 35:
        cycle_stage = "扩张期 🚀"
        cycle_score = 75
        cycle_desc = "板块整体强势，上涨家数占优，处于主升浪阶段，资金持续流入"
        cycle_risk = "趋势延续概率大，但需关注量能变化"
    elif avg_chg > 0 and up_ratio > 45:
        cycle_stage = "复苏期 🌱"
        cycle_score = 55
        cycle_desc = "板块温和上涨，涨跌接近平衡，但排名在改善，可能处于底部区域"
        cycle_risk = "方向未明，适合逐步建仓，不宜重仓"
    elif avg_chg > -2 and up_ratio > 30:
        cycle_stage = "调整期 📉"
        cycle_score = 35
        cycle_desc = "板块小幅下跌，市场情绪偏弱，可能是上升趋势中的正常调整"
        cycle_risk = "关注是否企稳，避免左侧抄底"
    else:
        cycle_stage = "衰退期 ❄️"
        cycle_score = 20
        cycle_desc = "板块明显下跌，多数个股走弱，资金流出明显，处于下行趋势"
        cycle_risk = "不宜参与，等待反转信号"
    
    # ---- 2. 产业链各环节供需矛盾分析 ----
    chain_map = _INDUSTRY_CHAIN_MAP.get(sector, {})
    board_data = _get_concept_board_data()
    chain_analysis = []
    chain_scores = []
    
    for stage_name, boards in chain_map.items():
        stage_items = []
        total_chg = 0
        valid_boards = 0
        
        for board in boards:
            info = _lookup_board(board, board_data)
            if info:
                up_ratio_b = info["up_count"] / max(info["up_count"] + info["down_count"], 1) * 100
                stage_items.append({
                    "name": board,
                    "change_pct": info["change_pct"],
                    "up_ratio": round(up_ratio_b, 1),
                    "leader": info["leader"],
                    "leader_chg": info["leader_chg"],
                })
                total_chg += info["change_pct"]
                valid_boards += 1
            else:
                stage_items.append({
                    "name": board,
                    "change_pct": None,
                    "up_ratio": None,
                    "leader": "--",
                    "leader_chg": None,
                })
        
        avg_stage_chg = round(total_chg / valid_boards, 2) if valid_boards > 0 else None
        
        # 判定该环节的供需状态
        if avg_stage_chg is not None and avg_stage_chg > 3 and any(i.get("up_ratio",0) and i["up_ratio"] > 75 for i in stage_items if i["up_ratio"]):
            status = "供不应求 🏭"
            status_score = 85
            status_desc = f"资金集中涌入，{valid_boards}个概念板块普涨，短期需求旺盛"
            opp_risk = "⚠️ 过热风险：涨幅过大可能短期回调，不宜追高"
        elif avg_stage_chg is not None and avg_stage_chg > 1:
            status = "需求旺盛 📈"
            status_score = 70
            status_desc = f"环节整体上涨，资金流入积极，供需格局向好"
            opp_risk = "✅ 机会：环节景气度高，关注领先股回调后机会"
        elif avg_stage_chg is not None and avg_stage_chg > -1:
            status = "供需平衡 ="
            status_score = 50
            status_desc = f"环节表现平稳，无明显供需失衡"
            opp_risk = "➡️ 中性：此环节暂不是主要矛盾，等待催化剂"
        elif avg_stage_chg is not None and avg_stage_chg > -3:
            status = "供给偏松 📉"
            status_score = 30
            status_desc = f"环节小幅下跌，供给略大于需求，短期承压"
            opp_risk = "🔍 关注：如果是上游环节走弱可能传导至下游"
        else:
            status = "供过于求 📦"
            status_score = 15
            status_desc = f"环节明显下跌，供给过剩或需求萎缩，资金流出"
            opp_risk = "🚫 风险：该环节产能过剩或需求不足，回避为主"
        
        chain_scores.append(status_score)
        
        chain_analysis.append({
            "stage": stage_name,
            "avg_change": avg_stage_chg,
            "status": status,
            "status_score": status_score,
            "desc": status_desc,
            "opp_risk": opp_risk,
            "boards": stage_items,
        })
    
    # 汇总整条产业链的供需矛盾评分（各环节均值）
    if chain_analysis:
        supply_score = round(sum(c["status_score"] for c in chain_analysis) / len(chain_analysis), 1)
        # 找出最紧张和最松弛的环节
        tightest = max(chain_analysis, key=lambda c: c["status_score"])
        loosest = min(chain_analysis, key=lambda c: c["status_score"])
        bottleneck = f"卡脖子环节在「{tightest['stage']}」（{tightest['status']}），"
        bottleneck += f"最薄弱环节在「{loosest['stage']}」（评分{loosest['status_score']}）" if loosest['stage'] != tightest['stage'] else f"整条链同向，需要重点关注"
        
        supply_demand = f"产业链评分{supply_score}分"
        supply_desc = bottleneck
        supply_outlook = f"上游→{chain_analysis[0]['status'] if chain_analysis else '—'} → 中游→{chain_analysis[1]['status'] if len(chain_analysis) > 1 else '—'} → 下游→{chain_analysis[2]['status'] if len(chain_analysis) > 2 else '—'}"
    else:
        supply_score = 50
        supply_demand = "无产业链数据"
        supply_desc = "该行业暂未建立产业链映射"
        supply_outlook = "" 
    
    # ---- 3. 量化预测 ----
    # 综合评分 = 景气周期分 * 0.5 + 供需分 * 0.3 + 排名分 * 0.2
    rank_score = max(0, 100 - rank_pct * 1.5) if rank else 50
    outlook_score = round(cycle_score * 0.5 + supply_score * 0.3 + rank_score * 0.2, 1)
    
    if outlook_score >= 75:
        outlook_label = "偏乐观 ✅"
        outlook_dir = "上涨 ↗️"
    elif outlook_score >= 55:
        outlook_label = "中性偏多 📈"
        outlook_dir = "震荡偏强 ↗️"
    elif outlook_score >= 35:
        outlook_label = "中性偏弱 📉"
        outlook_dir = "震荡偏弱 ↘️"
    else:
        outlook_label = "偏悲观 ❌"
        outlook_dir = "下跌 ↘️"
    
    # 近期走势判断
    if avg_chg > 2 and up_ratio > 65:
        short_term = "短期强势，但连续上涨后需警惕技术性回调"
    elif avg_chg < -1.5:
        short_term = "短期承压，关注是否有企稳信号"
    elif avg_chg > 0:
        short_term = "短期温和上行，趋势健康"
    else:
        short_term = "短期弱势震荡，等待方向选择"
    
    return {
        "sector": sector,
        # 景气周期
        "cycle_stage": cycle_stage,
        "cycle_score": cycle_score,
        "cycle_desc": cycle_desc,
        "cycle_risk": cycle_risk,
        # 供需矛盾（产业链各环节）
        "supply_demand": supply_demand,
        "supply_score": supply_score,
        "supply_desc": supply_desc,
        "supply_outlook": supply_outlook,
        "chain_analysis": chain_analysis,
        # 量化预测
        "outlook_score": outlook_score,
        "outlook_label": outlook_label,
        "outlook_dir": outlook_dir,
        "short_term": short_term,
    }


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
            df = pd.read_csv(path, encoding="utf-16", sep="	", engine="python")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            match = df[df["代码"] == code]
            if not match.empty:
                sector = match.iloc[0].get("所属行业", "")
            break

    # 行业前瞻
    industry = _get_industry_data(sector)
    
    # 行业景气周期 + 供需矛盾分析 + 量化预测
    cycle = _analyze_industry_cycle(sector, industry)
    if industry and cycle:
        industry["cycle_analysis"] = cycle

    return {
        "code": code,
        "name": name,
        "sector": sector,
        "financial_summary": fin,
        "revenue_breakdown": revenue,
        "industry_outlook": industry,
    }


@router.get("/{code}/supply_chain")
def supply_chain_api(code: str):
    """供应链上下游数据（概念板块），lazy加载"""
    from backend.routers.analysis import _get_stock_list
    stock_map = _get_stock_list()
    name = stock_map.get(code, "")

    # 获取行业
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

    supply = _get_supply_chain(sector)
    return {
        "code": code,
        "name": name,
        "sector": sector,
        "supply_chain": supply,
    }


def _recommend_mental_models(code, name, sector, total_pct, primary_name, pe, chg_pct, chg3d, rev_growth, profit_growth, roe, mcap, lifecycle_stage, industry_avg_chg):
    """推荐最适用的3个底层思维模型"""
    candidates = []

    # 1. 反脆弱 — 高波动/高负债/高集中度时触发
    if chg_pct is not None and abs(chg_pct) > 5:
        candidates.append({
            "model": "反脆弱 🛡️",
            "reason": f"今日涨幅{chg_pct:+.1f}%，波动剧烈，塔勒布式思维：这个仓位在波动中受益还是受损？",
            "question": "如果明日反向波动5%，你的持仓能否承受？",
            "tag": "risk"
        })
    if total_pct < 50:
        candidates.append({
            "model": "反脆弱 🛡️",
            "reason": f"矛盾总评分仅{total_pct}%，多个矛盾突出。反脆弱思维：在这样的标的上，你的仓位是否「有下限无上限」？",
            "question": "如果这只股票再跌20%，你的应对方案是什么？",
            "tag": "risk"
        })

    # 2. 二阶效应 — 高增长/高估值/板块联动
    if rev_growth is not None and rev_growth > 20:
        candidates.append({
            "model": "二阶效应 🔄",
            "reason": f"营收增长{rev_growth:.1f}%，高增长的二阶效应：需求可持续吗？竞争对手会跟进吗？",
            "question": "如果行业增速放缓，你的持仓逻辑会怎么变化？",
            "tag": "system"
        })
    if sector and industry_avg_chg is not None and abs(industry_avg_chg) > 3:
        candidates.append({
            "model": "二阶效应 🔄",
            "reason": f"{sector}板块今日涨幅{industry_avg_chg:+.1f}%，板块轮动的二阶效应：资金从哪来？下一个流向哪？",
            "question": "如果这个板块的热度消退，你的持仓会受到什么间接影响？",
            "tag": "system"
        })

    # 3. 幸存者偏差 — 只看涨不看跌
    if chg_pct is not None and chg_pct > 3:
        candidates.append({
            "model": "幸存者偏差 📊",
            "reason": f"今日涨{chg_pct:.1f}%，盈利容易导致幸存者偏差：你的分析逻辑是普遍的，还是只适用于上涨市场？",
            "question": "如果今天跌的不是涨，你会做出同样的买入决策吗？",
            "tag": "psychology"
        })

    # 4. 能力圈 — 需要警惕的认知边界
    if mcap is not None and mcap < 200:
        candidates.append({
            "model": "能力圈 🎯",
            "reason": f"市值仅{mcap:.0f}亿小盘股，你真的了解它的业务模式和竞争壁垒吗？",
            "question": "你能用两句话说清楚这家公司靠什么赚钱吗？如果说不清，就不在能力圈内。",
            "tag": "core"
        })
    if pe is not None and pe > 80:
        candidates.append({
            "model": "能力圈 🎯",
            "reason": f"PE高达{pe:.0f}倍，市场在定价一个高增长预期。你真的理解这个预期的依据吗？",
            "question": "你比市场更了解这个公司吗？如果不是，凭什么认为市场定价错了？",
            "tag": "core"
        })

    # 5. 安全边际 — 估值保护
    if pe is not None and pe > 40:
        candidates.append({
            "model": "安全边际 🛡️💰",
            "reason": f"PE {pe:.0f}倍，安全边际较薄。格雷厄姆式提问：如果停牌3年，你还会买吗？",
            "question": "当前价格下跌30%后，你的买入理由还成立吗？",
            "tag": "value"
        })
    if total_pct < 50 and primary_name:
        candidates.append({
            "model": "安全边际 🛡️💰",
            "reason": f"主要矛盾在「{primary_name}」，安全边际正在被侵蚀。最坏情况下你的亏损上限在哪？",
            "question": "你能给这个股票一个「不会亏钱」的买入价格吗？",
            "tag": "value"
        })

    # 6. 机会成本 — 持仓优化
    candidates.append({
        "model": "机会成本 📐",
        "reason": f"当前持仓{sector or name}的预期收益率，与现金/ETF/其他板块相比如何？",
        "question": "如果不持有这只，你会把资金投到哪里？那个选择的预期收益更高吗？",
        "tag": "portfolio"
    })

    # 7. 临界点 — 趋势转折
    if chg3d is not None and abs(chg3d) > 8:
        candidates.append({
            "model": "临界点/引爆点 💥",
            "reason": f"3日振幅{chg3d:+.1f}%，价格可能接近一个重要的转折点。格拉德威尔式提问：什么条件会触发趋势反转？",
            "question": "这个临界点到了之后，你是站在哪个方向？",
            "tag": "system"
        })

    # 8. 纳什均衡 — 博弈分析
    if sector:
        candidates.append({
            "model": "纳什均衡 ♟️",
            "reason": f"在{sector or ''}这个赛道上，你比机构投资者多知道什么？",
            "question": "如果你的对手盘是量化基金，他们现在在做什么？你的策略和他们的最优策略一致吗？",
            "tag": "game"
        })

    # 9. 汉隆剃刀 — 避免归因错误
    if chg_pct is not None and chg_pct < -3:
        candidates.append({
            "model": "汉隆剃刀 🪒",
            "reason": f"今日跌{chg_pct:.1f}%，不要归结为恶意（庄家砸盘/主力洗盘）。更可能只是随机波动或宏观因素。",
            "question": "排除阴谋论后，最合理的解释是什么？这个解释能指导你的下一步操作吗？",
            "tag": "psychology"
        })

    # 10. 叙事经济 — 市场在交易什么故事
    if sector:
        candidates.append({
            "model": "叙事经济 📖",
            "reason": f"{sector}当前的市场叙事是什么？这个叙事是新的还是老故事重讲？",
            "question": "当这个叙事被证伪时，市场会怎么反应？",
            "tag": "market"
        })

    # 11. 帕累托最优 — 持仓优化
    candidates.append({
        "model": "帕累托最优 ⚡",
        "reason": "在不增加风险的前提下，你的持仓组合能否改进？去掉最差的、加仓最好的？",
        "question": "你的持仓中，哪只股票是「不优化也不损失」的状态？哪只可以通过替换改善？",
        "tag": "portfolio"
    })

    # 12. 复利效应 — 长期视角
    if roe is not None and roe > 15:
        candidates.append({
            "model": "复利效应 📈",
            "reason": f"ROE {roe:.1f}%，如果这个ROE可持续，7年资产翻倍。复利的关键是连续性而非爆发性。",
            "question": "这个ROE能维持5年吗？阻力的来源是什么？",
            "tag": "longterm"
        })

    # 去重 + 排序 + 取top3
    seen = set()
    deduped = []
    for c in candidates:
        model_name = c["model"].split(" ")[0]
        if model_name not in seen:
            seen.add(model_name)
            deduped.append(c)

    # 按优先级排序：先核心→价值→risk→portfolio→system→其他
    priority = {"core": 0, "value": 1, "risk": 2, "portfolio": 3, "system": 4, "psychology": 5, "game": 6, "market": 7, "longterm": 8}
    deduped.sort(key=lambda x: priority.get(x.get("tag",""), 99))

    return deduped[:3]


# ============================================================
# 7. 矛盾分析：5大矛盾对 + 主次判定 + 转化条件
# ============================================================
def _get_contradiction_analysis(code: str) -> dict | None:
    """矛盾分析：贯穿辩证分析，找出主要/次要矛盾及转化条件"""
    import akshare as ak
    from backend.routers.analysis import _get_stock_list
    import numpy as np

    stock_map = _get_stock_list()
    name = stock_map.get(code, "")
    if not name:
        return None

    # ---- 1. 收集数据源 ----
    # 1a. 财务分析指标
    indicators = {}
    try:
        df_ind = ak.stock_financial_analysis_indicator(symbol=code, start_year="2023")
        df_ind = df_ind.sort_values("日期", ascending=False)
        records_ind = df_ind.to_dict("records")
        indicators = records_ind[0] if records_ind else {}
    except Exception:
        indicators = {}

    # 1b. 财务摘要（多期趋势）
    fin = _get_financial_summary(code)
    fin_records = (fin or {}).get("records", [])[-12:]  # 最近12期

    # 1c. 行业数据（从CSV）
    sector = None
    today = date.today()
    csv_df = None
    for i in range(5):
        d = (today - timedelta(days=i)).isoformat()
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            csv_df = pd.read_csv(path, encoding="utf-16", sep="\t", engine="python")
            csv_df["代码"] = csv_df["代码"].astype(str).str.strip("'\"")
            match = csv_df[csv_df["代码"] == code]
            if not match.empty:
                sector = match.iloc[0].get("所属行业", "")
            break

    industry = _get_industry_data(sector)

    def _flt(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        try:
            return round(float(v), 2)
        except (ValueError, TypeError):
            return None

    # ---- 2. 计算5大矛盾对 ----
    lat = indicators
    contradictions = []

    # === 矛盾① 价格 vs 价值 ===
    pv_items = []
    pv_score = 0

    # 先行：涨幅动量
    if csv_df is not None and not csv_df[csv_df["代码"] == code].empty:
        row = csv_df[csv_df["代码"] == code].iloc[0]
        cur_price = _flt(row.get("最新"))
        chg_pct = _flt(row.get("涨幅"))
        vol = _flt(row.get("成交量"))
        pe = _flt(row.get("市盈率"))
        pb = _flt(row.get("市净率"))
        mcap = _flt(row.get("总市值"))
        chg3d = _flt(row.get("3日涨幅"))
    else:
        cur_price = chg_pct = vol = pe = pb = mcap = chg3d = None

    # 同步：当前涨跌幅（0-10分）
    if chg_pct is not None:
        vol_score = 0
        if abs(chg_pct) > 7:
            vol_score = 10  # 极端波动
            pv_items.append({"type": "同步", "label": "当日涨跌幅", "value": f"{chg_pct:+.2f}%", "score": vol_score, "max": 10,
                             "verdict": "极端波动 ⚠️"})
        elif abs(chg_pct) > 4:
            vol_score = 8
            pv_items.append({"type": "同步", "label": "当日涨跌幅", "value": f"{chg_pct:+.2f}%", "score": vol_score, "max": 10,
                             "verdict": "强波动"})
        else:
            vol_score = 5
            pv_items.append({"type": "同步", "label": "当日涨跌幅", "value": f"{chg_pct:+.2f}%", "score": vol_score, "max": 10,
                             "verdict": "正常波动"})
        pv_score += vol_score

    # 同步：PE估值分位（0-10分）
    if pe is not None and pe > 0:
        if pe > 80:
            pe_score = 1
            pe_verdict = "极高估值 🔴"
        elif pe > 40:
            pe_score = 3
            pe_verdict = "偏高估值 🟡"
        elif pe > 20:
            pe_score = 6
            pe_verdict = "合理估值 🟢"
        elif pe > 10:
            pe_score = 8
            pe_verdict = "偏低估值 ✅"
        else:
            pe_score = 10
            pe_verdict = "极低估值 💎"
        pv_score += pe_score
        pv_items.append({"type": "同步", "label": "PE估值", "value": f"{pe:.1f}", "score": pe_score, "max": 10, "verdict": pe_verdict})

    # 先行：3日动量（0-8分）
    if chg3d is not None:
        mom_score = min(8, abs(chg3d) / 5 * 8)
        pv_score += mom_score
        pv_items.append({"type": "先行", "label": "3日动量", "value": f"{chg3d:+.2f}%", "score": round(mom_score, 1), "max": 8,
                         "verdict": "动量强" if abs(chg3d) > 5 else ("动量中" if abs(chg3d) > 2 else "动量弱")})

    # 滞后：ROE趋势（滞后验证价值）
    roe = _flt(lat.get("净资产收益率(%)"))
    if roe is not None:
        roe_score = min(8, roe / 15 * 8)
        pv_score += roe_score
        pv_items.append({"type": "滞后", "label": "ROE（价值锚）", "value": f"{roe:.2f}%", "score": round(roe_score, 1), "max": 8,
                         "verdict": "优秀" if roe > 15 else ("良好" if roe > 10 else ("一般" if roe > 5 else "偏低"))})

    contradictions.append({
        "id": "price_value",
        "name": "价格 vs 价值",
        "icon": "⚖️",
        "desc": "当前价格偏离内在价值的程度",
        "score": round(pv_score, 1),
        "max": 36,
        "pct": round(pv_score / 36 * 100, 1),
        "level": "alert" if pv_score >= 25 else ("warn" if pv_score >= 18 else "normal"),
        "items": pv_items,
        "transformation": "当PE突破极端分位+动量反转时，价格可能向价值回归" if (pe or 0) > 40 else
                          "当业绩超预期或行业催化时，低估可能被修正",
    })

    # === 矛盾② 成长 vs 估值 ===
    gv_items = []
    gv_score = 0

    # 先行：营收增速
    rev_growth = _flt(lat.get("主营业务收入增长率(%)"))
    if rev_growth is not None:
        rg_score = min(12, (rev_growth + 10) / 25 * 12) if rev_growth > -10 else 0
        gv_score += max(0, rg_score)
        gv_items.append({"type": "先行", "label": "营收增速", "value": f"{rev_growth:+.2f}%", "score": round(max(0, rg_score), 1), "max": 12,
                         "verdict": "高增长" if rev_growth > 20 else ("增长" if rev_growth > 0 else "下滑")})

    # 同步：利润增速
    profit_growth = _flt(lat.get("净利润增长率(%)"))
    if profit_growth is not None:
        pg_score = min(12, (profit_growth + 15) / 30 * 12) if profit_growth > -15 else 0
        gv_score += max(0, pg_score)
        gv_items.append({"type": "同步", "label": "净利润增速", "value": f"{profit_growth:+.2f}%", "score": round(max(0, pg_score), 1), "max": 12,
                         "verdict": "爆发" if profit_growth > 30 else ("增长" if profit_growth > 0 else "下滑")})

    # 同步：PEG（隐含估值合理性）
    if pe is not None and pe > 0 and profit_growth is not None and profit_growth > 0:
        peg = round(pe / profit_growth, 2)
        if peg < 1:
            peg_score = 10
            peg_verdict = "低估 💎"
        elif peg < 2:
            peg_score = 7
            peg_verdict = "合理 🟢"
        elif peg < 3:
            peg_score = 4
            peg_verdict = "偏高 🟡"
        else:
            peg_score = 1
            peg_verdict = "高估 🔴"
        gv_score += peg_score
        gv_items.append({"type": "同步", "label": "PEG", "value": f"{peg:.2f}", "score": peg_score, "max": 10, "verdict": peg_verdict})

    # 滞后：增长率趋势（多期比较）
    if len(fin_records) >= 3:
        try:
            rev_vals = []
            for r in fin_records[-3:]:
                v = r.get("营业总收入同比增长率")
                if v and v not in ("--", "", None):
                    rev_vals.append(float(str(v).replace("%", "")))
            if len(rev_vals) >= 2:
                trend = rev_vals[-1] - rev_vals[0]
                if trend > 5:
                    trend_score = 8
                    trend_verdict = "加速增长 ✅"
                elif trend > -5:
                    trend_score = 5
                    trend_verdict = "增速平稳"
                else:
                    trend_score = 2
                    trend_verdict = "增速放缓 ⚠️"
                gv_score += trend_score
                gv_items.append({"type": "滞后", "label": "增速趋势(3期)", "value": f"{trend:+.1f}pp", "score": trend_score, "max": 8,
                                 "verdict": trend_verdict})
        except Exception:
            pass

    contradictions.append({
        "id": "growth_valuation",
        "name": "成长 vs 估值",
        "icon": "📈",
        "desc": "成长速度是否已被市场充分定价",
        "score": round(gv_score, 1),
        "max": 42,
        "pct": round(gv_score / 42 * 100, 1),
        "level": "alert" if gv_score >= 30 else ("warn" if gv_score >= 20 else "normal"),
        "items": gv_items,
        "transformation": "营收增速连续2季降档>10pp时，高估值不可持续" if (profit_growth or 0) > 20 else
                          "营收/利润增速拐点向上时，低估值可能被重估",
    })

    # === 矛盾③ 盈利质量 vs 现金流 ===
    eq_items = []
    eq_score = 0

    # 先行：应收账款/营收比（利润质量预警）
    if len(fin_records) >= 2:
        try:
            ar_ratios = []
            for r in fin_records[-4:]:
                rev_val = r.get("营业总收入")
                ar_val = r.get("应收账款")
                if rev_val and ar_val and rev_val not in ("--", "", None) and ar_val not in ("--", "", None):
                    try:
                        ratio = float(str(ar_val).replace("亿", "")) / float(str(rev_val).replace("亿", ""))
                        ar_ratios.append(ratio)
                    except (ValueError, ZeroDivisionError):
                        pass
            if ar_ratios:
                avg_ar = sum(ar_ratios) / len(ar_ratios)
                ar_score = max(0, 8 - avg_ar * 10)
                eq_score += ar_score
                eq_items.append({"type": "先行", "label": "应收/营收比", "value": f"{avg_ar*100:.1f}%", "score": round(ar_score, 1), "max": 8,
                                 "verdict": "回款良好 ✅" if avg_ar < 0.2 else ("正常" if avg_ar < 0.4 else "回款偏慢 ⚠️")})
        except Exception:
            pass

    # 同步：OCF/净利润比率（核心指标）
    ocf_profit = _flt(lat.get("经营现金净流量与净利润的比率(%)"))
    if ocf_profit is not None:
        if ocf_profit > 100:
            ocf_score = 14
            ocf_verdict = "利润质量极高 💎"
        elif ocf_profit > 50:
            ocf_score = 10
            ocf_verdict = "利润质量良好 ✅"
        elif ocf_profit > 0:
            ocf_score = 5
            ocf_verdict = "利润质量偏低 ⚠️"
        else:
            ocf_score = 0
            ocf_verdict = "OCF为负 🔴"
        eq_score += ocf_score
        eq_items.append({"type": "同步", "label": "OCF/净利润", "value": f"{ocf_profit:.1f}%", "score": ocf_score, "max": 14,
                         "verdict": ocf_verdict})

    # 滞后：毛利率趋势（盈利能力持续性）
    gross_margin = _flt(lat.get("销售毛利率(%)"))
    if gross_margin is not None:
        gm_score = min(10, gross_margin / 30 * 10)
        eq_score += gm_score
        eq_items.append({"type": "滞后", "label": "毛利率", "value": f"{gross_margin:.2f}%", "score": round(gm_score, 1), "max": 10,
                         "verdict": "极高" if gross_margin > 50 else ("高" if gross_margin > 25 else ("中" if gross_margin > 10 else "低"))})

    contradictions.append({
        "id": "quality_cashflow",
        "name": "盈利质量 vs 现金流",
        "icon": "💧",
        "desc": "账面利润转化为真实现金的能力",
        "score": round(eq_score, 1),
        "max": 32,
        "pct": round(eq_score / 32 * 100, 1),
        "level": "alert" if eq_score >= 22 else ("warn" if eq_score >= 14 else "normal"),
        "items": eq_items,
        "transformation": "当OCF/净利润连续2期改善>30pp时，盈利质量矛盾缓解" if (ocf_profit or 0) < 50 else
                          "当应收增速持续>营收增速时，利润质量可能恶化",
    })

    # === 矛盾④ 负债扩张 vs 财务安全 ===
    df_items = []
    df_score = 0

    # 先行：总资产增长率（扩张信号）
    asset_growth = _flt(lat.get("总资产增长率(%)"))
    if asset_growth is not None:
        if asset_growth > 20:
            ag_score = 8
            ag_verdict = "激进扩张 🔥"
        elif asset_growth > 10:
            ag_score = 6
            ag_verdict = "稳步扩张 ✅"
        elif asset_growth > 0:
            ag_score = 4
            ag_verdict = "温和扩张"
        else:
            ag_score = 2
            ag_verdict = "收缩中"
        df_score += ag_score
        df_items.append({"type": "先行", "label": "总资产增长率", "value": f"{asset_growth:+.2f}%", "score": ag_score, "max": 8,
                         "verdict": ag_verdict})

    # 同步：资产负债率
    debt_ratio = _flt(lat.get("资产负债率(%)"))
    if debt_ratio is not None:
        if debt_ratio < 30:
            dr_score = 10
            dr_verdict = "极低杠杆 ✅"
        elif debt_ratio < 50:
            dr_score = 8
            dr_verdict = "合理杠杆 🟢"
        elif debt_ratio < 65:
            dr_score = 5
            dr_verdict = "偏高杠杆 🟡"
        else:
            dr_score = 2
            dr_verdict = "高杠杆 🔴"
        df_score += dr_score
        df_items.append({"type": "同步", "label": "资产负债率", "value": f"{debt_ratio:.1f}%", "score": dr_score, "max": 10,
                         "verdict": dr_verdict})

    # 同步：流动比率
    current_ratio = _flt(lat.get("流动比率(%)"))
    if current_ratio is not None:
        cr_val = current_ratio / 100  # akshare返回百分比
        if cr_val > 2.0:
            cr_score = 8
            cr_verdict = "非常充裕 ✅"
        elif cr_val > 1.5:
            cr_score = 6
            cr_verdict = "安全 🟢"
        elif cr_val > 1.0:
            cr_score = 4
            cr_verdict = "及格 🟡"
        else:
            cr_score = 1
            cr_verdict = "不足 🔴"
        df_score += cr_score
        df_items.append({"type": "同步", "label": "流动比率", "value": f"{cr_val:.2f}", "score": cr_score, "max": 8,
                         "verdict": cr_verdict})

    # 滞后：ROIC vs 融资成本（隐含判断）
    roic = _flt(lat.get("投入资本回报率(%)"))
    if roic is not None:
        if roic > 10:
            roic_score = 8
            roic_verdict = "资本回报优秀 ✅"
        elif roic > 5:
            roic_score = 5
            roic_verdict = "回报合理 🟢"
        else:
            roic_score = 2
            roic_verdict = "回报偏低 ⚠️"
        df_score += roic_score
        df_items.append({"type": "滞后", "label": "ROIC", "value": f"{roic:.2f}%", "score": roic_score, "max": 8,
                         "verdict": roic_verdict})

    contradictions.append({
        "id": "debt_safety",
        "name": "负债扩张 vs 财务安全",
        "icon": "🏛️",
        "desc": "加杠杆是否带来超额回报",
        "score": round(df_score, 1),
        "max": 34,
        "pct": round(df_score / 34 * 100, 1),
        "level": "alert" if df_score >= 24 else ("warn" if df_score >= 16 else "normal"),
        "items": df_items,
        "transformation": "当ROIC持续>融资成本且负债率<50%时，适度加杠杆有利" if (debt_ratio or 0) < 50 else
                          "当利率上升或ROIC下降时，高杠杆风险加剧",
    })

    # === 矛盾⑤ 行业景气 vs 个股地位 ===
    ii_items = []
    ii_score = 0

    # 先行：板块热度
    if industry:
        avg_chg = industry.get("avg_change", 0) or 0
        up_ratio = industry.get("up_ratio", 0) or 0
        rank = industry.get("rank", 0) or 0
        total_sectors = industry.get("total_sectors", 0) or 1

        # 板块涨幅热度
        if avg_chg > 2:
            sector_score = 8
            sec_verdict = "板块强势 🔥"
        elif avg_chg > 0:
            sector_score = 5
            sec_verdict = "板块温和"
        elif avg_chg > -2:
            sector_score = 3
            sec_verdict = "板块偏弱"
        else:
            sector_score = 1
            sec_verdict = "板块弱势 ❄️"
        ii_score += sector_score
        ii_items.append({"type": "先行", "label": "板块平均涨幅", "value": f"{avg_chg:+.2f}%", "score": sector_score, "max": 8,
                         "verdict": sec_verdict})

        # 上涨占比
        if up_ratio > 70:
            ur_score = 6
            ur_verdict = "普涨行情 ✅"
        elif up_ratio > 50:
            ur_score = 4
            ur_verdict = "涨多跌少"
        elif up_ratio > 30:
            ur_score = 2
            ur_verdict = "分化明显"
        else:
            ur_score = 1
            ur_verdict = "普跌 ❌"
        ii_score += ur_score
        ii_items.append({"type": "同步", "label": "板块上涨占比", "value": f"{up_ratio:.1f}%", "score": ur_score, "max": 6,
                         "verdict": ur_verdict})

        # 排名分位
        rank_pct = rank / total_sectors if total_sectors > 0 else 0.5
        if rank_pct < 0.2:
            rk_score = 8
            rk_verdict = "板块排名前列 🏆"
        elif rank_pct < 0.4:
            rk_score = 6
            rk_verdict = "板块排名中上 ✅"
        elif rank_pct < 0.6:
            rk_score = 4
            rk_verdict = "板块排名中游"
        else:
            rk_score = 1
            rk_verdict = "板块排名靠后"
        ii_score += rk_score
        ii_items.append({"type": "滞后", "label": "板块排名", "value": f"#{rank}/{total_sectors}", "score": rk_score, "max": 8,
                         "verdict": rk_verdict})

    # 个股 vs 板块 相对强弱
    if chg_pct is not None and industry:
        avg_chg = industry.get("avg_change", 0) or 0
        relative = chg_pct - avg_chg
        if relative > 3:
            rel_score = 8
            rel_verdict = "显著强于板块 💪"
        elif relative > 0:
            rel_score = 5
            rel_verdict = "略强于板块"
        elif relative > -3:
            rel_score = 3
            rel_verdict = "弱于板块"
        else:
            rel_score = 1
            rel_verdict = "显著弱于板块 ⚠️"
        ii_score += rel_score
        ii_items.append({"type": "同步", "label": "个股vs板块", "value": f"{relative:+.2f}pp", "score": rel_score, "max": 8,
                         "verdict": rel_verdict})

    contradictions.append({
        "id": "industry_position",
        "name": "行业景气 vs 个股地位",
        "icon": "🔭",
        "desc": "行业β收益 vs 个股α收益",
        "score": round(ii_score, 1),
        "max": 30,
        "pct": round(ii_score / 30 * 100, 1),
        "level": "alert" if ii_score >= 21 else ("warn" if ii_score >= 14 else "normal"),
        "items": ii_items,
        "transformation": "当板块持续走强但个股滞涨时，可能是补涨机会或基本面瑕疵" if (relative if 'relative' in dir() else 0) < 0 else
                          "当板块转弱但个股抗跌时，可能存在个股α",
    })

    # ---- 3. 思维模型注入 ----
    # 3a. 生命周期判定
    rev_growth_val = _flt(lat.get("主营业务收入增长率(%)")) or 0
    profit_growth_val = _flt(lat.get("净利润增长率(%)")) or 0
    asset_growth_val = _flt(lat.get("总资产增长率(%)")) or 0
    gross_margin_val = _flt(lat.get("销售毛利率(%)")) or 0
    ocf_profit_val = _flt(lat.get("经营现金净流量与净利润的比率(%)")) or 0

    if rev_growth_val > 20 and profit_growth_val > 20:
        lifecycle = {"stage": "成长期", "icon": "🌱", "desc": "营收+利润双高增长，处于快速扩张阶段",
                     "implication": "适合PEG估值，关注增速持续性而非绝对PE",
                     "models": ["生命周期", "复利效应", "红皇后效应"]}
    elif rev_growth_val > 5 and profit_growth_val > 0:
        lifecycle = {"stage": "成熟期", "icon": "🌳", "desc": "增长放缓但盈利稳定，进入成熟阶段",
                     "implication": "适合PE+股息率估值，关注护城河宽度",
                     "models": ["生命周期", "护城河", "规模效应"]}
    elif rev_growth_val < -5 or profit_growth_val < -10:
        lifecycle = {"stage": "衰退期", "icon": "🍂", "desc": "增长下滑，需警惕基本面恶化",
                     "implication": "适合PB+清算价值，关注转型可能性和现金储备",
                     "models": ["生命周期", "熵增定律", "创造性破坏"]}
    else:
        lifecycle = {"stage": "调整期", "icon": "🔄", "desc": "增速放缓后的调整或转型期",
                     "implication": "需区分是暂时调整还是长期下滑，关注拐点信号",
                     "models": ["生命周期", "均值回归", "反馈回路"]}

    # 3b. 为每个矛盾对注入关联思维模型
    _MODELS_MAP = {
        "price_value": {
            "models": ["势能", "均值回归", "锚定效应"],
            "desc": "价格偏离价值越远，回归势能越大"
        },
        "growth_valuation": {
            "models": ["复利效应", "生命周期", "边际效用递减"],
            "desc": "高增长终将放缓，复利曲线在成长期最陡峭"
        },
        "quality_cashflow": {
            "models": ["熵增定律", "滞后效应", "反馈回路"],
            "desc": "利润质量熵增不可持续，现金流滞后反映真实状况"
        },
        "debt_safety": {
            "models": ["杠杆/支点", "红皇后效应", "路径依赖"],
            "desc": "杠杆=双刃剑，ROIC>利率则正向放大，反之加速毁灭"
        },
        "industry_position": {
            "models": ["生态位", "进化论", "涌现"],
            "desc": "个股α=在行业生态位中的适应性，板块β=群体行为涌现"
        },
    }
    for con in contradictions:
        m = _MODELS_MAP.get(con["id"], {})
        con["models"] = m.get("models", [])
        con["models_desc"] = m.get("desc", "")

    # 3c. 反馈回路分析
    chg_trend = None
    if chg3d is not None:
        if chg3d > 5 and chg_pct is not None and chg_pct > 0:
            chg_trend = "正反馈 🔁"
            chg_trend_desc = "连续上涨强化上涨预期，趋势自我加强中。需警惕高潮后的均值回归"
        elif chg3d < -5 and chg_pct is not None and chg_pct < 0:
            chg_trend = "负反馈 🔄"
            chg_trend_desc = "连续下跌强化下跌预期，恐慌可能过度。关注反转信号"
        else:
            chg_trend = "均衡态 ⚖️"
            chg_trend_desc = "多空力量相对均衡，等待催化剂打破平衡"

    # 3d. 行为金融偏误提示
    behavioral_biases = []
    # 从数据中推断常见偏误
    if chg3d is not None and abs(chg3d) > 10:
        behavioral_biases.append({
            "bias": "从众效应",
            "icon": "🐑",
            "trigger": f"3日振幅{abs(chg3d):.1f}%",
            "warning": "短期剧烈波动时容易跟风操作，警惕群体情绪放大"
        })
    if pe is not None and pe < 15 and rev_growth_val > 20:
        behavioral_biases.append({
            "bias": "确认偏误",
            "icon": "🔄",
            "trigger": f"PE={pe:.0f}×成长={rev_growth_val:.1f}%",
            "warning": "低PE+高成长容易过度乐观，忽略利润质量等潜在风险"
        })
    if pe is not None and pe > 50:
        behavioral_biases.append({
            "bias": "锚定效应",
            "icon": "⚓",
            "trigger": f"PE={pe:.0f}×",
            "warning": "高PE可能被「这次不一样」的叙事锚定，历史均值终究回归"
        })
    if profit_growth_val < -10 and rev_growth_val > 5:
        behavioral_biases.append({
            "bias": "损失厌恶",
            "icon": "💔",
            "trigger": "增收不增利",
            "warning": "收入增长但利润下滑，投资者容易因「还有增长」而忽视盈利恶化"
        })
    if (ocf_profit_val or 0) < 30:
        behavioral_biases.append({
            "bias": "结果偏误",
            "icon": "🎲",
            "trigger": f"OCF/净利润={ocf_profit_val:.1f}%",
            "warning": "账面利润好看但现金流差，容易被表面数字迷惑，忽略真实造血能力"
        })

    # ---- 4. 主次矛盾判定 ----
    sorted_cons = sorted(contradictions, key=lambda c: c["score"], reverse=True)
    primary = sorted_cons[0] if sorted_cons else None
    secondary = sorted_cons[1] if len(sorted_cons) > 1 else None
    third = sorted_cons[2] if len(sorted_cons) > 2 else None

    # ---- 4. 矛盾转化条件 ----
    transformation_triggers = []
    for con in contradictions:
        transformation_triggers.append({
            "id": con["id"],
            "name": con["name"],
            "condition": con["transformation"],
            "current_score": con["score"],
            "is_primary": con["id"] == primary["id"] if primary else False,
        })

    # ---- 5. 总体研判 ----
    total_max = sum(c["max"] for c in contradictions)
    total_score = sum(c["score"] for c in contradictions)
    total_pct = round(total_score / total_max * 100, 1) if total_max > 0 else 0

    if total_pct >= 70:
        overall = "整体健康 ✅"
        overall_desc = "五大矛盾整体平衡，无明显系统性风险"
    elif total_pct >= 50:
        overall = "存在隐忧 ⚠️"
        overall_desc = f"主要矛盾在「{primary['name']}」，需重点关注" if primary else ""
    else:
        overall = "风险偏高 🔴"
        overall_desc = f"多个矛盾同时突出，建议谨慎，核心矛盾在「{primary['name']}」" if primary else ""

    return {
        "code": code,
        "name": name,
        "sector": sector or "",
        "total_score": total_score,
        "total_max": total_max,
        "total_pct": total_pct,
        "overall": overall,
        "overall_desc": overall_desc,
        "primary": {
            "id": primary["id"],
            "name": primary["name"],
            "icon": primary["icon"],
            "score": primary["score"],
            "pct": primary["pct"],
        } if primary else None,
        "secondary": {
            "id": secondary["id"],
            "name": secondary["name"],
            "icon": secondary["icon"],
            "score": secondary["score"],
            "pct": secondary["pct"],
        } if secondary else None,
        "third": {
            "id": third["id"],
            "name": third["name"],
            "icon": third["icon"],
            "score": third["score"],
            "pct": third["pct"],
        } if third else None,
        "contradictions": contradictions,
        "transformation_triggers": transformation_triggers,
        "lifecycle": lifecycle,
        "feedback_loop": {
            "trend": chg_trend,
            "desc": chg_trend_desc,
        } if chg_trend else None,
        "behavioral_biases": behavioral_biases,
        "behavioral_biases": behavioral_biases,
        "recommended_models": _recommend_mental_models(
            code=code, name=name, sector=sector or "",
            total_pct=total_pct, primary_name=(primary or {}).get("name",""),
            pe=pe, chg_pct=chg_pct, chg3d=chg3d,
            rev_growth=rev_growth, profit_growth=profit_growth,
            roe=roe, mcap=mcap,
            lifecycle_stage=(lifecycle or {}).get("stage",""),
            industry_avg_chg=((industry or {}).get("avg_change") or 0),
        ),
    }

@router.get("/{code}/contradiction")
def contradiction_api(code: str):
    """矛盾分析 API"""
    result = _get_contradiction_analysis(code)
    if not result:
        raise HTTPException(status_code=404, detail="数据不足，无法分析")
    return result


# ============================================================
# 8. 三张财务报表
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
            df = pd.read_csv(path, encoding="utf-16", sep="	", engine="python")
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
            df = pd.read_csv(path, encoding="utf-16", sep="	", engine="python")
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
