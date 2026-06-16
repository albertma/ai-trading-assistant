"""策略进化系统 — API路由"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from backend.services.strategy_evol.db import ensure_tables, get_db
from backend.services.strategy_evol.scorer import (
    run_batch_scan, score_stock, get_latest_scores, get_latest_batch,
    get_scan_status, get_scan_run_logs,
)
from backend.services.strategy_evol.evolution import run_evolution, get_evolution_history
from backend.services.strategy_evol.scan_pool import get_scan_pool
from backend.services.strategy_scan import run_strategy_scan, check_strategy_signal
import json
import uuid

router = APIRouter(prefix="/api/v1/strategy-evol", tags=["策略进化"])


@router.get("/scan-pool")
def api_scan_pool():
    """查看当前扫描池"""
    pool = get_scan_pool()
    return {"total": len(pool), "stocks": [{"code": c, "name": n} for c, n in pool]}


@router.get("/scan")
def api_scan(
    background_tasks: BackgroundTasks,
    session: str = Query("close", pattern="^(close|noon)$"),
    max_stocks: int = Query(20, ge=1, le=200),
):
    """异步触发全池扫描（后台执行，不阻塞）"""
    status = get_scan_status()
    if status["running"]:
        return {
            "status": "running",
            "batch_id": status["batch_id"],
            "progress": status["progress"],
            "message": "扫描正在进行中，请稍后通过 /results/latest 查看结果",
        }

    ensure_tables()
    batch_id = uuid.uuid4().hex[:12]
    background_tasks.add_task(run_batch_scan, session, max_stocks, batch_id)
    return {
        "status": "running",
        "batch_id": batch_id,
        "message": f"扫描已启动（{max_stocks}只，{session}时段），请稍后通过 /results/latest 查看结果",
    }


@router.get("/scan/status")
def api_scan_status():
    """查看当前扫描进度"""
    return get_scan_status()


@router.get("/scan/logs")
def api_scan_logs(limit: int = Query(30, le=100)):
    """获取扫描运行历史"""
    return {"logs": get_scan_run_logs(limit=limit)}


@router.get("/strategy-scan")
def api_strategy_scan(
    session: str = Query("close", pattern="^(close|noon)$"),
    max_stocks: int = Query(200, ge=10, le=1000),
):
    """策略驱动扫描：遍历所有策略 × 扫描池中的股票"""
    result = run_strategy_scan(session=session, max_stocks_per_strategy=max_stocks)
    return result


@router.get("/results")
def api_results(code: str = "", limit: int = Query(50, le=200)):
    """获取评分结果"""
    return {"results": get_latest_scores(code=code, limit=limit)}


@router.get("/results/latest")
def api_latest_batch():
    """获取最近一次批量扫描结果（按综合分排序）"""
    return {"results": get_latest_batch()}


@router.get("/results/{stock_code}")
def api_stock_result(stock_code: str):
    """获取某只股票最新评分"""
    ensure_tables()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM stock_scores WHERE stock_code=? ORDER BY id DESC LIMIT 1",
        (stock_code,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"股票 {stock_code} 暂无评分")
    r = dict(row)
    r["evidence"] = json.loads(r.get("evidence", "{}"))
    return r


# ── 维度权重 ──


@router.get("/weights")
def api_weights():
    """获取各维度当前权重"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM dimension_weights ORDER BY weight DESC").fetchall()
    conn.close()
    return {"weights": [dict(r) for r in rows]}


@router.put("/weights")
def api_update_weights(body: dict):
    """手动调整某个维度权重"""
    dim = body.get("dimension", "")
    weight = body.get("weight", 1.0)
    if dim not in ("technical", "fundamental", "narrative", "capital_flow", "sentiment"):
        raise HTTPException(400, f"无效维度: {dim}")
    weight = max(0.1, min(3.0, float(weight)))
    conn = get_db()
    conn.execute("UPDATE dimension_weights SET weight=?, last_updated=datetime('now','localtime') WHERE dimension=?", (weight, dim))
    conn.commit()
    conn.close()
    return {"dimension": dim, "weight": weight}


# ── 进化引擎 ──


@router.post("/evolve")
def api_evolve():
    """手动触发月度进化"""
    try:
        result = run_evolution()
        return result
    except Exception as e:
        raise HTTPException(500, f"进化失败: {e}")


