"""
个股资料缓存与搜索 API
"""
from fastapi import APIRouter, Query
from backend.services.db_client import (
    search_stock_info, get_stock_info, get_stock_info_count,
    refresh_stock_info_from_csv, refresh_stock_detail_from_akshare
)

router = APIRouter()


@router.get("/search")
def stock_info_search(
    q: str = Query("", min_length=1, description="搜索关键词：代码/名称/拼音首字母"),
    limit: int = Query(15, ge=1, le=50)
):
    """搜索个股（按代码/名称/拼音首字母）"""
    if not q.strip():
        return {"total": 0, "results": []}
    results = search_stock_info(q.strip(), limit)
    return {"total": len(results), "results": results}


@router.get("/count")
def stock_info_count():
    """获取已缓存个股数量"""
    return {"total": get_stock_info_count()}


@router.get("/{code}")
def stock_info_detail(code: str):
    """获取单只个股的详细资料"""
    info = get_stock_info(code)
    if not info:
        return {"code": code, "found": False, "message": "未找到该个股资料，请先刷新"}
    return {"code": code, "found": True, "data": info}


@router.post("/refresh")
def stock_info_refresh():
    """从本地CSV批量刷新个股基本资料（代码+名称+行业+市场+拼音首字母）"""
    count = refresh_stock_info_from_csv()
    total = get_stock_info_count()
    return {"refreshed": count, "total": total, "message": f"新增/更新 {count} 只，共 {total} 只"}


@router.post("/refresh-detail/{code}")
def stock_info_refresh_detail(code: str):
    """从akshare刷新单只个股的详细信息（股本、市值等）"""
    result = refresh_stock_detail_from_akshare(code)
    if result is None:
        return {"code": code, "success": False, "message": "刷新失败"}
    return {"code": code, "success": True, "data": result}
