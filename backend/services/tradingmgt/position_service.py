"""仓位管理模块 — 持仓业务逻辑（CRUD + 分析）"""

import os
import sqlite3

from .csv_store import read_all, write_all
from .constants import FX_RATES, MARKET_LABELS, CURRENCY_SYMBOLS, THEME_MAP, US_STOCK_INDUSTRY, HK_STOCK_INDUSTRY
from .price_service import detect_market, get_current_price, get_us_prices_batch, get_hk_prices_batch


def build_position(r: dict) -> dict:
    """将CSV行转换为PositionOut格式的dict"""
    code = r.get("代码", "")
    name = r.get("名称", "")
    qty = float(r.get("数量", 0))
    cost = float(r.get("成本价", 0))
    market = detect_market(code)

    live = get_current_price(code)
    current = live if live is not None else _safe_float(r.get("当前价"), 0.0)

    cost_total = round(qty * cost, 2)
    market_value = round(qty * current, 2)
    profit_amount = round(market_value - cost_total, 2)
    profit_pct = round((profit_amount / cost_total * 100) if cost_total else 0, 2)

    return {
        "code": code,
        "name": name,
        "quantity": qty,
        "cost_price": cost,
        "current_price": current,
        "cost_total": cost_total,
        "market_value": market_value,
        "profit_amount": profit_amount,
        "profit_pct": profit_pct,
        "note": r.get("备注", ""),
        "market": market,
        "market_label": MARKET_LABELS.get(market, market),
        "currency_symbol": CURRENCY_SYMBOLS.get(market, ""),
    }


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


# ======== 行业/主题 ========

def get_industry(code: str, name: str) -> str:
    """获取股票行业"""
    market = detect_market(code)
    if market == "a_stock":
        try:
            db_path = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT industry FROM stock_info WHERE code=?", (code,)
            ).fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
    elif market == "us_stock":
        return US_STOCK_INDUSTRY.get(code.upper(), "美股")
    elif market == "hk_stock":
        return HK_STOCK_INDUSTRY.get(code, "港股")
    return "其他"


def get_theme(industry: str) -> str:
    """行业 → 主题"""
    return THEME_MAP.get(industry, "其他")


# ======== 持仓 CRUD ========

def list_all() -> list[dict]:
    """获取所有持仓"""
    return read_all()


def add_one(code: str, name: str, quantity: float, cost_price: float, note: str = "") -> str:
    """添加持仓，返回消息"""
    rows = read_all()
    for r in rows:
        if r.get("代码") == code:
            raise ValueError(f"{code} 已在持仓中，请使用更新")

    market = detect_market(code)
    cost_total = round(quantity * cost_price, 2)
    rows.append({
        "代码": code,
        "名称": name,
        "数量": str(quantity),
        "成本价": str(cost_price),
        "当前价": "0",
        "持仓成本": str(cost_total),
        "当前市值": "0",
        "盈亏金额": "0",
        "盈亏比例": "0%",
        "备注": note,
        "市场": MARKET_LABELS.get(market, market),
    })
    write_all(rows)
    return f"已添加 {name}({code})"


def update_one(code: str, quantity=None, cost_price=None, note=None) -> str:
    """更新持仓，返回消息"""
    rows = read_all()
    found = False
    for r in rows:
        if r.get("代码") == code:
            if quantity is not None:
                r["数量"] = str(quantity)
            if cost_price is not None:
                r["成本价"] = str(cost_price)
            if note is not None:
                r["备注"] = note
            qty = float(r["数量"])
            cost = float(r["成本价"])
            r["持仓成本"] = str(round(qty * cost, 2))
            found = True
            break
    if not found:
        raise ValueError(f"未找到 {code}")
    write_all(rows)
    return f"已更新 {code}"


def delete_one(code: str) -> str:
    """删除持仓，返回消息"""
    rows = read_all()
    new_rows = [r for r in rows if r.get("代码") != code]
    if len(new_rows) == len(rows):
        raise ValueError(f"未找到 {code}")
    write_all(new_rows)
    return f"已删除 {code}"


