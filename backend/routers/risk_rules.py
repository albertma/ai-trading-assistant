"""
风控规则 CRUD + 自定义评估 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.db_client import (
    get_risk_rules, add_risk_rule, update_risk_rule,
    delete_risk_rule, toggle_risk_rule, get_rule_types, seed_default_rules,
)

router = APIRouter()


class RuleCreate(BaseModel):
    name: str
    description: str = ""
    rule_type: str
    field: str
    operator: str
    value: str
    unit: str = ""
    severity: str = "fail"
    custom_detail: str = ""
    sort_order: int = 0


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = None
    custom_detail: Optional[str] = None
    enabled: Optional[int] = None
    sort_order: Optional[int] = None


@router.get("")
def list_rules():
    """列出所有风控规则"""
    return {"rules": get_risk_rules(), "total": len(get_risk_rules())}


@router.post("")
def create_rule(rule: RuleCreate):
    """创建风控规则"""
    rid = add_risk_rule(rule.model_dump())
    if rid is None:
        raise HTTPException(400, "创建规则失败")
    rules = get_risk_rules()
    return {"id": rid, "message": "规则已创建", "total": len(rules)}


@router.put("/{rule_id}")
def modify_rule(rule_id: int, rule: RuleUpdate):
    """更新风控规则"""
    data = {k: v for k, v in rule.model_dump().items() if v is not None}
    ok = update_risk_rule(rule_id, data)
    if not ok:
        raise HTTPException(404, "规则不存在或更新失败")
    return {"message": "规则已更新"}


@router.delete("/{rule_id}")
def remove_rule(rule_id: int):
    """删除风控规则"""
    ok = delete_risk_rule(rule_id)
    if not ok:
        raise HTTPException(404, "规则不存在")
    return {"message": "规则已删除"}


@router.patch("/{rule_id}/toggle")
def toggle_rule(rule_id: int):
    """启用/禁用规则"""
    new_state = toggle_risk_rule(rule_id)
    if new_state is None:
        raise HTTPException(404, "规则不存在")
    return {"enabled": new_state, "message": "已启用" if new_state else "已禁用"}


@router.get("/types")
def list_rule_types():
    """获取可用规则字段定义"""
    return {"types": get_rule_types()}


@router.post("/init-defaults")
def init_defaults():
    """初始化预设规则"""
    count = seed_default_rules()
    return {"message": f"预设规则已初始化，共{count}条", "total": count}
