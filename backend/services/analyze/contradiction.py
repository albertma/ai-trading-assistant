"""
矛盾分析服务
5大矛盾对 + 主次判定 + 转化条件
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from typing import Any

import pandas as pd

from backend.services.market_service import get_daily_history
from backend.services.financial_service import (
    get_financial_summary,
    get_financial_indicators,
    get_revenue_breakdown,
)
from backend.services.external.csv_client import get_industry_from_code

DB_PATH = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")


class ContradictionAnalyzer:
    """矛盾分析 — 价格vs价值 / 成长vs估值 / 趋势vs反转 / 预期vs现实 / 行业vs个股"""

    @staticmethod
    def _safe_float(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except (ValueError, TypeError):
            return default

    @classmethod
    def analyze(cls, code: str, sector: str | None = None) -> dict[str, Any]:
        """5大矛盾对分析"""
        # 获取财务数据
        fin = get_financial_summary(code)
        records = fin.get("records", []) if fin else []
        latest = records[-1] if records else {}
        prev = records[-2] if len(records) >= 2 else {}

        # 技术数据
        df = get_daily_history(code)
        current_price = float(df["close"].iloc[-1]) if df is not None and not df.empty else 0
        ma20 = float(df["close"].tail(20).mean()) if df is not None and len(df) >= 20 else 0
        ma60 = float(df["close"].tail(60).mean()) if df is not None and len(df) >= 60 else 0
        change_5d = (current_price / float(df["close"].iloc[-6]) - 1) * 100 if df is not None and len(df) > 6 else 0
        change_20d = (current_price / float(df["close"].iloc[-21]) - 1) * 100 if df is not None and len(df) > 21 else 0

        # 行业数据
        if not sector or sector == "--":
            sector = get_industry_from_code(code, 5)

        # 获取行业板块数据用于个股对比
        industry_data = None
        industry_avg_chg = None
        try:
            from backend.services.external.csv_client import get_industry_data
            industry_data = get_industry_data(sector) if sector else None
            if industry_data:
                industry_avg_chg = industry_data.get("avg_change")
        except Exception:
            pass

        contradictions = []
        scores = []

        # ── 矛盾1: 价格 vs 价值（均线乖离 + 估值） ──
        val_score = 50
        val_items = []
        if current_price and ma20 and ma60:
            gap20 = (current_price - ma20) / ma20 * 100
            gap60 = (current_price - ma60) / ma60 * 100
            if gap20 > 20:
                val_items.append({"type": "danger", "label": "价格/MA20乖离", "value": f"{gap20:.1f}%", "verdict": "短期严重超买"})
                val_score -= 15
            elif gap20 > 10:
                val_items.append({"type": "warning", "label": "价格/MA20乖离", "value": f"{gap20:.1f}%", "verdict": "短期偏高"})
                val_score -= 8
            elif gap20 < -10:
                val_items.append({"type": "success", "label": "价格/MA20乖离", "value": f"{gap20:.1f}%", "verdict": "短期超卖"})
                val_score += 10
            else:
                val_items.append({"type": "info", "label": "价格/MA20乖离", "value": f"{gap20:.1f}%", "verdict": "正常范围"})

            if gap60 > 30:
                val_items.append({"type": "danger", "label": "价格/MA60乖离", "value": f"{gap60:.1f}%", "verdict": "中期严重偏离"})
                val_score -= 15
            elif gap60 > 15:
                val_items.append({"type": "warning", "label": "价格/MA60乖离", "value": f"{gap60:.1f}%", "verdict": "中期偏高"})
                val_score -= 8
            elif gap60 < -15:
                val_items.append({"type": "success", "label": "价格/MA60乖离", "value": f"{gap60:.1f}%", "verdict": "中期超卖"})
                val_score += 10
            else:
                val_items.append({"type": "info", "label": "价格/MA60乖离", "value": f"{gap60:.1f}%", "verdict": "正常范围"})

        val_pct = max(0, min(100, val_score))
        if val_pct < 40:
            val_verdict = "价格偏离价值较大"
        elif val_pct < 60:
            val_verdict = "价格与价值基本匹配"
        else:
            val_verdict = "价格低于内在价值，存在安全边际"
        contradictions.append({
            "id": "price_value", "icon": "💰", "name": "价格 vs 价值",
            "score": val_pct, "max": 100, "pct": val_pct,
            "desc": val_verdict, "items": val_items,
            "transformation": "等待回调至MA20附近或业绩验证后介入",
        })
        scores.append(("price_value", val_pct))

        # ── 矛盾2: 成长 vs 估值（营收增速 vs 市盈率） ──
        growth_score = 50
        growth_items = []
        rev_growth = cls._safe_float(latest.get("营业总收入同比增长率") or latest.get("revenue_yoy"))
        profit_growth = cls._safe_float(latest.get("净利润同比增长率") or latest.get("profit_yoy"))
        pe = cls._safe_float(latest.get("市盈率") or latest.get("pe"))

        if rev_growth > 0:
            growth_score += min(rev_growth / 2, 20)
            growth_items.append({"type": "success", "label": "营收增长", "value": f"{rev_growth:.1f}%", "verdict": "正向增长"})
        else:
            growth_score -= min(abs(rev_growth) / 2, 20)
            growth_items.append({"type": "danger", "label": "营收增长", "value": f"{rev_growth:.1f}%", "verdict": "负增长"})

        if profit_growth > 0:
            growth_score += min(profit_growth / 2, 20)
            growth_items.append({"type": "success", "label": "净利增长", "value": f"{profit_growth:.1f}%", "verdict": "盈利增长"})
        else:
            growth_score -= min(abs(profit_growth) / 2, 20)
            growth_items.append({"type": "danger", "label": "净利增长", "value": f"{profit_growth:.1f}%", "verdict": "盈利下滑"})

        growth_pct = max(0, min(100, growth_score))
        contradictions.append({
            "id": "growth_value", "icon": "📈", "name": "成长 vs 估值",
            "score": growth_pct, "max": 100, "pct": growth_pct,
            "desc": f"营收{'增长' if rev_growth > 0 else '下滑'}{rev_growth:.1f}%，净利{'增长' if profit_growth > 0 else '下滑'}{profit_growth:.1f}%，成长性{'好' if growth_pct > 60 else '一般' if growth_pct > 40 else '差'}",
            "items": growth_items,
            "transformation": "连续2个季度增速加快可确认成长拐点",
        })
        scores.append(("growth_value", growth_pct))

        # ── 矛盾3: 趋势 vs 反转（短期 vs 中期涨跌幅） ──
        trend_score = 50
        trend_items = []
        if change_5d > 0 and change_20d > 0:
            trend_score += 20
            trend_items.append({"type": "success", "label": "短期趋势", "value": f"{change_5d:.1f}%", "verdict": "短期上涨"})
            trend_items.append({"type": "success", "label": "中期趋势", "value": f"{change_20d:.1f}%", "verdict": "中期上涨"})
        elif change_5d < 0 and change_20d < 0:
            trend_score -= 20
            trend_items.append({"type": "danger", "label": "短期趋势", "value": f"{change_5d:.1f}%", "verdict": "短期下跌"})
            trend_items.append({"type": "danger", "label": "中期趋势", "value": f"{change_20d:.1f}%", "verdict": "中期下跌"})
        elif change_5d > 0 and change_20d < 0:
            trend_items.append({"type": "warning", "label": "背离", "value": f"5日{change_5d:.1f}% / 20日{change_20d:.1f}%", "verdict": "短多中空，可能反转"})
        else:
            trend_items.append({"type": "warning", "label": "背离", "value": f"5日{change_5d:.1f}% / 20日{change_20d:.1f}%", "verdict": "短空中多，可能企稳"})

        trend_pct = max(0, min(100, trend_score))
        contradictions.append({
            "id": "trend_reversal", "icon": "🔄", "name": "趋势 vs 反转",
            "score": trend_pct, "max": 100, "pct": trend_pct,
            "desc": f"5日涨跌{change_5d:.1f}%，20日涨跌{change_20d:.1f}%，{'趋势向好' if trend_pct > 60 else '方向不明' if trend_pct > 40 else '趋势偏弱'}",
            "items": trend_items,
            "transformation": "突破关键均线（MA60）并放量可确认反转",
        })
        scores.append(("trend_reversal", trend_pct))

        # ── 矛盾4: 预期 vs 现实（同比增速对比） ──
        expect_score = 50
        expect_items = []
        prev_rev = cls._safe_float(prev.get("营业总收入同比增长率") or prev.get("revenue_yoy"))
        prev_profit = cls._safe_float(prev.get("净利润同比增长率") or prev.get("profit_yoy"))

        if rev_growth and prev_rev:
            delta = rev_growth - prev_rev
            if delta > 10:
                expect_score += 20
                expect_items.append({"type": "success", "label": "营收增速变化", "value": f"{delta:+.1f}%", "verdict": "加速增长"})
            elif delta > 0:
                expect_score += 10
                expect_items.append({"type": "info", "label": "营收增速变化", "value": f"{delta:+.1f}%", "verdict": "小幅改善"})
            elif delta > -10:
                expect_score -= 10
                expect_items.append({"type": "warning", "label": "营收增速变化", "value": f"{delta:+.1f}%", "verdict": "增速放缓"})
            else:
                expect_score -= 20
                expect_items.append({"type": "danger", "label": "营收增速变化", "value": f"{delta:+.1f}%", "verdict": "大幅减速"})

        expect_pct = max(0, min(100, expect_score))
        contradictions.append({
            "id": "expect_reality", "icon": "🎯", "name": "预期 vs 现实",
            "score": expect_pct, "max": 100, "pct": expect_pct,
            "desc": f"营收增速从{prev_rev:.1f}%→{rev_growth:.1f}%，{'超预期' if expect_pct > 60 else '符合预期' if expect_pct > 40 else '不及预期'}",
            "items": expect_items,
            "transformation": "超预期持续2期以上可确认业绩拐点",
        })
        scores.append(("expect_reality", expect_pct))

        # ── 矛盾5: 行业 vs 个股（个股 vs 行业板块对比） ──
        sector_score = 50
        sector_items = []
        if industry_avg_chg is not None and current_price and df is not None and not df.empty:
            indiv = (current_price / float(df["close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0
            diff = indiv - industry_avg_chg
            if diff > 3:
                sector_score += 15
                sector_items.append({"type": "success", "label": "个股vs板块", "value": f"{diff:+.1f}%", "verdict": "明显强于板块"})
            elif diff > 0:
                sector_items.append({"type": "info", "label": "个股vs板块", "value": f"{diff:+.1f}%", "verdict": "略强于板块"})
            elif diff > -3:
                sector_items.append({"type": "warning", "label": "个股vs板块", "value": f"{diff:+.1f}%", "verdict": "略弱于板块"})
            else:
                sector_score -= 15
                sector_items.append({"type": "danger", "label": "个股vs板块", "value": f"{diff:+.1f}%", "verdict": "明显弱于板块"})

        sector_pct = max(0, min(100, sector_score))
        contradictions.append({
            "id": "sector_stock", "icon": "🏭", "name": "行业 vs 个股",
            "score": sector_pct, "max": 100, "pct": sector_pct,
            "desc": f"个股{'强于' if sector_pct > 60 else '同步于' if sector_pct > 40 else '弱于'}行业板块",
            "items": sector_items,
            "transformation": "个股持续领涨行业板块，说明有独立的α逻辑",
        })
        scores.append(("sector_stock", sector_pct))

        # 排序：按 pct 从低到高（矛盾越大越靠前）
        contradictions.sort(key=lambda c: c["pct"])
        total_score = sum(c["pct"] for c in contradictions)
        total_max = len(contradictions) * 100
        total_pct = round(total_score / total_max * 100, 1) if total_max else 0

        # 主次矛盾
        primary = contradictions[0] if contradictions else None
        secondary = contradictions[1] if len(contradictions) > 1 else None
        third = contradictions[2] if len(contradictions) > 2 else None

        # 整体判断
        if total_pct < 40:
            overall = "矛盾突出 ⚠️"
            overall_desc = f"总分{total_pct}%，多项矛盾突出，投资风险较大，建议等待矛盾缓和后再做决策"
        elif total_pct < 60:
            overall = "存在矛盾 ⚖️"
            overall_desc = f"总分{total_pct}%，部分矛盾需要关注，可重点跟踪主要矛盾的转化信号"
        else:
            overall = "矛盾较少 ✅"
            overall_desc = f"总分{total_pct}%，各项指标较为一致，投资逻辑清晰"

        return {
            "total_score": total_score,
            "total_max": total_max,
            "total_pct": total_pct,
            "overall": overall,
            "overall_desc": overall_desc,
            "primary": primary,
            "secondary": secondary,
            "third": third,
            "contradictions": contradictions,
        }
