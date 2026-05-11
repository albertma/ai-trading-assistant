"""仓位管理模块 — Pydantic 数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class Position(BaseModel):
    """新增/修改持仓请求"""
    code: str
    name: str
    quantity: float = Field(gt=0, description="持仓数量")
    cost_price: float = Field(gt=0, description="成本价")
    note: str = ""


class PositionOut(BaseModel):
    """持仓展示"""
    code: str
    name: str
    quantity: float
    cost_price: float
    current_price: float
    cost_total: float
    market_value: float
    profit_amount: float
    profit_pct: float
    note: str
    market: str
    market_label: str


class UpdatePositionBody(BaseModel):
    """更新持仓请求（部分字段）"""
    quantity: Optional[float] = None
    cost_price: Optional[float] = None
    note: Optional[str] = None


class TradeLogIn(BaseModel):
    """新增/修改交易日志"""
    direction: str = Field(..., pattern=r"^(买入|卖出)$")
    trade_date: str = Field(..., description="交易日期 YYYY-MM-DD")
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    note: str = ""
