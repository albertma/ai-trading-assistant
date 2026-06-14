"""AI深度分析层 — 用LLM对Top信号生成深度解读

调用系统配置的模型（DeepSeek V4）对精选信号做AI推理分析，
补充纯规则评分无法覆盖的深度洞察。
"""
import json
from typing import Optional
from pathlib import Path

from .models import StockScore, ScanReport
from .scorer import build_score


async def enhance_with_ai(
    scores: list[StockScore],
    max_analyze: int = 5,
    report_context: Optional[str] = None,
) -> list[StockScore]:
    """用AI对Top信号做深度分析

    对得分最高的N个信号逐一调用LLM生成深度解读，
    包括多空逻辑、风险评估、交易建议。

    Args:
        scores: 已排好序的StockScore列表
        max_analyze: 最多分析N只
        report_context: 市场背景信息
    """
    try:
        from openai import OpenAI
        import os

        api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('DASHSCOPE_API_KEY') or ''
        base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        model = os.environ.get('AI_MODEL', 'deepseek-v4')

        if not api_key:
            return scores

        client = OpenAI(api_key=api_key, base_url=base_url)

        for i, s in enumerate(scores[:max_analyze]):
            enhanced = await _analyze_single_stock(client, model, s, report_context)
            if enhanced:
                scores[i] = enhanced

    except Exception:
        pass  # AI不可用时不阻塞流程

    return scores


async def _analyze_single_stock(
    client, model: str,
    score: StockScore,
    market_context: Optional[str] = None,
) -> Optional[StockScore]:
    """对单只股票调用AI深度分析"""
    prompt = f"""你是一位专业的股票分析师。请从以下信息出发，对该股票进行深度分析。

## 股票基本信息
- 代码: {score.code} {score.name}
- 当前价: {score.current_price} 元
- 今日涨幅: {score.daily_change_pct:+.2f}%
- 行业: {score.industry}
- 量比: {score.volume_ratio}
- 总市值: {score.market_cap:.0f} 亿元
- 综合评分: {score.total_score}/100

## 技术面信号 ({len(score.technical_signals)}个)
{chr(10).join(f'- {s.pattern_name}(强度{s.strength}): {s.description}' for s in score.technical_signals)}

## 风险因素 ({len(score.risk_factors)}个)
{chr(10).join(f'- {r.risk_name}(严重度{r.severity}): {r.description}' for r in score.risk_factors) if score.risk_factors else '- 无明显风险'}

## 基本面信号 ({len(score.fundamental_signals)}个)
{chr(10).join(f'- {s.signal_name}: {s.description}' for s in score.fundamental_signals) if score.fundamental_signals else '- 暂无基础面数据'}

## 分析要求
请输出JSON格式的分析报告，只输出JSON，不要多余文字：
{{
    "ai_analysis": "一句话总结当前状态和机会（50字以内）",
    "bullish_case": "看多逻辑（列出2-3个关键理由，200字以内）",
    "bearish_case": "看空/风险逻辑（列出1-2个关键风险，100字以内）",
    "ai_confidence_adjustment": 0,
    "trading_opinion": "强烈推荐|推荐关注|建议观察|中性|回避",
    "key_levels": {{
        "support": "最近的支撑位",
        "resistance": "最近的阻力位"
    }},
    "action_comment": "具体交易建议（100字以内）"
}}

注意 ai_confidence_adjustment 范围为 -10 到 +10，表示对你觉得评分应上调或下调的幅度。
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        text = resp.choices[0].message.content.strip()

        # 提取JSON
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)

        # 更新评分
        adjustment = data.get('ai_confidence_adjustment', 0)
        score.total_score = max(0, min(100, score.total_score + adjustment))

        if data.get('ai_analysis'):
            score.ai_summary = data['ai_analysis']

        if data.get('bullish_case') or data.get('bearish_case'):
            lines = []
            if data.get('bullish_case'):
                lines.append('✅ 看多逻辑：')
                lines.append(f'  {data["bullish_case"]}')
            if data.get('bearish_case'):
                lines.append('⚠️ 看空逻辑：')
                lines.append(f'  {data["bearish_case"]}')
            if data.get('trading_opinion'):
                lines.append(f'🎯 观点：{data["trading_opinion"]}')
            if data.get('action_comment'):
                lines.append(f'💡 {data["action_comment"]}')
            score.ai_rationale = '\n'.join(lines)

    except Exception:
        pass

    return score
