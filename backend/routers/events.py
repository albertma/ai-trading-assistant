"""事件提醒 API — 限售解禁 / 重要日期管理"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.stock_events import (
    list_events, list_past_events, add_event, update_event, delete_event, ensure_table,
)

router = APIRouter(tags=["事件提醒"])


class EventCreate(BaseModel):
    code: str
    event_type: str = "解禁"
    event_date: str
    title: str = ""
    detail: str = ""
    source: str = ""


class EventUpdate(BaseModel):
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    source: Optional[str] = None


@router.get("/events")
def get_events(code: str = "", days: int = 90):
    """获取未来事件列表"""
    ensure_table()
    return {"events": list_events(code, days)}


@router.get("/events/past")
def get_past_events(code: str = "", days: int = 90):
    """获取过去的事件记录"""
    ensure_table()
    return {"events": list_past_events(code, days)}


@router.post("/events")
def create_event(event: EventCreate):
    """新增事件"""
    ensure_table()
    eid = add_event(
        event.code, event.event_type, event.event_date,
        event.title, event.detail, event.source,
    )
    if not eid:
        raise HTTPException(400, "创建事件失败")
    return {"id": eid, "message": "事件已创建"}


@router.put("/events/{event_id}")
def modify_event(event_id: int, event: EventUpdate):
    """修改事件"""
    ok = update_event(event_id, **event.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(404, "事件不存在或更新失败")
    return {"message": "事件已更新"}


@router.delete("/events/{event_id}")
def remove_event(event_id: int):
    """删除事件"""
    ok = delete_event(event_id)
    if not ok:
        raise HTTPException(404, "事件不存在")
    return {"message": "事件已删除"}
