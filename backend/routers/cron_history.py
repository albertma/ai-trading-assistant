"""Cron任务历史记录 API"""
from fastapi import APIRouter, Query
from backend.services.db_client import add_cron_log, update_cron_log, get_cron_history as _get_history

router = APIRouter()


@router.get("/cron-history")
def list_cron_history(
    limit: int = Query(50, description="返回条数"),
    task_name: str = Query(None, description="按任务名筛选"),
):
    """获取cron任务历史列表"""
    records = _get_history(limit=limit, task_name=task_name)
    return {"records": records, "total": len(records)}


@router.get("/cron-history/tasks")
def list_cron_tasks():
    """获取所有已记录的任务名称"""
    from backend.services.database.stock_db import get_db
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT task_name FROM cron_history ORDER BY task_name").fetchall()
    conn.close()
    return {"tasks": [r["task_name"] for r in rows]}


@router.post("/cron-history/create")
def create_cron_log(
    task_name: str = Query(..., description="任务名称"),
    status: str = Query("running", description="状态: running/success/failed"),
    message: str = Query("", description="日志消息"),
):
    """手动记录一条cron日志"""
    log_id = add_cron_log(task_name, status, message)
    return {"id": log_id, "status": "created"}


@router.put("/cron-history/{log_id}")
def edit_cron_log(
    log_id: int,
    status: str = Query(..., description="状态: running/success/failed"),
    message: str = Query("", description="日志消息"),
):
    """更新cron日志状态"""
    update_cron_log(log_id, status, message)
    return {"id": log_id, "status": "updated"}


@router.get("/cron-history/{log_id}")
def get_cron_log(log_id: int):
    """获取单条cron日志详情"""
    from backend.services.database.stock_db import get_db
    conn = get_db()
    row = conn.execute("SELECT * FROM cron_history WHERE id = ?", (log_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "not found"}
    return dict(row)
