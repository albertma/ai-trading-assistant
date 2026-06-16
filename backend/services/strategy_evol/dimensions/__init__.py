"""维度评分器 — 各维度独立评分"""
from __future__ import annotations

from backend.services.strategy_evol.dimensions.fundamental import score_fundamental
from backend.services.strategy_evol.dimensions.narrative import score_narrative
from backend.services.strategy_evol.dimensions.capital_flow import score_capital_flow
from backend.services.strategy_evol.dimensions.sentiment import score_sentiment

__all__ = [
    "score_fundamental",
    "score_narrative",
    "score_capital_flow",
    "score_sentiment",
]
