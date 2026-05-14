"""
矛盾分析V2：动态主次矛盾转换追踪
===================================
基于5大矛盾对的辩证框架，核心关注矛盾间的转化关系。

三层增强：
  1. 矛盾动量 — 分数和排名的时序变化（Δ + Δacceleration）
  2. 转换检测 — 主次矛盾的升降切换
  3. 矛盾生命周期 — 潜伏→激化→极值→转化→扬弃

输入：财务摘要records + 当日行情（可选）+ 板块数据（可选，A股）
输出：矛盾分析 + 动量 + 转换信号 + 生命周期 + 收敛性
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  5大矛盾对配置
# ──────────────────────────────────────────────
CONTRADICTION_DEFS = [
    {
        "id": "price_value",
        "name": "价格 vs 价值",
        "icon": "⚖️",
        "desc": "当前价格偏离内在价值的程度",
        "max": 36,
    },
    {
        "id": "growth_valuation",
        "name": "成长 vs 估值",
        "icon": "📈",
        "desc": "成长速度是否已被市场充分定价",
        "max": 42,
    },
    {
        "id": "quality_cashflow",
        "name": "盈利质量 vs 现金流",
        "icon": "💧",
        "desc": "账面利润转化为真实现金的能力",
        "max": 32,
    },
    {
        "id": "debt_safety",
        "name": "负债扩张 vs 财务安全",
        "icon": "🏛️",
        "desc": "加杠杆是否带来超额回报",
        "max": 34,
    },
    {
        "id": "industry_position",
        "name": "行业景气 vs 个股地位",
        "icon": "🔭",
        "desc": "行业β收益 vs 个股α收益",
        "max": 30,
    },
]

_CONTRADICTION_IDS = [c["id"] for c in CONTRADICTION_DEFS]


# ──────────────────────────────────────────────
#  工具函数
# ──────────────────────────────────────────────
def _flt(v):
    """安全的float转换"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return None


def _parse_fin_val(v):
    """从records字段解析数值（兼容字符串/None/百分比等）"""
    if v is None or v == "--" or v == "":
        return None
    try:
        return float(str(v).replace("%", "").replace("亿", ""))
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════
#  矛盾分析引擎
# ══════════════════════════════════════════════


