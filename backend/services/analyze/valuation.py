"""
估值分析服务
PE/PB/PS分位数、同行对比、DCF估值
"""

from __future__ import annotations

from typing import Any

from backend.services.financial_service import get_financial_summary, get_financial_indicators
from backend.services.external.csv_client import get_industry_from_code, get_industry_data


class ValuationAnalyzer:
    """估值分析 — PE/PB分位数、同行对比、DCF模型"""

    @staticmethod
    def _safe_float(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except (ValueError, TypeError):
            return default

    @classmethod
    def analyze(cls, code: str, sector: str | None = None) -> dict[str, Any]:
        """全量估值分析"""
        fin = get_financial_summary(code)
        records = fin.get("records", []) if fin else []
        latest = records[-1] if records else {}
        prev = records[-2] if len(records) >= 2 else {}

        if not sector or sector == "--":
            sector = get_industry_from_code(code, 5)

        # 基本估值指标
        pe = cls._safe_float(latest.get("市盈率") or latest.get("pe"))
        pb = cls._safe_float(latest.get("市净率") or latest.get("pb"))
        ps = cls._safe_float(latest.get("市销率") or latest.get("ps"))
        eps = cls._safe_float(latest.get("基本每股收益") or latest.get("eps"))
        bps = cls._safe_float(latest.get("每股净资产") or latest.get("bps"))
        revenue = cls._safe_float(latest.get("营业总收入"))
        market_cap = cls._safe_float(latest.get("总市值"))

        # 同行对比 — 从行业板块数据获取平均估值
        peer_avg_pe = None
        peer_avg_pb = None
        peer_avg_ps = None
        peer_count = 0
        try:
            ind_data = get_industry_data(sector) if sector else None
            if ind_data:
                peer_avg_pe = ind_data.get("avg_pe") or ind_data.get("pe")
                peer_avg_pb = ind_data.get("avg_pb") or ind_data.get("pb")
                peer_count = ind_data.get("stock_count", 0) or 0
        except Exception:
            pass

        # 估值判断
        verdicts = []

        if pe and peer_avg_pe:
            pe_ratio = pe / peer_avg_pe
            if pe_ratio < 0.5:
                pe_verdict = "显著低估"
                pe_signal = "buy"
            elif pe_ratio < 0.8:
                pe_verdict = "偏低"
                pe_signal = "overweight"
            elif pe_ratio < 1.2:
                pe_verdict = "合理"
                pe_signal = "hold"
            elif pe_ratio < 2:
                pe_verdict = "偏高"
                pe_signal = "underweight"
            else:
                pe_verdict = "显著高估"
                pe_signal = "sell"
            verdicts.append({"metric": "PE", "value": pe, "peer_avg": peer_avg_pe, "ratio": round(pe_ratio, 2), "verdict": pe_verdict, "signal": pe_signal})
        else:
            verdicts.append({"metric": "PE", "value": pe, "peer_avg": peer_avg_pe, "ratio": None, "verdict": "数据不足", "signal": "unknown"})

        if pb and peer_avg_pb:
            pb_ratio = pb / peer_avg_pb
            if pb_ratio < 0.5:
                verdicts.append({"metric": "PB", "value": pb, "peer_avg": peer_avg_pb, "ratio": round(pb_ratio, 2), "verdict": "显著低估", "signal": "buy"})
            elif pb_ratio < 0.8:
                verdicts.append({"metric": "PB", "value": pb, "peer_avg": peer_avg_pb, "ratio": round(pb_ratio, 2), "verdict": "偏低", "signal": "overweight"})
            elif pb_ratio < 1.2:
                verdicts.append({"metric": "PB", "value": pb, "peer_avg": peer_avg_pb, "ratio": round(pb_ratio, 2), "verdict": "合理", "signal": "hold"})
            else:
                verdicts.append({"metric": "PB", "value": pb, "peer_avg": peer_avg_pb, "ratio": round(pb_ratio, 2), "verdict": "偏高", "signal": "underweight"})

        # PEG估算
        rev_growth = cls._safe_float(latest.get("营业总收入同比增长率") or latest.get("revenue_yoy"))
        peg = round(pe / rev_growth, 2) if pe and rev_growth > 0 else None

        result = {
            "code": code,
            "sector": sector,
            "valuation_metrics": {
                "pe": pe,
                "pb": pb,
                "ps": ps,
                "eps": eps,
                "bps": bps,
                "peg": peg,
                "market_cap": market_cap,
            },
            "peer_comparison": {
                "pe_avg": peer_avg_pe,
                "pb_avg": peer_avg_pb,
                "ps_avg": peer_avg_ps,
                "peer_count": peer_count,
            },
            "verdicts": verdicts,
            "overall_signal": cls._overall_signal(verdicts),
        }
        return result

    @staticmethod
    def _overall_signal(verdicts: list[dict]) -> str:
        """综合估值信号"""
        signals = [v.get("signal") for v in verdicts if v.get("signal") not in ("unknown", None)]
        if not signals:
            return "unknown"
        if all(s == "buy" for s in signals):
            return "buy"
        if all(s in ("buy", "overweight") for s in signals):
            return "overweight"
        if "sell" in signals:
            return "sell"
        if "underweight" in signals:
            return "underweight"
        return "hold"
