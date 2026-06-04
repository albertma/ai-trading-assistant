"""持仓管理 API — 纯路由层（业务逻辑在 services/tradingmgt/）"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.tradingmgt import (
    position_service,
    trade_service,
)
from backend.services.tradingmgt.models import Position, PositionOut, UpdatePositionBody, TradeLogIn

router = APIRouter()


# ========== 持仓 CRUD ==========

@router.get("")
def list_positions():
    """获取所有持仓，按市场分组 + CNY汇总"""
    return position_service.get_grouped_positions()


@router.post("")
def add_position(pos: Position):
    """添加持仓"""
    try:
        msg = position_service.add_one(pos.code, pos.name, pos.quantity, pos.cost_price, pos.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "ok", "message": msg}


@router.put("/{code}")
def update_position(code: str, body: UpdatePositionBody):
    """更新持仓"""
    try:
        msg = position_service.update_one(code, body.quantity, body.cost_price, body.note)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "ok", "message": msg}


@router.delete("/{code}")
def delete_position(code: str):
    """删除持仓"""
    try:
        msg = position_service.delete_one(code)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "ok", "message": msg}


# ========== 交易日志 ==========

@router.get("/{code}/trades")
def list_trades(code: str):
    """获取某只股票的所有交易记录"""
    return trade_service.list_trades(code)


@router.post("/{code}/trades")
def add_trade(code: str, trade: TradeLogIn):
    """新增一笔交易 → 自动更新持仓"""
    return trade_service.add_trade(
        code, trade.direction, trade.trade_date,
        trade.quantity, trade.price, trade.note, trade.rationale,
    )


@router.put("/{code}/trades/{trade_id}")
def update_trade(code: str, trade_id: int, trade: TradeLogIn):
    """修改一笔交易记录 → 自动更新持仓"""
    try:
        return trade_service.update_trade(
            code, trade_id, trade.direction, trade.trade_date,
            trade.quantity, trade.price, trade.note, trade.rationale,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{code}/trades/{trade_id}")
def delete_trade(code: str, trade_id: int):
    """删除一笔交易记录 → 自动更新持仓"""
    try:
        return trade_service.delete_trade(code, trade_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ========== 持仓分析 ==========

@router.get("/analysis")
def position_analysis():
    """持仓多维度分析"""
    return position_service.analyze_positions()


# ========== 仓位权重检查 ==========

@router.get("/weight-check")
def check_weights(max_weight: float = 20.0):
    """检查每个持仓占组合总市值权重，超限返回警告"""
    return position_service.weight_check(max_weight_pct=max_weight)


# ========== 分批建仓/减仓建议 ==========

class BatchPlanBody(BaseModel):
    direction: str = "买入"
    total_qty: float = 1000
    current_price: float = 10.0
    batches: int = 3
    interval: float = 0.05


@router.post("/batch-plan")
def plan_batches(body: BatchPlanBody):
    """生成分批建仓/减仓建议"""
    return {"plan": position_service.batch_plan(
        body.direction, body.total_qty, body.current_price,
        body.batches, body.interval,
    )}
