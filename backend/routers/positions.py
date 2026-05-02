"""
持仓管理 API — 按市场分组 + 汇率换算 CNY
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import csv
import os
import sqlite3
from datetime import date
from pathlib import Path

from backend.config import POSITION_FILE, MARKET_DATA_DIR, JARVIS_DIR

router = APIRouter()

# 汇率（近似，用于汇总展示）
FX_RATES = {
    "a_stock": 1.0,    # A股 RMB
    "hk_stock": 0.93,  # HKD→CNY
    "us_stock": 7.25,  # USD→CNY
    "crypto": 7.25,    # Crypto→USD→CNY
}

MARKET_LABELS = {
    "a_stock": "A股",
    "hk_stock": "港股",
    "us_stock": "美股",
    "crypto": "加密货币",
}

CRYPTO_SYMBOLS = {"BTC","ETH","SOL","BNB","XRP","ADA","DOGE","DOT","AVAX","MATIC","LINK","UNI","ATOM","LTC","BCH","FIL","NEAR","APT","SUI","OP","ARB","PEPE","SHIB","INJ","TIA","SEI","STRK","ZRO","EIGEN","TAO","FET","AGIX","OCEAN","RENDER","GRT","ICP","EGLD","KAS","CRO","FTM","ALGO","VET","THETA","TRX","ALICE","SAND","MANA","AXS","GALA","ENJ","CHZ","APE","BLUR"}


def _detect_market(code: str) -> str:
    """根据代码判断市场"""
    c = code.strip().upper()
    if c in CRYPTO_SYMBOLS:
        return "crypto"
    if c.isdigit():
        if len(c) == 6:
            return "a_stock"
        if len(c) == 5:
            return "hk_stock"
        return "other"
    return "us_stock"


# ========== 数据模型 ==========
class Position(BaseModel):
    code: str
    name: str
    quantity: float = Field(gt=0, description="持仓数量")
    cost_price: float = Field(gt=0, description="成本价")
    note: str = ""


class PositionOut(BaseModel):
    code: str
    name: str
    quantity: float
    cost_price: float
    current_price: float
    cost_total: float
    market_value: float
    profit_amount: float
    profit_pct: float
    note: str
    market: str
    market_label: str


class UpdatePositionBody(BaseModel):
    quantity: Optional[float] = None
    cost_price: Optional[float] = None
    note: Optional[str] = None


# ========== 数据读写 ==========
def _read_positions() -> list[dict]:
    if not os.path.exists(POSITION_FILE):
        return []
    with open(POSITION_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_positions(rows: list[dict]):
    os.makedirs(os.path.dirname(POSITION_FILE), exist_ok=True)
    fieldnames = ["代码", "名称", "数量", "成本价", "当前价", "持仓成本", "当前市值", "盈亏金额", "盈亏比例", "备注", "市场"]
    with open(POSITION_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _get_current_price(code: str) -> float | None:
    """从本地行情CSV或实时API获取最新价"""
    from datetime import date, timedelta

    today = date.today()
    market = _detect_market(code)

    # A股：从本地CSV读取
    if market == "a_stock":
        for i in range(5):
            d = today - timedelta(days=i)
            for prefix in ["沪深京A股", "沪深重要指数"]:
                path = MARKET_DATA_DIR / f"{prefix}{d.isoformat()}.csv"
                if path.exists():
                    import pandas as pd
                    df = pd.read_csv(path, encoding="utf-16", sep="\t")
                    df["代码"] = df["代码"].astype(str).str.strip("'\"")
                    match = df[df["代码"] == code]
                    if not match.empty:
                        val = str(match.iloc[0].get("最新", "0"))
                        val = val.replace("--", "0").strip()
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None
        return None

    return None


# 美股价格（从CSV获取，不需要实时调用）
def _get_us_prices_batch(codes: list[str]) -> dict[str, float]:
    """美股价格：从CSV的当前价字段读取（已保存的行情）"""
    rows = _read_positions()
    result = {}
    for r in rows:
        code = r.get("代码", "").strip()
        if code in codes:
            raw = (r.get("当前价") or "0").strip()
            try:
                val = float(raw) if raw else 0.0
                if val > 0:
                    result[code] = val
            except (ValueError, TypeError):
                pass
    return result


# 港股价格（从CSV获取）
def _get_hk_prices_batch(codes: list[str]) -> dict[str, float]:
    """港股价格：从CSV的当前价字段读取"""
    rows = _read_positions()
    result = {}
    for r in rows:
        code = r.get("代码", "").strip()
        if code in codes:
            raw = (r.get("当前价") or "0").strip()
            try:
                val = float(raw) if raw else 0.0
                if val > 0:
                    result[code] = val
            except (ValueError, TypeError):
                pass
    return result


def _build_position(r: dict) -> dict:
    """将CSV行转换为PositionOut"""
    code = r.get("代码", "")
    name = r.get("名称", "")
    qty = float(r.get("数量", 0))
    cost = float(r.get("成本价", 0))
    market = _detect_market(code)

    live = _get_current_price(code)
    if live is not None:
        current = live
    else:
        raw = (r.get("当前价") or "0").strip()
        current = float(raw) if raw else 0.0

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
    }


# ========== API 路由 ==========
@router.get("")
def list_positions():
    """获取所有持仓，按市场分组 + CNY汇总"""
    rows = _read_positions()
    if not rows:
        return {"positions": [], "groups": {}, "summary": {}, "total_cny": {}}

    # 构建所有持仓
    all_positions = [_build_position(r) for r in rows]

    # 按市场分组
    groups: dict[str, list] = {}
    for p in all_positions:
        m = p["market"]
        if m not in groups:
            groups[m] = []
        groups[m].append(p)

    # 每组汇总 + CNY换算
    group_summaries = {}
    grand_cost = 0.0
    grand_value = 0.0
    grand_profit = 0.0
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
        }

        grand_cost += cost * fx
        grand_value += value * fx
        grand_profit += profit * fx
        grand_count += len(items)

    # 总汇
    total_summary = {
        "count": grand_count,
        "cost_cny": round(grand_cost, 2),
        "value_cny": round(grand_value, 2),
        "profit_cny": round(grand_profit, 2),
        "profit_pct": round((grand_profit / grand_cost * 100) if grand_cost else 0, 2),
    }

    return {
        "positions": all_positions,
        "groups": group_summaries,
        "total_cny": total_summary,
    }


@router.post("")
def add_position(pos: Position):
    """添加持仓"""
    rows = _read_positions()
    for r in rows:
        if r.get("代码") == pos.code:
            raise HTTPException(400, f"{pos.code} 已在持仓中，请使用更新")

    market = _detect_market(pos.code)
    rows.append({
        "代码": pos.code,
        "名称": pos.name,
        "数量": str(pos.quantity),
        "成本价": str(pos.cost_price),
        "当前价": "0",
        "持仓成本": str(round(pos.quantity * pos.cost_price, 2)),
        "当前市值": "0",
        "盈亏金额": "0",
        "盈亏比例": "0%",
        "备注": pos.note,
        "市场": MARKET_LABELS.get(market, market),
    })
    _write_positions(rows)
    return {"status": "ok", "message": f"已添加 {pos.name}({pos.code})"}


@router.put("/{code}")
def update_position(code: str, body: UpdatePositionBody):
    """更新持仓（JSON body）"""
    rows = _read_positions()
    found = False
    for r in rows:
        if r.get("代码") == code:
            if body.quantity is not None:
                r["数量"] = str(body.quantity)
            if body.cost_price is not None:
                r["成本价"] = str(body.cost_price)
            if body.note is not None:
                r["备注"] = body.note
            qty = float(r["数量"])
            cost = float(r["成本价"])
            r["持仓成本"] = str(round(qty * cost, 2))
            found = True
            break
    if not found:
        raise HTTPException(404, f"未找到 {code}")
    _write_positions(rows)
    return {"status": "ok", "message": f"已更新 {code}"}


@router.delete("/{code}")
def delete_position(code: str):
    """删除持仓"""
    rows = _read_positions()
    new_rows = [r for r in rows if r.get("代码") != code]
    if len(new_rows) == len(rows):
        raise HTTPException(404, f"未找到 {code}")
    _write_positions(new_rows)
    return {"status": "ok", "message": f"已删除 {code}"}


# ========== 持仓分析 ==========

# 行业→主题映射
THEME_MAP = {
    "光伏设备": "新能源", "电池": "新能源", "能源金属": "新能源", "电力": "新能源",
    "消费电子": "消费电子", "计算机设备": "科技", "电网设备": "新能源",
    "化学制药": "医药", "中药Ⅱ": "医药",
    "农化制品": "化工", "化学制品": "化工", "化学原料": "化工",
    "旅游零售Ⅱ": "消费", "航运港口": "周期",
    "小金属": "有色", "汽车零部件": "汽车",
    "半导体": "半导体",
}

# 美股→行业映射
US_STOCK_INDUSTRY = {
    "TSLA": "汽车", "TSM": "半导体", "CSCO": "科技",
    "GOOG": "互联网", "XPEV": "汽车",
    "AAPL": "消费电子", "MSFT": "科技", "AMZN": "互联网",
    "NVDA": "半导体", "AMD": "半导体", "INTC": "半导体",
    "META": "互联网", "NFLX": "互联网", "BABA": "互联网",
    "JD": "互联网", "PDD": "互联网", "BIDU": "科技",
    "NIO": "汽车", "LI": "汽车", "CRCL": "区块链",
}

# 港股→行业映射
HK_STOCK_INDUSTRY = {
    "01211": "汽车",
}


def _get_industry(code: str, name: str) -> str:
    """获取股票行业"""
    market = _detect_market(code)
    if market == "a_stock":
        try:
            db_path = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT industry FROM stock_info WHERE code=?", (code,)).fetchone()
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


def _get_theme(industry: str) -> str:
    """行业→主题"""
    return THEME_MAP.get(industry, "其他")


@router.get("/analysis")
def position_analysis():
    """持仓多维度分析"""
    rows = _read_positions()
    if not rows:
        return {"analysis": {"total": {"count": 0}}}

    # 批量获取美股/港股价格
    us_codes = [r.get("代码", "") for r in rows if _detect_market(r.get("代码", "")) == "us_stock"]
    hk_codes = [r.get("代码", "") for r in rows if _detect_market(r.get("代码", "")) == "hk_stock"]
    us_prices = _get_us_prices_batch(us_codes) if us_codes else {}
    hk_prices = _get_hk_prices_batch(hk_codes) if hk_codes else {}

    # 构建持仓（注入批量获取的实时价）
    positions = []
    for r in rows:
        code = r.get("代码", "")
        p = _build_position(r)
        market = _detect_market(code)
        if market == "us_stock" and code in us_prices:
            p["current_price"] = us_prices[code]
            qty = p["quantity"]
            cost_total = p["cost_total"]
            p["market_value"] = round(qty * us_prices[code], 2)
            p["profit_amount"] = round(p["market_value"] - cost_total, 2)
            p["profit_pct"] = round((p["profit_amount"] / cost_total * 100) if cost_total else 0, 2)
        elif market == "hk_stock" and code in hk_prices:
            p["current_price"] = hk_prices[code]
            qty = p["quantity"]
            cost_total = p["cost_total"]
            p["market_value"] = round(qty * hk_prices[code], 2)
            p["profit_amount"] = round(p["market_value"] - cost_total, 2)
            p["profit_pct"] = round((p["profit_amount"] / cost_total * 100) if cost_total else 0, 2)
        positions.append(p)

    # --- 1. 盈亏排行 ---
    by_profit = sorted(positions, key=lambda p: p["profit_amount"])
    top_losers = [{"code": p["code"], "name": p["name"], "profit": round(p["profit_amount"], 2)} for p in by_profit[:5]]
    top_winners = [{"code": p["code"], "name": p["name"], "profit": round(p["profit_amount"], 2)} for p in reversed(by_profit[-5:])]

    # --- 2. 市场分布 ---
    market_dist = {}
    for p in positions:
        m = p["market"]
        if m not in market_dist:
            market_dist[m] = {"label": MARKET_LABELS.get(m, m), "count": 0, "value": 0, "cost": 0, "profit": 0}
        market_dist[m]["count"] += 1
        market_dist[m]["value"] += p["market_value"]
        market_dist[m]["cost"] += p["cost_total"]
        market_dist[m]["profit"] += p["profit_amount"]

    for v in market_dist.values():
        v["value"] = round(v["value"], 2)
        v["cost"] = round(v["cost"], 2)
        v["profit"] = round(v["profit"], 2)

    market_dist_list = sorted(market_dist.items(), key=lambda x: x[1]["value"], reverse=True)
    market_breakdown = {m: v for m, v in market_dist_list}

    # --- 3. 行业分布 ---
    industry_data = {}
    for p in positions:
        ind = _get_industry(p["code"], p["name"])
        if ind not in industry_data:
            industry_data[ind] = {"industry": ind, "count": 0, "value": 0, "cost": 0, "profit": 0, "stocks": []}
        industry_data[ind]["count"] += 1
        industry_data[ind]["value"] += p["market_value"]
        industry_data[ind]["cost"] += p["cost_total"]
        industry_data[ind]["profit"] += p["profit_amount"]
        industry_data[ind]["stocks"].append(p["code"])

    for v in industry_data.values():
        v["value"] = round(v["value"], 2)
        v["cost"] = round(v["cost"], 2)
        v["profit"] = round(v["profit"], 2)

    industry_list = sorted(industry_data.values(), key=lambda x: x["value"], reverse=True)

    # --- 4. 主题分布 ---
    theme_data = {}
    for p in positions:
        ind = _get_industry(p["code"], p["name"])
        theme = _get_theme(ind)
        if theme not in theme_data:
            theme_data[theme] = {"theme": theme, "count": 0, "value": 0, "cost": 0, "profit": 0}
        theme_data[theme]["count"] += 1
        theme_data[theme]["value"] += p["market_value"]
        theme_data[theme]["cost"] += p["cost_total"]
        theme_data[theme]["profit"] += p["profit_amount"]

    for v in theme_data.values():
        v["value"] = round(v["value"], 2)
        v["cost"] = round(v["cost"], 2)
        v["profit"] = round(v["profit"], 2)

    theme_list = sorted(theme_data.values(), key=lambda x: x["value"], reverse=True)

    # --- 5. 汇总 ---
    total_cost = sum(p["cost_total"] for p in positions)
    total_value = sum(p["market_value"] for p in positions)
    total_profit = sum(p["profit_amount"] for p in positions)

    return {
        "analysis": {
            "total": {
                "count": len(positions),
                "cost": round(total_cost, 2),
                "value": round(total_value, 2),
                "profit": round(total_profit, 2),
                "profit_pct": round((total_profit / total_cost * 100) if total_cost else 0, 2),
            },
            "market_breakdown": market_breakdown,
            "industry_distribution": industry_list,
            "theme_distribution": theme_list,
            "top_winners": top_winners,
            "top_losers": top_losers,
        }
    }