@router.get("/evolve/history")
def api_evolve_history(limit: int = Query(12, le=48)):
    """获取进化历史"""
    return {"history": get_evolution_history(limit=limit)}


# ── 策略映射 ──


@router.get("/signals")
def api_signals():
    """获取最新策略信号（从 strategy_signals 表读取）"""
    ensure_tables()
    conn = get_db()

    # 获取最新批次
    latest_batch = conn.execute(
        "SELECT batch_id FROM strategy_signals ORDER BY id DESC LIMIT 1"
    ).fetchone()
    batch_id = latest_batch["batch_id"] if latest_batch else None

    # 按策略分组获取信号
    if batch_id:
        signals = conn.execute(
            """SELECT ss.*, s.name as strategy_name, s.dimension, s.buy_signal, s.scope_type, s.scope_value
               FROM strategy_signals ss
               LEFT JOIN strategies s ON ss.strategy_id = s.id
               WHERE ss.batch_id=?
               ORDER BY ss.confidence DESC""",
            (batch_id,),
        ).fetchall()
    else:
        signals = []

    # 聚合为策略视图
    strategy_map = {}
    strategy_configs = conn.execute(
        "SELECT id, name, dimension, buy_signal, scope_type, scope_value FROM strategies ORDER BY id"
    ).fetchall()
    conn.close()

    for sc in strategy_configs:
        sc = dict(sc)
        strategy_map[sc["id"]] = {
            "id": sc["id"],
            "name": sc["name"],
            "dimension": sc.get("dimension", "technical"),
            "buy_signal": sc.get("buy_signal", ""),
            "scope": f"{sc.get('scope_type','all')}:{sc.get('scope_value','')}",
            "triggered_count": 0,
            "triggered_stocks": [],
        }

    for sig in signals:
        sig = dict(sig)
        sid = sig["strategy_id"]
        if sid in strategy_map:
            strategy_map[sid]["triggered_count"] += 1
            strategy_map[sid]["triggered_stocks"].append({
                "code": sig["stock_code"],
                "name": sig.get("stock_name", ""),
                "confidence": sig.get("confidence", 0),
                "entry_price": sig.get("entry_price", 0),
                "stop_loss": sig.get("stop_loss", 0),
                "target_price": sig.get("target_price", 0),
                "signal_detail": sig.get("signal_detail", ""),
                "signal_id": sig["id"],
            })

    return {
        "strategies": sorted(strategy_map.values(), key=lambda x: -x["triggered_count"]),
        "batch_id": batch_id,
        "total_signals": len(signals),
    }


@router.get("/mappings")
def api_mappings(stock_code: str = ""):
    """获取策略映射列表"""
    conn = get_db()
    if stock_code:
        rows = conn.execute(
            """SELECT sm.*, s.name as strategy_name, s.dimension, s.buy_signal
               FROM strategy_mappings sm
               JOIN strategies s ON sm.strategy_id = s.id
               WHERE sm.stock_code=? AND sm.is_active=1
               ORDER BY sm.priority DESC""",
            (stock_code,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT sm.*, s.name as strategy_name, s.dimension, s.buy_signal
               FROM strategy_mappings sm
               JOIN strategies s ON sm.strategy_id = s.id
               WHERE sm.is_active=1
               ORDER BY s.dimension, sm.stock_code""",
        ).fetchall()
    conn.close()
    return {"mappings": [dict(r) for r in rows]}


@router.post("/mappings")
def api_add_mapping(body: dict):
    """添加策略映射"""
    stock_code = body.get("stock_code", "").strip()
    strategy_id = body.get("strategy_id", 0)
    priority = body.get("priority", 0)
    if not stock_code or not strategy_id:
        raise HTTPException(400, "stock_code 和 strategy_id 必填")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO strategy_mappings(stock_code, strategy_id, priority) VALUES (?,?,?)",
            (stock_code, strategy_id, priority),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(409, f"映射已存在")
        raise HTTPException(500, str(e))
    conn.close()
    return {"message": "映射已添加", "stock_code": stock_code, "strategy_id": strategy_id}


@router.delete("/mappings/{mapping_id}")
def api_delete_mapping(mapping_id: int):
    """删除策略映射"""
    conn = get_db()
    conn.execute("DELETE FROM strategy_mappings WHERE id=?", (mapping_id,))
    conn.commit()
    conn.close()
    return {"message": "已删除"}
