"""AI信号评分与融合 — 用AI推理产出综合评分"""
from pathlib import Path
from typing import Optional
import json

from .models import StockScore, ScanReport, TechnicalSignal, FundamentalSignal, NewsSignal, RiskFactor


def compute_technical_score(signals: list[TechnicalSignal], risks: list[RiskFactor]) -> float:
    """计算技术面评分 (0~100)，多信号叠加但递减"""
    if not signals:
        return 10.0

    # 基础分
    score = 20.0

    # 按强度排序，依次衰减
    sorted_sigs = sorted(signals, key=lambda s: s.strength, reverse=True)
    for i, s in enumerate(sorted_sigs):
        multiplier = max(0.2, 1.0 - i * 0.2)  # 第1个100%, 第2个80%, 第3个60%...
        score += s.strength * 0.25 * multiplier

    # 风险抵扣
    for r in risks:
        if r.risk_type == 'technical':
            score -= r.severity * 0.15
        elif r.risk_type == 'volume':
            score -= r.severity * 0.10

    return round(max(0, min(100, score)), 1)


def compute_fundamental_score(signals: list[FundamentalSignal]) -> float:
    """计算基本面评分"""
    if not signals:
        # 没有财务数据 = 未知，给个中低分
        return 25.0

    score = 30.0  # 有数据的基础分
    for s in signals:
        score += s.strength * 0.15

    return round(min(100, score), 1)


def compute_news_score(signals: list[NewsSignal]) -> float:
    """计算消息面评分"""
    if not signals:
        return 30.0  # 中性

    score = 40.0
    for s in signals:
        score += s.strength * s.sentiment * 0.3

    return round(max(0, min(100, score)), 1)


def compute_risk_score(risks: list[RiskFactor]) -> float:
    """计算风险评分 (越高越安全)"""
    if not risks:
        return 95.0  # 无风险，但留5分余地

    base = 100.0
    for r in risks:
        deduction = r.severity * 0.12
        base = max(0, base - deduction)

    return round(base, 1)


def compute_total_score(tech: float, funda: float, news: float, risk: float, has_funda: bool, has_news: bool) -> float:
    """加权总分 — 根据是否有数据动态调整权重"""
    # 当缺少某维度数据时，将该维度权重分配到技术面和风险上
    if not has_funda and not has_news:
        total = tech * 0.60 + risk * 0.40
    elif not has_funda:
        total = tech * 0.50 + news * 0.20 + risk * 0.30
    elif not has_news:
        total = tech * 0.50 + funda * 0.30 + risk * 0.20
    else:
        total = tech * 0.40 + funda * 0.25 + news * 0.20 + risk * 0.15
    return round(total, 1)


# ─── AI分析结论 ───

LEVELS = [
    (82, '强烈推荐', '⭐️⭐️⭐️⭐️⭐', '值得重点关注，可考虑入场'),
    (73, '推荐关注', '⭐️⭐️⭐️⭐', '信号明确，可列入观察'),
    (62, '建议观察', '⭐️⭐️⭐', '有信号但需进一步确认'),
    (50, '中性', '⭐️⭐', '信号不明显'),
    (0, '不推荐', '⭐', '暂无有效信号'),
]


def get_confidence_label(score: float) -> str:
    for threshold, label, stars, _ in LEVELS:
        if score >= threshold:
            return f'{label} {stars}'
    return '不推荐 ⭐'


def get_confidence_action(score: float) -> str:
    for threshold, _, _, action in LEVELS:
        if score >= threshold:
            return action
    return '暂无有效信号'


def build_score(
    code: str, name: str,
    technical_signals: list[TechnicalSignal],
    fundamental_signals: list[FundamentalSignal],
    news_signals: list[NewsSignal],
    risk_factors: list[RiskFactor],
    current_price: float = 0.0,
    daily_change_pct: float = 0.0,
    volume_ratio: float = 0.0,
    industry: str = '',
    market_cap: float = 0.0,
) -> StockScore:
    """构造完整评分"""
    tech_score = compute_technical_score(technical_signals, risk_factors)
    funda_score = compute_fundamental_score(fundamental_signals)
    news_score = compute_news_score(news_signals)
    risk_score = compute_risk_score(risk_factors)
    total = compute_total_score(tech_score, funda_score, news_score, risk_score,
                                has_funda=len(fundamental_signals) > 0,
                                has_news=len(news_signals) > 0)

    confidence = get_confidence_label(total)
    action = get_confidence_action(total)

    score = StockScore(
        code=code, name=name,
        total_score=total,
        technical_score=tech_score,
        fundamental_score=funda_score,
        news_score=news_score,
        risk_score=risk_score,
        technical_signals=technical_signals,
        fundamental_signals=fundamental_signals,
        news_signals=news_signals,
        risk_factors=risk_factors,
        current_price=current_price,
        daily_change_pct=daily_change_pct,
        volume_ratio=volume_ratio,
        industry=industry,
        market_cap=market_cap,
        ai_confidence=confidence,
    )

    score.ai_summary = _generate_summary(score)
    score.ai_rationale = _generate_rationale(score)
    score.ai_confidence = f'{confidence} | {action}'

    # 入场建议
    if total >= 62:
        score.entry_price = current_price
        if current_price > 0:
            score.stop_loss = round(current_price * 0.93, 2)
            score.take_profit = round(current_price * 1.15, 2)
        score.suggested_position = '10%' if total < 73 else '20%'

    return score


def _generate_summary(s: StockScore) -> str:
    """生成一句话摘要"""
    parts = []
    if s.technical_signals:
        patterns = [sig.pattern_name for sig in s.technical_signals[:3]]
        parts.append(f'今日{s.daily_change_pct:+.1f}%，出现{"+".join(patterns)}')
    if s.fundamental_signals:
        funds = [sig.signal_name for sig in s.fundamental_signals[:2]]
        parts.append(f'基本面{"、".join(funds)}')
    if s.risk_factors:
        risks = [r.risk_name for r in s.risk_factors[:2]]
        parts.append(f'⚠️ 关注{"、".join(risks)}')
    return ' | '.join(parts)


def _generate_rationale(s: StockScore) -> str:
    """生成多空逻辑"""
    bullish = []
    bearish = []

    for sig in s.technical_signals:
        bullish.append(f'📈 {sig.pattern_name}: {sig.description}')
    for sig in s.fundamental_signals:
        bullish.append(f'📊 {sig.signal_name}: {sig.description}')
    for r in s.risk_factors:
        bearish.append(f'⚠️ {r.risk_name}: {r.description}')

    lines = []
    if bullish:
        lines.append('✅ 看多方：')
        for b in bullish[:4]:
            lines.append(f'  • {b}')
    if bearish:
        lines.append('⚠️ 风险方：')
        for b in bearish[:3]:
            lines.append(f'  • {b}')

    lines.append(f'🎯 建议：{s.ai_confidence.split("|")[-1].strip()}')

    if s.entry_price:
        lines.append(f'💵 入场建议：{s.entry_price} | 止损：{s.stop_loss} | 止盈：{s.take_profit} | 仓位：{s.suggested_position}')

    return '\n'.join(lines)
