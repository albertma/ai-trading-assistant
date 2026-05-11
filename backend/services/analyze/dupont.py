"""
杜邦分析服务
ROE分解：净利率 × 资产周转率 × 权益乘数
"""

from __future__ import annotations

from typing import Any

from backend.services.financial_service import get_financial_indicators


class DupontAnalyzer:
    """杜邦分析 — ROE分解"""

    @staticmethod
    def _safe_float(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except (ValueError, TypeError):
            return default

    @classmethod
    def analyze(cls, code: str) -> dict[str, Any] | None:
        """杜邦ROE分解"""
        indicators = get_financial_indicators(code)
        if not indicators:
            return None

        rows = []
        for r in indicators[:8]:
            period = r.get("日期", "")
            roe = cls._safe_float(r.get("净资产收益率"))
            net_margin = cls._safe_float(r.get("销售净利率") or r.get("净利润率"))
            asset_turnover = cls._safe_float(r.get("总资产周转率"))
            equity_mult = cls._safe_float(r.get("权益乘数"))
            revenue = cls._safe_float(r.get("营业总收入"))
            net_profit = cls._safe_float(r.get("净利润"))
            total_assets = cls._safe_float(r.get("资产总计") or r.get("总资产"))
            debt_ratio = cls._safe_float(r.get("资产负债率"))

            rows.append({
                "period": period,
                "roe_pct": round(roe, 2),
                "net_margin_pct": round(net_margin, 2),
                "asset_turnover": round(asset_turnover, 4),
                "equity_multiplier": round(equity_mult, 4),
                "revenue": round(revenue, 2),
                "net_profit": round(net_profit, 2),
                "total_assets": round(total_assets, 2),
                "debt_ratio_pct": round(debt_ratio, 2),
            })

        # 变化分析
        changes = []
        for i in range(len(rows) - 1):
            curr, prev = rows[i], rows[i + 1]
            roe_change = round(curr["roe_pct"] - prev["roe_pct"], 2)
            direction = "改善" if roe_change > 0 else ("恶化" if roe_change < 0 else "持平")

            drivers = []
            nm_change = curr["net_margin_pct"] - prev["net_margin_pct"]
            at_change = curr["asset_turnover"] - prev["asset_turnover"]
            em_change = curr["equity_multiplier"] - prev["equity_multiplier"]

            if abs(nm_change) >= 0.5:
                drivers.append(f"净利率{'↑' if nm_change > 0 else '↓'}{nm_change:+.2f}%")
            if abs(at_change) >= 0.01:
                drivers.append(f"周转率{'↑' if at_change > 0 else '↓'}{at_change:+.4f}")
            if abs(em_change) >= 0.01:
                drivers.append(f"杠杆{'↑' if em_change > 0 else '↓'}{em_change:+.4f}")

            changes.append({
                "from_period": prev["period"],
                "to_period": curr["period"],
                "roe_change": roe_change,
                "direction": direction,
                "main_drivers": drivers,
            })

        return {
            "rows": rows,
            "changes": changes,
        }

    @classmethod
    def comment(cls, code: str) -> list[dict] | None:
        """杜邦分析文本评论（含营收/利润/毛利率/EPS）"""
        indicators = get_financial_indicators(code)
        if not indicators:
            return None

        commentaries = []
        for i in range(min(len(indicators) - 1, 4)):
            curr, prev = indicators[i], indicators[i + 1]
            roe_chg = cls._safe_float(curr.get("净资产收益率")) - cls._safe_float(prev.get("净资产收益率"))
            revenue_yoy = cls._safe_float(curr.get("营业总收入同比增长率"))
            profit_yoy = cls._safe_float(curr.get("净利润同比增长率"))
            gross_margin = cls._safe_float(curr.get("销售毛利率"))
            eps = cls._safe_float(curr.get("基本每股收益"))
            period = curr.get("日期", "")

            commentary = f"ROE{'改善' if roe_chg > 0 else '下滑'}{abs(roe_chg):.2f}%"
            if revenue_yoy:
                commentary += f"，营收{'增长' if revenue_yoy > 0 else '下滑'}{abs(revenue_yoy):.1f}%"
            if profit_yoy:
                commentary += f"，净利{'增长' if profit_yoy > 0 else '下滑'}{abs(profit_yoy):.1f}%"
            if gross_margin:
                commentary += f"，毛利率{gross_margin:.1f}%"
            if eps:
                commentary += f"，EPS{eps:.2f}"

            prev_period = prev.get("日期", "")
            commentaries.append({
                "from_period": prev_period,
                "to_period": period,
                "commentary": commentary,
                "details": {
                    "revenue_yoy": round(revenue_yoy, 2) if revenue_yoy else None,
                    "profit_yoy": round(profit_yoy, 2) if profit_yoy else None,
                    "gross_margin": round(gross_margin, 2) if gross_margin else None,
                    "eps": round(eps, 4) if eps else None,
                },
            })

        return commentaries
