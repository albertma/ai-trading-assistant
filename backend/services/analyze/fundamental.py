"""
基本面分析服务
财务摘要、主营业务构成、三张财务报表、费用分析、财报健康评分
"""

import sqlite3
import os
from datetime import date
from typing import Any

from backend.services.financial_service import (
    get_financial_summary,
    get_revenue_breakdown,
    get_expense_data,
    get_financial_indicators,
    get_management_changes,
    get_main_shareholders,
    get_balance_sheet,
    get_cash_flow_sheet,
    get_profit_sheet,
)

DB_PATH = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")


class FundamentalAnalyzer:
    """基本面分析 — 财务摘要/收入构成/财务报表/费用/健康评分"""

    @staticmethod
    def get_financial_summary(code: str) -> dict | None:
        """财务摘要（最近5期）"""
        fin = get_financial_summary(code)
        if fin and fin.get("records"):
            fin["records"] = fin["records"][-5:]
        return fin

    @staticmethod
    def get_revenue_breakdown(code: str) -> list | None:
        """主营业务构成"""
        return get_revenue_breakdown(code)

    @staticmethod
    def get_statements(code: str) -> dict[str, Any]:
        """三张财务报表"""
        result = {}
        try:
            bs = get_balance_sheet(code)
            if bs:
                result["balance_sheet"] = [{
                    "period": r.get("报告期") or r.get("日期", ""),
                    "items": {k: v for k, v in r.items() if k not in ("报告期", "日期")}
                } for r in bs[:8]]
        except Exception:
            result["balance_sheet"] = []

        try:
            pl = get_profit_sheet(code)
            if pl:
                result["profit_sheet"] = [{
                    "period": r.get("报告期") or r.get("日期", ""),
                    "items": {k: v for k, v in r.items() if k not in ("报告期", "日期")}
                } for r in pl[:8]]
        except Exception:
            result["profit_sheet"] = []

        try:
            cf = get_cash_flow_sheet(code)
            if cf:
                result["cash_flow"] = [{
                    "period": r.get("报告期") or r.get("日期", ""),
                    "items": {k: v for k, v in r.items() if k not in ("报告期", "日期")}
                } for r in cf[:8]]
        except Exception:
            result["cash_flow"] = []

        return result

    @staticmethod
    def get_expense_analysis(code: str) -> dict | None:
        """费用分析（销售/管理/研发/财务费用率）"""
        return get_expense_data(code)

    @staticmethod
    def compute_health_score(records: list[dict] | None, period: str = "latest") -> dict[str, Any]:
        """财报健康评分（6维度：成长性/盈利/偿债/运营/现金流/估值）"""
        if not records:
            return {"score": 0, "max": 100, "pct": 0, "level": "无数据", "checks": []}

        # 取最新一期数据
        latest = records[-1]
        prev = records[-2] if len(records) >= 2 else {}

        checks = []
        total = 0
        max_score = 100

        # 1. 营收增长（20分）
        rev_growth = latest.get("营业总收入同比增长率") or latest.get("revenue_yoy") or 0
        try:
            rev_growth = float(rev_growth)
        except (ValueError, TypeError):
            rev_growth = 0
        if rev_growth > 20:
            total += 20
        elif rev_growth > 10:
            total += 15
        elif rev_growth > 0:
            total += 10
        elif rev_growth > -10:
            total += 5
        checks.append({"item": "营收增长", "value": f"{rev_growth:.1f}%", "score": total if total <= 20 else 20, "max": 20})

        # 2. 净利增长（20分）
        profit_growth = latest.get("净利润同比增长率") or latest.get("profit_yoy") or 0
        try:
            profit_growth = float(profit_growth)
        except (ValueError, TypeError):
            profit_growth = 0
        profit_score = 0
        if profit_growth > 20:
            profit_score = 20
        elif profit_growth > 10:
            profit_score = 15
        elif profit_growth > 0:
            profit_score = 10
        elif profit_growth > -10:
            profit_score = 5
        total += profit_score
        checks.append({"item": "净利增长", "value": f"{profit_growth:.1f}%", "score": profit_score, "max": 20})

        # 3. 毛利率（15分）
        gm = latest.get("销售毛利率") or latest.get("gross_margin") or 0
        try:
            gm = float(gm)
        except (ValueError, TypeError):
            gm = 0
        gm_score = 0
        if gm > 60:
            gm_score = 15
        elif gm > 40:
            gm_score = 12
        elif gm > 20:
            gm_score = 8
        elif gm > 0:
            gm_score = 4
        total += gm_score
        checks.append({"item": "销售毛利率", "value": f"{gm:.1f}%", "score": gm_score, "max": 15})

        # 4. ROE（15分）
        roe = latest.get("净资产收益率") or latest.get("roe") or 0
        try:
            roe = float(roe)
        except (ValueError, TypeError):
            roe = 0
        roe_score = 0
        if roe > 20:
            roe_score = 15
        elif roe > 15:
            roe_score = 12
        elif roe > 10:
            roe_score = 8
        elif roe > 5:
            roe_score = 4
        total += roe_score
        checks.append({"item": "净资产收益率(ROE)", "value": f"{roe:.1f}%", "score": roe_score, "max": 15})

        # 5. 资产负债率（15分）
        debt = latest.get("资产负债率") or latest.get("debt_ratio") or 0
        try:
            debt = float(debt)
        except (ValueError, TypeError):
            debt = 0
        debt_score = 0
        if debt < 30:
            debt_score = 15
        elif debt < 50:
            debt_score = 12
        elif debt < 70:
            debt_score = 8
        else:
            debt_score = 4
        total += debt_score
        checks.append({"item": "资产负债率", "value": f"{debt:.1f}%", "score": debt_score, "max": 15})

        # 6. 流动比率（15分）
        cr = latest.get("流动比率") or latest.get("current_ratio") or 0
        try:
            cr = float(cr)
        except (ValueError, TypeError):
            cr = 0
        cr_score = 0
        if cr > 2.5:
            cr_score = 15
        elif cr > 1.5:
            cr_score = 12
        elif cr > 1:
            cr_score = 8
        else:
            cr_score = 4
        total += cr_score
        checks.append({"item": "流动比率", "value": f"{cr:.2f}", "score": cr_score, "max": 15})

        # 评级
        pct = round(total / max_score * 100, 1)
        if pct >= 80:
            level = "优秀"
        elif pct >= 60:
            level = "良好"
        elif pct >= 40:
            level = "一般"
        else:
            level = "较差"

        return {"score": total, "max": max_score, "pct": pct, "level": level, "checks": checks}
