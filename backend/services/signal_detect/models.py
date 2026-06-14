"""AI驱动投资流程 — 数据模型"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class TechnicalSignal:
    """技术面信号"""
    pattern_type: str          # large_bullish | three_white | hammer（精选系统限定的3种）
    pattern_name: str          # 中文名
    strength: float            # 0~100 信号强度
    description: str           # 简要说明
    kline_date: Optional[str] = None  # 信号出现日期


@dataclass
class FundamentalSignal:
    """基本面信号"""
    signal_type: str           # revenue_growth, profit_surge, roe_improve, pe_low, etc.
    signal_name: str
    strength: float            # 0~100
    value: str                 # 具体数值/描述
    description: str


@dataclass
class NewsSignal:
    """消息面信号"""
    topic: str                 # 主题/叙事
    sentiment: float           # -1.0 ~ +1.0
    strength: float            # 0~100
    source: str
    summary: str
    url: Optional[str] = None


@dataclass
class RiskFactor:
    """风险因素"""
    risk_type: str             # price_risk, volume_risk, fundamental_risk, news_risk
    risk_name: str
    severity: float            # 0~100
    description: str


@dataclass
class StockScore:
    """股票综合评分"""
    code: str
    name: str
    total_score: float         # 0~100 总分
    
    # 各维度评分
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    news_score: float = 0.0
    risk_score: float = 0.0    # 越高越安全(逆指标)
    
    # 技术面信号详情
    technical_signals: list[TechnicalSignal] = field(default_factory=list)
    fundamental_signals: list[FundamentalSignal] = field(default_factory=list)
    news_signals: list[NewsSignal] = field(default_factory=list)
    risk_factors: list[RiskFactor] = field(default_factory=list)
    
    # 当前行情
    current_price: float = 0.0
    daily_change_pct: float = 0.0
    volume_ratio: float = 0.0
    industry: str = ""
    market_cap: float = 0.0
    
    # AI分析结论
    ai_summary: str = ""
    ai_confidence: str = ""     # 强烈推荐, 建议关注, 中性, 回避
    ai_rationale: str = ""
    
    # 入场建议
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    suggested_position: str = ""  # 10%, 20%, 观望
    
    scanned_at: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M'))


@dataclass
class ScanReport:
    """每日扫描报告"""
    date: str
    scan_type: str                # 午盘/收盘/盘中
    scanned_index: str = "hs300"  # hs300 / csi500 / star50
    market_summary: str = ""
    total_scanned: int = 0
    top_signals: list[StockScore] = field(default_factory=list)
    watchlist_signals: list[StockScore] = field(default_factory=list)
    risk_warnings: list[dict] = field(default_factory=list)
    ai_overall_analysis: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M'))
