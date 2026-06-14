"""交易计划 API — 全生命周期管理"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.trading_plans import (
    ensure_table, list_plans, get_plan, create_plan,
    update_plan, delete_plan, evaluate_signals,
    analyze_support_resistance,
)

router = APIRouter(tags=["交易计划"])


class PlanCreate(BaseModel):
    code: str
    name: str = ""
    direction: str = "long"
    entry_price: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    plan_quantity: int = 0
    entry_reason: str = ""
    kline_notes: str = ""


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    direction: Optional[str] = None
    status: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    plan_quantity: Optional[int] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    kline_notes: Optional[str] = None
    signal_notes: Optional[str] = None
    actual_entry_price: Optional[float] = None
    actual_exit_price: Optional[float] = None
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None


@router.get("/trading-plans")
def list_trading_plans(status: str = "", code: str = ""):
    """获取交易计划列表"""
    ensure_table()
    return {"plans": list_plans(status, code)}


@router.get("/trading-plans/{plan_id}")
def get_trading_plan(plan_id: int):
    """获取单个交易计划详情"""
    ensure_table()
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "计划不存在")
    return {"plan": plan}


@router.post("/trading-plans")
def create_trading_plan(plan: PlanCreate):
    """创建交易计划"""
    ensure_table()
    pid = create_plan(
        plan.code, plan.name, plan.direction,
        plan.entry_price, plan.stop_loss, plan.take_profit,
        plan.plan_quantity, plan.entry_reason, plan.kline_notes,
    )
    if not pid:
        raise HTTPException(400, "创建失败")
    return {"id": pid, "message": "交易计划已创建"}


@router.put("/trading-plans/{plan_id}")
def update_trading_plan(plan_id: int, plan: PlanUpdate):
    """更新交易计划"""
    ok = update_plan(plan_id, **plan.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(404, "计划不存在或更新失败")
    return {"message": "已更新"}


@router.delete("/trading-plans/{plan_id}")
def delete_trading_plan(plan_id: int):
    """删除交易计划"""
    ok = delete_plan(plan_id)
    if not ok:
        raise HTTPException(404, "计划不存在")
    return {"message": "已删除"}


@router.get("/trading-plans/support-resistance/{code}")
def get_support_resistance(code: str, direction: str = "long"):
    """获取支撑/阻力位分析，推荐入场/止损/止盈，计算预期盈亏比"""
    ensure_table()
    return analyze_support_resistance(code, direction)


@router.get("/trading-plans/{plan_id}/signals")
def get_plan_signals(plan_id: int):
    """评估交易计划的入场/出场信号"""
    ensure_table()
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "计划不存在")
    return evaluate_signals(plan)
