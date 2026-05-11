"""持仓管理 API — 纯路由层（业务逻辑在 services/tradingmgt/）"""

from fastapi import APIRouter, HTTPException

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
        trade.quantity, trade.price, trade.note,
    )


@router.put("/{code}/trades/{trade_id}")
def update_trade(code: str, trade_id: int, trade: TradeLogIn):
    """修改一笔交易记录 → 自动更新持仓"""
    try:
        return trade_service.update_trade(
            code, trade_id, trade.direction, trade.trade_date,
            trade.quantity, trade.price, trade.note,
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