# ======== 分组汇总 ========

def get_grouped_positions() -> dict:
    """获取所有持仓，按市场分组 + CNY汇总"""
    rows = read_all()
    if not rows:
        return {"positions": [], "groups": {}, "total_cny": {}}

    all_positions = [build_position(r) for r in rows]

    groups: dict[str, list] = {}
    for p in all_positions:
        groups.setdefault(p["market"], []).append(p)

    group_summaries = {}
    grand_cost = grand_value = grand_profit = 0.0
    grand_count = 0

    for market, items in groups.items():
        fx = FX_RATES.get(market, 1.0)
        cost = sum(p["cost_total"] for p in items)
        value = sum(p["market_value"] for p in items)
        profit = sum(p["profit_amount"] for p in items)
        profit_pct = round((profit / cost * 100) if cost else 0, 2)

        group_summaries[market] = {
            "label": MARKET_LABELS.get(market, market),
            "count": len(items),
            "cost": round(cost, 2),
            "value": round(value, 2),
            "profit": round(profit, 2),
            "profit_pct": profit_pct,
            "cost_cny": round(cost * fx, 2),
            "value_cny": round(value * fx, 2),
            "profit_cny": round(profit * fx, 2),
            "currency_symbol": CURRENCY_SYMBOLS.get(market, ""),
        }
        grand_cost += cost * fx
        grand_value += value * fx
        grand_profit += profit * fx
        grand_count += len(items)

    total_summary = {
        "count": grand_count,
        "cost_cny": round(grand_cost, 2),
        "value_cny": round(grand_value, 2),
        "profit_cny": round(grand_profit, 2),
        "profit_pct": round((grand_profit / grand_cost * 100) if grand_cost else 0, 2),
    }

    return {
        "positions": all_positions,
        "groups": groups,
        "group_summaries": group_summaries,
        "total_cny": total_summary,
    }


# ======== 持仓分析 ========