class ContradictionEngine:
    """矛盾分析引擎 — 可被A股/美股/其他市场复用"""

    def __init__(
        self,
        code: str,
        name: str,
        # 财务摘要 records（与A股financial_summary.records兼容）
        fin_records: list[dict] | None = None,
        # 财务分析指标（latest period）
        indicators: dict | None = None,
        # 当日行情
        cur_price: float | None = None,
        chg_pct: float | None = None,
        pe: float | None = None,
        pb: float | None = None,
        mcap: float | None = None,
        chg3d: float | None = None,
        # 板块数据（可选）
        industry_avg_chg: float | None = None,
        industry_up_ratio: float | None = None,
        industry_rank: int | None = None,
        industry_total: int | None = None,
        sector_name: str | None = None,
    ):
        self.code = code
        self.name = name
        self.fin_records = fin_records or []
        self.indicators = indicators or {}
        self.lat = self.indicators  # 最新一期指标

        # 行情
        self.cur_price = cur_price
        self.chg_pct = chg_pct
        self.pe = pe
        self.pb = pb
        self.mcap = mcap
        self.chg3d = chg3d

        # 板块
        self.industry_avg_chg = industry_avg_chg
        self.industry_up_ratio = industry_up_ratio
        self.industry_rank = industry_rank
        self.industry_total = industry_total
        self.sector_name = sector_name

    # ── 5大矛盾评分 ────────────────────────

    def _score_price_value(self) -> dict:
        """矛盾① 价格 vs 价值"""
        items = []
        score = 0
        _max = 36

        # 同步：当日涨跌幅
        if self.chg_pct is not None:
            abs_chg = abs(self.chg_pct)
            if abs_chg > 7:
                vs = 10
                vd = "极端波动 ⚠️"
            elif abs_chg > 4:
                vs = 8
                vd = "强波动"
            else:
                vs = 5
                vd = "正常波动"
            score += vs
            items.append({"type": "同步", "label": "当日涨跌幅", "value": f"{self.chg_pct:+.2f}%", "score": vs, "max": 10, "verdict": vd})

        # 同步：PE
        if self.pe is not None and self.pe > 0:
            if self.pe > 80:
                ps, pd = 1, "极高估值 🔴"
            elif self.pe > 40:
                ps, pd = 3, "偏高估值 🟡"
            elif self.pe > 20:
                ps, pd = 6, "合理估值 🟢"
            elif self.pe > 10:
                ps, pd = 8, "偏低估值 ✅"
            else:
                ps, pd = 10, "极低估值 💎"
            score += ps
            items.append({"type": "同步", "label": "PE估值", "value": f"{self.pe:.1f}", "score": ps, "max": 10, "verdict": pd})

        # 先行：3日动量
        if self.chg3d is not None:
            ms = min(8, abs(self.chg3d) / 5 * 8)
            score += ms
            items.append({
                "type": "先行", "label": "3日动量", "value": f"{self.chg3d:+.2f}%",
                "score": round(ms, 1), "max": 8,
                "verdict": "动量强" if abs(self.chg3d) > 5 else ("动量中" if abs(self.chg3d) > 2 else "动量弱"),
            })

        # 滞后：ROE
        roe = _flt(self.lat.get("净资产收益率(%)") or _parse_fin_val(self.lat.get("净资产收益率")))
        if roe is not None:
            rs = min(8, roe / 15 * 8)
            score += rs
            items.append({
                "type": "滞后", "label": "ROE（价值锚）", "value": f"{roe:.2f}%",
                "score": round(rs, 1), "max": 8,
                "verdict": "优秀" if roe > 15 else ("良好" if roe > 10 else ("一般" if roe > 5 else "偏低")),
            })

        return self._pack("price_value", score, _max, items)

    def _score_growth_valuation(self) -> dict:
        """矛盾② 成长 vs 估值"""
        items = []
        score = 0
        _max = 42

        rev_g = _flt(self.lat.get("主营业务收入增长率(%)") or _parse_fin_val(self.lat.get("营业总收入同比增长率")))
        profit_g = _flt(self.lat.get("净利润增长率(%)") or _parse_fin_val(self.lat.get("净利润同比增长率")))

        # 先行：营收增速
        if rev_g is not None:
            rg = min(12, (rev_g + 10) / 25 * 12) if rev_g > -10 else 0
            score += max(0, rg)
            items.append({
                "type": "先行", "label": "营收增速", "value": f"{rev_g:+.2f}%",
                "score": round(max(0, rg), 1), "max": 12,
                "verdict": "高增长" if rev_g > 20 else ("增长" if rev_g > 0 else "下滑"),
            })

        # 同步：利润增速
        if profit_g is not None:
            pg = min(12, (profit_g + 15) / 30 * 12) if profit_g > -15 else 0
            score += max(0, pg)
            items.append({
                "type": "同步", "label": "净利润增速", "value": f"{profit_g:+.2f}%",
                "score": round(max(0, pg), 1), "max": 12,
                "verdict": "爆发" if profit_g > 30 else ("增长" if profit_g > 0 else "下滑"),
            })

        # 同步：PEG
        if self.pe and self.pe > 0 and profit_g and profit_g > 0:
            peg = round(self.pe / profit_g, 2)
            if peg < 1:
                ps, pd = 10, "低估 💎"
            elif peg < 2:
                ps, pd = 7, "合理 🟢"
            elif peg < 3:
                ps, pd = 4, "偏高 🟡"
            else:
                ps, pd = 1, "高估 🔴"
            score += ps
            items.append({"type": "同步", "label": "PEG", "value": f"{peg:.2f}", "score": ps, "max": 10, "verdict": pd})

        # 滞后：营收增速趋势
        if len(self.fin_records) >= 3:
            try:
                vals = []
                for r in self.fin_records[-3:]:
                    v = _parse_fin_val(r.get("营业总收入同比增长率"))
                    if v is not None:
                        vals.append(v)
                if len(vals) >= 2:
                    trend = vals[-1] - vals[0]
                    ts = 8 if trend > 5 else (5 if trend > -5 else 2)
                    score += ts
                    items.append({
                        "type": "滞后", "label": "增速趋势(3期)", "value": f"{trend:+.1f}pp",
                        "score": ts, "max": 8,
                        "verdict": "加速增长 ✅" if trend > 5 else ("增速平稳" if trend > -5 else "增速放缓 ⚠️"),
                    })
            except Exception:
                pass

        return self._pack("growth_valuation", score, _max, items)

    def _score_quality_cashflow(self) -> dict:
        """矛盾③ 盈利质量 vs 现金流"""
        items = []
        score = 0
        _max = 32

        # 先行：应收/营收比
        if len(self.fin_records) >= 2:
            try:
                ratios = []
                for r in self.fin_records[-4:]:
                    rev = _parse_fin_val(r.get("营业总收入"))
                    ar = _parse_fin_val(r.get("应收账款"))
                    if rev and ar and rev > 0 and ar > 0:
                        ratios.append(ar / rev)
                if ratios:
                    avg_ar = sum(ratios) / len(ratios)
                    as_ = max(0, 8 - avg_ar * 10)
                    score += as_
                    items.append({
                        "type": "先行", "label": "应收/营收比", "value": f"{avg_ar*100:.1f}%",
                        "score": round(as_, 1), "max": 8,
                        "verdict": "回款良好 ✅" if avg_ar < 0.2 else ("正常" if avg_ar < 0.4 else "回款偏慢 ⚠️"),
                    })
            except Exception:
                pass

        # 同步：OCF/净利润
        ocf_p = _flt(self.lat.get("经营现金净流量与净利润的比率(%)"))
        if ocf_p is not None:
            if ocf_p > 100:
                os_, od = 14, "利润质量极高 💎"
            elif ocf_p > 50:
                os_, od = 10, "利润质量良好 ✅"
            elif ocf_p > 0:
                os_, od = 5, "利润质量偏低 ⚠️"
            else:
                os_, od = 0, "OCF为负 🔴"
            score += os_
            items.append({"type": "同步", "label": "OCF/净利润", "value": f"{ocf_p:.1f}%", "score": os_, "max": 14, "verdict": od})

        # 滞后：毛利率
        gm = _flt(self.lat.get("销售毛利率(%)") or _parse_fin_val(self.lat.get("销售毛利率")))
        if gm is not None:
            gs = min(10, gm / 30 * 10)
            score += gs
            items.append({
                "type": "滞后", "label": "毛利率", "value": f"{gm:.2f}%",
                "score": round(gs, 1), "max": 10,
                "verdict": "极高" if gm > 50 else ("高" if gm > 25 else ("中" if gm > 10 else "低")),
            })

        return self._pack("quality_cashflow", score, _max, items)

    def _score_debt_safety(self) -> dict:
        """矛盾④ 负债扩张 vs 财务安全"""
        items = []
        score = 0
        _max = 34

        # 先行：总资产增长率
        ag = _flt(self.lat.get("总资产增长率(%)"))
        if ag is not None:
            if ag > 20:
                as_, ad = 8, "激进扩张 🔥"
            elif ag > 10:
                as_, ad = 6, "稳步扩张 ✅"
            elif ag > 0:
                as_, ad = 4, "温和扩张"
            else:
                as_, ad = 2, "收缩中"
            score += as_
            items.append({"type": "先行", "label": "总资产增长率", "value": f"{ag:+.2f}%", "score": as_, "max": 8, "verdict": ad})

        # 同步：资产负债率
        dr = _flt(self.lat.get("资产负债率(%)") or _parse_fin_val(self.lat.get("资产负债率")))
        if dr is not None:
            if dr < 30:
                ds, dd = 10, "极低杠杆 ✅"
            elif dr < 50:
                ds, dd = 8, "合理杠杆 🟢"
            elif dr < 65:
                ds, dd = 5, "偏高杠杆 🟡"
            else:
                ds, dd = 2, "高杠杆 🔴"
            score += ds
            items.append({"type": "同步", "label": "资产负债率", "value": f"{dr:.1f}%", "score": ds, "max": 10, "verdict": dd})

        # 同步：流动比率
        cr = _flt(self.lat.get("流动比率") or self.lat.get("流动比率(%)"))
        if cr is not None:
            cr_val = cr / 100 if cr > 10 else cr  # akshare有时候返回百分比
            if cr_val > 2.0:
                cs, cd = 8, "非常充裕 ✅"
            elif cr_val > 1.5:
                cs, cd = 6, "安全 🟢"
            elif cr_val > 1.0:
                cs, cd = 4, "及格 🟡"
            else:
                cs, cd = 1, "不足 🔴"
            score += cs
            items.append({"type": "同步", "label": "流动比率", "value": f"{cr_val:.2f}", "score": cs, "max": 8, "verdict": cd})

        # 滞后：ROIC
        roic = _flt(self.lat.get("投入资本回报率(%)"))
        if roic is not None:
            if roic > 10:
                rs, rd = 8, "资本回报优秀 ✅"
            elif roic > 5:
                rs, rd = 5, "回报合理 🟢"
            else:
                rs, rd = 2, "回报偏低 ⚠️"
            score += rs
            items.append({"type": "滞后", "label": "ROIC", "value": f"{roic:.2f}%", "score": rs, "max": 8, "verdict": rd})

        return self._pack("debt_safety", score, _max, items)

    def _score_industry_position(self) -> dict:
        """矛盾⑤ 行业景气 vs 个股地位"""
        items = []
        score = 0
        _max = 30

        # 先行：板块平均涨幅
        if self.industry_avg_chg is not None:
            ac = self.industry_avg_chg
            if ac > 2:
                ss, sd = 8, "板块强势 🔥"
            elif ac > 0:
                ss, sd = 5, "板块温和"
            elif ac > -2:
                ss, sd = 3, "板块偏弱"
            else:
                ss, sd = 1, "板块弱势 ❄️"
            score += ss
            items.append({"type": "先行", "label": "板块平均涨幅", "value": f"{ac:+.2f}%", "score": ss, "max": 8, "verdict": sd})

        # 同步：上涨占比
        if self.industry_up_ratio is not None:
            ur = self.industry_up_ratio
            if ur > 70:
                us, ud = 6, "普涨行情 ✅"
            elif ur > 50:
                us, ud = 4, "涨多跌少"
            elif ur > 30:
                us, ud = 2, "分化明显"
            else:
                us, ud = 1, "普跌 ❌"
            score += us
            items.append({"type": "同步", "label": "板块上涨占比", "value": f"{ur:.1f}%", "score": us, "max": 6, "verdict": ud})

        # 滞后：板块排名
        if self.industry_rank is not None and self.industry_total:
            rp = self.industry_rank / self.industry_total
            if rp < 0.2:
                rs, rd = 8, "板块排名前列 🏆"
            elif rp < 0.4:
                rs, rd = 6, "板块排名中上 ✅"
            elif rp < 0.6:
                rs, rd = 4, "板块排名中游"
            else:
                rs, rd = 1, "板块排名靠后"
            score += rs
            items.append({"type": "滞后", "label": "板块排名", "value": f"#{self.industry_rank}/{self.industry_total}", "score": rs, "max": 8, "verdict": rd})

        # 个股 vs 板块相对强弱
        if self.chg_pct is not None and self.industry_avg_chg is not None:
            rel = self.chg_pct - self.industry_avg_chg
            if rel > 3:
                rs, rd = 8, "显著强于板块 💪"
            elif rel > 0:
                rs, rd = 5, "略强于板块"
            elif rel > -3:
                rs, rd = 3, "弱于板块"
            else:
                rs, rd = 1, "显著弱于板块 ⚠️"
            score += rs
            items.append({"type": "同步", "label": "个股vs板块", "value": f"{rel:+.2f}pp", "score": rs, "max": 8, "verdict": rd})

        return self._pack("industry_position", score, _max, items)

    @staticmethod
    def _pack(cid: str, score: float, _max: int, items: list) -> dict:
        """打包单个矛盾结果"""
        pct = round(score / _max * 100, 1) if _max > 0 else 0
        if pct >= 70:
            level = "alert"
        elif pct >= 45:
            level = "warn"
        else:
            level = "normal"
        return {
            "id": cid,
            "name": next(c["name"] for c in CONTRADICTION_DEFS if c["id"] == cid),
            "icon": next(c["icon"] for c in CONTRADICTION_DEFS if c["id"] == cid),
            "desc": next(c["desc"] for c in CONTRADICTION_DEFS if c["id"] == cid),
            "score": round(score, 1),
            "max": _max,
            "pct": pct,
            "level": level,
            "items": items,
        }

    # ── 全量分析 ────────────────────────────

    def _score_all(self, skip_momentum: bool = False) -> list[dict]:
        """评分所有5个矛盾，返回排序后的列表（不含辩证分析）"""
        contradictions = []
        contradictions.append(self._score_price_value())
        contradictions.append(self._score_growth_valuation())
        contradictions.append(self._score_quality_cashflow())
        contradictions.append(self._score_debt_safety())
        contradictions.append(self._score_industry_position())
        contradictions.sort(key=lambda c: c["pct"], reverse=True)
        for i, c in enumerate(contradictions):
            c["rank"] = i + 1
        return contradictions

    # ── 第四层：思考问题生成（AI驱动）──────────

    def _generate_thinking_questions(self, contradictions: list[dict],
                                     dialectics: dict) -> list[dict]:
        """
        基于实际数据分析 + AI推理，生成针对这家公司具体情况的思考问题。
        每个问题包含：分类、问题本身、触发原因、思考方向。
        """
        # ── 构建输入数据 ──
        lines = [f"股票: {self.name} ({self.code})", f"行业: {self.sector_name or '未知'}"]
        lines.append("")

        # 财务摘要
        fin = {
            "毛利率": _parse_fin_val(self.indicators.get("销售毛利率(%)")),
            "净利润增长率": _parse_fin_val(self.indicators.get("净利润增长率(%)")),
            "营收增长率": _parse_fin_val(self.indicators.get("主营业务收入增长率(%)")),
            "资产负债率": _parse_fin_val(self.indicators.get("资产负债率(%)")),
            "ROE": _parse_fin_val(self.indicators.get("净资产收益率(%)")),
            "PE": self.pe,
            "PB": self.pb,
            "市值(亿)": _parse_fin_val(self.indicators.get("总市值(元)")),
        }
        valid_fin = {k: v for k, v in fin.items() if v is not None}
        if valid_fin:
            lines.append("【财务数据】")
            for k, v in valid_fin.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        # 行情
        if self.cur_price is not None or self.chg_pct is not None:
            lines.append("【行情】")
            if self.cur_price is not None:
                lines.append(f"  现价: {self.cur_price}")
            if self.chg_pct is not None:
                lines.append(f"  当日涨跌: {self.chg_pct:+.2f}%")
            lines.append("")

        # 行业对比
        if self.industry_avg_chg is not None or self.industry_rank is not None:
            lines.append("【行业定位】")
            if self.industry_avg_chg is not None:
                lines.append(f"  行业平均涨幅: {self.industry_avg_chg:+.2f}%")
            if self.industry_rank is not None and self.industry_total is not None:
                lines.append(f"  板块排名: {self.industry_rank}/{self.industry_total}")
            lines.append("")

        # 矛盾评分
        lines.append("【矛盾分析结果】")
        for c in contradictions:
            lines.append(f"  {c['icon']} {c['name']}: {c.get('pct',0)}% — {c.get('desc','')}")
        lines.append(f"  总分: {sum(c.get('pct',0) for c in contradictions)}/{len(contradictions)*100}")
        lines.append("")

        # 辩证分析
        lines.append("【矛盾动量变化】")
        for m in dialectics.get("momentum", []):
            chg = m.get("score_change", 0)
            lines.append(f"  {m['name']}: Δ{chg:+.1f} 排名变化:{m.get('rank_change',0)}")
        lines.append("")

        lcs = dialectics.get("lifecycle", [])
        if lcs:
            lines.append("【矛盾生命周期】")
            for lc in lcs:
                lines.append(f"  {lc['name']}: {lc.get('stage','未知')}")
            lines.append("")

        conv = dialectics.get("convergence", {})
        if conv:
            lines.append(f"【收敛性】{conv.get('status','未知')} — {conv.get('detail','')}")
            lines.append("")

        context = "\n".join(lines)

        # ── 缓存检查：code + report_period ──
        from backend.services.db_client import get_contradiction_ai_cache, save_contradiction_ai_cache
        report_period = ""
        if self.fin_records:
            last = self.fin_records[-1]
            report_period = last.get("报告期") or last.get("period") or last.get("财报日期", "")

        if report_period:
            cached = get_contradiction_ai_cache(self.code, report_period)
            if cached:
                log.info(f"矛盾分析AI缓存命中: {self.code} @ {report_period}")
                return cached

        PROMPT = """你是一位深入理解辩证法的投研分析师。给定一只股票的矛盾分析数据和财务信息，请生成最关键的思考问题。

要求：
1. 生成 2-4 个核心问题，每一个都必须基于具体数据特征触发，不是泛泛而谈
2. 问题要帮助投资者看到「代码算不出、需要人判断」的维度
3. 包含：投资逻辑的盲区、数据的内在矛盾、需要外部验证的假设

返回 JSON 数组，格式：
[
  {
    "category": "分类名（如 成本结构/负债质量/矛盾转化/预期差/系统风险）",
    "icon": "emoji",
    "question": "具体问题（30-80字，直击核心）",
    "trigger": "触发条件的简要说明",
    "think_along": "思考方向提示（20-50字）"
  }
]

如果数据不足以生成有意义的分析，返回 []。
只返回 JSON，不要包含其他文字。"""

        try:
            from openai import OpenAI
            import yaml
            from pathlib import Path

            config_path = Path.home() / ".hermes" / "config.yaml"
            cfg = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
            providers = cfg.get("custom_providers", [])
            ai_client = None
            for p in providers:
                if p.get("name") == "deepseek-v4-flash":
                    ai_client = OpenAI(api_key=p["api_key"], base_url=p["base_url"])
                    break
            if not ai_client:
                ai_client = OpenAI(api_key=cfg.get("model", {}).get("api_key", ""),
                                   base_url="https://api.deepseek.com")

            resp = ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": f"分析以下数据，生成思考问题：\n\n{context}"},
                ],
                temperature=0.5,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import json as _json
            questions = _json.loads(raw.strip())
            if isinstance(questions, list):
                # 写入缓存
                if report_period:
                    try:
                        save_contradiction_ai_cache(self.code, report_period, questions[:6])
                    except Exception:
                        pass
                return questions[:6]
        except Exception:
            log.warning(f"AI思考问题生成失败，回退默认逻辑", exc_info=True)

        # ── 回退：硬编码逻辑 ──
        return self._fallback_questions(contradictions, dialectics)

    def _fallback_questions(self, contradictions, dialectics):
        """AI失败时的回退方案：精简版硬编码问题"""
        questions = []
        c_map = {c["id"]: c for c in contradictions}
        momentum_map = {m["id"]: m for m in (dialectics.get("momentum") or [])}

        gross_margin = _parse_fin_val(self.indicators.get("销售毛利率(%)"))
        revenue_growth = _parse_fin_val(self.indicators.get("主营业务收入增长率(%)"))
        net_profit_growth = _parse_fin_val(self.indicators.get("净利润增长率(%)"))
        debt_ratio = _parse_fin_val(self.indicators.get("资产负债率(%)"))

        # 毛利与收入背离
        if gross_margin is not None and gross_margin < 0:
            questions.append({
                "category": "成本结构", "icon": "🏭",
                "question": "毛利率为负——当前亏损是扩张期阵痛还是结构性问题？",
                "trigger": f"毛利率{gross_margin}%", "think_along": "检查经营现金流与净利润方向是否一致。"
            })

        # 增收不增利
        if (revenue_growth is not None and net_profit_growth is not None
                and revenue_growth > 15 and net_profit_growth < 5):
            questions.append({
                "category": "盈利质量", "icon": "📈",
                "question": "营收增长快但利润没跟上——增长靠降价换量还是费用失控？",
                "trigger": f"营收{revenue_growth}%/净利{net_profit_growth}%",
                "think_along": "查看销售/管理费用率变化，判断增长可持续性。"
            })

        # 主要矛盾
        primary = contradictions[0] if contradictions else None
        if primary:
            p_id = primary["id"]
            p_momo = momentum_map.get(p_id, {})
            p_chg = p_momo.get("score_change", 0) or 0
            if p_chg > 5:
                questions.append({
                    "category": "矛盾转化", "icon": "🔄",
                    "question": f"主要矛盾「{primary['name']}」正在激化（Δ{p_chg:+.1f}）——推动它上升的关键变量是什么？",
                    "trigger": f"Δ{p_chg:+.1f}，矛盾度{primary.get('pct',0)}%",
                    "think_along": "分析外部变量（价格/政策/竞争）变化方向。"
                })

        # 多矛盾发散
        conv = dialectics.get("convergence", {})
        if conv.get("status") == "divergent":
            questions.append({
                "category": "系统风险", "icon": "🌪️",
                "question": "多个矛盾方向不一，投资逻辑不清晰——该等信号收敛还是这就是机会？",
                "trigger": f"{conv.get('conflict_count',0)}个矛盾突出",
                "think_along": "发散期需要更长持有周期，你的周期匹配吗？"
            })

        return questions[:6]

    def analyze(self) -> dict:
        """执行全量矛盾分析"""
        contradictions = self._score_all()

        # 主次矛盾判定
        primary = contradictions[0] if contradictions else None
        secondary = contradictions[1] if len(contradictions) > 1 else None
        third = contradictions[2] if len(contradictions) > 2 else None

        total_score = sum(c["pct"] for c in contradictions)
        total_max = len(contradictions) * 100
        total_pct = round(total_score / total_max * 100, 1) if total_max > 0 else 0

        dialectics = self._compute_dialectics(contradictions)
        thinking_questions = self._generate_thinking_questions(contradictions, dialectics)

        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector_name or "",
            "total_score": round(total_score, 1),
            "total_max": total_max,
            "total_pct": total_pct,
            "overall": "矛盾突出 ⚠️" if total_pct < 40 else ("存在矛盾 ⚖️" if total_pct < 60 else "矛盾较少 ✅"),
            "overall_desc": f"总分{total_pct}%，需关注主要矛盾的转化信号" if total_pct < 60 else "各项指标较为一致",
            "primary": primary,
            "secondary": secondary,
            "third": third,
            "contradictions": contradictions,
            "dialectics": dialectics,
            "thinking_questions": thinking_questions,
            "_source": self.code,
        }

    # ── 辩证分析 ────────────────────────────

    def _compute_dialectics(self, contradictions: list[dict]) -> dict:
        """
        三层辩证分析：
          1. 矛盾动量 — 历史分数 Δ + 排名 Δ
          2. 矛盾生命周期 — 潜伏/激化/极值/转化/扬弃
          3. 收敛性分析 — 多矛盾方向是否一致
        """
        momentum = self._compute_momentum(contradictions)
        lifecycle = self._compute_lifecycle(contradictions)
        convergence = self._compute_convergence(contradictions)
        return {
            "momentum": momentum,
            "lifecycle": lifecycle,
            "convergence": convergence,
        }

    # ── 第一层：矛盾动量 ─────────────────────

    def _compute_momentum(self, contradictions: list[dict]) -> list[dict]:
        """
        对比当前矛盾排名与历史排名，检测转换信号。
        基于 fin_records 近4期分别计算矛盾分数，然后看排名变化。
        """
        if len(self.fin_records) < 2:
            return []

        # 取最近4期（或更少）
        num_periods = min(4, len(self.fin_records))
        history = []

        for i in range(num_periods):
            period_records = self.fin_records[: -(num_periods - 1) + i]
            if not period_records:
                continue
            # 用该期数据构建临时引擎评分
            temp_engine = ContradictionEngine(
                code=self.code, name=self.name,
                fin_records=period_records,
                indicators=self._build_lat_from_record(period_records[-1]) if period_records else {},
                cur_price=self.cur_price, chg_pct=self.chg_pct,
                pe=self.pe, pb=self.pb, mcap=self.mcap, chg3d=self.chg3d,
                industry_avg_chg=self.industry_avg_chg,
                industry_up_ratio=self.industry_up_ratio,
                industry_rank=self.industry_rank,
                industry_total=self.industry_total,
                sector_name=self.sector_name,
            )
            temp = temp_engine._score_all()
            scores = {}
            for c in temp:
                scores[c["id"]] = {"score": c["score"], "pct": c["pct"], "rank": c.get("rank", 99)}
            history.append(scores)

        if len(history) < 2:
            return []

        current = history[-1]
        prev = history[-2]
        prev2 = history[0] if len(history) >= 3 else None

        result = []
        for cid in _CONTRADICTION_IDS:
            cur = current.get(cid, {})
            old = prev.get(cid, {})
            old2 = prev2.get(cid, {}) if prev2 else {}

            delta_score = _flt(cur.get("score"))
            prev_score = _flt(old.get("score"))
            score_chg = (delta_score - prev_score) if delta_score is not None and prev_score is not None else None

            delta_rank = cur.get("rank")
            prev_rank = old.get("rank")
            rank_chg = (prev_rank - delta_rank) if delta_rank is not None and prev_rank is not None else None
            # rank_chg > 0 = 排名上升（矛盾加剧）

            # 加速度：比较最近两段Δ的差值
            accel = None
            if old2:
                s1 = delta_score
                s2 = _flt(old.get("score"))
                s3 = _flt(old2.get("score"))
                if s1 is not None and s2 is not None and s3 is not None:
                    d1 = s1 - s2
                    d2 = s2 - s3
                    accel = round(d1 - d2, 1)

            result.append({
                "id": cid,
                "name": next(c["name"] for c in CONTRADICTION_DEFS if c["id"] == cid),
                "current_score": delta_score,
                "prev_score": prev_score,
                "score_change": score_chg,
                "current_rank": delta_rank,
                "prev_rank": prev_rank,
                "rank_change": rank_chg,
                "acceleration": accel,
                "direction": "intensifying" if (score_chg or 0) > 0 else ("resolving" if (score_chg or 0) < 0 else "stable"),
                "signal": self._eval_momentum_signal(score_chg, rank_chg, accel),
            })
        return result

    @staticmethod
    def _eval_momentum_signal(score_chg: float | None, rank_chg: int | None, accel: float | None) -> dict | None:
        """评估动量信号"""
        if score_chg is None:
            return None
        signals = []
        if score_chg and abs(score_chg) > 5:
            signals.append("加速" if score_chg > 0 else "减速")
        if rank_chg and rank_chg > 1:
            signals.append("升级")
        elif rank_chg and rank_chg < -1:
            signals.append("降级")
        if accel is not None and abs(accel) > 3:
            signals.append("势头增强" if accel > 0 else "势头减弱")
        if not signals:
            return None
        return {"summary": " · ".join(signals), "score_change": score_chg, "rank_change": rank_chg, "acceleration": accel}

    @staticmethod
    def _build_lat_from_record(record: dict) -> dict:
        """从一条records记录构建indicators格式"""
        return {
            "主营业务收入增长率(%)": record.get("营业总收入同比增长率"),
            "净利润增长率(%)": record.get("净利润同比增长率"),
            "销售毛利率(%)": record.get("销售毛利率"),
            "销售净利率(%)": record.get("销售净利率"),
            "净资产收益率(%)": record.get("净资产收益率"),
            "资产负债率(%)": record.get("资产负债率"),
            "流动比率": record.get("流动比率"),
        }

    # ── 第二层：矛盾生命周期 ─────────────────

    def _compute_lifecycle(self, contradictions: list[dict]) -> list[dict]:
        """给每个矛盾标生命周期阶段"""
        result = []
        for c in contradictions:
            pct = c["pct"]
            # 取动量数据
            momentum = next(
                (m for m in (self._compute_momentum(contradictions) if len(self.fin_records) >= 2 else []) if m["id"] == c["id"]),
                None,
            )
            score_chg = (momentum or {}).get("score_change") or 0
            rank = c.get("rank", 5)

            if pct < 20:
                stage = "潜伏期"
                icon = "💤"
                desc = "矛盾尚未显化，无紧迫感"
            elif pct < 50 and score_chg > 5:
                stage = "激化期"
                icon = "🔥"
                desc = "矛盾正在快速形成，需密切关注"
            elif pct >= 50 and pct < 75:
                stage = "极值区"
                icon = "⚡"
                desc = "矛盾最尖锐处，也是转化潜力最大的时刻"
            elif pct >= 50 and score_chg < -5:
                stage = "转化期"
                icon = "🔄"
                desc = "矛盾正在缓解，机会可能正在兑现"
            elif pct < 30 and score_chg < -10 and rank <= 2:
                stage = "扬弃期"
                icon = "✨"
                desc = "主要矛盾已消退，但留下了新的格局"
            else:
                stage = "持续期"
                icon = "♾️"
                desc = "矛盾持续存在，未见明显转化信号"

            result.append({
                "id": c["id"],
                "name": c["name"],
                "stage": stage,
                "icon": icon,
                "desc": desc,
                "pct": pct,
                "score_change": score_chg,
            })
        return result

    # ── 第三层：收敛性分析 ──────────────────

    def _compute_convergence(self, contradictions: list[dict]) -> dict:
        """分析多矛盾之间的方向一致性"""
        if not contradictions:
            return {"status": "no_data", "detail": "无数据"}

        # 提取各矛盾方向
        directions = {}
        for c in contradictions:
            pct = c["pct"]
            if pct >= 50:
                directions[c["id"]] = "conflict"  # 矛盾大 = 有问题
            elif pct >= 30:
                directions[c["id"]] = "neutral"
            else:
                directions[c["id"]] = "aligned"  # 矛盾小 = 没问题

        conflict_count = sum(1 for v in directions.values() if v == "conflict")
        aligned_count = sum(1 for v in directions.values() if v == "aligned")

        if conflict_count >= 3:
            status = "divergent"
            detail = f"{conflict_count}个矛盾同时突出，系统风险较大"
        elif aligned_count >= 3:
            status = "convergent"
            detail = f"{aligned_count}个矛盾方向一致，投资逻辑清晰"
        else:
            status = "mixed"
            detail = "矛盾方向不一，需等待信号收敛"

        return {
            "status": status,
            "detail": detail,
            "conflict_count": conflict_count,
            "aligned_count": aligned_count,
            "total": len(contradictions),
        }
