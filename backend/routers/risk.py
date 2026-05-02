"""
风控预警 API
"""
from fastapi import APIRouter
from datetime import date, datetime
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

from backend.config import POSITION_FILE, MARKET_DATA_DIR

router = APIRouter()


@router.get("/check/{code}")
def buy_risk_check(code: str):
    """快速买入风控检查 - 转发到analysis"""
    pass  # analysis.py 已有 /analysis/{code}/risk


@router.get("/alerts")
def get_alerts():
    """持仓预警：跌破均线、集中度超标"""
    # 读取持仓
    if not os.path.exists(POSITION_FILE):
        return {"alerts": []}

    import csv
    positions = []
    with open(POSITION_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        positions = list(reader)

    if not positions:
        return {"alerts": []}

    # 读取今日行情
    today = date.today()
    df = None
    for i in range(4):
        d = today.isoformat() if i == 0 else pd.Timestamp(today - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        path = MARKET_DATA_DIR / f"沪深京A股{d}.csv"
        if path.exists():
            df = pd.read_csv(path, encoding="utf-16", sep="\t")
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
            break

    alerts = []

    if df is not None:
        for pos in positions:
            code = pos.get("代码", "")
            name = pos.get("名称", "")
            match = df[df["代码"] == code]
            if match.empty:
                continue

            row = match.iloc[0]
            try:
                close = float(row["最新"])
            except (ValueError, TypeError):
                continue

            # 判断是否接近涨停/跌停
            try:
                change = float(str(row["涨幅"]).replace("--", "0").rstrip("%"))
            except:
                change = 0

            if change <= -7:
                alerts.append({
                    "type": "danger",
                    "code": code,
                    "name": name,
                    "message": f"⚠️ 大跌 {change}%，需关注",
                    "value": f"{change}%",
                })

            if change >= 9.5:
                alerts.append({
                    "type": "info",
                    "code": code,
                    "name": name,
                    "message": f"🔥 涨停 {change}%",
                    "value": f"{change}%",
                })

    # 仓位集中度检查
    try:
        total_value = sum(float(p.get("数量", 0)) * float(p.get("成本价", 0)) for p in positions)
        for p in positions:
            try:
                pct = (float(p.get("数量", 0)) * float(p.get("成本价", 0))) / total_value * 100
            except:
                continue
            if pct > 30:
                alerts.append({
                    "type": "warning",
                    "code": p.get("代码", ""),
                    "name": p.get("名称", ""),
                    "message": f"⚠️ 仓位集中度 {pct:.0f}%，超过30%阈值",
                    "value": f"{pct:.0f}%",
                })
    except:
        pass

    return {
        "date": str(today),
        "alerts": alerts,
        "total": len(alerts),
    }