def analyze_positions() -> dict:
    """持仓多维度分析（统一折合CNY）"""
    rows = read_all()
    if not rows:
        return {"analysis": {"total": {"count": 0}}}

    us_codes = [r.get("代码", "") for r in rows if detect_market(r.get("代码", "")) == "us_stock"]
    hk_codes = [r.get("代码", "") for r in rows if detect_market(r.get("代码", "")) == "hk_stock"]
    us_prices = get_us_prices_batch(us_codes) if us_codes else {}
    hk_prices = get_hk_prices_batch(hk_codes) if hk_codes else {}

    # 构建持仓，同时计算本币和CNY值
    positions = []
    for r in rows:
        code = r.get("代码", "")
        p = build_position(r)
        market = detect_market(code)
        if market == "us_stock" and code in us_prices:
            p["current_price"] = us_prices[code]
            qty = p["quantity"]
            cost_local = p["cost_total"]
            p["market_value"] = round(qty * us_prices[code], 2)
            p["profit_amount"] = round(p["market_value"] - cost_local, 2)
            p["profit_pct"] = round((p["profit_amount"] / cost_local * 100) if cost_local else 0, 2)
        elif market == "hk_stock" and code in hk_prices:
            p["current_price"] = hk_prices[code]
            qty = p["quantity"]
            cost_local = p["cost_total"]
            p["market_value"] = round(qty * hk_prices[code], 2)
            p["profit_amount"] = round(p["market_value"] - cost_local, 2)
            p["profit_pct"] = round((p["profit_amount"] / cost_local * 100) if cost_local else 0, 2)

        # 折合CNY
        fx = FX_RATES.get(market, 1.0)
        p["cost_cny"] = round(p["cost_total"] * fx, 2)
        p["value_cny"] = round(p["market_value"] * fx, 2)
        p["profit_cny"] = round(p["profit_amount"] * fx, 2)
        positions.append(p)

    # 1. 盈亏排行（本币）
    by_profit = sorted(positions, key=lambda p: p["profit_amount"])
    top_losers = [
        {"code": p["code"], "name": p["name"], "profit": round(p["profit_amount"], 2), "currency": CURRENCY_SYMBOLS.get(p["market"], "")}
        for p in by_profit[:5]
    ]
    top_winners = [
        {"code": p["code"], "name": p["name"], "profit": round(p["profit_amount"], 2), "currency": CURRENCY_SYMBOLS.get(p["market"], "")}
        for p in reversed(by_profit[-5:])
    ]

    # 2. 市场分布（本币 + CNY）
    market_dist = {}
    for p in positions:
        m = p["market"]
        if m not in market_dist:
            market_dist[m] = {
                "label": MARKET_LABELS.get(m, m), "count": 0,
                "value": 0, "cost": 0, "profit": 0,
                "value_cny": 0, "cost_cny": 0, "profit_cny": 0,
                "currency": CURRENCY_SYMBOLS.get(m, ""),
            }
        market_dist[m]["count"] += 1
        market_dist[m]["value"] += p["market_value"]
        market_dist[m]["cost"] += p["cost_total"]
        market_dist[m]["profit"] += p["profit_amount"]
        market_dist[m]["value_cny"] += p["value_cny"]
        market_dist[m]["cost_cny"] += p["cost_cny"]
        market_dist[m]["profit_cny"] += p["profit_cny"]

    for v in market_dist.values():
        for k in ("value", "cost", "profit", "value_cny", "cost_cny", "profit_cny"):
            v[k] = round(v[k], 2)

    market_breakdown = dict(
        sorted(market_dist.items(), key=lambda x: x[1]["value_cny"], reverse=True)
    )

    # 3. 行业分布（统一折CNY）
    industry_data = {}
    for p in positions:
        ind = get_industry(p["code"], p["name"])
        if ind not in industry_data:
            industry_data[ind] = {
                "industry": ind, "count": 0,
                "value_cny": 0, "cost_cny": 0, "profit_cny": 0, "stocks": [],
            }
        industry_data[ind]["count"] += 1
        industry_data[ind]["value_cny"] += p["value_cny"]
        industry_data[ind]["cost_cny"] += p["cost_cny"]
        industry_data[ind]["profit_cny"] += p["profit_cny"]
        industry_data[ind]["stocks"].append(p["code"])

    for v in industry_data.values():
        for k in ("value_cny", "cost_cny", "profit_cny"):
            v[k] = round(v[k], 2)

    industry_list = sorted(industry_data.values(), key=lambda x: x["value_cny"], reverse=True)

    # 4. 主题分布（统一折CNY）
    theme_data = {}
    for p in positions:
        ind = get_industry(p["code"], p["name"])
        theme = get_theme(ind)
        if theme not in theme_data:
            theme_data[theme] = {"theme": theme, "count": 0, "value_cny": 0, "cost_cny": 0, "profit_cny": 0}
        theme_data[theme]["count"] += 1
        theme_data[theme]["value_cny"] += p["value_cny"]
        theme_data[theme]["cost_cny"] += p["cost_cny"]
        theme_data[theme]["profit_cny"] += p["profit_cny"]

    for v in theme_data.values():
        for k in ("value_cny", "cost_cny", "profit_cny"):
            v[k] = round(v[k], 2)

    theme_list = sorted(theme_data.values(), key=lambda x: x["value_cny"], reverse=True)

    # 总汇总（CNY）
    total_cost_cny = sum(p["cost_cny"] for p in positions)
    total_value_cny = sum(p["value_cny"] for p in positions)
    total_profit_cny = sum(p["profit_cny"] for p in positions)

    return {
        "analysis": {
            "total": {
                "count": len(positions),
                "cost_cny": round(total_cost_cny, 2),
                "value_cny": round(total_value_cny, 2),
                "profit_cny": round(total_profit_cny, 2),
                "profit_pct": round((total_profit_cny / total_cost_cny * 100) if total_cost_cny else 0, 2),
            },
            "market_breakdown": market_breakdown,
            "industry_distribution": industry_list,
            "theme_distribution": theme_list,
            "top_winners": top_winners,
            "top_losers": top_losers,
        }
    }
